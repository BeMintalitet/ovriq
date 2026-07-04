@echo off
title OVRIQ - certifikat-fix
set SERVER=62.238.6.143
echo.
echo   Genstarter Caddy saa den henter certifikat forfra (DNS er klar nu)...
echo.
ssh -o StrictHostKeyChecking=accept-new root@%SERVER% "cd /opt/ovriq && ufw allow 443/udp >/dev/null 2>&1; docker compose restart caddy && echo '--- venter 25 sek paa ACME ---' && sleep 25 && docker compose logs --tail 30 caddy | grep -Ei 'certificate|obtain|error|rate' && echo '=== LOKALT HTTPS-TJEK ===' && curl -s https://api.ovriq.xyz/health && echo OK"
echo.
pause
