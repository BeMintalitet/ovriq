# OVRIQ → GitHub · 3 trin

## 1. Push koden (2 min)
Dobbeltklik **PUSH.bat** i denne mappe. Første gang åbner Windows selv
GitHub-login i din browser (Git Credential Manager) — log ind, færdig.
Har du ikke Git installeret, installerer den det selv via winget og beder
dig køre den igen.

## 2. Omdøb repo'et (30 sek, anbefalet)
Repo'et hedder "GitHub-org-ovriq-" — omdøb til **ovriq**:
GitHub → Settings → General → Repository name → `ovriq` → Rename.
Gamle links omdirigeres automatisk, så PUSH.bat virker stadig bagefter.

## 3. Landing page live på ovriq.xyz (5 min, gratis)
1. GitHub → Settings → Pages → "Deploy from a branch" → Branch: `main`,
   mappe: `/docs` → Save. (Landing pagen ligger klar i `docs/` med CNAME.)
2. Hostinger → DNS for ovriq.xyz:
   - CNAME-record: `www` → `bemintalitet.github.io`
   - A-records for rod-domænet (@): `185.199.108.153`, `185.199.109.153`,
     `185.199.110.153`, `185.199.111.153`
3. GitHub → Settings → Pages → Custom domain: `ovriq.xyz` → Save →
   vent på DNS-tjek → slå "Enforce HTTPS" til.

Efter push kører GitHub Actions automatisk hele testsuiten + Postgres-
integrationstest + sikkerhedsscan ved hvert eneste push — det er CI'en
fra `.github/workflows/ci.yml`.

Bemærk: repo'et skal være **Public** for gratis GitHub Pages — og et
offentligt, dateret repo er samtidig din først-brugs-dokumentation af
OVRIQ-navnet.
