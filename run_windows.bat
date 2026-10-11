@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
    echo Install first using install_online_windows.bat or install_offline_windows.bat.
    pause
    exit /b 1
)
.venv\Scripts\python.exe main.py
if errorlevel 1 pause
