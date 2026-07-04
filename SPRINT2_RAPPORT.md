# OVRIQ · FASE 1 · SPRINT 2-RAPPORT

**Dato:** 2026-07-04 · **Tests: 12/12 grønne** (+ Postgres-test aktiv i CI)

## Leveret

| Komponent | Bevis |
|---|---|
| Global omdøbning VORNIQ→OVRIQ (pakke, valuta OQ, env, Docker, CI, docs) | 0 gamle referencer i kode; fuld suite grøn |
| Sælger-SDK (`ovriq/sdk/`) | `OvriqClient`: register/sell/buy/deliver/balance |
| Eksempel-bot (`examples/seller_bot.py`, <50 linjer) | E2E: 13 leverancer, +365,48 OQ |
| Web-dashboard (`/` og `/dashboard`) | Serverer live grid, 4,7 KB |
| Landing page (`site/index.html`) til ovriq.xyz | Statisk, GitHub Pages-klar |
| Ny masterplan (`OVRIQ_MASTERPLAN.txt`) + skill (`ovriq-master-agent.skill`) | Pakket og valideret |

## E2E-smoke (rigtig server + SDK-bots)

Sælger: 13 leverancer, saldo 1000 → 1365,4834 OQ. Køber: 1000 → 632,68 OQ.
Treasury: 1,8366 OQ (præcis 0,5%). Journal-seq 68, invariant OK, kæde valid.
Regnestykket balancerer eksakt: 1365,4834 = 1000 + 367,32 − 1,8366.

## Ejerens 5-minutters to-do

1. Installér den nye skill (`ovriq-master-agent.skill`) og slet den gamle
   vorniq-skill i Settings → Capabilities.
2. Opret gratis GitHub-org **ovriq** + repo, push `ovriq/`-mappen (CI kører selv).
3. Peg ovriq.xyz på GitHub Pages (gratis) med `site/index.html` — landing
   page live for 0 kr. (Hostinger DNS: CNAME → <org>.github.io).

Gamle `vorniq/`- og `VORNIQ_MASTERPLAN.txt`-filer kan slettes eller beholdes
som historik — alt aktivt arbejde foregår nu i `ovriq/`.

## Automation Controller-status

Alle handlinger L0-L1 (kode+test i sandbox). Ingen penge rørt. Ingen caps ramt.
**Næste:** GitHub-repo op → CI grøn → derefter Gate 2-forberedelse
(PayPal Checkout-integration i sandbox-mode — stadig ingen rigtige penge).
