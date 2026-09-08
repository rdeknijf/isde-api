from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from isde_api.main import DISCLAIMER, create_app
from isde_api.models import Product, Source, Subsidy
from isde_api.storage import CATEGORIES, publish, query


@pytest.fixture
def dataset():
    sources = [
        Source(
            category=c,
            url=f"https://www.rvo.nl/{c}.xlsx",
            published_month="2026-08",
            fetched_at=datetime(2026, 9, 7, tzinfo=UTC),
            sha256=str(i) * 64,
        )
        for i, c in enumerate(CATEGORIES)
    ]
    products = [
        Product(
            meldcode="KA00001",
            category=s.category,
            manufacturer="Märk & 100%",
            model=f"Example {i}",
            subsidies=[
                Subsidy(purpose="single_measure", amount_cents=2025, unit="EUR/m2")
            ],
            attributes={"value": None},
            source=s,
        )
        for i, s in enumerate(sources)
    ]
    return products, sources


def test_current_import_and_same_month_correction(tmp_path, dataset):
    products, sources = dataset
    path = tmp_path / "current.db"
    assert publish(path, products, sources)
    before = query(path)
    assert not publish(path, products, sources)
    assert query(path) == before
    revised = sources[0].model_copy(update={"sha256": "f" * 64})
    updated = products[0].model_copy(update={"model": "Corrected", "source": revised})
    assert publish(path, [updated, *products[1:]], [revised, *sources[1:]])
    assert query(path, model="corrected")[1] == 1
    assert query(path)[1] == 5
    # Partial import must never replace the complete current data.
    with pytest.raises(ValueError):
        publish(path, [updated], [revised])
    assert query(path, model="corrected")[1] == 1


def test_preserve_duplicate_codes_and_rows(tmp_path, dataset):
    products, sources = dataset
    products.append(products[0].model_copy(update={"model": "Other application"}))
    path = tmp_path / "current.db"
    publish(path, products, sources)
    items, total, _ = query(path, code="KA00001")
    assert total == len(items) == 6
    assert len({p.category for p in items}) == 5


def test_api_filters_pagination_export_and_errors(tmp_path, dataset):
    path = tmp_path / "current.db"
    publish(path, *dataset)
    # ASGI test transport never connects to the network.
    client = TestClient(create_app(path))
    response = client.get("/v1/meldcode/ka00001")
    assert response.status_code == 200
    assert response.json()["total"] == 5
    assert response.json()["disclaimer"] == DISCLAIMER
    first = client.get("/v1/products?limit=2").json()
    second = client.get("/v1/products?limit=2&offset=2").json()
    assert first["total"] == second["total"] == 5
    assert {p["category"] for p in first["items"]}.isdisjoint(
        p["category"] for p in second["items"]
    )
    filtered = client.get(
        "/v1/products",
        params={"category": "glass", "manufacturer": "MÄRK", "model": "example"},
    )
    assert filtered.json()["total"] == 1
    assert client.get("/v1/products", params={"manufacturer": "%"}).json()["total"] == 5
    assert (
        client.get("/v1/products", params={"manufacturer": "' OR 1=1 --"}).json()[
            "total"
        ]
        == 0
    )
    export = client.get("/v1/export").json()
    assert len(export["items"]) == export["total"] == 5
    assert export["items"][0]["subsidies"][0]["amount_cents"] == 2025
    assert export["items"][0]["source"]["published_month"] == "2026-08"
    categories = client.get("/v1/categories").json()["items"]
    assert sum(c["count"] for c in categories) == export["total"]
    assert len(categories) == 5
    assert all(c["subsidy_units"] == ["EUR/m2"] for c in categories)
    assert client.get("/health").json()["products"] == 5
    for url in (
        "/v1/products?limit=201",
        "/v1/products?offset=-1",
        "/v1/products?category=invalid",
    ):
        assert client.get(url).status_code == 422
    missing = client.get("/v1/meldcode/unknown")
    assert missing.status_code == 404
    assert "current data" in missing.json()["detail"]
    assert missing.json()["disclaimer"] == DISCLAIMER
    assert client.get("/v1/history").status_code == 404
    paths = client.get("/openapi.json").json()["paths"]
    assert set(paths) == {
        "/health",
        "/v1/meldcode/{code}",
        "/v1/products",
        "/v1/categories",
        "/v1/export",
    }


def test_empty_database_is_unavailable(tmp_path):
    path = tmp_path / "missing.db"
    client = TestClient(create_app(path))
    for url in ("/health", "/v1/categories", "/v1/products", "/v1/export"):
        assert client.get(url).status_code == 503
    assert not path.exists()


def test_ingest_failure_keeps_previous_data(tmp_path, dataset, monkeypatch):
    from isde_api import ingest

    products, sources = dataset
    path = tmp_path / "current.db"
    publish(path, products, sources)
    before = query(path)
    monkeypatch.setattr(
        ingest, "fetch_sources", lambda _: [(s, b"invalid") for s in sources]
    )
    result = CliRunner().invoke(
        ingest.main, ["--database", str(path), "--raw-dir", str(tmp_path / "raw")]
    )
    assert result.exit_code != 0
    assert "previous data retained" in result.output
    assert query(path) == before


def test_import_transaction_rollback(tmp_path, dataset):
    import sqlite3

    path: Path = tmp_path / "current.db"
    publish(path, *dataset)
    before = query(path)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            "CREATE TRIGGER reject_insert BEFORE INSERT ON products "
            "BEGIN SELECT RAISE(ABORT, 'test write failure'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        publish(path, *dataset)
    assert query(path) == before
