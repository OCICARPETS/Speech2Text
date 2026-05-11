# Speech2Text — Autostart im Windows-Startup-Ordner einrichten
#
# Legt zwei Shortcuts in %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup:
#   - Speech2Text-Daemon.lnk   → scripts\start-daemon-hidden.bat (hidden, pythonw)
#   - Speech2Text-Hotkey.lnk   → src\shortcut.ahk               (AHK v2)
#
# Beide starten beim nächsten Windows-Login automatisch. Für Debugging kann
# der Daemon weiterhin manuell via scripts\start-daemon.bat (sichtbar) oder
# direkt über Python gestartet werden.
#
# Deinstallation: scripts\uninstall-autostart.ps1

$ErrorActionPreference = "Stop"

$startup = [Environment]::GetFolderPath('Startup')
# $PSScriptRoot ist der scripts/ Ordner → Projekt-Root ist ein Level hoch
$project = Split-Path -Parent $PSScriptRoot

$daemonBat = Join-Path $project "scripts\start-daemon-hidden.bat"
$hotkeyAhk = Join-Path $project "src\shortcut.ahk"

if (-not (Test-Path $daemonBat)) {
    throw "Nicht gefunden: $daemonBat"
}
if (-not (Test-Path $hotkeyAhk)) {
    throw "Nicht gefunden: $hotkeyAhk"
}

$shell = New-Object -ComObject WScript.Shell

# --- Daemon-Shortcut ---
$daemonLnk = Join-Path $startup "Speech2Text-Daemon.lnk"
$s1 = $shell.CreateShortcut($daemonLnk)
$s1.TargetPath = $daemonBat
$s1.WorkingDirectory = $project
$s1.WindowStyle = 7   # minimized (pythonw zeigt eh kein Fenster — Sicherheitsgurt)
$s1.Description = "Speech2Text Python-Daemon (hidden, stdout → %APPDATA%\Speech2Text\daemon.log)"
$s1.Save()
Write-Host "  ✓ $daemonLnk"

# --- Hotkey-Shortcut ---
$hotkeyLnk = Join-Path $startup "Speech2Text-Hotkey.lnk"
$s2 = $shell.CreateShortcut($hotkeyLnk)
$s2.TargetPath = $hotkeyAhk
$s2.WorkingDirectory = (Split-Path -Parent $hotkeyAhk)
$s2.Description = "Speech2Text AutoHotkey Push-to-Talk"
$s2.Save()
Write-Host "  ✓ $hotkeyLnk"

Write-Host ""
Write-Host "Autostart eingerichtet. Beim nächsten Windows-Login starten Daemon + Hotkey automatisch."
Write-Host "Entfernen mit: scripts\uninstall-autostart.ps1"
