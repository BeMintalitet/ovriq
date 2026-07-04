# OVRIQ · Sprint: Svindeldetektion

**Tests: 28/28 grønne · bandit: 0 fund · penge rørt: 0**

## Leveret — Compliance-Vagtens første aktive værn

`engine.risk_report()` scanner den uforanderlige journal for to mønstre, der
spiller omdømme- og volumensystemet:

1. **reciprocal_wash** (høj alvor) — to noder handler frem og tilbage (A→B og
   B→A gentagne gange). Klassisk kunstig volumen mellem egne noder.
2. **counterparty_concentration** (medium) — en sælgers volumen kommer næsten
   udelukkende fra én køber, typisk en køber der pumper sælgerens omdømme.

Kun AFREGNEDE handler tæller (escrow-refunderede er ikke reel volumen).
Detektionen er READ-ONLY og deterministisk (samme journal → samme flag,
verificeret via replay). Ingen node fryses automatisk — flagene eskaleres til
ejeren, præcis som autonomi-niveauerne foreskriver.

## Adgang
`GET /admin/risk` med header `X-Admin-Token` (constant-time-tjek mod
OVRIQ_ADMIN_TOKEN). Uden token-env svarer endpointet 503. `risk_flags`-tælleren
indgår nu i `/metrics`, så driftsvagten kan alarmere ved fund.

## Aktivering i prod (valgfrit)
Tilføj `OVRIQ_ADMIN_TOKEN=<langt tilfældigt>` til serverens .env og kør
REBUILD.bat. Uden den er risiko-API'et bare slået fra — resten kører uændret.
