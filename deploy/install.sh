#!/usr/bin/env bash
# SlideLab — one-time server setup (Ubuntu 22.04 / 24.04, e.g. Oracle Cloud Always Free Ampere A1).
# Run from the project folder:   bash deploy/install.sh
set -euo pipefail

cd "$(dirname "$0")"
DEPLOY_DIR="$(pwd)"
say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

if [ "$(id -u)" -eq 0 ]; then SUDO=""; else SUDO="sudo"; fi

say "1/6 Docker o'rnatilmoqda"
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | $SUDO sh
  $SUDO usermod -aG docker "${USER:-ubuntu}" || true
fi
DOCKER="$SUDO docker"

say "2/6 Swap (zaxira xotira) 2 GB"
if ! swapon --show | grep -q '/swapfile'; then
  $SUDO fallocate -l 2G /swapfile && $SUDO chmod 600 /swapfile
  $SUDO mkswap /swapfile >/dev/null && $SUDO swapon /swapfile
  echo '/swapfile none swap sw 0 0' | $SUDO tee -a /etc/fstab >/dev/null
fi

say "3/6 80 va 443 portlarini ochish (Oracle Ubuntu tasvirlari ularni yopiq saqlaydi)"
if command -v iptables >/dev/null 2>&1; then
  for p in 80 443; do
    $SUDO iptables -C INPUT -p tcp --dport "$p" -j ACCEPT 2>/dev/null || \
      $SUDO iptables -I INPUT 6 -m state --state NEW -p tcp --dport "$p" -j ACCEPT
  done
  if command -v netfilter-persistent >/dev/null 2>&1; then $SUDO netfilter-persistent save >/dev/null; fi
fi

say "4/6 Sozlamalar (deploy/.env)"
if [ ! -f .env ]; then
  read -rp "Telegram BOT_TOKEN: " BOT_TOKEN
  read -rp "OPENAI_API_KEY (sk-...): " OPENAI_API_KEY
  read -rp "ADMIN_IDS (Telegram ID, vergul bilan): " ADMIN_IDS
  read -rp "Domen (masalan: slidelab.duckdns.org): " DOMAIN
  read -rp "Admin panel paroli (bo'sh qoldirsa faqat /admin havolasi ishlaydi): " ADMIN_PASSWORD
  umask 077
  cat > .env <<EOF
BOT_TOKEN=${BOT_TOKEN}
OPENAI_API_KEY=${OPENAI_API_KEY}
ADMIN_IDS=${ADMIN_IDS}
DOMAIN=${DOMAIN}
ADMIN_LOGIN=admin
ADMIN_PASSWORD=${ADMIN_PASSWORD}
ADMIN_SECRET=$(openssl rand -hex 32)
POSTGRES_PASSWORD=$(openssl rand -hex 24)
# TezCheck (to'lov): kabinetdan oling, keyin "bash deploy/update.sh" bilan qayta ishga tushiring
TEZCHECK_API_KEY=
TEZCHECK_CASH_DESK_CODE=
TEZCHECK_WEBHOOK_SECRET=
# Foto manbalar (ixtiyoriy)
PIXABAY_API_KEY=
PEXELS_API_KEY=
EOF
  echo "deploy/.env yaratildi (faqat siz o'qiy olasiz). Keyin ham tahrirlashingiz mumkin: nano deploy/.env"
else
  echo "deploy/.env allaqachon bor — o'zgartirilmadi."
fi

say "5/6 Bot ishga tushirilmoqda (birinchi marta 5-10 daqiqa)"
$DOCKER compose up -d --build

say "6/6 Har kuni soat 03:30 da baza zaxira nusxasi"
chmod +x "$DEPLOY_DIR/backup.sh" "$DEPLOY_DIR/update.sh"
( crontab -l 2>/dev/null | grep -v 'slidelab-backup' ; echo "30 3 * * * $DEPLOY_DIR/backup.sh >/dev/null 2>&1 # slidelab-backup" ) | crontab -

DOMAIN_NOW="$(grep '^DOMAIN=' .env | cut -d= -f2)"
say "Tayyor!"
echo "  Loglar:        cd $DEPLOY_DIR && $DOCKER compose logs -f bot"
echo "  Admin panel:   https://${DOMAIN_NOW}/admin   (yoki botda /admin)"
echo "  Tekshirish:    https://${DOMAIN_NOW}/diag"
echo "  TezCheck webhook manzili: https://${DOMAIN_NOW}/payments/tezcheck/webhook"
