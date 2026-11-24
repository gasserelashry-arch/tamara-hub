@echo off
cd /d "%~dp0"
echo ============================================================
echo Atlas recommended sync
echo  - Transfers SLA.xlsx = ONLY SLA authority
echo  - KB Ashry = knowledge / SOP only (never overrides SLA)
echo ============================================================
echo.
echo [1/3] Running ops sync...
python _ops_sync_recommended.py
if errorlevel 1 goto fail
echo.
echo [2/3] Embedding into index.html...
python _embed_store.py
if errorlevel 1 goto fail
echo.
echo [3/3] Patching ops UI + revision badge...
python _patch_ops_ui.py
if errorlevel 1 goto fail
echo.
echo DONE locally.
echo Next: run Publish_For_Agents.bat to push to agents.
echo Reports: _ops_sync_recommended_report.json
echo          _ops_kb_transfers_mismatch.json
echo.
pause
exit /b 0
:fail
echo FAILED. See Python errors above.
pause
exit /b 1
