# OVRIQ → produktion · 3 trin (~10 min)

Server: **62.238.6.143** (Hetzner Helsinki, verificeret EU). Backups: til.

## 1. DNS først (Hostinger, 1 min)
Tilføj i DNS for ovriq.xyz:
- **Type A · Name `api` · Target `62.238.6.143`** · TTL 14400

(Rør ikke ved @/www-records — de peger på landing pagen via GitHub Pages.)

## 2. Push deploy-scriptet (1 min)
Dobbeltklik **PUSH.bat** — serveren henter setup-scriptet fra GitHub, så det
skal ligge i repoet først.

## 3. Deploy (5-8 min)
Dobbeltklik **DEPLOY.bat**. Den sender din lokale `.env` sikkert til serveren
(via SSH — aldrig gennem chat/cloud) og kører opsætningen: firewall + fail2ban,
Docker, klon af repoet, PostgreSQL, API og Caddy. Root-passwordet fra
Hetzner-mailen indtastes når der spørges.

Caddy henter automatisk TLS-certifikat, så snart DNS fra trin 1 er slået
igennem (minutter til et par timer).

## Verifikation (når den er oppe)
- `https://api.ovriq.xyz/health` → `{"status":"ok", ...}`
- `https://api.ovriq.xyz/portal` → portalen, live på nettet
- `https://api.ovriq.xyz/dashboard` → live grid
- `https://api.ovriq.xyz/docs` → API-docs

**Gate 1-uret starter ved succesfuldt sundhedstjek: 30 dages stabil drift.**

## Drift-kommandoer (via ssh root@62.238.6.143)
```
cd /opt/ovriq
docker compose logs -f api      # live logs
docker compose ps               # status
git pull && docker compose up -d --build   # deploy ny version
```
