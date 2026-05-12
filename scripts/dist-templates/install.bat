@echo off
REM Speech2Text - Installation
REM Kopiert die Bundle-Exes nach %LocalAppData%\Programs\Speech2Text,
REM legt eine Desktop-Verknuepfung an und fragt optional nach Autostart.

setlocal enabledelayedexpansion
set "INSTALL_DIR=%LocalAppData%\Programs\Speech2Text"
set "SCRIPT_DIR=%~dp0"
set "DESKTOP=%USERPROFILE%\Desktop"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

echo.
echo ===========================================
echo   Speech2Text - Installation
echo ===========================================
echo.
echo Quelle: %SCRIPT_DIR%
echo Ziel:   %INSTALL_DIR%
echo.

REM Eventuell laufende Instanzen sauber beenden
echo Beende laufende Instanzen ...
taskkill /F /IM Speech2Text-Daemon.exe   >nul 2>&1
taskkill /F /IM Speech2Text-Hotkey.exe   >nul 2>&1
taskkill /F /IM Speech2Text-Settings.exe >nul 2>&1

REM Zielverzeichnis vorbereiten
if not exist "%INSTALL_DIR%"        mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\assets" mkdir "%INSTALL_DIR%\assets"

REM Dateien kopieren
echo Kopiere Dateien ...
copy /Y "%SCRIPT_DIR%Speech2Text-Daemon.exe"   "%INSTALL_DIR%\" >nul
copy /Y "%SCRIPT_DIR%Speech2Text-Hotkey.exe"   "%INSTALL_DIR%\" >nul
copy /Y "%SCRIPT_DIR%Speech2Text-Settings.exe" "%INSTALL_DIR%\" >nul
copy /Y "%SCRIPT_DIR%assets\speech2text.ico"   "%INSTALL_DIR%\assets\" >nul
copy /Y "%SCRIPT_DIR%uninstall.bat"            "%INSTALL_DIR%\" >nul
copy /Y "%SCRIPT_DIR%README.txt"               "%INSTALL_DIR%\" >nul
if exist "%SCRIPT_DIR%LIZENZEN.txt" (
  copy /Y "%SCRIPT_DIR%LIZENZEN.txt"           "%INSTALL_DIR%\" >nul
)

REM Desktop-Verknuepfung
echo Lege Desktop-Verknuepfung an ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%DESKTOP%\Speech2Text.lnk'); $sc.TargetPath = '%INSTALL_DIR%\Speech2Text-Hotkey.exe'; $sc.IconLocation = '%INSTALL_DIR%\assets\speech2text.ico'; $sc.Description = 'Speech2Text - Caps Lock Push-to-Talk'; $sc.Save()"

REM Autostart-Frage
echo.
set "AUTOSTART="
set /P "AUTOSTART=Bei Windows-Anmeldung automatisch starten? (J/N) "
if /I "%AUTOSTART%"=="J" goto :install_autostart
if /I "%AUTOSTART%"=="Y" goto :install_autostart
goto :skip_autostart

:install_autostart
echo Lege Autostart-Eintrag an ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%STARTUP%\Speech2Text.lnk'); $sc.TargetPath = '%INSTALL_DIR%\Speech2Text-Hotkey.exe'; $sc.IconLocation = '%INSTALL_DIR%\assets\speech2text.ico'; $sc.Description = 'Speech2Text - Autostart'; $sc.Save()"
echo Autostart eingerichtet.
goto :done

:skip_autostart
echo Autostart uebersprungen.

:done
echo.
echo ===========================================
echo   Installation abgeschlossen
echo ===========================================
echo.
echo Start: Doppelklick auf "Speech2Text" auf dem Desktop.
echo.
echo Beim ersten Start:
echo   1. Tray-Icon (Mikrofon, rechts unten)
echo   2. Rechtsklick - Einstellungen
echo   3. OpenAI-API-Key eintragen (sk-...)
echo   4. Speichern und Schliessen
echo.
echo Bedienung:
echo   - Caps Lock halten = Aufnahme
echo   - Caps Lock loslassen = Transkription + Optimierung + Auto-Paste
echo.
pause
endlocal
