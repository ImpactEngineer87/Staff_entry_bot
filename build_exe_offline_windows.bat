@echo off
cd /d "%~dp0"
py -3 scripts\install_offline.py --include-build
if errorlevel 1 goto failed
.venv\Scripts\python.exe scripts\build_windows.py
if errorlevel 1 goto failed
echo Ready: dist\StaffEntryBot.exe
pause
exit /b 0
:failed
echo Offline EXE build failed. Read the message above.
pause
exit /b 1
