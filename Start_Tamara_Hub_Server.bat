@echo off
title Tamara Hub - Live Server (Port 8080)
color 0A
cd /d "%~dp0"

:: Load ADMIN_PASS from .env or admin_pass.txt if not already set
if not defined ADMIN_PASS (
  if exist "admin_pass.txt" (
    set /p ADMIN_PASS=<admin_pass.txt
  )
)
if not defined ADMIN_PASS (
  if exist ".env" (
    for /f "usebackq tokens=1,* delims==" %%a in (".env") do (
      if /I "%%a"=="ADMIN_PASS" set "ADMIN_PASS=%%b"
    )
  )
)
if not defined ADMIN_PASS (
  echo.
  echo [!] ADMIN_PASS is required.
  echo     Create admin_pass.txt with one line = your password
  echo     or copy .env.example to .env and set ADMIN_PASS=...
  echo.
  pause
  exit /b 1
)

:: Free port 8080 if an old server instance was still running
for /f "tokens=5" %%p in ('netstat -aon 2^>nul ^| findstr ":8080 "') do (
    taskkill /F /PID %%p >nul 2>&1
)

:: Add Windows Firewall rule for port 8080
netsh advfirewall firewall show rule name="Tamara Hub 8080" >nul 2>&1
if %errorlevel% neq 0 (
    netsh advfirewall firewall add rule name="Tamara Hub 8080" dir=in action=allow protocol=TCP localport=8080 profile=any >nul 2>&1
)

echo ============================================================================
echo   TAMARA HUB - SERVER STARTED SUCCESSFULLY
echo ============================================================================
echo.
echo   * Admin Link (Your PC):   http://localhost:8080
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    for /f "tokens=* delims= " %%b in ("%%a") do (
        echo %%b | findstr /b "127." >nul || echo %%b | findstr /b "169.254." >nul || echo   * Local Network Link:     http://%%b:8080
    )
)
echo.
echo   Keep this window open while using the tool.
echo   For a public permanent link, deploy to Render (see README.md).
echo ============================================================================
echo.

where python >nul 2>&1
if %errorlevel% equ 0 (
    start "" "http://localhost:8080"
    python tamara_hub_server.py
    exit /b
)

where py >nul 2>&1
if %errorlevel% equ 0 (
    start "" "http://localhost:8080"
    py -3 tamara_hub_server.py
    exit /b
)

if exist "C:\Python314\python.exe" (
    start "" "http://localhost:8080"
    "C:\Python314\python.exe" tamara_hub_server.py
    exit /b
)

echo [!] Python not found — cannot start live sync server.
pause
