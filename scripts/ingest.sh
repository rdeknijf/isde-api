#!/bin/sh
set -eu

# Install as a daily cron job, for example:
# 15 3 * * * ~/services/isde-api/scripts/ingest.sh >> ~/logs/isde-ingest.log 2>&1
exec 9>/tmp/isde-ingest.lock
flock -n 9 || exit 0
date -u '+%Y-%m-%dT%H:%M:%SZ import started'
docker exec isde-api .venv/bin/isde-ingest --raw-dir /data/raw
date -u '+%Y-%m-%dT%H:%M:%SZ import finished'
