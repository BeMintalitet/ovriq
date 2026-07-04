# OVRIQ · Sprint: Ingen løse ender ved launch

**Tests: 51/51 grønne · bandit: 0 Medium+ · penge rørt: 0**

Du bad om at få appen skubbet ud med invitationer — eller et system der
fjerner de løse ender. Her er den ærlige opdeling og hvad jeg byggede.

## Grænsen (ærligt)
Jeg kan ikke poste på HN/Reddit/Discord i dit navn — det er dine konti, din
stemme, og fora straffer bot-spam. Ét klodset Show HN kan brænde muligheden
permanent. Så selve opslaget er dit ene klik (teksterne ligger klar i
OUTREACH_KLAR.md). MEN de to løse ender der reelt ville dræbe en launch, har
jeg fjernet:

## 1. Byen ser aldrig død ud (liquidity-maker)
En OVRIQ-drevet maker-node holder nu ALTID stående udbud (2 pr. ressource) og
et par åbne opgaver live, og leverer automatisk når en ægte køber fylder en
ordre. Den KØBER aldrig af sig selv → ingen wash, ingen kunstig afregnet
volumen (svindeldetektionen giver 0 flag). Resultat: en besøgende fra dine
opslag møder et levende marked med reelle varer at handle mod — ikke en spøgelsesby.
Kører som valgfri compose-service med persisteret identitet (genstart ophober
ikke døde noder). Slå fra med `docker compose stop maker`.

## 2. Agenter kan finde OVRIQ selv (discovery-manifest)
`GET /.well-known/agent.json` (+ `/manifest`) udstiller en maskinlæsbar
beskrivelse af hele markedspladsen: base-URL, auth, ressourcer, kategorier,
gebyr, alle endpoints, roadmap. Nu kan agent-directories og andre agenter
auto-opdage og auto-onboarde mod OVRIQ uden et menneske i midten. Det er den
måde M2M-økosystemet faktisk vokser på.

## Shipping (svar på dit spørgsmål)
Nej — du behøver ikke shippe hver gang. Ændringer hober sig op i projektmappen.
Sig GO så mange gange du vil, og kør SHIP.bat én gang til sidst; den deployer
altid den nyeste samlede tilstand. Serveren kører blot den forrige version
indtil da.

## Din ene handling tilbage
Post Show HN (hverdag kl. 14-16, tekst i OUTREACH_KLAR.md) og ping mig — så
bemander jeg svar-vagten. Nu lander de besøgende på et levende, selv-opdageligt
marked. Den løse ende er væk.
