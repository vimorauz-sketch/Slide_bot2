#!/usr/bin/env bash
# Daily PostgreSQL backup into ~/slidelab-backups (the last 14 are kept).
# Restore:  gunzip -c FILE.sql.gz | docker compose exec -T db psql -U slidelab -d slidelab
set -euo pipefail
cd "$(dirname "$0")"
OUT="${HOME}/slidelab-backups"
mkdir -p "$OUT"
if [ "$(id -u)" -eq 0 ]; then D="docker"; else D="sudo docker"; fi
$D compose exec -T db pg_dump -U slidelab -d slidelab | gzip > "$OUT/slidelab-$(date +%Y%m%d-%H%M).sql.gz"
ls -1t "$OUT"/slidelab-*.sql.gz | tail -n +15 | xargs -r rm -f
