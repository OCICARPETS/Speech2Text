"""Speech2Text - Distribution-Build (Variante B).

Packt aus build/dist/ + assets/ + scripts/dist-templates/ ein
selbstextrahierendes ZIP-Paket fuer einfache Verteilung.

Inhalt der ZIP:
  Speech2Text-v{VERSION}/
    Speech2Text-Daemon.exe
    Speech2Text-Hotkey.exe   (ab v1.3: Python-Tray-App, kein AutoHotkey mehr)
    Speech2Text-Settings.exe
    assets/speech2text.ico
    install.bat       - kopiert nach %%LocalAppData%%\\Programs\\Speech2Text,
                        legt Desktop-Verknuepfung + optional Autostart an
    uninstall.bat     - sauberer Rueckbau
    README.txt        - Kurzanleitung (inkl. SmartScreen-Hinweis)
    LIZENZEN.txt      - Open-Source-Komponenten + OpenAI-Datenpolitik

Voraussetzung: Daemon-, Hotkey- und Settings-Exe muessen aktuell in
build/dist/ liegen — vorher per build-daemon.ps1, build-tray.ps1 und
build-settings.ps1 bauen.

Aufruf:
  .venv\\Scripts\\python.exe scripts\\build-distribution.py
"""
from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

# Kein .resolve() — siehe Memory feedback_path_resolve_unc_falle (I: ist
# Substituted-Drive auf UNC; resolve() macht externe Tools unzugaenglich).
PROJECT_ROOT = Path(__file__).parent.parent
VERSION = "1.3"
DIST_NAME = f"Speech2Text-v{VERSION}"

SRC_DIST = PROJECT_ROOT / "build" / "dist"
SRC_ASSETS = PROJECT_ROOT / "assets"
TEMPLATES = PROJECT_ROOT / "scripts" / "dist-templates"
OUT_DIR = PROJECT_ROOT / "dist"


def main() -> int:
    required = [
        SRC_DIST / "Speech2Text-Daemon.exe",
        SRC_DIST / "Speech2Text-Hotkey.exe",
        SRC_DIST / "Speech2Text-Settings.exe",
        SRC_ASSETS / "speech2text.ico",
        TEMPLATES / "install.bat",
        TEMPLATES / "uninstall.bat",
        TEMPLATES / "README.txt",
        TEMPLATES / "LIZENZEN.txt",
    ]
    missing = [p for p in required if not p.exists()]
    if missing:
        print("FEHLT:", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        print(
            "\nBundle-Exes vor dem Distribution-Build erzeugen:",
            file=sys.stderr,
        )
        print("  scripts\\build-daemon.ps1", file=sys.stderr)
        print("  scripts\\build-settings.ps1", file=sys.stderr)
        print("  scripts\\build-tray.ps1", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    staging = OUT_DIR / DIST_NAME
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    (staging / "assets").mkdir()

    print(f"Staging: {staging}")
    print("Kopiere Bundle-Exes ...")
    shutil.copy2(SRC_DIST / "Speech2Text-Daemon.exe", staging)
    shutil.copy2(SRC_DIST / "Speech2Text-Hotkey.exe", staging)
    shutil.copy2(SRC_DIST / "Speech2Text-Settings.exe", staging)
    print("Kopiere Icon ...")
    shutil.copy2(SRC_ASSETS / "speech2text.ico", staging / "assets")
    print("Kopiere Templates ...")
    shutil.copy2(TEMPLATES / "install.bat", staging)
    shutil.copy2(TEMPLATES / "uninstall.bat", staging)
    shutil.copy2(TEMPLATES / "README.txt", staging)
    shutil.copy2(TEMPLATES / "LIZENZEN.txt", staging)

    zip_path = OUT_DIR / f"{DIST_NAME}.zip"
    if zip_path.exists():
        zip_path.unlink()
    print(f"Packe ZIP: {zip_path}")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in sorted(staging.rglob("*")):
            if p.is_file():
                arc = p.relative_to(OUT_DIR)
                z.write(p, arc)

    size_mb = zip_path.stat().st_size / 1024 / 1024
    print()
    print("=" * 50)
    print(f"OK Distribution erstellt:")
    print(f"   {zip_path} ({size_mb:.1f} MB)")
    print(f"   Inhalt: siehe {staging}")
    print("=" * 50)
    print()
    print("Test-Plan:")
    print("  1. ZIP auf Zielsystem entpacken")
    print("  2. install.bat doppelklicken")
    print("  3. Frage Autostart beantworten")
    print("  4. Desktop-Verknuepfung 'Speech2Text' aufrufen")
    print("  5. Tray - Einstellungen - API-Key setzen")
    print("  6. Caps Lock halten + diktieren")
    return 0


if __name__ == "__main__":
    sys.exit(main())
