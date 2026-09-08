# ISDE Meldcode API

Live service: <https://isde.deknijf.com>. API documentation: <https://isde.deknijf.com/docs>.

A free API for the current RVO ISDE product lists. It covers heat pumps, insulation, glass, solar boilers, and ventilation. No account or API key is necessary.

## Run locally

```sh
uv sync
prek install
uv run isde-ingest
uv run uvicorn isde_api.main:app --host 127.0.0.1 --port 8011
```

Open <http://127.0.0.1:8011> for the page or <http://127.0.0.1:8011/docs> for interactive API documentation. Set `DATABASE_PATH` to change the SQLite path. The default is `data/isde.db`. Use `isde-ingest --raw-dir` to change the raw archive path.

## Endpoints

| Endpoint | Result |
| --- | --- |
| `GET /v1/meldcode/{code}` | All current records for a meldcode. An unknown code returns 404. |
| `GET /v1/products` | Current records with `category`, `manufacturer`, and `model` filters. |
| `GET /v1/categories` | Category counts, subsidy units, and source metadata. |
| `GET /v1/export` | The complete current dataset as JSON. |
| `GET /health` | Dataset availability and source metadata. Returns 503 before the first successful import. |
| `GET /docs` | Interactive OpenAPI documentation. |

Search accepts `limit` from 1 to 200 and a nonnegative `offset`. The default limit is 50. Manufacturer and model filters use case-insensitive substring matches. The `total` field counts all matches before pagination. Category values are `heat_pumps`, `insulation`, `glass`, `solar_boilers`, and `ventilation`.

```sh
curl 'http://127.0.0.1:8011/v1/meldcode/KA01290'
curl 'http://127.0.0.1:8011/v1/products?category=heat_pumps&manufacturer=Alpha&limit=10'
curl 'http://127.0.0.1:8011/v1/export' -o current.json
```

## Data contract

Each product includes its meldcode, category, manufacturer, model, subsidies, category-specific attributes, and source metadata. Missing source values remain null. Subsidy amounts use integer euro cents. `EUR/product` identifies an amount per product; `EUR/m2` identifies an amount per square metre. For example, `amount_cents: 2025` with `unit: EUR/m2` means EUR 20.25 per square metre.

Subsidy purposes preserve source distinctions: `standard`, `second_heat_pump`, `single_measure`, `multiple_measures`, `biobased_bonus`, and `monument`. Do not add these amounts without the applicable RVO rules. Attributes retain source values; fields such as insulation thickness can contain text.

Source metadata includes the official URL, the published month where available, the retrieval time, and the SHA-256 content hash. These dates describe the source. They do not establish eligibility dates. The current lists contain 8,044 records as verified on 2026-09-07. That count can change.

The importer discovers the five product workbooks from the RVO page. It excludes application forms and rejects ambiguous links or unsupported workbook layouts. It validates all five categories before one database transaction replaces the current data. A failed import retains the previous dataset. A source correction within the same month updates the data. The importer checks the source bytes on every run, even if the URL stays the same.

Raw files persist under `data/raw/<category>/<sha256>.xlsx`, with source metadata in the category directory. SQLite stores only the current normalized records. Historical tables, date queries, and change feeds remain outside v1. Duplicate codes remain separate records; the lookup response always uses an `items` list.

## Validation

```sh
uv run pytest --cov=isde_api --cov-report=term-missing
uv run ruff check src tests
uv run ruff format --check src tests
uv run ty check
uv run pre-commit run --files src/isde_api/*.py tests/*.py
```

The default tests block network sockets. They permit Unix sockets for the ASGI event loop. The browser test requires a local server and runs separately:

```sh
uv run playwright install chromium
ISDE_BROWSER_URL=http://127.0.0.1:8010 uv run pytest tests/test_browser.py --allow-hosts=127.0.0.1
```

The browser test checks category counts, lookup success and failure, clipboard content, mobile overflow, and unavailable data. It saves desktop and mobile screenshots under `data/screenshots/`. All data and screenshots stay outside version control.

`prek install` wires the pre-commit checks (ruff, ty, and the beads snapshot export). Run it after `uv sync` on a fresh checkout.

## Container and deployment

```sh
uv run isde-ingest
mkdir -p data/raw
docker compose up -d --build
curl 'http://127.0.0.1:8010/health'
```

The local container binds only to loopback. It runs as UID 1000 and mounts `./data` at `/data`. The data directory must permit that user to write.

The prepared production configuration uses the existing `proxy` network, the `websecure` Traefik entrypoint, and the `myresolver` certificate resolver on buckland. It removes the local port mapping and sets the host to `isde.deknijf.com`.

The live project and its data reside under `~/services/isde-api` on buckland. Cloudflare proxies the CNAME `isde.deknijf.com` to `buckland.deknijf.com`. Run deployment updates from that directory:

```sh
docker compose -f compose.yaml -f compose.production.yaml up -d --build
```

The daily cron entry is:

```cron
15 3 * * * /home/rdeknijf/services/isde-api/scripts/ingest.sh >> /home/rdeknijf/logs/isde-ingest.log 2>&1
```

Create the log directory before installation. The wrapper uses `flock` to prevent overlapping scheduled imports. It explicitly archives raw workbooks under `/data/raw` inside the persistent volume. The public deployment and an actual cron-triggered import passed verification on 2026-09-07. The daily schedule uses Europe/Amsterdam time. Stop the container to roll back the release; keep `data/` for a later restart.

## Source and reuse

RVO supplies the [meldcode lists](https://www.rvo.nl/subsidies-financiering/isde/meldcodelijsten). Its [open-data policy](https://www.rvo.nl/onderwerpen/open-data) permits reuse and distribution of information. Dataset-specific terms can override the general attribution rule. See `AGENTS.md` for the checked terms.

This is an independent service. These downloads confer no rights. Product data does not establish subsidy eligibility. Check the current RVO conditions. A code absent from this API does not establish ineligibility.

## Project state

`AGENTS.md` holds the scope and instructions. `STATUS.md` holds verified state. Beads holds all tasks; use `bd ready` and `bd show <id>`. Historical features remain deferred.
