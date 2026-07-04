# OVRIQ · SPRINT 4-RAPPORT (portal + jura)

**Dato:** 2026-07-04 · **Tests: 19/19 grønne** · bandit: 0 fund · penge rørt: 0

## Leveret

| Komponent | Detaljer |
|---|---|
| **/portal** | Selvbetjening i browseren: opret node (proof-of-work løses i JS/WebCrypto), API-nøgle vises én gang og gemmes kun i brugerens egen browser, saldo vises live, køb credits med ét klik |
| **/credits/return** | PayPal-redirect lander nu på en rigtig side der auto-capturer og viser "+X OQ" — redirect-fejlen fra sandbox-testen er lukket |
| **/credits/cancel** | Pæn annulleringsside |
| **/vilkaar + /privatliv** | Serveres direkte fra `legal/*.md` — advokaten redigerer markdown, siden opdaterer sig selv |
| **legal/vilkaar.md** | UDKAST: gavekort-model, straks-levering/fortrydelsesret, escrow-vilkår, ansvarsbegrænsning — [ADVOKAT]-markeringer hvor der kræves svar |
| **legal/privatliv.md** | UDKAST: GDPR-grundlag pr. datatype, journal-uforanderlighed vs. sletteret (art. 17-undtagelse markeret til advokat) |

## Beta-flowet er nu komplet (sandbox)

Menneske: åbn /portal → opret node → køb 100 DKK via PayPal → auto-capture → saldo 1100 OQ.
Maskine: SDK → register → sell/buy → deliver → settled.
Samme ledger, samme journal, samme regler.

## Udestående på Gate 2 (uændret — virkelighedspunkter)

Advokat-review (brief + begge udkast er klar at sende) · CVR ind i vilkårene ·
bogføringskobling · 25.000 kr. beta-salg. Teknikken er færdig.
