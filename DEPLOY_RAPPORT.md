# OVRIQ · DEPLOY-RAPPORT · Fase 1 milepæl

**Dato:** 2026-07-04 · **Status: LIVE PÅ https://api.ovriq.xyz** 🟢

## Produktionsmiljøet

| Komponent | Status |
|---|---|
| Server | Hetzner CX23, Helsinki (EU), hærdet: UFW (22/80/443), fail2ban |
| TLS | Let's Encrypt, auto-fornyelse via Caddy |
| Database | PostgreSQL 16, hash-kædet event-journal (async-boot verificeret i prod) |
| API + portal + dashboard + docs | Alle HTTP 200 |
| Backups | Hetzner daglige snapshots + journalens egen uforanderlighed |

## Handel #1 (bevis, over det åbne internet)

Sælger `oq_9c974a…` listede 5× datapakke @ 10 OQ → køber `oq_5a577f…` matchede
→ escrow → levering med hash-bevis → **kontrakt #1 SETTLED**.
Saldi eksakt: 1049.7500 / 950.0000 OQ · treasury 0.2500 OQ (præcis 0,5 %) ·
journal-seq 5 · invariant OK · kæde valid · latency 3,21 ms.

## Fejl fundet og rettet under deploy (loopets værdi)

1. Batch-parser-crash i DEPLOY.bat (parentes i echo-blok) → omskrevet med goto.
2. `httpx` manglede i prod-requirements (lå kun i dev) → tilføjet.
3. PUSH.bat genskabte git-historik ved hvert push → nu inkrementel; server
   nulstilles med `git reset --hard origin/main` via REBUILD.bat.

## Udestående

- **Betalinger på prod er "disabled"**: serverens .env mangler PayPal-sandbox-creds.
  Kør DEPLOY.bat én gang (den scp'er din lokale .env) → derefter virker
  /portal-køb i sandbox-mode på det rigtige domæne, inkl. korrekt return-URL.
- **GATE 1-URET ER STARTET**: 30 dages stabil drift fra i dag. Månedlig
  restore-øvelse planlægges efter uge 1.

## Byen er åben

Enhver agent i verden kan nu: `POST https://api.ovriq.xyz/nodes/register`
