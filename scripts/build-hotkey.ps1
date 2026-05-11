# Speech2Text - Build der AHK-Hotkey-Exe via Ahk2Exe.
#
# Erzeugt build\dist\Speech2Text-Hotkey.exe aus src\shortcut.ahk.
# Das Icon assets\speech2text.ico wird ins Exe eingebettet (Tray + Verknuepfung).
# Base-Exe ist AutoHotkey v2 64-Bit (system-installiert).
#
# Ahk2Exe liegt im Projekt unter tools\Ahk2Exe\Ahk2Exe.exe (lokales Build-Tool,
# NICHT in requirements.txt). Falls fehlt, neu downloaden via:
#   curl -sSL -o tools\Ahk2Exe\_dl.zip <github-release-url>
# (oder das Python-Snippet aus der Anleitung)
#
# Aufruf:
#   powershell -ExecutionPolicy Bypass -File scripts\build-hotkey.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

$Ahk2Exe = Join-Path $ProjectRoot "tools\Ahk2Exe\Ahk2Exe.exe"
$AhkBase = "C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe"
$Source  = Join-Path $ProjectRoot "src\shortcut.ahk"
$Icon    = Join-Path $ProjectRoot "assets\speech2text.ico"
$OutDir  = Join-Path $ProjectRoot "build\dist"
$OutExe  = Join-Path $OutDir "Speech2Text-Hotkey.exe"

if (-not (Test-Path $Ahk2Exe)) { Write-Error "Ahk2Exe nicht gefunden: $Ahk2Exe"; exit 1 }
if (-not (Test-Path $AhkBase)) { Write-Error "AutoHotkey-Base nicht gefunden: $AhkBase"; exit 1 }
if (-not (Test-Path $Source))  { Write-Error "Source nicht gefunden: $Source"; exit 1 }
if (-not (Test-Path $Icon))    { Write-Error "Icon nicht gefunden: $Icon"; exit 1 }

New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

# Ahk2Exe-Argumente:
#   /in    Source-Skript
#   /out   Ziel-Exe
#   /icon  einzubettendes Icon
#   /base  AHK-Runtime (v2 64-bit), wird Teil der Exe
$Args = @(
    "/in",   $Source,
    "/out",  $OutExe,
    "/icon", $Icon,
    "/base", $AhkBase
)

Write-Host ""
Write-Host "Ahk2Exe-Build startet ..." -ForegroundColor Cyan
Write-Host "  Source : $Source"
Write-Host "  Icon   : $Icon"
Write-Host "  Base   : $AhkBase"
Write-Host "  Output : $OutExe"
Write-Host ""

# Ahk2Exe gibt selbst bei Erfolg einen non-zero ExitCode zurueck — Erfolgs-
# kriterium ist die Existenz der Output-Datei (mit Mtime nach Build-Start).
$BuildStart = Get-Date
& $Ahk2Exe @Args | Out-Host

if (Test-Path $OutExe) {
    $Item = Get-Item $OutExe
    $Size = [math]::Round($Item.Length / 1KB, 1)
    if ($Item.LastWriteTime -lt $BuildStart) {
        Write-Warning "Output-Datei existiert, aber LastWriteTime ist vor Build-Start - vermutlich alter Build."
    }
    Write-Host ""
    Write-Host "OK Build erfolgreich: $OutExe ($Size KB)" -ForegroundColor Green
} else {
    Write-Error "Ahk2Exe-Build fehlgeschlagen - keine Output-Datei erzeugt."
    exit 1
}
