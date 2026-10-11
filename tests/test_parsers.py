from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from typing import TYPE_CHECKING

import pytest
from openpyxl import Workbook

from isde_api.models import Category, Source
from isde_api.parsers import LAYOUTS, WorkbookParseError, parse_workbook

if TYPE_CHECKING:
    from collections.abc import Sequence


def workbook_bytes(
    category: Category,
    rows: Sequence[Sequence[object]],
    *,
    headers: Sequence[object] | None = None,
) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Meldcodes"
    layout = LAYOUTS[category]
    worksheet.append(headers or list(layout.headers.values()))
    for row in rows:
        worksheet.append(row)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()


def source(category: Category) -> Source:
    return Source(
        category=category,
        url=f"https://example.test/{category}.xlsx",
        published_month="2026-08",
        fetched_at=datetime(2026, 9, 7, tzinfo=UTC),
        sha256=sha256(category.encode()).hexdigest(),
    )


@pytest.mark.parametrize(
    ("category", "row", "expected_subsidies", "expected_attributes"),
    [
        (
            "heat_pumps",
            [
                "KA01290",
                "Alpha",
                "WZSV",
                6,
                "  €4.425",
                " €1.234,50",
                "R407C",
                1774,
                "Grond-Water",
            ],
            [
                ("standard", 442500, "EUR/product"),
                ("second_heat_pump", 123450, "EUR/product"),
            ],
            {
                "power_kw": 6,
                "refrigerant": "R407C",
                "gwp": 1774,
                "product_category": "Grond-Water",
            },
        ),
        (
            "insulation",
            [
                "KA29424",
                "STEICO",
                "protect M",
                "WF",
                3.5,
                "161",
                " €20,25",
                " €40,50",
                "  .",
                "Gevel",
                "Alle woningen",
            ],
            [
                ("single_measure", 2025, "EUR/m2"),
                ("multiple_measures", 4050, "EUR/m2"),
                ("biobased_bonus", None, "EUR/m2"),
            ],
            {
                "material": "WF",
                "minimum_rd_value": 3.5,
                "minimum_thickness_mm": "161",
                "product_category": "Gevel",
                "dwelling_type": "Alle woningen",
            },
        ),
        (
            "glass",
            [
                "KA31741",
                "KA30558",
                "Eko",
                "1VSG",
                1.3,
                "€46,00",
                "€92,00",
                ".",
                "Glas",
                "Alle woningen",
            ],
            [
                ("single_measure", 4600, "EUR/m2"),
                ("multiple_measures", 9200, "EUR/m2"),
                ("monument", None, "EUR/m2"),
            ],
            {
                "parent_meldcode": "KA30558",
                "ug_value": 1.3,
                "product_category": "Glas",
                "dwelling_type": "Alle woningen",
            },
        ),
        (
            "solar_boilers",
            [
                "KA08006",
                "12-Zonneboiler",
                "200-TW-24",
                1125,
                "€1.148",
                "Tot en met 5m2",
            ],
            [("standard", 114800, "EUR/product")],
            {"annual_output_kwh": 1125, "surface_area": "Tot en met 5m2"},
        ),
        (
            "ventilation",
            [
                "KA32097",
                "ClimaRad",
                "Ventura V1X",
                "Decentrale balansventilatie WTW",
                "€400",
            ],
            [("standard", 40000, "EUR/product")],
            {"product_category": "Decentrale balansventilatie WTW"},
        ),
    ],
)
def test_parse_category(category, row, expected_subsidies, expected_attributes):
    products = parse_workbook(workbook_bytes(category, [row]), source(category))

    assert len(products) == 1
    product = products[0]
    assert product.meldcode == row[0]
    assert product.manufacturer == row[1 if category != "glass" else 2]
    assert product.attributes == expected_attributes
    assert [
        (item.purpose, item.amount_cents, item.unit) for item in product.subsidies
    ] == expected_subsidies
    assert product.source == source(category)


def test_preserves_duplicate_rows():
    row = ["KA32097", "ClimaRad", "Ventura V1X", "WTW", "€400"]
    products = parse_workbook(
        workbook_bytes("ventilation", [row, row]), source("ventilation")
    )
    assert [product.meldcode for product in products] == ["KA32097", "KA32097"]


def test_rejects_changed_header():
    headers: list[object] = list(LAYOUTS["ventilation"].headers.values())
    headers[-1] = "Nieuw subsidiebedrag"
    with pytest.raises(WorkbookParseError, match="unsupported Meldcodes headers"):
        parse_workbook(
            workbook_bytes("ventilation", [], headers=headers), source("ventilation")
        )


@pytest.mark.parametrize("amount", ["free", "€12,345", -1, True])
def test_rejects_malformed_amount(amount):
    row = ["KA32097", "ClimaRad", "Ventura V1X", "WTW", amount]
    with pytest.raises(WorkbookParseError, match="invalid subsidy amount"):
        parse_workbook(workbook_bytes("ventilation", [row]), source("ventilation"))


def test_rejects_data_row_without_meldcode():
    row = [None, "ClimaRad", "Ventura V1X", "WTW", "€400"]
    with pytest.raises(WorkbookParseError, match="data but no meldcode"):
        parse_workbook(workbook_bytes("ventilation", [row]), source("ventilation"))


@pytest.mark.parametrize(
    "amount,cents", [(20.25, 2025), (4425, 442500), (0, 0), ("€0,00", 0)]
)
def test_numeric_amounts(amount, cents):
    row = ["KA32097", "Brand", "Model", "WTW", amount]
    product = parse_workbook(
        workbook_bytes("ventilation", [row]), source("ventilation")
    )[0]
    assert product.subsidies[0].amount_cents == cents


def test_internal_blank_header_rejected():
    headers: list[object] = list(LAYOUTS["ventilation"].headers.values())
    headers.insert(1, None)
    with pytest.raises(WorkbookParseError, match="unsupported Meldcodes headers"):
        parse_workbook(
            workbook_bytes("ventilation", [], headers=headers), source("ventilation")
        )


def test_empty_workbook_produces_no_records():
    assert (
        parse_workbook(workbook_bytes("ventilation", []), source("ventilation")) == []
    )
