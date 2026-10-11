"""Discover and archive the current RVO ISDE source workbooks."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import cast
from urllib.parse import urljoin, urlparse

import httpx

from .models import Category, Source

SOURCE_PAGE = "https://www.rvo.nl/subsidies-financiering/isde/meldcodelijsten"
_CATEGORIES = ("heat_pumps", "insulation", "glass", "solar_boilers", "ventilation")
_MAX_PAGE_BYTES = 5 * 1024 * 1024
_MAX_WORKBOOK_BYTES = 100 * 1024 * 1024
_TIMEOUT = httpx.Timeout(30.0, connect=10.0)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        self._href = dict(attrs).get("href")
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text)))
            self._href = None
            self._text = []


def _official_url(url: str, *, page_url: str | None = None) -> str:
    absolute = urljoin(page_url or SOURCE_PAGE, url)
    parsed = urlparse(absolute)
    if parsed.scheme != "https" or parsed.hostname not in {"rvo.nl", "www.rvo.nl"}:
        raise ValueError(f"source URL is not an official RVO HTTPS URL: {absolute}")
    if not parsed.path.lower().endswith((".xlsx", ".xls")):
        raise ValueError(f"source URL is not an Excel workbook: {absolute}")
    if not parsed.path.lower().startswith("/sites/default/files/"):
        raise ValueError(f"source URL is outside the RVO files directory: {absolute}")
    return absolute


def _official_page_url(url: str) -> str:
    absolute = urljoin(SOURCE_PAGE, url)
    parsed = urlparse(absolute)
    if parsed.scheme != "https" or parsed.hostname not in {"rvo.nl", "www.rvo.nl"}:
        raise ValueError(f"source URL is not an official RVO HTTPS URL: {absolute}")
    return absolute


def _category(text: str) -> str | None:
    value = text.casefold()
    if "warmtepomp" in value:
        return "heat_pumps"
    if "isolatie" in value:
        return "insulation"
    if "glas" in value:
        return "glass"
    if "zonneboiler" in value:
        return "solar_boilers"
    if "ventilatie" in value:
        return "ventilation"
    return None


def _published_month(url: str) -> str | None:
    match = re.search(r"(?<!\d)(20\d{2})[-_/](0[1-9]|1[0-2])(?!\d)", url)
    return f"{match.group(1)}-{match.group(2)}" if match else None


def discover_sources(html: str, page_url: str = SOURCE_PAGE) -> dict[str, str]:
    """Return the five current workbook URLs found on the official RVO page."""
    parsed_page = urlparse(page_url)
    if parsed_page.scheme != "https" or parsed_page.hostname not in {
        "rvo.nl",
        "www.rvo.nl",
    }:
        raise ValueError("page URL must be an official RVO HTTPS URL")
    parser = _LinkParser()
    parser.feed(html)
    candidates: dict[str, set[str]] = {kind: set() for kind in _CATEGORIES}
    for href, label in parser.links:
        candidate = urljoin(page_url, href)
        label_text = label.casefold()
        if (
            "aanvraag" in label_text
            or "monument" in label_text
            or "meldcodelijst" not in label_text
        ):
            continue
        kind = _category(f"{label} {candidate}")
        if kind is None:
            continue
        try:
            candidates[kind].add(_official_url(candidate, page_url=page_url))
        except ValueError:
            continue
    ambiguous = [kind for kind in _CATEGORIES if len(candidates[kind]) > 1]
    if ambiguous:
        raise ValueError(
            f"RVO page contains multiple workbook links: {', '.join(ambiguous)}"
        )
    missing = [kind for kind in _CATEGORIES if not candidates[kind]]
    if missing:
        raise ValueError(
            f"RVO page does not contain all five workbook links: {', '.join(missing)}"
        )
    return {kind: next(iter(candidates[kind])) for kind in _CATEGORIES}


def _download(client: httpx.Client, url: str, limit: int, *, workbook: bool) -> bytes:
    for _ in range(4):
        with client.stream("GET", url) as response:
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("RVO response has a redirect without a location")
                url = (
                    _official_url(location, page_url=url)
                    if workbook
                    else _official_page_url(urljoin(url, location))
                )
                continue
            response.raise_for_status()
            declared = response.headers.get("content-length")
            if declared and int(declared) > limit:
                raise ValueError("RVO response exceeds the permitted size")
            chunks: list[bytes] = []
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > limit:
                    raise ValueError("RVO response exceeds the permitted size")
                chunks.append(chunk)
            return b"".join(chunks)
    raise ValueError("RVO returned too many redirects")


def _write_archive(raw_dir: Path, source: Source, content: bytes) -> None:
    category_dir = raw_dir / source.category
    category_dir.mkdir(parents=True, exist_ok=True)
    digest = source.sha256
    workbook = category_dir / f"{digest}.xlsx"
    if not workbook.exists():
        workbook.write_bytes(content)
    metadata_path = category_dir / "metadata.json"
    records: list[dict[str, object]] = []
    if metadata_path.exists():
        loaded = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, list):
            raise ValueError(f"invalid source metadata: {metadata_path}")
        records = loaded
    if not any(record.get("sha256") == digest for record in records):
        records.append(
            {
                "category": source.category,
                "url": source.url,
                "published_month": source.published_month,
                "fetched_at": source.fetched_at.isoformat(),
                "sha256": digest,
            }
        )
        metadata_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")


def fetch_sources(raw_dir: Path) -> list[tuple[Source, bytes]]:
    """Fetch and archive the current RVO workbooks, retaining every content revision."""
    raw_dir = Path(raw_dir)
    with httpx.Client(timeout=_TIMEOUT, follow_redirects=False) as client:
        page = _download(client, SOURCE_PAGE, _MAX_PAGE_BYTES, workbook=False).decode(
            "utf-8"
        )
        urls = discover_sources(page)
        result: list[tuple[Source, bytes]] = []
        for category, url in urls.items():
            content = _download(client, url, _MAX_WORKBOOK_BYTES, workbook=True)
            fetched_at = datetime.now(UTC)
            source = Source(
                category=cast("Category", category),
                url=url,
                published_month=_published_month(url),
                fetched_at=fetched_at,
                sha256=hashlib.sha256(content).hexdigest(),
            )
            _write_archive(raw_dir, source, content)
            result.append((source, content))
    return result
