@echo off
REM Speech2Text — Daemon im Hintergrund starten (kein CMD-Fenster)
REM Logs landen in %APPDATA%\Speech2Text\daemon.log
REM
REM Wird von scripts\install-autostart.ps1 im Windows-Startup-Ordner verlinkt.
REM Für Debugging lieber scripts\start-daemon.bat nutzen (zeigt Live-Log).

cd /d "%~dp0.."

REM pythonw.exe startet ohne Console. Bevorzugt venv, sonst System-Python.
if exist ".venv\Scripts\pythonw.exe" (
    start "" ".venv\Scripts\pythonw.exe" src\recorder.py --hidden
) else (
    start "" pythonw src\recorder.py --hidden
)
