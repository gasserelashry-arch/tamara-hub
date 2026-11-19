@echo off
title Tamara Hub - Public Tunnel
cd /d "%~dp0"

if not defined ADMIN_PASS (
  if exist "admin_pass.txt" set /p ADMIN_PASS=<admin_pass.txt
)
if not defined ADMIN_PASS (
  echo Create admin_pass.txt first (one line = your admin password).
  pause
  exit /b 1
)

echo Starting Tamara Hub on port 8080...
start "Tamara Hub Server" cmd /c "set ADMIN_PASS=%ADMIN_PASS%&& set PORT=8080&& python tamara_hub_server.py"

timeout /t 3 /nobreak >nul

where cloudflared >nul 2>&1
if %errorlevel% equ 0 (
  echo Opening public Cloudflare tunnel...
  cloudflared tunnel --url http://127.0.0.1:8080
  exit /b
)

if exist "%TEMP%\cloudflared.exe" (
  echo Opening public Cloudflare tunnel...
  "%TEMP%\cloudflared.exe" tunnel --url http://127.0.0.1:8080
  exit /b
)

echo cloudflared not found. Install from https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/
echo Or deploy permanently to Render (see README.md).
pause
