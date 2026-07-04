# OVRIQ FASE 1 — JERNET · Arkitekturblueprint

## Beslutninger (Chefarkitekten)

1. **Penge er Decimal.** Al OQ håndteres som `Decimal` kvantiseret til 4
   decimaler (bankers rounding). Float eksisterer ikke i pengekode. Ledger-
   invarianten er nu EKSAKT (`==`, ingen tolerance).

2. **Event-sourcing er sandhedskilden.** Enhver statsændring (REGISTER,
   ORDER, CANCEL, DELIVER, EXPIRE) skrives som ét event til en append-only,
   hash-kædet journal FØR den bekræftes til kalderen (write-ahead). Genstart
   = afspil journalen → identisk state, bevisbart. Dette generaliserer
   [N0D3-X]-ledgerens hash-kæde til HELE systemet og opfylder samtidig
   regel 4 (uforanderlig log).

3. **Determinisme er et krav.** Alle id'er (noder, ordrer, handler,
   kontrakter) og tidsstempler genereres ved kommando-tid og gemmes i
   eventet; replay genbruger dem. Ingen RNG, ingen ur-opslag i apply-vejen.

4. **To journal-backends, samme interface:**
   - `FileJournal`: JSONL + fsync pr. event. Dev/sandbox og små deployments.
   - `PostgresJournal`: `events`-tabel (asyncpg), samme replay. Prod.
   Skift via `OVRIQ_DATABASE_URL`. Skemaet ligger i `schema.sql`.

5. **Snapshots senere.** Replay er O(events); ved >100k events indføres
   snapshot hver N events. Ikke gate-krav; noteret som fase 1.1.

## Dataflow

```
API-kald → validér → byg event → journal.append (fsync) → apply(state) → svar
Boot     → journal.read_all → apply hvert event → klar
```

## Gate 1-krav og hvordan de opfyldes

| Krav | Løsning | Bevis |
|---|---|---|
| 0 datatab ved genstart | Write-ahead journal | QA crash/replay-test |
| Decimal-penge | ovriq.core.money | Unit-tests, eksakt invariant |
| PostgreSQL | PostgresJournal + schema.sql + compose | CI-integrationstest v. deploy |
| Restore demonstreret | Journal-kopi → ny proces → identisk state | QA-test |
| Load 100x | Samme single-writer-design; jonglering måles | Stress-test i suiten |
| EU-hosting/TLS/CI | Dockerfile, compose, GitHub Actions, Caddy-note | SRE-artefakter |

## Diktat til Backend-Smeden

Byg `ovriq/`-pakken: `core/money.py`, `core/engine.py` (deterministisk
state machine, alle [N0D3-X]-regler bevaret: price-time priority, self-trade-
guard, ejerskabs-checks, eksponerings-check, escrow-tilstandsmaskine, PoW-
registrering, rate limiting), `storage.py` (begge journals + schema),
`api/server.py` (endpoints fra [N0D3-X] + `/health`, OQ-terminologi).
Ingen float i nogen pengevej. Alle apply-funktioner rene og ur-frie.
