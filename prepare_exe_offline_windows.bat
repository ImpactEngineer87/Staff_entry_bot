@echo off
cd /d "%~dp0"
py -3 scripts\prepare_offline.py --include-build
if errorlevel 1 (
    echo Preparation failed. Read the message above and rerun when connected.
)
pause
