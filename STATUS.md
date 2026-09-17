# STATUS

Attention: maintain

## Last update

2026-09-08: Public health confirms 8,044 records. The scheduled daily import finished successfully at 03:15:06 Europe/Amsterdam with unchanged source content. V1 remains live at <https://isde.deknijf.com>.

## Completed

1. Python 3.14.7 with uv, FastAPI, SQLite, Click, openpyxl, and the required quality tools.
2. Source discovery excludes application forms and rejects ambiguous links. Raw workbook hashes and metadata persist under `data/raw/`.
3. Category parsers preserve source-specific subsidies and units. Direct workbook checks confirm the counts and example amounts. No duplicate meldcodes occur in this import.
4. Atomic current-data imports retain the previous dataset after a failure. Repeated live imports report unchanged source content.
5. Current lookup, filtered search, categories, complete JSON export, health, and OpenAPI documentation work in the container.
6. The landing page passes desktop and mobile browser checks for counts, lookup, clipboard, overflow, and failure states. Screenshots: `data/screenshots/desktop.png` and `mobile.png`.
7. Validation: 32 offline tests pass, with 91% code coverage. The separate Playwright test passes. Ruff, ty, and pre-commit pass for all new Python files. The wheel includes the static page. Docker build and API smoke checks pass.
8. Docker and Traefik configuration matches the inspected buckland network, entrypoint, and certificate resolver. The daily import wrapper passes a local container run.

## Open

The current-data v1 implementation and deployment are complete. Five implementation epics remain open because their historical or other deferred children remain unfinished. Beads holds those extensions. History, date queries, change feeds, and billing remain deferred.

## Deployment

Rutger approved public release on 2026-09-07. The service runs in `/home/rdeknijf/services/isde-api` on buckland. Cloudflare record `330cfa455642db126090549300d3cbf6` is a proxied CNAME from `isde.deknijf.com` to `buckland.deknijf.com`. The production Compose override uses the existing `proxy` network and exposes no host port. Public responses report `CF-Cache-Status: DYNAMIC`; no custom cache rule is needed for current data.

The crontab runs `/home/rdeknijf/services/isde-api/scripts/ingest.sh` daily at 03:15 in buckland's Europe/Amsterdam timezone. Logs go to `/home/rdeknijf/logs/isde-ingest.log`. An actual cron-triggered import finished at `2026-09-07T20:31:07Z` with 8,044 records and unchanged source content. The normal daily import also finished successfully at `2026-09-08T01:15:06Z`. The temporary verification entry was removed; only the daily entry remains. The previous crontab is saved remotely as `crontab.before-isde`.

Public verification: `/`, `/docs`, `/openapi.json`, `/health`, lookup, search, categories, and export return 200. The export contains exactly 8,044 items. Unknown codes return 404. The public Playwright test passes; screenshots under `data/screenshots/` now show the live site. The local Docker preview remains at <http://127.0.0.1:8010>.

## Blockers

None for v1. The current session prohibits Git operations, so no commits or pushes occurred. Beads and project documents retain the verified state. The test client still emits upstream deprecation warnings; the checks pass.

## Deadlines

None.

## Beads evaluation

- 2026-09-08: moved to shared-server mode (`bd init --shared-server`, one Dolt server under `~/.beads/shared-server/`), same as square, causa, and ancestors. GitHub sync via `scripts/bd-sync`, tracked `.beads/issues.jsonl` snapshot on every commit. `scripts/install-hooks.sh` is gone: `prek install` owns the hook path now.

Purpose: judge whether beads works well as the task system for agent-driven projects. Record friction, wins, and verdict here.

- 2026-09-07: `bd init` and batch create (`bd create --silent`, `bd dep add`) ran non-interactively without issues. 40 issues, no cycles.
- 2026-09-07: `bd` has no GUI by design. Community web UI `npx -y beads-ui start` works (Issues, Epics, Board tabs, screenshot verified). Other options listed in the beads repo `docs/community-tools.md`; none official.
- 2026-09-07: `bd init` wrote `.claude/settings.json`, `.codex/` hooks, and `.agents/skills/beads/` into the repo unbidden, and appended a section to `AGENTS.md`. Committed as-is for the evaluation.
- 2026-09-07: Dolt backend is embedded; `.beads/issues.jsonl` export is off by default. Cross-machine sync needs a git remote plus `bd dolt push`. Not set up yet.

- 2026-09-07: The dependency graph made task selection and independent file ownership clear. It kept historical features outside v1. Keep Beads for this project.
- 2026-09-07: `pre-commit install` refused the Beads-owned hook path. `scripts/install-hooks.sh` now chains quality checks after the Beads hook. Two runs confirm idempotence; a deliberate undefined-name probe confirms lint failures stop the quality check.
- 2026-09-07: Worker completion messages needed direct review. The first source-discovery implementation selected application forms; a realistic fixture now catches that error. Beads records task state but does not verify implementation quality.
- 2026-09-07: `pre-commit --all-files` covers tracked files only. With new files and no Git operations, explicit `--files` was necessary to check this build.

- 2026-09-07: Beads refused to close epics with deferred children. Those epics remain open; the current-data task completions remain accurate.
