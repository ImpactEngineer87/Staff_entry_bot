@echo off
cd /d "%~dp0"
py -3 scripts\prepare_offline.py
if errorlevel 1 (
    echo Package preparation failed. Read the message above and try again.
)
pause
