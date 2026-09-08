FROM python:3.14.7-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.9 /uv /uvx /bin/

RUN useradd --create-home --uid 1000 app

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src/ src/
RUN uv sync --frozen --no-dev && chown -R app:app /app

USER app

ENV DATABASE_PATH=/data/isde.db

EXPOSE 8000

CMD [".venv/bin/uvicorn", "isde_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
