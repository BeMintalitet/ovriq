@echo off
title OVRIQ - SHIP (push til GitHub + deploy til server)
cd /d "%~dp0"
set SERVER=62.238.6.143
set TOKEN=J5Ue2tI3OlDCsPqD10jAYl8MIpEuIR9E
echo.
echo   ========================================
echo    OVRIQ SHIP  -  kode til GitHub OG server
echo   ========================================
echo.

where git >nul 2>&1
if errorlevel 1 goto nogit
where ssh >nul 2>&1
if errorlevel 1 goto nossh

echo   [1/2] Pusher kode til GitHub...
if not exist .git goto firstpush
git add -A
git commit -m "OVRIQ update %date% %time%"
git push origin main
if errorlevel 1 git push origin main --force
goto deploy

:firstpush
git init -b main
git config user.name "BeMintalitet"
git config user.email "benjaminfosskristoffersen@gmail.com"
git config core.autocrlf false
git remote add origin https://github.com/BeMintalitet/ovriq.git
git add -A
git commit -m "OVRIQ"
git push -u origin main --force

:deploy
echo.
echo   [2/2] Deployer paa serveren (indtast server-password)...
ssh -o StrictHostKeyChecking=accept-new root@%SERVER% "cd /opt/ovriq && git fetch origin main && git reset --hard origin/main && ( grep -q '^OVRIQ_ADMIN_TOKEN=' .env || echo 'OVRIQ_ADMIN_TOKEN=%TOKEN%' >> .env ) && docker compose build --no-cache api && docker compose up -d && echo '--- venter 12 sek ---' && sleep 12 && docker compose ps && echo '=== HEALTH ===' && curl -s https://api.ovriq.xyz/health && echo"
echo.
echo   FAERDIG. Dashboard: https://api.ovriq.xyz/dashboard
echo.
pause
exit /b

:nogit
echo   Git mangler. Installer: winget install --id Git.Git -e
pause
exit /b

:nossh
echo   OpenSSH mangler. Indstillinger - Apps - Valgfrie funktioner - OpenSSH-klient
pause
