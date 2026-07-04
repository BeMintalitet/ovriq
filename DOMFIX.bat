@echo off
title OVRIQ - domaene-fix paa serveren
set SERVER=62.238.6.143
echo.
echo   Retter OVRIQ_DOMAIN paa serveren til api.ovriq.xyz og genstarter Caddy...
echo.
ssh -o StrictHostKeyChecking=accept-new root@%SERVER% "cd /opt/ovriq && sed -i 's|^OVRIQ_DOMAIN=.*|OVRIQ_DOMAIN=api.ovriq.xyz|' .env && grep -q '^OVRIQ_PUBLIC_URL=' .env && sed -i 's|^OVRIQ_PUBLIC_URL=.*|OVRIQ_PUBLIC_URL=https://api.ovriq.xyz|' .env || echo 'OVRIQ_PUBLIC_URL=https://api.ovriq.xyz' >> .env; docker compose up -d --force-recreate caddy && echo '--- venter 25 sek paa certifikat ---' && sleep 25 && docker compose logs --tail 15 caddy | grep -Ei 'obtain|certificate|got|error' && echo '=== HTTPS-TJEK ===' && curl -s https://api.ovriq.xyz/health && echo ' OK'"
echo.
pause
