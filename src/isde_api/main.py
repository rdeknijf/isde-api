"""Free access to the current RVO ISDE product lists."""

import os
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException

from isde_api.models import Category, Product, Source
from isde_api.storage import DataUnavailableError, query

SOURCE_PAGE = "https://www.rvo.nl/subsidies-financiering/isde/meldcodelijsten"
DISCLAIMER = (
    "Independent service using RVO data. These downloads confer no rights. "
    "Product data does not establish subsidy eligibility. "
    "Check the current RVO conditions."
)


class Records(BaseModel):
    items: list[Product]
    total: int
    sources: list[Source]
    source: str = SOURCE_PAGE
    disclaimer: str = DISCLAIMER


class CategoryCount(BaseModel):
    category: Category
    count: int
    source: Source
    subsidy_units: list[str]


class Categories(BaseModel):
    items: list[CategoryCount]
    source: str = SOURCE_PAGE
    disclaimer: str = DISCLAIMER


def create_app(database: Path | None = None) -> FastAPI:
    app = FastAPI(title="ISDE Meldcode API", version="1.0.0", description=DISCLAIMER)
    db_path = (
        database
        if database is not None
        else Path(os.environ.get("DATABASE_PATH", "data/isde.db"))
    )

    @app.exception_handler(DataUnavailableError)
    async def unavailable(_request: Request, exc: DataUnavailableError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "detail": str(exc),
                "source": SOURCE_PAGE,
                "disclaimer": DISCLAIMER,
            },
        )

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.detail,
                "source": SOURCE_PAGE,
                "disclaimer": DISCLAIMER,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def invalid_request(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": list(e["loc"]), "msg": e["msg"], "type": e["type"]}
                    for e in exc.errors()
                ],
                "source": SOURCE_PAGE,
                "disclaimer": DISCLAIMER,
            },
        )

    @app.get("/health")
    def health() -> dict:
        _, total, sources = query(db_path, limit=0)
        return {
            "status": "ok",
            "products": total,
            "sources": [s.model_dump(mode="json") for s in sources],
            "source": SOURCE_PAGE,
            "disclaimer": DISCLAIMER,
        }

    @app.get("/v1/meldcode/{code}", response_model=Records)
    def meldcode(code: str) -> Records:
        items, total, sources = query(db_path, code=code.strip().upper())
        if not items:
            raise HTTPException(
                404,
                "Meldcode not found in the current data. "
                "This does not establish subsidy ineligibility.",
            )
        return Records(items=items, total=total, sources=sources)

    @app.get("/v1/products", response_model=Records)
    def products(
        category: Category | None = None,
        manufacturer: Annotated[str | None, Query(max_length=200)] = None,
        model: Annotated[str | None, Query(max_length=200)] = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> Records:
        items, total, sources = query(
            db_path,
            category=category,
            manufacturer=manufacturer,
            model=model,
            limit=limit,
            offset=offset,
        )
        return Records(items=items, total=total, sources=sources)

    @app.get("/v1/categories", response_model=Categories)
    def categories() -> Categories:
        items, _, sources = query(db_path)
        return Categories(
            items=[
                CategoryCount(
                    category=s.category,
                    count=sum(p.category == s.category for p in items),
                    source=s,
                    subsidy_units=sorted(
                        {
                            a.unit
                            for p in items
                            if p.category == s.category
                            for a in p.subsidies
                        }
                    ),
                )
                for s in sources
            ]
        )

    @app.get("/v1/export", response_model=Records)
    def export() -> Records:
        items, total, sources = query(db_path)
        return Records(items=items, total=total, sources=sources)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def landing() -> str:
        return Path(__file__).with_name("static").joinpath("index.html").read_text()

    return app


app = create_app()
