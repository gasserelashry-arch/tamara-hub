@echo off
title Tamara Hub - Restart Public Link
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Restart_Public_Link.ps1"
pause
