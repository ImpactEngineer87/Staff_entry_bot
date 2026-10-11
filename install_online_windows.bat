@echo off
cd /d "%~dp0"
py -3 -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install --retries 8 --timeout 120 -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip check
if errorlevel 1 goto failed
echo Installation complete. Open run_windows.bat to start the app.
pause
exit /b 0
:failed
echo Installation failed. Read the message above and try again.
pause
exit /b 1
