@echo off
title OVRIQ - deploy til Hetzner
cd /d "%~dp0"
set SERVER=62.238.6.143
set RAWNEW=https://raw.githubusercontent.com/BeMintalitet/ovriq/main/deploy/server_setup.sh
set RAWOLD=https://raw.githubusercontent.com/BeMintalitet/GitHub-org-ovriq-/main/deploy/server_setup.sh
echo.
echo   OVRIQ - PRODUKTIONS-DEPLOY
echo   Server: %SERVER% - Hetzner Helsinki
echo   Root-passwordet fra Hetzner-mailen skal indtastes 2-3 gange.
echo.

where ssh >nul 2>&1
if errorlevel 1 goto nossh

if not exist .env goto noenv
echo   [1/2] Sender .env sikkert til serveren...
scp -o StrictHostKeyChecking=accept-new .env root@%SERVER%:/root/ovriq.env
goto run

:noenv
echo   [1/2] Ingen lokal .env fundet - serveren startes uden PayPal-creds
goto run

:run
echo   [2/2] Koerer server-setup - haerdning, Docker, stak...
ssh -o StrictHostKeyChecking=accept-new root@%SERVER% "curl -fsSL %RAWNEW% -o /tmp/s.sh || curl -fsSL %RAWOLD% -o /tmp/s.sh; bash /tmp/s.sh"
echo.
echo   FAERDIG. Tjek https://api.ovriq.xyz/health om et par minutter.
echo.
pause
exit /b

:nossh
echo   OpenSSH mangler. Installer: Indstillinger - Apps - Valgfrie funktioner - OpenSSH-klient
pause
