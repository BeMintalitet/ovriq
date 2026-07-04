@echo off
title OVRIQ - push til GitHub
cd /d "%~dp0"
echo.
echo   OVRIQ - push til GitHub
echo.

where git >nul 2>&1
if errorlevel 1 goto nogit

if exist .git goto update

echo   Foerste push: opretter git-historik...
git init -b main
git config user.name "BeMintalitet"
git config user.email "benjaminfosskristoffersen@gmail.com"
git config core.autocrlf false
git remote add origin https://github.com/BeMintalitet/ovriq.git
git add -A
git commit -m "OVRIQ initial"
git push -u origin main --force
goto done

:update
echo   Committer aendringer oven paa eksisterende historik...
git add -A
git commit -m "OVRIQ update %date% %time%"
git push -u origin main
if errorlevel 1 git push -u origin main --force
goto done

:done
echo.
echo   FAERDIG - https://github.com/BeMintalitet/ovriq
pause
exit /b

:nogit
echo   Git mangler. Installer: winget install --id Git.Git -e
pause
