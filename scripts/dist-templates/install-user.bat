@echo off
REM Speech2Text - Benutzer-Einrichtung (pro Mitarbeiter, OHNE Admin)
REM ----------------------------------------------------------------------
REM Legt Desktop- + Autostart-Verknuepfung auf die ZENTRAL installierte App an
REM (%ProgramFiles%\Speech2Text). Config + API-Key bleiben pro Nutzer in
REM %APPDATA%\Speech2Text (DPAPI-verschluesselt).
REM Voraussetzung: Der Admin hat zuvor install-admin.bat ausgefuehrt.

setlocal enabledelayedexpansion
set "INSTALL_DIR=%ProgramFiles%\Speech2Text"
set "EXE=%INSTALL_DIR%\Speech2Text-Hotkey.exe"
set "DESKTOP=%USERPROFILE%\Desktop"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

echo.
echo ===========================================
echo   Speech2Text - Benutzer-Einrichtung
echo ===========================================
echo.

if not exist "%EXE%" (
  echo FEHLER: Zentrale Installation nicht gefunden:
  echo   %EXE%
  echo.
  echo Bitte zuerst den Administrator install-admin.bat ausfuehren lassen.
  echo.
  pause
  exit /b 1
)

REM Nur die EIGENE alte Instanz beenden. Als normaler Nutzer kann taskkill
REM ohnehin nur eigene Prozesse beenden (fremde RDP-Sitzungen bleiben unberuehrt -
REM "Zugriff verweigert" wird stillschweigend uebersprungen).
taskkill /F /IM Speech2Text-Hotkey.exe   >nul 2>&1
taskkill /F /IM Speech2Text-Daemon.exe   >nul 2>&1
taskkill /F /IM Speech2Text-Settings.exe >nul 2>&1

echo Lege Desktop-Verknuepfung an ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%DESKTOP%\Speech2Text.lnk'); $sc.TargetPath = '%EXE%'; $sc.IconLocation = '%INSTALL_DIR%\assets\speech2text.ico'; $sc.Description = 'Speech2Text - Caps Lock Push-to-Talk'; $sc.Save()"

echo Lege Autostart-Eintrag an ...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ws = New-Object -ComObject WScript.Shell; $sc = $ws.CreateShortcut('%STARTUP%\Speech2Text.lnk'); $sc.TargetPath = '%EXE%'; $sc.IconLocation = '%INSTALL_DIR%\assets\speech2text.ico'; $sc.Description = 'Speech2Text - Autostart'; $sc.Save()"

echo Starte Speech2Text ...
start "" "%EXE%"

echo.
echo ===========================================
echo   Einrichtung abgeschlossen
echo ===========================================
echo.
echo Beim ersten Start:
echo   1. Tray-Icon (Mikrofon, rechts unten) - Einstellungs-Fenster oeffnet sich
echo   2. OpenAI-API-Key eintragen (sk-...) - wird pro Nutzer DPAPI-verschluesselt
echo   3. Speichern und Schliessen
echo.
echo Bedienung: Caps Lock halten = Aufnahme, loslassen = Text einfuegen.
echo.
pause
endlocal
