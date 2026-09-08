from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Category = Literal[
    "heat_pumps",
    "insulation",
    "glass",
    "solar_boilers",
    "ventilation",
]


class Source(BaseModel):
    model_config = ConfigDict(frozen=True)

    category: Category
    url: str
    published_month: str | None = None
    fetched_at: datetime
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Subsidy(BaseModel):
    model_config = ConfigDict(frozen=True)

    purpose: str
    amount_cents: int | None
    unit: str


class Product(BaseModel):
    model_config = ConfigDict(frozen=True)

    meldcode: str = Field(pattern=r"^KA[0-9]{5}$")
    category: Category
    manufacturer: str | None
    model: str | None
    subsidies: list[Subsidy]
    attributes: dict[str, Any]
    source: Source
