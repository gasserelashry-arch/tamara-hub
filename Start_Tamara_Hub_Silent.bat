@echo off
cd /d "C:\Users\gasser.elashry\Downloads\Tamara_Hub_Local_Server_Package"
if not defined ADMIN_PASS (
  if exist "admin_pass.txt" set /p ADMIN_PASS=<admin_pass.txt
)
set PORT=8080
where python >nul 2>&1 && start "Tamara Hub" /MIN python tamara_hub_server.py && exit /b
where py >nul 2>&1 && start "Tamara Hub" /MIN py -3 tamara_hub_server.py && exit /b
