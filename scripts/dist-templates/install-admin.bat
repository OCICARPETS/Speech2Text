@echo off
REM Speech2Text - ZENTRALE Installation (Terminal-Server, EINMAL durch Admin)
REM ----------------------------------------------------------------------
REM Kopiert die Programm-Exes nach %ProgramFiles%\Speech2Text (read-only fuer
REM normale Nutzer). Jeder Mitarbeiter fuehrt danach EINMAL install-user.bat aus
REM (legt nur seine Verknuepfungen an; Config bleibt pro Nutzer in %APPDATA%).
REM
REM ERFORDERT ADMIN-RECHTE (Schreibzugriff auf %ProgramFiles%).
REM   -> Rechtsklick - "Als Administrator ausfuehren"

setlocal enabledelayedexpansion
set "INSTALL_DIR=%ProgramFiles%\Speech2Text"
set "SCRIPT_DIR=%~dp0"

echo.
echo ===========================================
echo   Speech2Text - Zentrale Installation (Admin)
echo ===========================================
echo.
echo Quelle: %SCRIPT_DIR%
echo Ziel:   %INSTALL_DIR%
echo.

REM Admin-Rechte pruefen (net session gelingt nur mit erhoehten Rechten)
net session >nul 2>&1
if errorlevel 1 (
  echo FEHLER: Dieses Skript braucht Administrator-Rechte.
  echo         Rechtsklick auf install-admin.bat - "Als Administrator ausfuehren".
  echo.
  pause
  exit /b 1
)

REM Hinweis: Programm-Update bei laufenden Instanzen kann an gesperrten Exes
REM scheitern. Wir killen hier NICHT maschinenweit (das wuerde fremde RDP-
REM Sitzungen treffen). Vor einem Update bitte sicherstellen, dass niemand das
REM Tool aktiv nutzt - sonst meldet copy "Zugriff verweigert" fuer die Exe.

if not exist "%INSTALL_DIR%"        mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\assets" mkdir "%INSTALL_DIR%\assets"

echo Kopiere Programm-Dateien ...
copy /Y "%SCRIPT_DIR%Speech2Text-Daemon.exe"   "%INSTALL_DIR%\"        >nul || goto :copyfail
copy /Y "%SCRIPT_DIR%Speech2Text-Hotkey.exe"   "%INSTALL_DIR%\"        >nul || goto :copyfail
copy /Y "%SCRIPT_DIR%Speech2Text-Settings.exe" "%INSTALL_DIR%\"        >nul || goto :copyfail
copy /Y "%SCRIPT_DIR%assets\speech2text.ico"   "%INSTALL_DIR%\assets\" >nul || goto :copyfail
copy /Y "%SCRIPT_DIR%install-user.bat"         "%INSTALL_DIR%\"        >nul
copy /Y "%SCRIPT_DIR%uninstall.bat"            "%INSTALL_DIR%\"        >nul
copy /Y "%SCRIPT_DIR%README.txt"               "%INSTALL_DIR%\"        >nul
if exist "%SCRIPT_DIR%LIZENZEN.txt" copy /Y "%SCRIPT_DIR%LIZENZEN.txt" "%INSTALL_DIR%\" >nul

echo.
echo ===========================================
echo   Zentrale Installation abgeschlossen
echo ===========================================
echo.
echo Programm liegt unter:  %INSTALL_DIR%
echo.
echo NAECHSTER SCHRITT - pro Mitarbeiter (OHNE Admin):
echo   Jeder Nutzer fuehrt einmal aus:
echo       "%INSTALL_DIR%\install-user.bat"
echo   Das legt Desktop- + Autostart-Verknuepfung an. Der OpenAI-API-Key
echo   wird beim ersten Start pro Nutzer im Einstellungs-Fenster eingetragen
echo   (DPAPI-verschluesselt, nur fuer den jeweiligen Windows-Account lesbar).
echo.
pause
endlocal
goto :eof

:copyfail
echo.
echo FEHLER beim Kopieren - laeuft das Tool noch (Exe gesperrt)?
echo Bitte alle Speech2Text-Instanzen beenden und erneut versuchen.
echo.
pause
endlocal
exit /b 1
