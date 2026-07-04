# OVRIQ · Sprint: Flow mellem siderne

**Tests: 49/49 grønne · bandit: 0 fund · penge rørt: 0**

## Hvad der manglede (dit input)
Der var ingen vej ud til ovriq.xyz fra app-siderne, og for lidt flow imellem
dem. En besøgende kunne lande på /portal og stå fast.

## Løst — konsistent navigation overalt
En fælles nav-bjælke er nu på ALLE sider:
`ovriq.xyz` (magenta, tydelig vej hjem) · Marked · Portal · API-docs · GitHub.
Den aktuelle side markeres, så man altid ved hvor man er.

Sider med nav: dashboard, portal, køb-retur, køb-annulleret, vilkår, privatliv.
Landing pagen (ovriq.xyz) har fået en top-nav der fører direkte ind i den
levende app: "Live marked", "Kom i gang" (fremhævet), API og GitHub.

Resultatet: en ubrudt sløjfe — landing → portal → marked → docs → tilbage —
uden at nogen kan gå i stå. QA verificerer at hver side har nav + hjem-link.

## Aktivering
Kør `SHIP.bat` (push + deploy i ét). Landing page-navet går live via GitHub
Pages automatisk efter push.
