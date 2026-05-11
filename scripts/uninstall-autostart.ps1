# Speech2Text — Autostart entfernen (Gegenstück zu install-autostart.ps1)

$startup = [Environment]::GetFolderPath('Startup')
$targets = @("Speech2Text-Daemon.lnk", "Speech2Text-Hotkey.lnk")

foreach ($name in $targets) {
    $path = Join-Path $startup $name
    if (Test-Path $path) {
        Remove-Item $path -Force
        Write-Host "  ✓ entfernt: $path"
    } else {
        Write-Host "  - nicht vorhanden: $path"
    }
}

Write-Host ""
Write-Host "Autostart entfernt. Laufende Daemon-/Hotkey-Prozesse werden nicht beendet —"
Write-Host "die bleiben aktiv bis zum nächsten Logout / Neustart."
