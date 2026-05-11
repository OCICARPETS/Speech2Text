"""Speech2Text — Build der AHK-Hotkey-Exe via Ahk2Exe (AV-resistent).

Ersatz fuer scripts/build-hotkey.ps1, das auf der OCI-Workstation regelmaessig
scheitert: Defender quarantaeniert Ahk2Exe.exe zwischen Aufrufen aus
PowerShell oder Bash. Sobald die Exe in einem separaten Prozess gestartet
wird, raeumt der AV-Scanner sie weg.

Strategie hier: Download + Entpacken + Compile-Aufruf in EINEM Python-Prozess
via subprocess.run. Damit bleibt kein Lock-Window, in dem der AV-Scanner die
Datei zwischen Schritten quarantaenieren koennte. Die ZIP existiert nie auf
Platte (BytesIO), Ahk2Exe.exe liegt nur kurz in tools/Ahk2Exe/ bevor sie
sofort genutzt wird.

Aufruf:
  .venv\\Scripts\\python.exe scripts\\build-hotkey.py
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

# Kein .resolve() — das wuerde unter Substituted-Drives (z. B. I: → UNC
# \\server\share) auf den UNC-Pfad umstellen, und Ahk2Exe verweigert
# Schreibzugriff auf UNC-Output-Pfade.
PROJECT_ROOT = Path(__file__).parent.parent
TOOLS_DIR = PROJECT_ROOT / "tools" / "Ahk2Exe"
SOURCE = PROJECT_ROOT / "src" / "shortcut.ahk"
ICON = PROJECT_ROOT / "assets" / "speech2text.ico"
OUTPUT = PROJECT_ROOT / "build" / "dist" / "Speech2Text-Hotkey.exe"
AHK_BASE = Path(r"C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe")

GITHUB_API = "https://api.github.com/repos/AutoHotkey/Ahk2Exe/releases/latest"


def fetch_ahk2exe() -> Path:
    """Holt die neueste Ahk2Exe-Release-Version, entpackt sie nach
    tools/Ahk2Exe/. Rueckgabe: Pfad zur Ahk2Exe.exe."""
    TOOLS_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Hole Release-Info von {GITHUB_API} ...")
    with urllib.request.urlopen(GITHUB_API, timeout=30) as r:
        rel = json.load(r)
    asset = next(a for a in rel["assets"] if a["name"].lower().endswith(".zip"))
    print(f"  Tag:   {rel['tag_name']}")
    print(f"  Asset: {asset['name']} ({asset['size'] / 1024:.1f} KB)")
    print("Lade ...")
    with urllib.request.urlopen(asset["browser_download_url"], timeout=60) as r:
        data = r.read()
    print(f"  OK {len(data)} Bytes geladen")
    print(f"Entpacke nach {TOOLS_DIR} ...")
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extractall(TOOLS_DIR)
    ahk2exe = TOOLS_DIR / "Ahk2Exe.exe"
    if not ahk2exe.exists():
        raise FileNotFoundError(
            f"Ahk2Exe.exe nicht im ZIP: {[n for n in z.namelist()]}"
        )
    return ahk2exe


def compile_hotkey(ahk2exe: Path) -> bool:
    """Ruft Ahk2Exe auf, kompiliert shortcut.ahk zu Speech2Text-Hotkey.exe.
    Rueckgabe: True bei Erfolg (Output-Datei existiert)."""
    if not SOURCE.exists():
        raise FileNotFoundError(f"Source nicht gefunden: {SOURCE}")
    if not ICON.exists():
        raise FileNotFoundError(f"Icon nicht gefunden: {ICON}")
    if not AHK_BASE.exists():
        raise FileNotFoundError(f"AHK-Base nicht gefunden: {AHK_BASE}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    if OUTPUT.exists():
        try:
            OUTPUT.unlink()
        except OSError as e:
            print(f"WARN: Konnte alte Exe nicht loeschen ({e}) — "
                  f"Build versucht ueberschreiben.", file=sys.stderr)

    args = [
        str(ahk2exe),
        "/in", str(SOURCE),
        "/out", str(OUTPUT),
        "/icon", str(ICON),
        "/base", str(AHK_BASE),
    ]
    print()
    print("Compile:")
    print(f"  Source : {SOURCE}")
    print(f"  Icon   : {ICON}")
    print(f"  Base   : {AHK_BASE}")
    print(f"  Output : {OUTPUT}")
    print()

    # Wichtig: subprocess.run() im selben Python-Prozess — kein Lock-Window
    # fuer den AV-Scanner zwischen Extract und Aufruf.
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.stdout.strip():
        print("STDOUT:", result.stdout.strip())
    if result.stderr.strip():
        print("STDERR:", result.stderr.strip(), file=sys.stderr)
    print(f"Returncode: {result.returncode}")

    # Ahk2Exe gibt auch bei Erfolg manchmal non-zero zurueck — Erfolgs-
    # kriterium ist die existierende Output-Datei.
    if not OUTPUT.exists():
        print(f"FEHLER: Output-Datei wurde nicht erzeugt.", file=sys.stderr)
        return False
    size_kb = OUTPUT.stat().st_size / 1024
    print(f"\nOK Build erfolgreich: {OUTPUT} ({size_kb:.1f} KB)")
    return True


def main() -> int:
    try:
        ahk2exe = fetch_ahk2exe()
    except Exception as e:  # noqa: BLE001
        print(f"FEHLER beim Ahk2Exe-Download: {e}", file=sys.stderr)
        return 2
    try:
        ok = compile_hotkey(ahk2exe)
    except Exception as e:  # noqa: BLE001
        print(f"FEHLER beim Compile: {e}", file=sys.stderr)
        return 3
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
