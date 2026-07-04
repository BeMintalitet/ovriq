@echo off
title OVRIQ - tvungen genbygning paa serveren
set SERVER=62.238.6.143
echo.
echo   Nulstiller serverens kode til GitHub-versionen og genbygger uden cache...
echo.
ssh -o StrictHostKeyChecking=accept-new root@%SERVER% "cd /opt/ovriq && git fetch origin main && git reset --hard origin/main && docker compose build --no-cache api && docker compose up -d && echo '--- venter 12 sek ---' && sleep 12 && docker compose ps && echo '=== API-LOGS ===' && docker compose logs --tail 20 api && echo '=== HEALTH (internt) ===' && docker compose exec -T api python -c \"import urllib.request;print(urllib.request.urlopen('http://127.0.0.1:8642/health').read().decode())\""
echo.
pause
