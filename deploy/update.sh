#!/usr/bin/env bash
# Update to the latest code from GitHub and restart (data and settings are kept).
set -euo pipefail
cd "$(dirname "$0")"
if [ "$(id -u)" -eq 0 ]; then D="docker"; else D="sudo docker"; fi
./backup.sh || echo "zaxira nusxa olinmadi — davom etamiz"
git -C .. pull --ff-only
$D compose up -d --build
$D image prune -f >/dev/null
echo "Yangilandi. Loglar: $D compose logs -f bot"
