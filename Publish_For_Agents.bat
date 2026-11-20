@echo off
title Publish Tamara Hub for Agents (free permanent link)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Publish_For_Agents.ps1"
pause
