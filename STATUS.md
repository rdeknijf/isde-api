# STATUS

Attention: maintain

## Goal

Serve the current RVO ISDE meldcodelijsten as a free public JSON API at <https://isde.deknijf.com>. V1 (current data only) is complete. History, date queries, change feeds, and billing are deferred extensions in Beads.

## Last update

2026-11-09: Moved to the erebor cluster; the buckland stack is stopped. See Deployment.

2026-11-03: Source history check (bead isde-ami.3). The 2025-02 and 2025-06 lists return 404 at RVO, and the Wayback searches found no copy of those eight URLs; the 47 older workbooks that were still reachable are now in the buckland raw archive. This change is documentation and archive data only; the service was not redeployed.

2026-11-01: Dependency refresh (PR #4: Python 3.15, uv 0.13.6, FastAPI 0.162, ruff 0.17.3, ty 0.0.95), merged as `7ca9fba` and deployed to buckland at 07:58 UTC. 32 offline tests pass with 88.7% coverage. After the deploy, `/health`, `/v1/products`, and `/v1/categories` answer with the October data.

## Verified state (2026-11-01)

- Public `/health` reports 6,916 records from the October 2026 release (`published_month` 2026-10). The daily import ran at 2026-11-01T02:15:05Z with unchanged source content.
- Counts per category: heat_pumps 2,816, glass 1,876, insulation 1,723, solar_boilers 295, ventilation 206. A direct row count of each raw October workbook gives the same numbers, so the parser loses no rows.
- The count fell from 8,120 (September) to 6,916 (October) at the 2026-10-09 import. RVO shortened the lists; the `Meldcodes` headers are identical in the August, September, and October workbooks.
- A local import against the live RVO page finds the same five October workbooks with the same SHA-256 hashes as production. RVO has not yet published a November release.
- From 2026-09-11 to 2026-09-23 every daily import failed with "RVO page does not contain all five workbook links: heat_pumps, insulation, glass, solar_boilers, ventilation", so the page had no usable link for any category. The previous data stayed online, and the import recovered by itself on 2026-09-24 with the September release. No alert exists for failed imports (bead `isde-iha`); only `~/logs/isde-ingest.log` on buckland shows them.
- 2026-11-03: Old workbook URLs can become unavailable at RVO. The 2025-02 and 2025-06 lists return 404 and the Wayback searches found no copy; every workbook URL found from 2025-09 to 2026-10 still answers. Details are in `AGENTS.md` under "Older monthly releases".
- 2026-11-03: The raw archive on buckland now holds 62 workbooks from 2025-05 to 2026-10 (47 recovered from RVO and Wayback, 15 from the daily import). Each file matches the SHA-256 in its `metadata.json` record; recovered files from Wayback carry a `retrieved_via` field. The pre-change metadata is in `~/backups/isde-raw-metadata-2026-11-03.tar.gz` on buckland. An import after the change validated 6,916 records, and `/health` still reports 6,916 products.
- 2026-11-03: With Rutger's approval, the 40 older workbook URLs that RVO still serves and Wayback did not hold (2025-09 to 2026-07, except 2026-05) went to `web.archive.org/save`. Wayback CDX now lists a capture of 2026-11-03 for all 40, so a public third-party copy exists for every workbook found from 2025-09 to 2026-07.
- The raw archive is in the daily buckland restic backup (`~/services/backup/backup.sh`, run by `hass-backup.timer` at 02:00, replicated to `/mnt/staddle`); the 2026-11-03 02:00 snapshot contains `data/raw`, but it predates the 47 recovered files; the next daily run (2026-11-04 02:00) is the first that can include them, and no snapshot with them is verified yet. A second copy is on anduril in `~/.local/share/isde-api/raw-archive/` (manual `rsync` on 2026-11-03, all hashes verified, not scheduled).

## Deployment

The service runs on the erebor cluster since 2026-11-09 (namespace `isde-api`, 1 GiB volume, manifests in `deploy/erebor/`), behind ingress-nginx and Cloudflare (proxied CNAME `isde.deknijf.com` to `erebor.deknijf.com`). Flux reconciles `deploy/erebor` from `main`. Release: set the new image SHA in `deploy/erebor/deployment.yaml` and `deploy/erebor/cronjob.yaml` and merge to `main`.

The CronJob `isde-ingest` runs daily at 03:15 Europe/Amsterdam. Its first run is due on 2026-11-10 and was not observed when this was written. No backup job exists for the volume on erebor yet (bead sq-wnlp in rdeknijf/square).

The old Compose stack in `/home/rdeknijf/services/isde-api` on buckland is stopped, its cron line is commented out, and it is out of `~/services/update.sh`. Its files stay.

## Decisions

- 2026-09-07: Rutger approved the public release of current-data v1 at `isde.deknijf.com`.
- 2026-10-11: The beads database moved to the Dolt server `beads.deknijf.com:3306` (database `isde`).

## Blockers

None.

## Deadlines

None.

## Resume path

Read `AGENTS.md`, then run `bd ready` and `bd list --status=open`. Check freshness with `curl https://isde.deknijf.com/health` and `kubectl --context erebor -n isde-api get jobs`.

## Beads evaluation

Purpose: judge whether beads works well as the task system for agent-driven projects. Verdict (2026-09-07): keep Beads for this project.

- 2026-09-07: `bd init` and batch create (`bd create --silent`, `bd dep add`) ran non-interactively. 40 issues, no cycles. The dependency graph made task selection and file ownership clear and kept historical features outside v1.
- 2026-09-07: `bd` has no GUI by design. The community web UI `npx -y beads-ui start` works (Issues, Epics, Board tabs).
- 2026-09-07: `bd init` wrote `.claude/settings.json`, `.codex/` hooks, and `.agents/skills/beads/` into the repo unbidden, and appended a section to `AGENTS.md`.
- 2026-09-07: Worker completion messages needed direct review. The first source-discovery implementation selected application forms; a realistic fixture now catches that error. Beads records task state but does not verify implementation quality.
- 2026-09-07: Beads refuses to close epics with deferred children, so the five v1 epics stay open.
- 2026-09-08: `prek install` owns the hook path; the beads snapshot export runs as a prek hook (`scripts/bd-export-hook.sh`).
