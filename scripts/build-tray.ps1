# Speech2Text - Build der Python-Tray-App als eigenstaendige Exe.
#
# Ersetzt die alte build-hotkey.ps1 / build-hotkey.py (AHK/Ahk2Exe-Bundle).
# Erzeugt build\dist\Speech2Text-Hotkey.exe via PyInstaller (one-file, no-console).
# Icon wird eingebettet (Taskmanager) UND als Datendatei mitgepackt (Tray-Icon
# zur Laufzeit via PIL.Image.open).
#
# PyInstaller liegt im venv (BUILD-Tool, NICHT in requirements.txt).
# Falls fehlt: .venv\Scripts\pip install PyInstaller
#
# Optionen:
#   -Clean    Loescht build\tray\ vor dem Build (sauberer Neuaufbau)
#   -Console  Baut MIT Konsolen-Fenster (Debug-Variante)
#
# Aufruf:
#   powershell -ExecutionPolicy Bypass -File scripts\build-tray.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\build-tray.ps1 -Clean

param(
    [switch]$Clean,
    [switch]$Console
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Python = ".\.venv\Scripts\python.exe"
$Name   = "Speech2Text-Hotkey"

if (-not (Test-Path $Python)) {
    Write-Error "venv-Python nicht gefunden: $Python"
    exit 1
}
if (-not (Test-Path ".\assets\speech2text.ico")) {
    Write-Error "Icon nicht gefunden: .\assets\speech2text.ico"
    exit 1
}
if (-not (Test-Path ".\src\tray_app.py")) {
    Write-Error "Source nicht gefunden: .\src\tray_app.py"
    exit 1
}
$Icon   = (Resolve-Path ".\assets\speech2text.ico").Path
$Source = (Resolve-Path ".\src\tray_app.py").Path
$SrcDir = (Resolve-Path ".\src").Path

if ($Clean -and (Test-Path ".\build\tray")) {
    Write-Host "Cleanup: build\tray\ wird geloescht ..." -ForegroundColor DarkGray
    Remove-Item -Recurse -Force ".\build\tray"
}

# --add-data sorgt dafuer, dass speech2text.ico im PyInstaller-onefile-Bundle
# unter _MEIPASS/assets/ landet. tray_app.py liest es zur Laufzeit ueber
# sys._MEIPASS (siehe _icon_path-Helper).
# --paths .\src damit config, daemon_client, keyboard_hook, _arch_fix gefunden
# werden (flach unter src/).
# --collect-all tkinter: Pflicht ab v1.4 Punkt 1. Der Custom-Toast (src/toast.py)
# importiert tkinter LAZY in seinem ToastUI-Thread. Das Tray-Bundle zog bisher
# KEIN tkinter (nur der Settings-Prozess) -> ohne expliziten Collect fehlen die
# tcl/tk-Datendateien im onefile und das Toast-Toplevel crasht zur Laufzeit
# (Dev-Python kaschiert das, da System-Python tk hat). Verifizieren per
# Bundle-Smoke der gebauten Exe (Cycle -> Toast, kein TclError in tray.log).
$PyiArgs = @(
    "-m", "PyInstaller",
    "--onefile",
    "--name", $Name,
    "--icon", $Icon,
    "--add-data", "$Icon;assets",
    "--distpath", ".\build\dist",
    "--workpath", ".\build\tray\work",
    "--specpath", ".\build\tray",
    "--paths", $SrcDir,
    "--collect-all", "pystray",
    "--collect-all", "PIL",
    "--collect-all", "tkinter",
    "--noconfirm"
)
if (-not $Console) {
    $PyiArgs += "--noconsole"
}
$PyiArgs += $Source

$ModeLabel = if ($Console) { "Console (Debug)" } else { "No-Console (Production)" }

Write-Host ""
Write-Host "PyInstaller-Build (Tray-App) startet ..." -ForegroundColor Cyan
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
    Write-Host "Test: Doppelklick auf $ExePath - Tray-Icon erscheint."
} else {
    Write-Error "Build fehlgeschlagen (Exit-Code $BuildExitCode)"
    exit 1
}
