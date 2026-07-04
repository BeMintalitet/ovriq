@echo off
title OVRIQ - database-password-fix
set SERVER=62.238.6.143
echo.
echo   Synkroniserer databasens password med .env og genstarter API'et...
echo.
ssh -o StrictHostKeyChecking=accept-new root@%SERVER% "cd /opt/ovriq && PW=$(grep '^POSTGRES_PASSWORD=' .env | cut -d= -f2- | tr -d '\r') && docker compose exec -T db psql -U ovriq -d ovriq -c \"ALTER USER ovriq WITH PASSWORD '$PW';\" && docker compose restart api && echo '--- venter 12 sek ---' && sleep 12 && docker compose ps && echo '=== HEALTH ===' && curl -s https://api.ovriq.xyz/health && echo ' OK'"
echo.
pause
