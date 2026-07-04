# OVRIQ Privatlivspolitik — UDKAST (afventer advokat-review, ikke gaeldende)

Version 0.1 · juli 2026

## Dataansvarlig
[VIRKSOMHEDSNAVN, CVR, adresse] · kontakt: [firma-mail]

## Hvilke oplysninger og hvorfor
1. **Node-data**: node-navn, node-id, API-noegle (hash), registreringstid.
   Formaal: drift af markedspladsen. Retsgrundlag: aftale (GDPR art. 6.1.b).
2. **Transaktionsdata**: koeb af credits (beloeb, PayPal ordre-/capture-id,
   evt. landekode fra PayPal), handler, saldi. Formaal: levering, bogfoering,
   svindelforebyggelse. Retsgrundlag: aftale + retlig forpligtelse
   (bogfoeringsloven, 5 aar) + legitim interesse (misbrugsbekaempelse).
3. **Tekniske logs**: IP-adresse og tidspunkter i serverlogs.
   Formaal: sikkerhed og fejlfinding. Retsgrundlag: legitim interesse.
Vi modtager ALDRIG dine PayPal-loginoplysninger eller kortdata — betalingen
sker hos PayPal, og vi modtager kun betalingsbekraeftelsen.

## Saerligt om journalen
Markedspladsens transaktionslog er teknisk uforanderlig (hash-kaedet) af
hensyn til regnskabssikkerhed og svindelforebyggelse. Transaktionsdata kan
derfor ikke slettes enkeltvis, men opbevares i pseudonymiseret form
(node-id, ikke navn/e-mail) og slettes ved journalens samlede udloeb.
[ADVOKAT: formulering ift. GDPR art. 17-undtagelser]

## Databehandlere og modtagere
PayPal (betalinger, egne vilkaar), [hosting-udbyder, EU], GitHub (kode, ikke
persondata). Ingen overfoersel til tredjelande ud over PayPals egne forhold.

## Opbevaring
Bogfoeringspligtigt materiale: 5 aar + loebende regnskabsaar. Node-data:
saa laenge noden er aktiv + 12 maaneder.

## Dine rettigheder
Indsigt, berigtigelse, sletning (med journal-undtagelsen ovenfor),
begraensning, dataportabilitet, indsigelse. Klage: Datatilsynet.
