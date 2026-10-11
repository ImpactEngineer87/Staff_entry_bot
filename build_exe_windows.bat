@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    py -3 -m venv .venv
    if errorlevel 1 goto failed
)
.venv\Scripts\python.exe -m pip install --retries 8 --timeout 120 --find-links wheelhouse -r requirements-build.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip check
if errorlevel 1 goto failed
.venv\Scripts\python.exe scripts\build_windows.py
if errorlevel 1 goto failed
echo Ready: dist\StaffEntryBot.exe
pause
exit /b 0
:failed
echo EXE build failed. Read the message above.
pause
exit /b 1
