@echo off
cd /d "%~dp0"
echo Menjalankan Dasbor Komparasi Rumah (mode debug)...
echo Jika ada error, pesannya akan tampil di bawah ini.
echo.
if exist "venv\Scripts\python.exe" (
    "venv\Scripts\python.exe" desktop_app.py
) else (
    python desktop_app.py
)
echo.
pause
