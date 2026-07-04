@echo off
title OVRIQ - opdater server (nyt dashboard + risiko-API)
set SERVER=62.238.6.143
set TOKEN=J5Ue2tI3OlDCsPqD10jAYl8MIpEuIR9E
echo.
echo   Deployer nyeste kode og aktiverer risiko-API'et...
echo.
ssh -o StrictHostKeyChecking=accept-new root@%SERVER% "cd /opt/ovriq && git fetch origin main && git reset --hard origin/main && ( grep -q '^OVRIQ_ADMIN_TOKEN=' .env && sed -i 's|^OVRIQ_ADMIN_TOKEN=.*|OVRIQ_ADMIN_TOKEN=%TOKEN%|' .env || echo 'OVRIQ_ADMIN_TOKEN=%TOKEN%' >> .env ) && docker compose build --no-cache api && docker compose up -d && echo '--- venter 12 sek ---' && sleep 12 && docker compose ps && echo '=== HEALTH ===' && curl -s https://api.ovriq.xyz/health && echo && echo '=== RISK (skal svare 200) ===' && curl -s -o /dev/null -w 'risk: %%{http_code}\n' -H 'X-Admin-Token: %TOKEN%' https://api.ovriq.xyz/admin/risk"
echo.
echo   FAERDIG. Dashboard: https://api.ovriq.xyz/dashboard
echo   Dit admin-token (gem det sikkert, del ALDRIG): %TOKEN%
echo.
pause
