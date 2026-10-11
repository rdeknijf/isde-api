"""Current data only. Readers see one complete, validated import."""

import json
import sqlite3
from contextlib import closing
from typing import TYPE_CHECKING

from isde_api.models import Category, Product, Source

if TYPE_CHECKING:
    from pathlib import Path

CATEGORIES: tuple[Category, ...] = (
    "heat_pumps",
    "insulation",
    "glass",
    "solar_boilers",
    "ventilation",
)


class DataUnavailableError(Exception):
    """No complete dataset has been imported yet."""


def publish(path: Path, products: list[Product], sources: list[Source]) -> bool:
    """Replace the current dataset in one transaction; return whether bytes changed."""
    by_category = {source.category: source for source in sources}
    if len(sources) != len(CATEGORIES) or set(by_category) != set(CATEGORIES):
        raise ValueError(
            "An import must contain exactly one source for all five categories"
        )
    if {p.category for p in products} != set(CATEGORIES):
        raise ValueError("An import must contain products in all five categories")
    for product in products:
        if product.source != by_category[product.category]:
            raise ValueError("Product source does not match the imported source")
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=30)) as db, db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute(
            "CREATE TABLE IF NOT EXISTS sources "
            "(category TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        db.execute(
            "CREATE TABLE IF NOT EXISTS products (id INTEGER PRIMARY KEY, "
            "category TEXT NOT NULL REFERENCES sources(category), "
            "meldcode TEXT NOT NULL, "
            "manufacturer TEXT NOT NULL, model TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        db.execute("CREATE INDEX IF NOT EXISTS products_code ON products(meldcode)")
        db.execute("CREATE INDEX IF NOT EXISTS products_category ON products(category)")
        db.execute("BEGIN IMMEDIATE")
        old = {
            category: json.loads(payload)["sha256"]
            for category, payload in db.execute("SELECT category, payload FROM sources")
        }
        changed = old != {s.category: s.sha256 for s in sources}
        # Reparse identical bytes too: parser fixes must take effect on the next import.
        db.execute("DELETE FROM products")
        db.execute("DELETE FROM sources")
        db.executemany(
            "INSERT INTO sources VALUES (?, ?)",
            [(s.category, s.model_dump_json()) for s in sources],
        )
        db.executemany(
            "INSERT INTO products(category, meldcode, manufacturer, model, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                (
                    p.category,
                    p.meldcode,
                    (p.manufacturer or "").casefold(),
                    (p.model or "").casefold(),
                    p.model_dump_json(exclude={"source"}),
                )
                for p in products
            ],
        )
    return changed


def query(
    path: Path,
    *,
    code: str | None = None,
    category: str | None = None,
    manufacturer: str | None = None,
    model: str | None = None,
    limit: int | None = None,
    offset: int = 0,
) -> tuple[list[Product], int, list[Source]]:
    """Read records, counts and source metadata from the same SQLite snapshot."""
    if not path.is_file():
        raise DataUnavailableError("No current dataset. Run isde-ingest first.")
    clauses: list[str] = []
    params: list[str | int] = []
    for column, value in (("meldcode", code), ("category", category)):
        if value is not None:
            clauses.append(f"p.{column} = ?")
            params.append(value)
    for column, value in (("manufacturer", manufacturer), ("model", model)):
        if value is not None:
            clauses.append(f"instr(p.{column}, ?) > 0")
            params.append(value.casefold())
    # Every clause holds a fixed column name; all values are bound parameters.
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    try:
        with closing(
            sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        ) as db:
            db.execute("BEGIN")
            sources = [
                Source.model_validate_json(r[0])
                for r in db.execute("SELECT payload FROM sources ORDER BY category")
            ]
            if {s.category for s in sources} != set(CATEGORIES):
                raise DataUnavailableError("No complete current dataset")
            total = db.execute(
                "SELECT count(*) FROM products p" + where,  # noqa: S608
                params,
            ).fetchone()[0]
            sql = (
                "SELECT p.payload, s.payload FROM products p "  # noqa: S608
                "JOIN sources s ON s.category = p.category"
                + where
                + " ORDER BY p.meldcode, p.category, p.id"
            )
            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                params.extend([limit, offset])
            records = [
                Product.model_validate({**json.loads(p), "source": json.loads(s)})
                for p, s in db.execute(sql, params)
            ]
            return records, total, sources
    except sqlite3.OperationalError as exc:
        raise DataUnavailableError("Current dataset is unavailable") from exc
