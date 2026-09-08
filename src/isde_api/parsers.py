import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any

from openpyxl import load_workbook

from isde_api.models import Product, Source, Subsidy


class WorkbookParseError(ValueError):
    """The workbook does not match the supported RVO format."""


@dataclass(frozen=True)
class Layout:
    headers: dict[str, str]
    subsidies: tuple[tuple[str, str, str], ...]
    attributes: tuple[tuple[str, str], ...]


LAYOUTS: dict[str, Layout] = {
    "heat_pumps": Layout(
        headers={
            "meldcode": "MELDCODE",
            "manufacturer": "Fabrikant / Merknaam",
            "model": "Model",
            "power_kw": "Vermogen (KW)",
            "subsidy": "Subsidiebedrag",
            "second_heat_pump_subsidy": "Subsidiebedragt 2e warmtepomp",
            "refrigerant": "NAAM_KOUDEMIDDEL",
            "gwp": "GWP",
            "product_category": "Categorie",
        },
        subsidies=(
            ("subsidy", "standard", "EUR/product"),
            ("second_heat_pump_subsidy", "second_heat_pump", "EUR/product"),
        ),
        attributes=(
            ("power_kw", "power_kw"),
            ("refrigerant", "refrigerant"),
            ("gwp", "gwp"),
            ("product_category", "product_category"),
        ),
    ),
    "insulation": Layout(
        headers={
            "meldcode": "MELDCODE",
            "manufacturer": "Fabrikant / Merknaam",
            "model": "Model",
            "material": "NAAM_MATERIAAL",
            "minimum_rd_value": "MIN_WAARDE_RD",
            "minimum_thickness_mm": "MIN_DIKTE_MM",
            "single_measure_subsidy": "Subsidiebedrag bij een enkele maatregel",
            "multiple_measures_subsidy": "Subsidiebedrag bij meerdere maateregelen",
            "biobased_bonus": "BioBased Bonus",
            "product_category": "Categorie",
            "dwelling_type": "Woning Type",
        },
        subsidies=(
            ("single_measure_subsidy", "single_measure", "EUR/m2"),
            ("multiple_measures_subsidy", "multiple_measures", "EUR/m2"),
            ("biobased_bonus", "biobased_bonus", "EUR/m2"),
        ),
        attributes=(
            ("material", "material"),
            ("minimum_rd_value", "minimum_rd_value"),
            ("minimum_thickness_mm", "minimum_thickness_mm"),
            ("product_category", "product_category"),
            ("dwelling_type", "dwelling_type"),
        ),
    ),
    "glass": Layout(
        headers={
            "meldcode": "MELDCODE",
            "parent_meldcode": "Hoofdmeldcode",
            "manufacturer": "Fabrikant / Merknaam",
            "model": "Model",
            "ug_value": "Ug waarde",
            "single_measure_subsidy": "Subsidiebedrag bij een enkele maatregel",
            "multiple_measures_subsidy": "Subsidiebedrag bij meerdere maateregelen",
            "monument_subsidy": "Subsidiebedrag Monumentale woning",
            "product_category": "Categorie",
            "dwelling_type": "Woning Type",
        },
        subsidies=(
            ("single_measure_subsidy", "single_measure", "EUR/m2"),
            ("multiple_measures_subsidy", "multiple_measures", "EUR/m2"),
            ("monument_subsidy", "monument", "EUR/m2"),
        ),
        attributes=(
            ("parent_meldcode", "parent_meldcode"),
            ("ug_value", "ug_value"),
            ("product_category", "product_category"),
            ("dwelling_type", "dwelling_type"),
        ),
    ),
    "solar_boilers": Layout(
        headers={
            "meldcode": "MELDCODE",
            "manufacturer": "Fabrikant / Merknaam",
            "model": "Model",
            "annual_output_kwh": "Jaarproductie (KWh)",
            "subsidy": "Subsidiebedrag",
            "surface_area": "Oppervlakte",
        },
        subsidies=(("subsidy", "standard", "EUR/product"),),
        attributes=(
            ("annual_output_kwh", "annual_output_kwh"),
            ("surface_area", "surface_area"),
        ),
    ),
    "ventilation": Layout(
        headers={
            "meldcode": "MELDCODE",
            "manufacturer": "Fabrikant / Merknaam",
            "model": "Model",
            "product_category": "Categorie",
            "subsidy": "Subsidiebedrag",
        },
        subsidies=(("subsidy", "standard", "EUR/product"),),
        attributes=(("product_category", "product_category"),),
    ),
}


def _normalise_header(value: object) -> str:
    return " ".join(str(value).split()).casefold()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _attribute_value(value: object) -> Any:
    if isinstance(value, str):
        return value.strip() or None
    return value


def _amount_cents(value: object) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise WorkbookParseError(f"invalid subsidy amount: {value!r}")

    if isinstance(value, int | float | Decimal):
        euros = Decimal(str(value))
        if euros < 0:
            raise WorkbookParseError(f"invalid subsidy amount: {value!r}")
        cents = euros * 100
        if cents != cents.to_integral_value():
            raise WorkbookParseError(f"invalid subsidy amount precision: {value!r}")
        return int(cents)

    text = str(value).replace("\u00a0", "").replace("€", "").replace(" ", "")
    if not text or text == ".":
        return None
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]{3})*(?:,[0-9]{1,2})?|[0-9]+", text):
        raise WorkbookParseError(f"invalid subsidy amount: {value!r}")

    normalised = text.replace(".", "").replace(",", ".")
    try:
        euros = Decimal(normalised)
    except InvalidOperation as error:
        raise WorkbookParseError(f"invalid subsidy amount: {value!r}") from error
    cents = euros * 100
    if cents != cents.to_integral_value():
        raise WorkbookParseError(f"invalid subsidy amount precision: {value!r}")
    return int(cents)


def _column_indexes(header_row: tuple[object, ...], layout: Layout) -> dict[str, int]:
    expected = [_normalise_header(value) for value in layout.headers.values()]
    actual = [_normalise_header(value) for value in header_row[: len(expected)]]
    has_extra_header = any(value is not None for value in header_row[len(expected) :])
    if actual != expected or has_extra_header:
        raise WorkbookParseError(
            "unsupported Meldcodes headers: expected "
            f"{list(layout.headers.values())!r}, "
            f"got {[value for value in header_row if value is not None]!r}"
        )
    return {name: index for index, name in enumerate(layout.headers)}


def parse_workbook(content: bytes, source: Source) -> list[Product]:
    """Parse one current RVO workbook using its source category."""
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as error:
        raise WorkbookParseError("invalid Excel workbook") from error
    try:
        if "Meldcodes" not in workbook.sheetnames:
            raise WorkbookParseError("workbook has no Meldcodes sheet")

        layout = LAYOUTS[source.category]
        rows = workbook["Meldcodes"].iter_rows(values_only=True)
        try:
            header_row = next(rows)
        except StopIteration as error:
            raise WorkbookParseError("Meldcodes sheet is empty") from error
        columns = _column_indexes(header_row, layout)

        products: list[Product] = []
        for row_number, row in enumerate(rows, start=2):
            if all(
                value is None or (isinstance(value, str) and not value.strip())
                for value in row
            ):
                continue
            meldcode = _optional_text(row[columns["meldcode"]])
            if meldcode is None:
                raise WorkbookParseError(f"row {row_number} has data but no meldcode")
            try:
                subsidies = [
                    Subsidy(
                        purpose=purpose,
                        amount_cents=_amount_cents(row[columns[column]]),
                        unit=unit,
                    )
                    for column, purpose, unit in layout.subsidies
                ]
                products.append(
                    Product(
                        meldcode=meldcode,
                        category=source.category,
                        manufacturer=_optional_text(row[columns["manufacturer"]]),
                        model=_optional_text(row[columns["model"]]),
                        subsidies=subsidies,
                        attributes={
                            name: _attribute_value(row[columns[column]])
                            for column, name in layout.attributes
                        },
                        source=source,
                    )
                )
            except (ValueError, IndexError) as error:
                if isinstance(error, WorkbookParseError):
                    raise WorkbookParseError(f"row {row_number}: {error}") from error
                raise WorkbookParseError(
                    f"invalid row {row_number}: {error}"
                ) from error
        return products
    finally:
        workbook.close()
