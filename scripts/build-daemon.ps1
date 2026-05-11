# Speech2Text - Build des Python-Daemons als eigenstaendige Exe.
#
# Erzeugt build\dist\Speech2Text-Daemon.exe via PyInstaller (one-file, no-console).
# Das Icon assets\speech2text.ico wird ins Exe eingebettet (Taskmanager-Logo).
#
# PyInstaller liegt im venv (BUILD-Tool, NICHT in requirements.txt).
# Falls fehlt: .venv\Scripts\pip install PyInstaller
#
# Optionen:
#   -Clean    Loescht build\ vor dem Build (sauberer Neuaufbau)
#   -Console  Baut MIT sichtbarem Konsolen-Fenster (Debug-Variante)
#
# Aufruf:
#   powershell -ExecutionPolicy Bypass -File scripts\build-daemon.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\build-daemon.ps1 -Clean
#   powershell -ExecutionPolicy Bypass -File scripts\build-daemon.ps1 -Clean -Console

param(
    [switch]$Clean,
    [switch]$Console
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Python = ".\.venv\Scripts\python.exe"
$Name   = "Speech2Text-Daemon"

# PyInstaller resolviert Icon und Source relativ zum --specpath. Wir nutzen
# absolute Pfade, damit das unabhaengig vom spec-Speicherort funktioniert.
if (-not (Test-Path $Python)) {
    Write-Error "venv-Python nicht gefunden: $Python"
    exit 1
}
if (-not (Test-Path ".\assets\speech2text.ico")) {
    Write-Error "Icon nicht gefunden: .\assets\speech2text.ico"
    exit 1
}
if (-not (Test-Path ".\src\recorder.py")) {
    Write-Error "Source nicht gefunden: .\src\recorder.py"
    exit 1
}
$Icon   = (Resolve-Path ".\assets\speech2text.ico").Path
$Source = (Resolve-Path ".\src\recorder.py").Path

if ($Clean -and (Test-Path ".\build")) {
    Write-Host "Cleanup: build\ wird geloescht ..." -ForegroundColor DarkGray
    Remove-Item -Recurse -Force ".\build"
}

# PyInstaller-Argumente. --collect-all sounddevice faengt PortAudio-DLL +
# Submodule. --collect-submodules openai vermeidet typische Hidden-Imports.
$PyiArgs = @(
    "-m", "PyInstaller",
    "--onefile",
    "--name", $Name,
    "--icon", $Icon,
    "--distpath", ".\build\dist",
    "--workpath", ".\build\work",
    "--specpath", ".\build",
    "--collect-all", "sounddevice",
    "--collect-submodules", "openai",
    "--noconfirm"
)
if (-not $Console) {
    $PyiArgs += "--noconsole"
}
$PyiArgs += $Source

$ModeLabel = if ($Console) { "Console (Debug)" } else { "No-Console (Production)" }

Write-Host ""
Write-Host "PyInstaller-Build startet ..." -ForegroundColor Cyan
Write-Host "  Source : $Source"
Write-Host "  Icon   : $Icon"
Write-Host "  Output : .\build\dist\$Name.exe"
Write-Host "  Mode   : $ModeLabel"
Write-Host ""

& $Python @PyiArgs
$BuildExitCode = $LASTEXITCODE

$ExePath = ".\build\dist\$Name.exe"
if (($BuildExitCode -eq 0) -and (Test-Path $ExePath)) {
    $Size = [math]::Round((Get-Item $ExePath).Length / 1MB, 2)
    Write-Host ""
    Write-Host "OK Build erfolgreich: $ExePath ($Size MB)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Test:   & '$ExePath'    (im Hintergrund - Tray-Daemon)"
    Write-Host "Health: Invoke-WebRequest http://127.0.0.1:17321/health"
} else {
    Write-Error "Build fehlgeschlagen (Exit-Code $BuildExitCode)"
    exit 1
}
