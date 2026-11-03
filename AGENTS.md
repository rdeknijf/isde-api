# ISDE Meldcode API

Public REST API serving the current RVO ISDE meldcodelijsten for heat pumps, insulation, glass, solar boilers, and ventilation as clean JSON.

Origin: discovery run 2026-09-06, ranked first in `~/projects/idea-machine/api-opportunities.md` (Codex round, score 8.0). Sister project and pattern reference: `~/projects/grid-emissions-api` (ENTSO-E to FastAPI plus SQLite).

## Mission

Provide a useful free public service and demonstrate reliable implementation. RVO provides downloadable Excel lists and an online product lookup. This API makes the current product data easy to reuse. Revenue and buyer commitments are not v1 requirements.

## V1 scope (confirmed 2026-09-07)

Serve current data only: meldcode lookup, product search, categories, and a complete JSON download. Include source references, retrieval dates, and explicit subsidy units. Product data does not establish subsidy eligibility.

Keep source URLs, published months where available, retrieval dates, and content hashes with the current data. Retain raw source files for error investigation and possible later reprocessing. These are source records, not historical eligibility dates.

Keep ingestion separate from API queries so a later change can add historical storage. V1 stores only the current normalised data. Do not implement history tables, release comparison, historical backfill, snapshot endpoints, or date query parameters. History remains a later extension, not a v1 prerequisite.

No accounts, metered billing, or speculative usage counters. Use Beads for deferred work. Rutger authorised the current-data v1 build on 2026-09-07.

## Verified facts (2026-09-07)

- Source page: <https://www.rvo.nl/subsidies-financiering/isde/meldcodelijsten>. Page text: "Deze lijsten worden maandelijks bijgewerkt" and "aan deze downloads kunt u geen rechten ontlenen".
- Five current lists (August 2026 release), all xlsx, under `/sites/default/files/2026-08/`: Hoogrendementsglas, Isolatiematerialen, Ventilatie-units, Warmtepompen, Zonneboilers. URLs carry the month in both path and filename, so URL discovery must scrape the page, not guess.
- Each workbook has two sheets: `Toelichting` (column glossary) and `Meldcodes` (data). Row 1 of `Meldcodes` is the header.
- Column layout differs per category. Warmtepompen: `MELDCODE, Fabrikant / Merknaam, Model, Vermogen (KW), Subsidiebedrag, Subsidiebedragt 2e warmtepomp, NAAM_KOUDEMIDDEL, GWP, Categorie`. Isolatiematerialen: `MELDCODE, Fabrikant / Merknaam, Model, NAAM_MATERIAAL, MIN_WAARDE_RD, MIN_DIKTE_MM, Subsidiebedrag bij een enkele maatregel, Subsidiebedrag bij meerdere maateregelen, BioBased Bonus, Categorie, Woning Type`. Headers contain typos (`Subsidiebedragt`, `maateregelen`); map them explicitly, do not rely on exact text staying stable.
- Amounts are formatted strings with leading spaces and Dutch separators (`'  €4.425'`, `' €20,25'`, `'  .'` for empty). Parse to integer cents.
- Meldcodes look like `KA01290` (KA plus five digits) in both inspected lists.
- Reuse checked 2026-09-07: <https://www.rvo.nl/onderwerpen/open-data> says "U mag deze hergebruiken." and "U bent niet verplicht RVO als bron te vermelden, tenzij het anders vermeld staat bij de datasets en webservices." The policy permits reuse and distribution of information, including apps. Images have separate restrictions. The meldcode download page states that the downloads confer no rights; it shows no separate reuse restriction. Include attribution and this disclaimer.
- Older monthly releases (checked 2026-11-03, bead isde-ami.3): old workbook URLs can become unavailable at RVO, so keep our own raw archive. Evidence:
  - The 2024-10 Wayback snapshots of the page link PDF lists, not xlsx. This check recovered no xlsx workbook from before 2025.
  - 2025-02 and 2025-06: the page linked four xlsx lists each. All eight URLs return 404 at RVO, and the Wayback searches found no capture of them.
  - 2025-05: both URLs return 404 at RVO. The Wayback prefix search found the insulation and solar boiler workbooks, and both downloads from Wayback succeeded.
  - 2025-09 to 2026-10: every URL found still returns the workbook at RVO. The recovered set has no heat pump list for 2025-12, only ventilation for 2026-01, and no insulation list for 2026-04. Files with other names can exist.
  - The earliest ventilation workbook found is from 2026-01. The 2025 page snapshots link four categories.
  - No file found for 2025-01, 03, 04, 07, 08. The search used Wayback page snapshots, a Wayback prefix search per month, and (except for 2025-01) a probe of the usual file name pattern at RVO. A file with a different name can still exist.
  - All 47 recovered files are in the raw archive on buckland since 2026-11-03. The current parser reads insulation and solar boilers from 2025-05, and all five categories from 2026-02. It rejects the 2025-09 to 2025-12 glass files, the 2025-09 to 2025-11 heat pump files, and the 2026-01 ventilation file. Older glass lists use `MAX_WAARDE_U` and `Subsidiebedrag Monumentale woning` (no `Hoofdmeldcode`, no `Ug waarde`). Older heat pump lists have no `Subsidiebedragt 2e warmtepomp`. The 2026-01 ventilation list uses `Meldcode, Fabrikant, Type, Categorie, Subsidiebedrag`.
- Existing competitor: ISDEscan (<https://isdescan.nl/isde-meldcode-check>), consumer lookup, no API, no history.
- Rutger's own ISDE application context lives in `~/projects/isolation-subsidies` (meldcode verification for his 2026 application). Useful as a real test case; not a dependency.

## Stack (decided)

- Python, latest stable (3.15, pinned in `.python-version`; the Docker image installs the same version through uv); uv, ruff, ty, pytest, pytest-cov, pytest-socket, prek; src layout, no `__init__.py` in tests.
- FastAPI plus SQLite, same shape as grid-emissions-api. openpyxl for ingestion.
- Deploy: Docker plus Traefik on buckland, behind Cloudflare. Rutger selected `isde.deknijf.com` for now on 2026-09-07.
- Task tracking: beads (`bd`) in `.beads/`, see *Issue tracking* below. This project was also the evaluation of beads as a task system; the findings are in `STATUS.md` under "Beads evaluation".

## Commands

Verified so far:

```bash
bd ready          # unblocked tasks
bd list --all     # everything
bd dep tree <id>  # dependency tree of an epic
bd graph <id>     # ASCII layered dependency graph (wide terminal)
npx -y beads-ui start   # community web UI on http://127.0.0.1:3000 (Issues, Epics, Board); verified 2026-09-07
```

Implementation commands verified on 2026-09-07:

```sh
uv sync
uv run isde-ingest
uv run pytest
uv run ruff check .
uv run ty check
uv run prek run --all-files
uv run prek install
uv audit --locked
docker compose up -d --build
curl http://127.0.0.1:8010/health
ISDE_BROWSER_URL=http://127.0.0.1:8010 uv run pytest tests/test_browser.py --allow-hosts=127.0.0.1
```

Use `README.md` for the API contract and deployment commands. The local Docker preview uses port 8010. `scripts/ingest.sh` archives raw sources in the persistent `/data/raw` volume. `prek install` wires the pre-commit checks, including the beads snapshot export. Rutger approved public deployment on 2026-09-07. V1 is live at https://isde.deknijf.com with a verified daily import at 03:15 Europe/Amsterdam. See STATUS.md for deployment details.

## Open decisions

- Whether to include the "Aanvraag vermelding" forms (manufacturer application forms). Out of scope for v1.
- The August 2026 import contained 8,044 records and no duplicate meldcodes within or across categories. The October 2026 release has 6,916 records, also without duplicates. The API preserves duplicate records if future lists contain them.


<!-- BEGIN BEADS CODEX SETUP: generated by bd setup codex -->
## Beads Issue Tracker

Use Beads (`bd`) for durable task tracking in repositories that include it. Use the `beads` skill at `.agents/skills/beads/SKILL.md` (project install) or `~/.agents/skills/beads/SKILL.md` (global install) for Beads workflow guidance, then use the `bd` CLI for issue operations.

### Quick Reference

```bash
bd ready                # Find available work
bd show <id>            # View issue details
bd update <id> --claim  # Claim work
bd close <id>           # Complete work
bd prime                # Refresh Beads context
```

### Rules

- Use `bd` for all task tracking; do not create markdown TODO lists.
- Run `bd prime` when Beads context is missing or stale. Codex 0.129.0+ can load Beads context automatically through native hooks; use `/hooks` to inspect or toggle them.
- Keep persistent project memory in Beads via `bd remember`; do not create ad hoc memory files.

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.
<!-- END BEADS CODEX SETUP -->

## Issue tracking

The backlog is beads in this repository: `.beads/`, id prefix `isde`, synced with GitHub issues in `rdeknijf/isde-api`. The tracked `.beads/issues.jsonl` is the backup, and a pre-commit hook (`scripts/bd-export-hook.sh`) keeps it current on every commit. On a fresh clone, restore the working data with `bd bootstrap --yes`.

Pull at the start of a session:

```sh
scripts/bd-sync pull
```

Push only per epic, never the whole backlog:

```sh
scripts/bd-sync push --parent <epic-id>
scripts/bd-sync push --issues <id,id>
```

A bare `bd github sync` is forbidden. It pushes every bead to GitHub, and GitHub holds only what was pushed on purpose. `scripts/bd-sync` refuses a push without a scope for that reason.

GitHub issues are the INBOX, not the backlog. `scripts/bd-sync pull` brings a new issue into beads, and triage does the routing.

Status vocabulary:

- `open` plus label `triage`: unrouted inbox item.
- `open`: routed and ready to pick up.
- `in_progress`: someone is on it.
- `blocked`: waiting on something.
- `blocked` plus label `needs-human`: waiting on Rutger.
- `closed`: done.

Effort is a label: `effort:XS`, `effort:S`, `effort:M`, `effort:L`, `effort:XL`.

This repository is mounted in `rdeknijf/square` as the submodule `context/isde-api`; square's `docs/isde-api.md` holds the square-side notes.
