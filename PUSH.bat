@echo off
title OVRIQ - push til GitHub
cd /d "%~dp0"
echo.
echo   ░▒▓ OVRIQ → GitHub ▓▒░
echo.

where git >nul 2>&1
if errorlevel 1 (
  echo   Git er ikke installeret. Installerer via winget...
  winget install --id Git.Git -e --source winget
  echo.
  echo   Luk dette vindue og dobbeltklik PUSH.bat igen.
  pause
  exit /b
)

if exist .git rmdir /s /q .git
git init -b main
git config user.name "BeMintalitet"
git config user.email "benjaminfosskristoffersen@gmail.com"
git config core.autocrlf false
git add -A
git commit -m "OVRIQ fase 1: Decimal-pengemotor, event-journal m. genstartsbevis, API, SDK, dashboard, landing page, Docker/CI"
git remote add origin https://github.com/BeMintalitet/GitHub-org-ovriq-.git

echo.
echo   Pusher... (foerste gang aabner GitHub-login i din browser - log ind der)
git push -u origin main
if errorlevel 1 (
  echo.
  echo   Push afvist - repo'et indeholder sikkert en README fra oprettelsen.
  choice /c JN /m "  Overskriv repo'ets indhold med OVRIQ-koden? [J/N]"
  if errorlevel 2 exit /b
  git push -u origin main --force
)

echo.
echo   ✔ FAERDIG - se koden paa https://github.com/BeMintalitet/GitHub-org-ovriq-
echo.
pause
