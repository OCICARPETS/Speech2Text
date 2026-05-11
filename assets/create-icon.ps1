# Speech2Text — Tray-Icon generieren
#
# Erzeugt assets\speech2text.ico:
#   - 32×32 px, anti-aliased
#   - OCI Electric Blue (#2563EB) Kreis-Hintergrund
#   - weißes "S2T" in Segoe UI Bold
#
# Neu ausführen, wenn das Design geändert werden soll:
#   powershell -ExecutionPolicy Bypass -File assets\create-icon.ps1
#
# Das AHK-Skript lädt die .ico automatisch beim Start (src\shortcut.ahk).

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$size = 32
$bmp = New-Object System.Drawing.Bitmap $size, $size
$g = [System.Drawing.Graphics]::FromImage($bmp)
$g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
$g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias

# Hintergrund-Kreis — Electric Blue (Dashboard-Brand)
$bg = [System.Drawing.Color]::FromArgb(255, 37, 99, 235)
$bgBrush = New-Object System.Drawing.SolidBrush $bg
$g.FillEllipse($bgBrush, 0, 0, ($size - 1), ($size - 1))

# "S2T"-Text in Weiß
$whiteBrush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::White)
$font = [System.Drawing.Font]::new([string]"Segoe UI", [single]10.0, [System.Drawing.FontStyle]::Bold)
$sf = New-Object System.Drawing.StringFormat
$sf.Alignment = [System.Drawing.StringAlignment]::Center
$sf.LineAlignment = [System.Drawing.StringAlignment]::Center
$rect = New-Object System.Drawing.RectangleF 0, 0, $size, $size
$g.DrawString("S2T", $font, $whiteBrush, $rect, $sf)

$g.Dispose()

# Bitmap → Icon → Datei
$hIcon = $bmp.GetHicon()
$icon = [System.Drawing.Icon]::FromHandle($hIcon)
$outPath = Join-Path $PSScriptRoot "speech2text.ico"
$fs = [System.IO.File]::Create($outPath)
try {
    $icon.Save($fs)
} finally {
    $fs.Close()
    $bmp.Dispose()
}
Write-Host "  OK Icon erstellt: $outPath"
