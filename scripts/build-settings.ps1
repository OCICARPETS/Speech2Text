# Speech2Text - Build der Settings-GUI als eigenstaendige Exe.
#
# Erzeugt build\dist\Speech2Text-Settings.exe via PyInstaller (one-file,
# no-console). Wird vom Tray-Eintrag "Einstellungen..." aufgerufen, statt
# pythonw.exe + settings.py (die im Bundle-Setup nicht da sind).
#
# PyInstaller liegt im venv (BUILD-Tool, NICHT in requirements.txt).
#
# Optionen:
#   -Clean    Loescht spec/work fuer Settings vor Build
#
# Aufruf:
#   powershell -ExecutionPolicy Bypass -File scripts\build-settings.ps1

param(
    [switch]$Clean
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Python = ".\.venv\Scripts\python.exe"
$Name   = "Speech2Text-Settings"

if (-not (Test-Path $Python)) { Write-Error "venv-Python nicht gefunden: $Python"; exit 1 }
if (-not (Test-Path ".\assets\speech2text.ico")) { Write-Error "Icon fehlt"; exit 1 }
if (-not (Test-Path ".\src\settings.py")) { Write-Error "Source fehlt"; exit 1 }
$Icon   = (Resolve-Path ".\assets\speech2text.ico").Path
$Source = (Resolve-Path ".\src\settings.py").Path

if ($Clean) {
    if (Test-Path ".\build\work\$Name") { Remove-Item -Recurse -Force ".\build\work\$Name" }
    if (Test-Path ".\build\$Name.spec") { Remove-Item -Force ".\build\$Name.spec" }
}

# --collect-all sounddevice fuer den Mikrofon-Test (rec/play/query_devices).
# tkinter wird von PyInstaller automatisch gefunden.
# --paths .\src damit `import config` aus settings.py funktioniert.
$PyiArgs = @(
    "-m", "PyInstaller",
    "--onefile",
    "--noconsole",
    "--name", $Name,
    "--icon", $Icon,
    "--distpath", ".\build\dist",
    "--workpath", ".\build\work",
    "--specpath", ".\build",
    "--paths", (Resolve-Path ".\src").Path,
    "--collect-all", "sounddevice",
    "--noconfirm",
    $Source
)

Write-Host ""
Write-Host "PyInstaller-Build (Settings) startet ..." -ForegroundColor Cyan
Write-Host "  Source : $Source"
Write-Host "  Output : .\build\dist\$Name.exe"
Write-Host ""

& $Python @PyiArgs
$BuildExitCode = $LASTEXITCODE

$ExePath = ".\build\dist\$Name.exe"
if (($BuildExitCode -eq 0) -and (Test-Path $ExePath)) {
    $Size = [math]::Round((Get-Item $ExePath).Length / 1MB, 2)
    Write-Host ""
    Write-Host "OK Build erfolgreich: $ExePath ($Size MB)" -ForegroundColor Green
} else {
    Write-Error "Build fehlgeschlagen (Exit-Code $BuildExitCode)"
    exit 1
}
