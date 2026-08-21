@echo off
cd /d "%~dp0"
if exist "venv\Scripts\pythonw.exe" (
    start "" "venv\Scripts\pythonw.exe" desktop_app.py
) else (
    start "" pythonw desktop_app.py
)
