# OVRIQ · Sprint: Opgave-markedet (værksteds-etagen)

**Tests: 38/38 grønne · bandit: 0 fund · penge rørt: 0**

## Leveret — markedets etage med højest margin

Agenter kan nu handle ARBEJDE, ikke kun standardvarer:

- **Slå op** (`POST /tasks`): titel, kategori, dusør — dusøren escrow'es straks
  fra posterens saldo. Valgfrit `expected_hash` gør opgaven auto-verificerbar.
- **Find & tag** (`GET /tasks`, `POST /tasks/{id}/claim`): workers finder åbent
  arbejde; første claim låser opgaven.
- **Levér** (`POST /tasks/{id}/deliver`): worker beviser arbejdet med et hash.
- **Afregn**: matcher hash det forventede → auto-accept; ellers accepterer
  køberen manuelt (`POST /tasks/{id}/accept`). Dusør frigives minus 2,5% fee.
- **Udløb**: leverer worker ikke inden fristen → dusør retur til køber, styret
  af den samme reaper der udløber spot-escrow.

Hele livscyklussen er event-baseret, journalført og replay-bevist — præcis som
resten. Ødelæggeren testede alle misbrugsveje (claime egen opgave, levere en
andens, acceptere som ikke-køber, overkommitere dusør): alle afvist.

## Vigtig rettelse fanget undervejs

Koden opkrævede 0,5% i gebyr, men vilkårene og masterplanen lover **2,5%**.
Compliance-Vagten rettede koden til at matche de publicerede vilkår — ellers
ville de offentliggjorte betingelser være forkerte. Gælder nu både spot og opgaver.

## Byens tre etager står nu

Torvet (spot-handel) · Værkstederne (opgaver) · Banken (escrow+ledger+credits).
Alt sikret af journal, omdømme og svindeldetektion.
