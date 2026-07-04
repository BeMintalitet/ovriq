# Compliance-brief · Gate 2 (PENGE IND) · til advokat-review

Udarbejdet af Compliance-Vagten. Formål: én times fintech-advokat-gennemgang
før første rigtige krone. Spørgsmålene nederst er dem, advokaten SKAL svare på.

## Modellen

- OVRIQ sælger **prepaid credits (OQ)**: 1 OQ = 1 DKK, købes via PayPal
  Checkout (min 25 / max 1.000 DKK pr. køb, håndhævet i kode).
- **Gavekort-model:** OQ kan KUN bruges på OVRIQs egen markedsplads og kan
  IKKE udbetales, overdrages til andre platforme eller veksles tilbage.
  Ingen penge-ud-funktionalitet eksisterer i koden i denne fase.
- Al kreditering sker på verificerede PayPal-fakta (capture-beløb fra
  PayPals API-svar), idempotent, og journalføres uforanderligt (hash-kædet
  event-journal). Fuldt revisionsspor fra krone til credit.

## Vurderinger der ønskes bekræftet

1. **Betalingsformidling:** Da OQ kun kan bruges hos udstederen selv
   (single-platform, ingen udbetaling), er vurderingen at modellen falder
   uden for PSD2/betalingsinstitut-krav ("limited network"/gavekort-
   undtagelsen). Bekræft, og angiv grænserne (beløbslofter/indberetning?).
2. **Moms:** OQ vurderes som **enkeltformålsvoucher** (varen/ydelsen og
   momssatsen kendt ved salg) → moms afregnes ved SALG af credits, ikke ved
   forbrug. Bekræft sats og fakturakrav (kunderne kan være virksomheder og
   udlændinge — OSS-ordning relevant?).
3. **AML:** Ingen udbetaling ⇒ lav hvidvaskrisiko, men wash-trade-mønstre
   mellem noder overvåges (Controller). Er der registrerings-/underretnings-
   pligter alligevel ved denne størrelse?
4. **Vilkår:** Udkast til handelsbetingelser følger (credits udløber ikke?
   fortrydelsesret ved køb af credits? B2B-only-klausul som forenkling?).
5. **DAC7:** Platformen formidler salg mellem tredjeparter fra fase 3 —
   bekræft at DAC7-indberetningspligt først indtræder dér, ikke i fase 2.

## Tekniske kontroller (implementeret og testet)

Idempotent kreditering (dobbelt-capture/webhook-retry kan ikke dobbelt-
minte) · webhook-signaturverifikation · server-side beløbsvalidering ·
valutalås (DKK) · live-mode teknisk blokeret bag eksplicit flag + gate ·
købs-caps 25-1.000 DKK · fuld journal med hash-kæde.

## Gate 2-tjekliste

- [ ] Advokat har bekræftet pkt. 1-5 (én times møde; dette brief sendes forud)
- [ ] CVR på plads og PayPal Business verificeret på CVR
- [ ] Handelsbetingelser + privatlivspolitik publiceret på ovriq.xyz
- [ ] Bogføring koblet til (PayPal-rapporter → Dinero/Billy)
- [ ] Sandbox-testflow gennemført af ejer (se PAYPAL_SETUP.md)
- [ ] Første 25.000 kr. i beta-salg — FØRST HEREFTER må
      OVRIQ_ALLOW_LIVE_PAYMENTS=yes sættes
