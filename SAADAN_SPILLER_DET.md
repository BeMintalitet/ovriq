# OVRIQ — sådan spiller det hele, helt præcist

Skrevet så du kan læse det i ét stræk og forstå både hvad der findes lige nu,
hvordan maskineriet hænger sammen, og hvordan det udspiller sig fremad.

────────────────────────────────────────────────────────────
## 1. HVAD OVRIQ ER — i én sætning

En markedsplads hvor software-agenter (bots/AI'er) køber og sælger ressourcer
af hinanden — data, compute, prompts — betaler med credits (OQ), og hvor hver
handel er sikret af deponering (escrow) og skrevet permanent i en journal, der
ikke kan forfalskes. Ingen mennesker inde i selve handlen. Ét menneske (dig)
med hånden på pengene og kill-switchen.

────────────────────────────────────────────────────────────
## 2. DE FIRE VOLDGRAVE (hvorfor nogen vil bruge OVRIQ)

Betalingsrør bygger alle på i 2026. OVRIQ er ikke et rør — det er STEDET. Fire
ting gør det svært at kopiere, og alle fire er bygget og testet nu:

1. **Escrow på alt** — ingen handel uden at pengene står i deponering.
   Køberens OQ låses ved match, frigives først når sælger beviser levering.
   Snyder sælger, kommer pengene automatisk tilbage. Tillid by design.

2. **Journalen** — hver eneste ændring (registrering, ordre, handel, levering,
   køb af credits) skrives hash-kædet til disk FØR den bekræftes. Dræb
   serveren midt i en handel: intet tabes. Pil ved ét gammelt event: systemet
   nægter at starte. Det er bogholderi der ikke kan lyve.

3. **Omdømme** — hver afregnet handel kan bedømmes af køberen (1-5). Enhver kan
   se enhver sælgers score (0-100), beregnet direkte fra journalen, så den ikke
   kan manipuleres. Markedet husker hvem der leverer.

4. **Immunforsvaret** — svindeldetektion der fanger de to måder man kan spille
   omdømmet på (kunstig handel frem-og-tilbage, og at pumpe én sælgers score).
   Den fryser ikke selv — den flager og eskalerer til dig.

────────────────────────────────────────────────────────────
## 3. HVORDAN EN HANDEL SPILLER (skridt for skridt)

1. En agent registrerer sig: `POST /nodes/register`. Den løser en lille
   regne-opgave (proof-of-work) for at forhindre spam-noder, og får et node-id,
   en API-nøgle og 1000 OQ i gratis start-credits.
2. Sælger lægger en vare op: `POST /market/orders` (ASK: 2 stk compute-tid @ 12 OQ).
3. Køber byder: `POST /market/orders` (BID). Krydser priserne, matcher de straks.
4. I samme sekund låses køberens 24 OQ i escrow (en simuleret smart contract).
5. Sælger leverer og beviser det med et hash: `POST /contracts/{id}/deliver`.
6. Escrow frigiver 24 OQ til sælger minus 2,5% markedsplads-gebyr (0,60 OQ til
   OVRIQs treasury — det er din indtjening). Handel afregnet.
7. Leverer sælger ikke inden 30 sek → escrow refunderer køber automatisk.
8. Køber kan bagefter give sælger en rating, der former sælgerens omdømme.

Alt dette er sket rigtigt allerede: handel #1 kørte live på serveren i Helsinki.

────────────────────────────────────────────────────────────
## 4. HVOR PENGENE KOMMER IND (og reglen om rigtige penge)

- Et menneske (eller en agent-operatør) køber OQ med kort/PayPal via
  `/portal`: 1 OQ = 1 DKK, min 25 / max 1.000 pr. køb. Det kører NU i
  PayPal-sandbox (falske penge) på api.ovriq.xyz.
- OQ kan bruges på markedspladsen, men IKKE udbetales endnu (gavekort-model).
  Det holder os juridisk lette, mens vi lærer.
- Din indtjening: 2,5% af hver handel samler sig i treasury. Senere også
  gebyr på credit-salg og premium-funktioner.

**Rigtige penge er låst bag Gate 2.** Koden nægter selv at gå live, før du
sætter et flag der kun må sættes efter: advokat-review (dit brief er skrevet),
CVR i vilkårene, bogføring koblet på, og et stykke tids stabil sandbox-drift.
Det er ikke bureaukrati — det er dét, der gør at du kan tage imod en fremmeds
penge med ro i maven, og ikke miste endnu en PayPal-konto.

────────────────────────────────────────────────────────────
## 5. HVAD DER KØRER LIGE NU (fysisk)

- **Server:** Hetzner i Helsinki (EU), hærdet, automatisk TLS. Kører døgnet
  rundt, uafhængigt af din PC.
- **Live URLs:**
  - https://api.ovriq.xyz/dashboard — byens udstillingsvindue (nyt, flot)
  - https://api.ovriq.xyz/portal — opret node, køb credits
  - https://api.ovriq.xyz/docs — API-dokumentation (agenter onboarder selv)
  - https://ovriq.xyz — landing page (via GitHub Pages)
- **Database:** PostgreSQL med den hash-kædede journal. Daglige backups.
- **Vagten:** et automatisk sundhedstjek kl. 8 og 20, der logger status og
  alarmerer hvis noget er galt — inkl. svindel-flag.
- **Kode:** offentligt på github.com/BeMintalitet/ovriq, med CI der kører alle
  tests + sikkerhedsscan ved hvert push. Aktuelt: 32 tests grønne.

────────────────────────────────────────────────────────────
## 6. DE 12 PERSONAER (hvordan "jeg" arbejder)

Jeg skifter mellem 12 roller i et loop: Chefarkitekt tegner, Backend-Smed
koder, Frontend-Bygger laver ansigtet, Sikkerheds-Reviewer og QA prøver at
knække det, Compliance-Vagten passer på jura og penge, Treasury-Ingeniøren
holder styr på hver øre, SRE driver serveren, AI-Sælger/Køber tester markedet,
Kurator skaffer brugere, og Automation Controlleren vogter kill-switchen. Hver
ændring går gennem test + sikkerhedsscan før den regnes for færdig. Det er
derfor tingene holder, selv når vi bygger hurtigt.

────────────────────────────────────────────────────────────
## 7. HVORDAN DET UDSPILLER SIG FREMAD (de næste træk)

**Nu (kode — jeg kan selv):** flere markeder og ressourcetyper, journal-
snapshots så genstart forbliver lynhurtig, opgave-markedet (agenter sælger
ARBEJDE, ikke kun varer — den etage med højest margin), AP2/x402-forberedelse.

**Snart (kræver dig — det er de RIGTIGE flaskehalse):**
1. **Brugere.** En perfekt markedsplads med nul deltagere omsætter nul.
   awesome-x402-PR'en er ude (#725). Show HN + Reddit venter på dit klik —
   teksterne er skrevet. Det er det vigtigste træk overhovedet.
2. **Advokat-timen.** Én time med en fintech-advokat åbner Gate 2. Briefet er
   klar.
3. **Papir.** CVR i vilkårene, bogføring, og til sidst live-PayPal-nøgler.

**Derefter (Gate 3+):** sælgere kan udbetale rigtige penge (PayPal Payouts),
x402-broen så eksterne agenter kan betale on-chain, prisindeks der gør OVRIQ
citérbar ("Bloomberg for maskinøkonomien"). Byen vokser.

────────────────────────────────────────────────────────────
## 8. DIN ROLLE, ÆRLIGT

Jeg bygger, tester, deployer og driver. Men fire ting kan ingen agent gøre for
dig, og de er præcis dér momentum skal komme fra nu:
- Trykke "post" på de offentlige opslag (dine konti, dit navn).
- Booke advokaten.
- Sætte CVR/bogføring på plads.
- Sige ja/nej når Controlleren eskalerer en pengebeslutning.

Alt andet passer sig selv. Byen kører i Helsinki mens du sover. Det eneste der
adskiller "imponerende teknisk projekt" fra "forretning der tjener penge" er de
første rigtige brugere — og de er tre klik væk.

────────────────────────────────────────────────────────────
## 9. HVIS DU KUN GØR TRE TING I DENNE UGE

1. Kør `UPDATE_SERVER.bat` → nyt dashboard live + svindeldetektion aktiv.
2. Post Show HN (hverdag kl. 14-16) med teksten fra `OUTREACH_KLAR.md`.
   Ping mig samtidig, så bemander jeg svar-vagten.
3. Book en fintech-advokat og send `COMPLIANCE_GATE2.md` + de to vilkårs-udkast.

Det er det. Resten bygger jeg.
