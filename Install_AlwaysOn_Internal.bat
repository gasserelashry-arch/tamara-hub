@echo off
title Tamara Hub - Install Always-On Internal Link
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install_AlwaysOn_Internal.ps1"
pause
