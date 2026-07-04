#!/usr/bin/env bash
# OVRIQ server-setup · køres som root på Ubuntu 24.04 · idempotent
set -euo pipefail
REPO="https://github.com/BeMintalitet/ovriq.git"
REPO_FALLBACK="https://github.com/BeMintalitet/GitHub-org-ovriq-.git"
DIR=/opt/ovriq

echo "═══ [1/6] Systemhærdning ═══"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ufw fail2ban git curl >/dev/null
ufw allow 22/tcp >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null
systemctl enable --now fail2ban >/dev/null 2>&1 || true

echo "═══ [2/6] Docker ═══"
command -v docker >/dev/null || curl -fsSL https://get.docker.com | sh >/dev/null 2>&1
systemctl enable --now docker >/dev/null

echo "═══ [3/6] Kode ═══"
if [ -d "$DIR/.git" ]; then git -C "$DIR" pull -q
else git clone -q "$REPO" "$DIR" || git clone -q "$REPO_FALLBACK" "$DIR"; fi

echo "═══ [4/6] Miljø ═══"
[ -f /root/ovriq.env ] && mv /root/ovriq.env "$DIR/.env"
touch "$DIR/.env"; sed -i 's/\r$//' "$DIR/.env"
grep -q '^POSTGRES_PASSWORD=' "$DIR/.env" || \
  echo "POSTGRES_PASSWORD=$(head -c 24 /dev/urandom | base64 | tr -dc 'a-zA-Z0-9' | head -c 32)" >> "$DIR/.env"
grep -q '^OVRIQ_DOMAIN=' "$DIR/.env" || echo "OVRIQ_DOMAIN=api.ovriq.xyz" >> "$DIR/.env"
grep -q '^OVRIQ_PUBLIC_URL=' "$DIR/.env" || echo "OVRIQ_PUBLIC_URL=https://api.ovriq.xyz" >> "$DIR/.env"
chmod 600 "$DIR/.env"

echo "═══ [5/6] Stak op ═══"
cd "$DIR" && docker compose up -d --build --quiet-pull 2>&1 | tail -3

echo "═══ [6/6] Sundhedstjek ═══"
sleep 8
docker compose ps --format '{{.Name}} {{.Status}}'
curl -fs http://127.0.0.1:8642/health 2>/dev/null \
  || docker compose exec -T api python -c "import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8642/health').read().decode())" \
  || echo "API'et varmer stadig op — tjek om lidt: docker compose logs api"
echo ""
echo "✔ OVRIQ kører. Når DNS (api.ovriq.xyz → denne server) er slået igennem,"
echo "  henter Caddy selv TLS-certifikat, og https://api.ovriq.xyz/portal er live."
