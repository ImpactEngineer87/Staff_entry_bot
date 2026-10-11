@echo off
cd /d "%~dp0"
py -3 scripts\install_offline.py
if errorlevel 1 (
    echo Offline installation failed. Read the message above.
)
pause
