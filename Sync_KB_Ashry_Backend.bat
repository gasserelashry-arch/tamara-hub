@echo off
cd /d "%~dp0"
echo ============================================
echo  Atlas — Load KB Ashry.docx backend
echo  Source: C:\Users\gasser.elashry\Downloads\KB Ashry.docx
echo ============================================
python _kb_ashry_backend.py
if errorlevel 1 goto fail
echo.
echo Cache written: _kb_ashry_backend_cache.json
echo Open Update Hub -^> KB Ashry Auto-Sync -^> Load from Backend Doc
echo Or keep local server running and use the in-app Load button.
echo.
pause
exit /b 0
:fail
echo FAILED — check that KB Ashry.docx exists in Downloads.
pause
exit /b 1
