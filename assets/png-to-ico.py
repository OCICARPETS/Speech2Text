"""Speech2Text — PNG → Multi-Size-ICO Konverter.

Erzeugt assets/speech2text.ico aus einer Source-PNG mit allen Standard-
Tray-/Shortcut-Größen (16, 24, 32, 48, 64, 128, 256). Pillow encodet die
großen Größen (256) automatisch als PNG-im-ICO (sonst wäre das ICO ~260 KB).

Source-PNG-Empfehlung:
- Quadratisch (z. B. 256×256 oder 512×512), sonst wird auf die längere Seite
  zentriert quadriert.
- Transparenter Hintergrund (Alpha-Kanal).
- Icon zentral und vollflächig — Pillow scaliert auf 16 px runter und kleine
  Details sehen sonst matschig aus.

Aufruf:
  python assets/png-to-ico.py                            # Default-Pfade
  python assets/png-to-ico.py source.png                 # eigene Source
  python assets/png-to-ico.py source.png target.ico      # eigene Beide

Pillow ist BUILD-Tool, NICHT in requirements.txt. Ad-hoc nachinstallieren:
  .venv\\Scripts\\pip install Pillow
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parent
DEFAULT_TARGET = ASSETS / "speech2text.ico"

ICON_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48),
              (64, 64), (128, 128), (256, 256)]


def find_source() -> Path | None:
    """Wenn kein Source-Argument: erstes nicht-versteckte PNG im Projekt-Root.
    Bevorzugt Dateien mit 'icon' oder 'logo' im Namen."""
    project_root = ASSETS.parent
    candidates = sorted(project_root.glob("*.png"))
    if not candidates:
        return None
    # Bevorzugt Namen mit "icon" oder "logo"
    for c in candidates:
        if "icon" in c.name.lower() or "logo" in c.name.lower():
            return c
    return candidates[0]


def main() -> int:
    if len(sys.argv) > 1:
        src = Path(sys.argv[1])
    else:
        found = find_source()
        if found is None:
            print("❌  Keine Source-PNG angegeben und keine im Projekt-Root "
                  "gefunden.", file=sys.stderr)
            return 1
        src = found
    dst = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_TARGET

    if not src.exists():
        print(f"❌  Source nicht gefunden: {src}", file=sys.stderr)
        return 1

    img = Image.open(src).convert("RGBA")
    print(f"   Source: {src} ({img.size[0]}×{img.size[1]} {img.mode})")

    # Falls nicht quadratisch: auf die größere Seite zentriert quadrieren
    if img.size[0] != img.size[1]:
        side = max(img.size)
        square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        offset = ((side - img.size[0]) // 2, (side - img.size[1]) // 2)
        square.paste(img, offset)
        img = square
        print(f"   → quadriert auf {side}×{side}")

    img.save(dst, format="ICO", sizes=ICON_SIZES)
    print(f"OK Multi-Size-ICO erstellt: {dst}")
    print(f"   Größen: {', '.join(f'{w}×{h}' for w, h in ICON_SIZES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
