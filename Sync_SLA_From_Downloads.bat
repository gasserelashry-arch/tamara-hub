@echo off
cd /d "%~dp0"
echo Parsing Transfers SLA.xlsx + Due Date Preference SLA docx...
python _parse_sla_sources.py
if errorlevel 1 goto fail
echo Applying Due Date Preference SLAs (5x verified)...
python _apply_sla_verified.py
if errorlevel 1 goto fail
echo Strict curated Transfers SLA finalize (5x verified)...
python _sla_strict_finalize.py
if errorlevel 1 goto fail
echo Syncing tool + KB Ashry from Transfers SLA (source of truth)...
python _sync_transfers_authority.py
if errorlevel 1 goto fail
echo Embedding into index.html...
python _embed_store.py
if errorlevel 1 goto fail
echo.
echo DONE. Restart/refresh Atlas (localhost).
echo Reports: _transfers_authority_report.json
pause
exit /b 0
:fail
echo FAILED. Check Python errors above.
pause
exit /b 1
