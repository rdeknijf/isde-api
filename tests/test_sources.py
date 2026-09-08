from __future__ import annotations

import json

import httpx
import pytest

from isde_api.sources import SOURCE_PAGE, discover_sources, fetch_sources


def _page() -> str:
    links = {
        "heat_pumps": "Warmtepompen",
        "insulation": "Isolatiematerialen",
        "glass": "Hoogrendementsglas",
        "solar_boilers": "Zonneboilers",
        "ventilation": "Ventilatie-units",
    }
    return "".join(
        f'<a href="/sites/default/files/2026-08/{category}.xlsx">'
        f"Meldcodelijst {label}</a>"
        for category, label in links.items()
    )


def test_discover_sources_returns_exact_categories() -> None:
    form = '<a href="/sites/default/files/form.xlsx">Aanvraag vermelding warmtepomp</a>'
    html = form + _page()
    result = discover_sources(html)

    assert list(result) == [
        "heat_pumps",
        "insulation",
        "glass",
        "solar_boilers",
        "ventilation",
    ]
    assert result["heat_pumps"].startswith(
        "https://www.rvo.nl/sites/default/files/2026-08/"
    )


def test_discover_sources_rejects_ambiguous_category() -> None:
    extra = (
        '<a href="/sites/default/files/2026-08/other.xlsx">'
        "Meldcodelijst Warmtepompen</a>"
    )
    html = _page() + extra

    try:
        discover_sources(html)
    except ValueError as error:
        assert "multiple" in str(error)
    else:
        raise AssertionError("ambiguous category links must fail")


def test_discover_sources_rejects_missing_or_external_workbook() -> None:
    html = '<a href="https://example.com/evil.xlsx">Warmtepompen</a>'

    try:
        discover_sources(html)
    except ValueError as error:
        assert "five" in str(error)
    else:
        raise AssertionError("missing official links must fail")


def test_fetch_sources_deduplicates_same_hash_and_retains_revision(
    monkeypatch, tmp_path
):
    current = {"content": b"xlsx bytes"}
    requests = []

    def respond(request):
        requests.append(str(request.url))
        return (
            httpx.Response(200, text=_page())
            if str(request.url) == SOURCE_PAGE
            else httpx.Response(200, content=current["content"])
        )

    real_client = httpx.Client
    monkeypatch.setattr(
        "isde_api.sources.httpx.Client",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    first = fetch_sources(tmp_path)
    fetch_sources(tmp_path)
    assert len(requests) == 12
    for source, content in first:
        assert (
            tmp_path / source.category / f"{source.sha256}.xlsx"
        ).read_bytes() == content
        assert (
            len(json.loads((tmp_path / source.category / "metadata.json").read_text()))
            == 1
        )
    current["content"] = b"changed bytes"
    fetch_sources(tmp_path)
    assert len(list((tmp_path / "glass").glob("*.xlsx"))) == 2
    assert len(json.loads((tmp_path / "glass" / "metadata.json").read_text())) == 2


@pytest.mark.parametrize(
    "mode", ["too_large", "redirect_external", "redirect_loop", "http_error"]
)
def test_download_rejects_bad_responses(mode):
    from isde_api.sources import _download

    def respond(request):
        if mode == "too_large":
            return httpx.Response(200, content=b"12345")
        if mode == "redirect_external":
            return httpx.Response(
                302, headers={"location": "https://example.com/evil.xlsx"}
            )
        if mode == "redirect_loop":
            return httpx.Response(302, headers={"location": str(request.url)})
        return httpx.Response(500)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises((ValueError, httpx.HTTPStatusError)):
            _download(
                client,
                "https://www.rvo.nl/sites/default/files/test.xlsx",
                4,
                workbook=True,
            )
