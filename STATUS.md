# STATUS

Attention: maintain

## Goal

Serve the current RVO ISDE meldcodelijsten as a free public JSON API at <https://isde.deknijf.com>. V1 (current data only) is complete. History, date queries, change feeds, and billing are deferred extensions in Beads.

## Last update

2026-11-01: Dependency refresh (PR #4: Python 3.15, uv 0.13.6, FastAPI 0.162, ruff 0.17.3, ty 0.0.95), merged as `7ca9fba` and deployed to buckland at 07:58 UTC. 32 offline tests pass with 88.7% coverage. After the deploy, `/health`, `/v1/products`, and `/v1/categories` answer with the October data.

## Verified state (2026-11-01)

- Public `/health` reports 6,916 records from the October 2026 release (`published_month` 2026-10). The daily import ran at 2026-11-01T02:15:05Z with unchanged source content.
- Counts per category: heat_pumps 2,816, glass 1,876, insulation 1,723, solar_boilers 295, ventilation 206. A direct row count of each raw October workbook gives the same numbers, so the parser loses no rows.
- The count fell from 8,120 (September) to 6,916 (October) at the 2026-10-09 import. RVO shortened the lists; the `Meldcodes` headers are identical in the August, September, and October workbooks.
- A local import against the live RVO page finds the same five October workbooks with the same SHA-256 hashes as production. RVO has not yet published a November release.
- From 2026-09-11 to 2026-09-23 every daily import failed with "RVO page does not contain all five workbook links: heat_pumps, insulation, glass, solar_boilers, ventilation", so the page had no usable link for any category. The previous data stayed online, and the import recovered by itself on 2026-09-24 with the September release. No alert exists for failed imports (bead `isde-iha`); only `~/logs/isde-ingest.log` on buckland shows them.
- Older releases stay online at RVO: the August 2026 heat pump workbook URL still returns the archived file (same SHA-256).

## Deployment

The service runs as Docker Compose in `/home/rdeknijf/services/isde-api` on buckland, behind the host Traefik and Cloudflare (proxied CNAME `isde.deknijf.com` to `buckland.deknijf.com`). The production override `compose.production.yaml` uses the external `proxy` network and exposes no host port. The buckland checkout and its `DEPLOYED_COMMIT` file are at `7ca9fba` (Python 3.15.2, FastAPI 0.162.0 in the running container, checked 2026-11-01). Release: `git pull && docker compose -f compose.yaml -f compose.production.yaml up -d --build && git rev-parse HEAD > DEPLOYED_COMMIT`; a bare `docker compose up` drops the production override.

The buckland crontab runs `scripts/ingest.sh` daily at 03:15 Europe/Amsterdam and appends to `/home/rdeknijf/logs/isde-ingest.log`. Raw workbooks and per-category metadata persist under `data/raw/` on the host. The move to k3s is bead `isde-hxk` (deferred).

## Decisions

- 2026-09-07: Rutger approved the public release of current-data v1 at `isde.deknijf.com`.
- 2026-10-11: The beads database moved to the Dolt server `beads.deknijf.com:3306` (database `isde`).

## Blockers

None.

## Deadlines

None.

## Resume path

Read `AGENTS.md`, then run `bd ready` and `bd list --status=open`. Check freshness with `curl https://isde.deknijf.com/health` and `ssh buckland tail ~/logs/isde-ingest.log`.

## Beads evaluation

Purpose: judge whether beads works well as the task system for agent-driven projects. Verdict (2026-09-07): keep Beads for this project.

- 2026-09-07: `bd init` and batch create (`bd create --silent`, `bd dep add`) ran non-interactively. 40 issues, no cycles. The dependency graph made task selection and file ownership clear and kept historical features outside v1.
- 2026-09-07: `bd` has no GUI by design. The community web UI `npx -y beads-ui start` works (Issues, Epics, Board tabs).
- 2026-09-07: `bd init` wrote `.claude/settings.json`, `.codex/` hooks, and `.agents/skills/beads/` into the repo unbidden, and appended a section to `AGENTS.md`.
- 2026-09-07: Worker completion messages needed direct review. The first source-discovery implementation selected application forms; a realistic fixture now catches that error. Beads records task state but does not verify implementation quality.
- 2026-09-07: Beads refuses to close epics with deferred children, so the five v1 epics stay open.
- 2026-09-08: `prek install` owns the hook path; the beads snapshot export runs as a prek hook (`scripts/bd-export-hook.sh`).
