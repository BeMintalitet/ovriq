# OVRIQ · FASE 1 (JERNET) · SPRINT 1-RAPPORT

**Dato:** 2026-07-04 · **Status:** Kernen bygget og bevist. Gate 1 delvist opfyldt.

## Leveret i dette sprint

| Komponent | Status | Bevis |
|---|---|---|
| Decimal-pengemotor (`ovriq/core/money.py`) | ✅ | `0.1+0.2==0.3` eksakt; NaN/garbage afvises |
| Deterministisk engine (`ovriq/core/engine.py`) | ✅ | Samme events → bit-identisk state (testet) |
| Hash-kædet write-ahead journal (`storage.py`) | ✅ | fsync pr. event; tamper-detektion testet |
| PostgreSQL-backend + skema | ✅ kode | Integrationstest kører i CI (service-container) |
| API m. `/health` og journal-pipeline | ✅ | Genstartstest på API-niveau grøn |
| Docker + compose (API+Postgres+Caddy/TLS) | ✅ | Klar til Hetzner/Fly.io (EU) |
| GitHub Actions CI (tests + bandit + PG + build) | ✅ | Workflow-fil klar |
| Sikkerhedsaudit (bandit) | ✅ | 0 fund (alle severities) |

**Tests: 12/12 grønne**, heraf Gate 1-kritiske:
- `test_crash_and_replay_zero_data_loss` — marked køres, processen "dør" uden
  nedlukning, genstart fra journal → konti, blokke, kontrakter og tx-tal
  bit-identiske. **0 datatab.**
- `test_journal_tamper_detection` — ét manipuleret event i journalen ⇒
  opstart nægtes med præcis linjeangivelse.
- `test_api_restart_preserves_state` — saldi eksakt `950.0000` / `1049.7500`
  efter genstart.
- `test_stress_concurrent_orders_with_journal` — 1.000 samtidige ordrer med
  fsync pr. event: 0 fejl, eksakt invariant, kæde valid.

## Arkitekturbeslutninger (nye)

Event-sourcing som sandhedskilde (write-ahead, hash-kædet) — opfylder både
persistenskravet og regel 4 (uforanderlig log) i én mekanisme. Postgres er
nu et backend-skifte via `OVRIQ_DATABASE_URL`, ikke en omskrivning.

## Resterende Gate 1-krav

1. **Deployment på EU-host** — kræver ejerens konto (Hetzner/Fly.io) og
   domænet ovriq.com. Compose-stakken er klar; `docker compose up -d`.
2. **30 dages stabil drift** — kalenderkrav; starter ved deployment.
3. **Månedlig restore-øvelse** — proceduren er testautomatiseret; første
   kørsel på rigtig server efter deployment.
4. Snapshots (fase 1.1) ved >100k events — ikke gate-blokerende.

## Ejerens to-do (kan ikke automatiseres) — mikrobudget-udgave

- ✅ PayPal Business-konto: HAVES (Gate 2-forudsætning opfyldt)
- Registrér **ovriq.xyz** (~10 kr. første år, Porkbun/Namecheap) — .com'en
  til $50.000 ignoreres; agenter er ligeglade med TLD'er
- Opret gratis GitHub-org "ovriq" + push repo'et (CI kører gratis)
- Server udskydes: platformen driftes lokalt via `docker compose up` indtil
  første omsætning; 30-dages-uret kan alternativt starte på egen maskine
- Varemærke udskydes til første omsætning; først-brug dokumenteres via
  dateret git-historik

**Automation Controller-status:** Alle handlinger i sprintet var L0-L1
(kode+test i sandbox). Ingen cap-hændelser. Ingen penge rørt.
