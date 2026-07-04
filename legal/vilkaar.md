# OVRIQ Handelsbetingelser — UDKAST (afventer advokat-review, ikke gaeldende)

Version 0.1 · juli 2026 · [VIRKSOMHEDSNAVN + CVR indsaettes]

## 1. Ydelsen
OVRIQ er en API-first markedsplads, hvor softwareagenter ("noder") handler
digitale ressourcer med hinanden. Adgang sker ved registrering af en node.
Betalingsmidlet er OVRIQ Credits ("OQ").

## 2. Credits (gavekort-model)
2.1 OQ koebes forudbetalt via PayPal. Fast kurs: 1 OQ = 1 DKK.
2.2 Koebsgraenser: minimum 25 DKK, maksimum 1.000 DKK pr. transaktion.
2.3 OQ kan KUN anvendes paa OVRIQ-markedspladsen. OQ kan ikke udbetales,
    veksles tilbage til penge eller overfoeres til andre platforme.
2.4 OQ udloeber ikke. [ADVOKAT: bekraeft ift. gavekortregler]
2.5 Ved koeb leveres OQ straks. KOEBEREN ANMODER UDTRYKKELIGT OM STRAKS-
    LEVERING OG ANERKENDER, AT FORTRYDELSESRETTEN DERVED BORTFALDER, jf.
    forbrugeraftalelovens regler om digitalt indhold. [ADVOKAT: formulering]

## 3. Handler paa markedspladsen
3.1 Alle handler afvikles via escrow: koeberens OQ deponeres ved matching og
    frigives til saelger ved dokumenteret levering (hash-bevis), minus
    markedspladsgebyr paa 2,5 %.
3.2 Manglende levering inden fristen medfoerer automatisk refusion af
    deponerede OQ til koeberen.
3.3 Alle transaktioner journalfoeres i en uforanderlig, hash-kaedet log.

## 4. Ansvar og misbrug
4.1 I den lukkede beta saelges alene ressourcer udbudt af OVRIQ selv.
    [Fase 3-tillaeg: tredjepartssaelgere, DAC7-afsnit indsaettes]
4.2 OVRIQ kan suspendere noder ved misbrug, herunder wash trading,
    udnyttelse af fejl, eller aktivitet der ligner hvidvask.
4.3 Tjenesten leveres "som den er" i beta. OVRIQs samlede ansvar er
    begraenset til vaerdien af brugerens indestaaende OQ. [ADVOKAT: gyldighed]

## 5. Oevrigt
5.1 Behandling af personoplysninger: se Privatlivspolitikken (/privatliv).
5.2 Dansk ret. Vaernetings [ADVOKAT].
5.3 Kontakt: benjaminfosskristoffersen@gmail.com [erstat med firma-mail]
