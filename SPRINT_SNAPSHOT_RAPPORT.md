# OVRIQ · Sprint: Snapshots + Opgaver på dashboard + API-polish

**Tests: 42/42 grønne · bandit: 0 fund · penge rørt: 0**

## 1. Journal-snapshots — byen booter lynhurtigt for altid

Problemet: efterhånden som journalen vokser til millioner af events, ville en
genstart tage længere og længere at afspille. Løst:

- `engine.export_state()` / `load_state()` — fuld, JSON-sikker serialisering af
  hele markedets tilstand. Heaps (order books) gemmes ikke, men genopbygges
  eksakt fra ordrerne ved load.
- Snapshot skrives atomisk (temp-fil + rename), så en halv skrivning aldrig kan
  efterlade en korrupt fil.
- Ved boot: hop direkte til snapshot-state, afspil KUN de events der kom efter.
- Serveren tager selv et snapshot hvert 2. minut og ét ved ren nedlukning.

Bevist: snapshot-round-trip giver bit-identisk state (konti, omdømme, stats,
blok-hashes), og boot-fra-snapshot + hale == fuld replay. Genstart forbliver
under et øjeblik uanset hvor stor journalen bliver.

## 2. Opgave-markedet er nu synligt på dashboardet

Besøgende ser nu, at der er ARBEJDE at tjene på: en "Aabne opgaver"-tabel med
titel, kategori og dusør, plus to nye nøglekort — antal åbne opgaver og samlet
dusør "i spil". Et tomt torv ser dødt ud; et torv med dusører i spil trækker
workers til.

## 3. API-polering

`/docs` har nu en professionel titel, beskrivelse af hele flowet og
auth-instruktioner — så en udvikler der lander fra awesome-x402-PR'en straks
forstår hvad OVRIQ er og kan onboarde sig selv.

## Aktivering
Kør `UPDATE_SERVER.bat` (deployer alt via git reset + rebuild). Snapshots
starter automatisk; intet ekstra setup.
