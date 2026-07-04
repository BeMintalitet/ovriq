@echo off
title OVRIQ - serverdiagnose
set SERVER=62.238.6.143
echo.
echo   Henter status fra %SERVER% (indtast root-password)...
echo.
ssh -o StrictHostKeyChecking=accept-new root@%SERVER% "echo '=== SETUP-SCRIPT KOERT? ==='; ls -la /opt/ovriq 2>&1 | head -5; echo; echo '=== DOCKER ==='; docker compose -f /opt/ovriq/docker-compose.yml ps 2>&1; echo; echo '=== API-LOGS (sidste 25) ==='; docker compose -f /opt/ovriq/docker-compose.yml logs --tail 25 api 2>&1; echo; echo '=== CADDY-LOGS (sidste 15) ==='; docker compose -f /opt/ovriq/docker-compose.yml logs --tail 15 caddy 2>&1; echo; echo '=== UFW ==='; ufw status 2>&1"
echo.
pause
