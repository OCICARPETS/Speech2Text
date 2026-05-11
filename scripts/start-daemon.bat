@echo off
REM Speech2Text — Python-Daemon starten
REM Erwartet: Python 3.11+ im PATH, .env vorhanden (siehe .env.example)

cd /d "%~dp0.."

REM venv nutzen, wenn vorhanden
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" src\recorder.py
) else (
    python src\recorder.py
)

REM Bei Absturz nicht sofort Fenster schließen, damit Fehler lesbar sind
if errorlevel 1 pause
