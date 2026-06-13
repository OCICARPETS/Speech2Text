@echo off
REM Speech2Text - Deinstallation
REM Entfernt Verknuepfungen + Programm. Config in %APPDATA%\Speech2Text bleibt.
REM Deckt beide Installationsarten ab:
REM   - per-User:  %LocalAppData%\Programs\Speech2Text  (kein Admin)
REM   - zentral:   %ProgramFiles%\Speech2Text           (braucht Admin)

setlocal
set "USER_DIR=%LocalAppData%\Programs\Speech2Text"
set "CENTRAL_DIR=%ProgramFiles%\Speech2Text"
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

REM Eigene Instanz beenden (als normaler Nutzer session-beschraenkt)
echo Beende laufende Instanzen ...
taskkill /F /IM Speech2Text-Daemon.exe   >nul 2>&1
taskkill /F /IM Speech2Text-Hotkey.exe   >nul 2>&1
taskkill /F /IM Speech2Text-Settings.exe >nul 2>&1

REM Eigene Verknuepfungen entfernen (pro Nutzer)
echo Entferne Verknuepfungen ...
if exist "%DESKTOP%\Speech2Text.lnk" del "%DESKTOP%\Speech2Text.lnk"
if exist "%STARTUP%\Speech2Text.lnk" del "%STARTUP%\Speech2Text.lnk"

REM per-User-Installation entfernen (falls vorhanden)
if exist "%USER_DIR%" (
    echo Loesche per-User-Installation %USER_DIR% ...
    rmdir /S /Q "%USER_DIR%" 2>nul
)

REM Zentrale Installation entfernen - nur mit Admin
if not exist "%CENTRAL_DIR%" goto :done_central
net session >nul 2>&1
if errorlevel 1 goto :central_needs_admin
echo Loesche zentrale Installation %CENTRAL_DIR% ...
rmdir /S /Q "%CENTRAL_DIR%" 2>nul
if exist "%CENTRAL_DIR%" echo HINWEIS: Verzeichnis nicht vollstaendig geloescht - laeuft das Tool noch? Bitte manuell entfernen: %CENTRAL_DIR%
goto :done_central
:central_needs_admin
echo.
echo HINWEIS: Zentrale Installation gefunden: %CENTRAL_DIR%
echo Deine persoenlichen Verknuepfungen wurden entfernt. Das ZENTRALE Programm
echo kann nur ein Administrator entfernen - uninstall.bat als Administrator
echo ausfuehren, falls das Tool fuer ALLE entfernt werden soll.
:done_central

echo.
echo Deinstalliert.
echo.
echo Hinweis: Konfiguration in %%APPDATA%%\Speech2Text bleibt erhalten
echo (config.json mit API-Key, Modus-Overrides). Bei Bedarf manuell loeschen.
echo.
pause
endlocal
goto :eof

:abort
echo Abgebrochen.
pause
endlocal
