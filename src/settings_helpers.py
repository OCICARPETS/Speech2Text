"""Helper-Konstanten + Funktionen für settings.py.

Auslagerung aus settings.py (>= 934 Zeilen Hard-Limit überschritten).
Inhalt:
  - HELP_*-Texte für den Hilfe-Toggle
  - list_input_devices() — Audio-Device-Enumeration via sounddevice
  - Layout-Konstanten (MIC_TEST_DURATION_S, PASTE_MODES, AUDIO_DEFAULT_LABEL)
"""
from __future__ import annotations

# --- Layout-Konstanten ------------------------------------------------------

MIC_TEST_DURATION_S = 3
SAMPLE_RATE = 16000
PREROLL_MS_MAX = 500    # Hard-Limit aus recorder.py (= Ringpuffer-Größe)
POSTROLL_MS_MAX = 500   # Hard-Limit aus recorder.py
MODE_PROMPT_SOFT_MAX = 4000  # Counter wird ab hier rot — kein hartes Limit

# --- UI-Theme (v1.3 GUI-Refresh) -------------------------------------------

THEME_NAME = "clam"          # konsistent über Windows, weniger 90er-Look
PAD_X = 12                   # horizontales Padding pro Sektion
PAD_Y = 6                    # vertikales Padding pro Feld
TAB_PADDING = (14, 12, 14, 8)  # left, top, right, bottom
GROUP_FONT = ("Segoe UI", 9, "bold")
HINT_FG = "#666"
DIRTY_FG = "#B45309"         # Amber für „geändert, nicht gespeichert"
ERROR_FG = "#c00"

PASTE_MODES: list[tuple[str, str]] = [
    ("clipboard_ctrl_v", "Clipboard + Ctrl+V (Standard)"),
    ("clipboard_only",   "Nur Clipboard (manuell Ctrl+V)"),
    ("send_input",       "Nur SendInput (langsamer, robuster)"),
]

# Wenn audio_device == None → Windows-Default (folgt Headset-Wechsel).
AUDIO_DEFAULT_LABEL = "Windows-Standardgerät (dynamisch)"


# --- Hilfetexte (Hilfe-Toggle in Settings-GUI) ------------------------------

HELP_API_KEY = (
    "OpenAI-API-Key (sk-…). Wird mit Windows-DPAPI verschlüsselt — "
    "nur dieser Windows-Account kann ihn entschlüsseln."
)
HELP_PASTE_MODE = (
    "Wie der Text ins Zielfenster kommt: Clipboard+Strg+V (Standard, "
    "schnell), nur Clipboard (manuell einfügen), SendInput (tippt "
    "Zeichen für Zeichen — robuster in Terminals/CLI)."
)
HELP_AUDIO = (
    "Mikrofon. Standard folgt dem Windows-Default und wechselt automatisch "
    "beim Headset-An-/Abstecken."
)
HELP_HOTKEY = (
    "Haupt-Push-to-Talk-Taste — halten zum Aufnehmen, loslassen zum "
    "Beenden + Transkribieren. Klicke „🎯 Erfassen…“ und drücke die "
    "gewünschte Taste oder Tasten-Kombination."
)
HELP_CYCLE_HOTKEY = (
    "Optional. Tipp-Hotkey, der den aktiven Modus durch die unten "
    "gewählten Cycle-Modi durchschaltet. Leer lassen, wenn nicht "
    "benötigt — Modus-Wechsel geht dann nur über die Modus-Liste oder "
    "Modus-Hotkeys."
)
HELP_MODE_HOTKEY = (
    "Optional. Eigene Push-to-Talk-Taste für genau diesen Modus — "
    "halten startet eine Aufnahme im fixierten Modus, ohne den aktiven "
    "Modus zu ändern."
)
HELP_MODE_IN_CYCLE = (
    "Wenn aktiv, ist dieser Modus Teil der Cycle-Reihe. Reihenfolge "
    "entspricht der Modus-Liste oben."
)
HELP_PREBUFFER = (
    "Mikro permanent offen, fängt das erste Wort vorab ab. Win11 zeigt "
    "dann durchgehend einen Mikro-Indikator im Systemtray."
)
HELP_PREROLL = (
    "Wieviel Audio vor dem Tastendruck angehängt wird (nur bei aktivem "
    "Pre-Recording). 300 ms Default reicht meist; bis 500 ms bei wer "
    "schon im Sprechen drückt."
)
HELP_POSTROLL = (
    "Wieviel Audio nach dem Tasten-Loslassen weiter aufgezeichnet wird — "
    "fängt nachschwingende Wörter ab. Erhöht die Wartezeit bis zum "
    "fertigen Text um diesen Wert."
)
HELP_MODE_NAME = (
    "Anzeigename des Modus — beliebig anpassbar. Leer/identisch mit "
    "Standard → kein Override gespeichert."
)
HELP_MODE_PROMPT = (
    "System-Prompt für den ausgewählten Modus. Editierbar — beim Speichern "
    "wird der Wert gegen den Standard-Prompt verglichen, nur Abweichungen "
    "werden als Override persistiert. Leer = kein Optimize-Call (wie Raw "
    "Draft). Per ↺-Button stellst du den Standard wieder her."
)


# --- Audio-Device-Liste -----------------------------------------------------

def list_input_devices() -> list[tuple[int | None, str]]:
    """Eingabe-Geräte aus sounddevice. Erstes Element: Default (None).

    Lazy-Import von sounddevice — wenn die Lib nicht da ist oder beim
    Query crasht (Treiber-Problem), wird einfach nur der Default-Eintrag
    angeboten. Settings-GUI bleibt nutzbar.
    """
    items: list[tuple[int | None, str]] = [(None, AUDIO_DEFAULT_LABEL)]
    try:
        import sounddevice as sd
        for idx, dev in enumerate(sd.query_devices()):
            if dev.get("max_input_channels", 0) > 0:
                items.append((idx, f"[{idx}] {dev['name']}"))
    except Exception:  # noqa: BLE001
        pass
    return items
