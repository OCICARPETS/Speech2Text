@echo off
REM Speech2Text - Deinstallation
REM Beendet laufende Instanzen, entfernt Verknuepfungen und das
REM Programm-Verzeichnis. Konfiguration in %APPDATA%\Speech2Text bleibt.

setlocal
set "INSTALL_DIR=%LocalAppData%\Programs\Speech2Text"
set "DESKTOP=%USERPROFILE%\Desktop"
set "STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"

echo.
echo ===========================================
echo   Speech2Text - Deinstallation
echo ===========================================
echo.

set "CONFIRM="
set /P "CONFIRM=Wirklich deinstallieren? (J/N) "
if /I not "%CONFIRM%"=="J" if /I not "%CONFIRM%"=="Y" goto :abort

REM Laufende Instanzen beenden
echo Beende laufende Instanzen ...
taskkill /F /IM Speech2Text-Daemon.exe   >nul 2>&1
taskkill /F /IM Speech2Text-Hotkey.exe   >nul 2>&1
taskkill /F /IM Speech2Text-Settings.exe >nul 2>&1

REM Verknuepfungen entfernen
echo Entferne Verknuepfungen ...
if exist "%DESKTOP%\Speech2Text.lnk" del "%DESKTOP%\Speech2Text.lnk"
if exist "%STARTUP%\Speech2Text.lnk" del "%STARTUP%\Speech2Text.lnk"

REM Programm-Verzeichnis loeschen — aber nicht das, in dem dieses
REM Skript gerade laeuft (sonst Self-Delete-Problem auf Windows).
REM Workaround: Wir verschieben uninstall.bat NICHT mit weg; der User
REM kann das Verzeichnis nach Skript-Ende manuell entfernen, falls
REM es noch existiert (passiert nur, wenn uninstall.bat aus dem
REM Install-Dir selbst gestartet wurde).
if exist "%INSTALL_DIR%" (
    echo Loesche %INSTALL_DIR% ...
    rmdir /S /Q "%INSTALL_DIR%" 2>nul
    if exist "%INSTALL_DIR%" (
        echo HINWEIS: Verzeichnis konnte nicht vollstaendig geloescht werden.
        echo          Bitte manuell entfernen nach Beenden dieses Fensters:
        echo          %INSTALL_DIR%
    )
)

echo.
echo Deinstalliert.
echo.
echo Hinweis: Konfiguration in %%APPDATA%%\Speech2Text bleibt erhalten
echo (config.json mit API-Key, Modus-Overrides). Bei Bedarf manuell
echo loeschen.
echo.
pause
endlocal
goto :eof

:abort
echo Abgebrochen.
pause
endlocal
