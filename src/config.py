"""Config-Layer für Speech2Text — JSON in %APPDATA% + DPAPI-Key-Verschlüsselung.

Ablage: %APPDATA%\\Speech2Text\\config.json

Der OpenAI-API-Key wird per Windows-DPAPI (CryptProtectData) verschlüsselt und
als Base64 im JSON abgelegt. Entschlüsseln kann nur der eingeloggte Windows-User,
auch kein Admin des gleichen Systems.

Fallback: wenn config.json fehlt oder keinen Key enthält, nutzt recorder.py
OPENAI_API_KEY aus .env (nur für Entwicklung). Keine automatische Migration.

Details: Projektplanung/05_Einstellungsmenue/SPEZIFIKATION.md §5 + Config-Schema.
"""
from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path

# --- Modi (siehe 05_Einstellungsmenue/SPEZIFIKATION.md §A2) -----------------

# prompt=None signalisiert Raw-Draft: kein gpt-4o-mini-Call, Rohtranskript 1:1.
# Sonderfall "manual": prompt wird zur Laufzeit aus config["manual_prompt"]
# gezogen — siehe get_mode_prompt(). Leerer manual_prompt → wie Raw Draft.
MODES: dict[str, dict[str, str | None]] = {
    "raw_draft": {
        "ui_name": "Raw Draft",
        "description": "Roh-Transkript 1:1 — keine Optimierung, kein "
                       "Zweit-API-Call. Schnellste Variante.",
        "prompt": None,
    },
    "clean_dictation": {
        "ui_name": "Clean Dictation",
        "description": "Entfernt nur Füllwörter (äh, em, halt) und "
                       "Wortwiederholungen. Struktur bleibt exakt erhalten.",
        "prompt": (
            "Entferne ausschließlich Füllwörter (äh, em, halt, so) und "
            "Wortwiederholungen. Behalte die Struktur exakt bei. "
            "Antworte ausschließlich mit dem bereinigten Text, ohne "
            "Einleitung oder Kommentar."
        ),
    },
    "polished_text": {
        "ui_name": "Polished Text",
        "description": "Korrigiert Grammatik und Interpunktion, entfernt "
                       "Füllwörter. Inhaltlich unverändert.",
        "prompt": (
            "Entferne Füllwörter und korrigiere Grammatik sowie "
            "Interpunktion. Der Text soll sauber, aber inhaltlich "
            "unverändert bleiben. "
            "Antworte ausschließlich mit dem bereinigten Text, ohne "
            "Einleitung oder Kommentar."
        ),
    },
    "smart_flow": {
        "ui_name": "Smart Flow",
        "description": "Wie Polished, plus geglättete Satzübergänge — "
                       "professionelle Lesbarkeit, Kerngehalt erhalten.",
        "prompt": (
            "Optimiere den Text für professionelle Lesbarkeit. Korrigiere "
            "Grammatik, entferne Füllwörter und glätte Satzübergänge, "
            "während der Kerngehalt präzise erhalten bleibt. "
            "Antworte ausschließlich mit dem optimierten Text, ohne "
            "Einleitung oder Kommentar."
        ),
    },
    "mirror_tone": {
        "ui_name": "Mirror Tone",
        "description": "Behutsame Korrektur — behält Tonalität und "
                       "individuellen Sprachstil bewusst bei.",
        "prompt": (
            "Korrigiere Grammatik und entferne Füllwörter. Achte penibel "
            "darauf, die ursprüngliche Tonalität und den individuellen "
            "Sprachstil des Sprechers beizubehalten. "
            "Antworte ausschließlich mit dem bereinigten Text, ohne "
            "Einleitung oder Kommentar."
        ),
    },
    "warm_friendly": {
        "ui_name": "Warm & Friendly",
        "description": "Schreibt freundlich, nahbar und wertschätzend um.",
        "prompt": (
            "Korrigiere Grammatik und entferne Füllwörter. Schreibe den "
            "Text in einem besonders freundlichen, nahbaren und "
            "wertschätzenden Tonfall um. "
            "Antworte ausschließlich mit dem umgeschriebenen Text, ohne "
            "Einleitung oder Kommentar."
        ),
    },
    "executive": {
        "ui_name": "Executive / Boss",
        "description": "Führungssprache — klar, bestimmt, effizient, "
                       "ergebnisorientiert.",
        "prompt": (
            "Korrigiere Grammatik und entferne Füllwörter. Formuliere den "
            "Text wie eine Führungskraft: klar, bestimmt, effizient und "
            "ergebnisorientiert. "
            "Antworte ausschließlich mit dem umformulierten Text, ohne "
            "Einleitung oder Kommentar."
        ),
    },
    "unleashed": {
        "ui_name": "Unleashed (Rage)",
        "description": "Maximale Intensität, Leidenschaft, aggressive "
                       "'Biest'-Attitüde — Sinn bleibt, Tonfall eskaliert.",
        "prompt": (
            "Korrigiere Grammatik und entferne Füllwörter. Behalte den "
            "Sinn, aber formuliere den Text mit maximaler Intensität, "
            "Leidenschaft und einer aggressiven 'Biest'-Attitüde. "
            "Antworte ausschließlich mit dem umformulierten Text, ohne "
            "Einleitung oder Kommentar."
        ),
    },
    "claude_code_prompt": {
        "ui_name": "Claude Code Prompt",
        "description": "Wandelt die Notiz in einen präzisen Coding-Prompt "
                       "um (Imperativ, Backticks, Kontext/Aufgabe-Labels).",
        "prompt": (
            "Wandle die gesprochene Notiz in einen präzisen Prompt für "
            "Claude Code (CLI-Coding-Agent) um. Regeln:\n"
            "- Imperativ statt Höflichkeitsform ('Refactor X' statt "
            "'Könntest du bitte X').\n"
            "- Füllwörter, Selbstkorrekturen und Ähs entfernen; Sinn "
            "unverändert lassen.\n"
            "- Datei-/Ordnerpfade, Funktions-, Variablen- und "
            "Klassennamen, Commands und Flags in `backticks` setzen.\n"
            "- Wenn der Sprecher Kontext UND Aufgabe nennt: mit kurzen "
            "Fettdruck-Labels strukturieren ('**Kontext:**' / "
            "'**Aufgabe:**' / '**Constraints:**'). Bei reinen Einzeilern: "
            "als Fließtext lassen.\n"
            "- Nichts hinzudichten: keine erfundenen Pfade, keine "
            "technischen Vermutungen, keine Beispiele, die der Sprecher "
            "nicht erwähnt hat.\n"
            "- Alle konkreten Details (Zahlen, Namen, Versionen, Pfade) "
            "wörtlich übernehmen.\n"
            "- Ergänzungen des Sprechers ('und dann vielleicht noch X') "
            "als 'optional: X' mitnehmen.\n"
            "- Ausgabe ist der reine Prompt-Text — keine Meta-Einleitung, "
            "kein 'Hier ist dein Prompt:'."
        ),
    },
    "manual": {
        "ui_name": "Manuell (eigener Prompt)",
        "description": "Kein Default-Prompt — gib unten einen eigenen ein. "
                       "Leer = wie Raw Draft (kein Optimize-Call).",
        "prompt": None,
    },
}

DEFAULT_MODE = "polished_text"

# --- Schema ------------------------------------------------------------------

CONFIG_FILENAME = "config.json"
APPDATA_SUBDIR = "Speech2Text"

DEFAULT_CONFIG: dict = {
    "api_key_encrypted": "",
    "mode": DEFAULT_MODE,
    "paste_mode": "clipboard_ctrl_v",
    "audio_device": None,
    # Hotkeys in AHK-v2-Notation (^=Ctrl, !=Alt, +=Shift, #=Win, dann Tasten-
    # Token). Wird 1:1 an AHK übergeben.
    #   main:     Haupt-Push-to-Talk-Taste, nimmt im aktiven Modus auf.
    #   cycle:    Tap-Hotkey, schaltet den aktiven Modus durch cycle_loop.
    #   per_mode: optionaler Hotkey pro Modus (Push-to-Talk in fixem Modus,
    #             ändert den aktiven Modus NICHT).
    "hotkeys": {
        "main": "CapsLock",
        "cycle": None,
        "per_mode": {},
    },
    # Liste der mode_ids, die per Cycle durchgeschaltet werden (Reihenfolge
    # entspricht der Liste). Modi nicht in der Liste sind nur über main +
    # eigenen Hotkey erreichbar.
    "cycle_loop": [],
    # Wenn True: Daemon hält den Mikro-Stream dauerhaft offen und füllt einen
    # 500-ms-Ringpuffer. Bei /start werden bis zu preroll_ms vor das Diktat
    # gehängt → kein verschlucktes erstes Wort. Trade-off: Mikro-LED /
    # Win11-Privacy-Indikator leuchten dauerhaft.
    "prebuffer_enabled": True,
    # Pre-Roll in Millisekunden (0–500). Hard-Limit oben = Ringpuffer-Größe.
    "preroll_ms": 300,
    # Post-Roll: Audio NACH Tasten-Loslassen in ms (0–500). Fängt
    # nachschwingende Wörter ab. Kostet Latenz bis zum fertigen Text.
    "postroll_ms": 200,
    # Per-Modus User-Overrides: {mode_id: {"ui_name"?: str, "prompt"?: str}}.
    # Werden gegen MODES-Default gemergt; nur abweichende Felder werden
    # gespeichert. Leerer prompt-String → wirkt wie None (Raw Draft).
    "mode_overrides": {},
    # Legacy (vor Session 5d): eigener Manual-Prompt. Wird in load_config()
    # automatisch nach mode_overrides["manual"]["prompt"] migriert.
    "manual_prompt": "",
}


def config_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    return Path(appdata) / APPDATA_SUBDIR if appdata else Path.home() / ".speech2text"


def config_path() -> Path:
    return config_dir() / CONFIG_FILENAME


# --- DPAPI-Wrapper (Windows) -------------------------------------------------

class _DATA_BLOB(ctypes.Structure):  # noqa: N801 — WinAPI-Struct
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


_crypt32 = ctypes.windll.crypt32
_kernel32 = ctypes.windll.kernel32


def _blob_in(data: bytes) -> _DATA_BLOB:
    buf = ctypes.create_string_buffer(data, len(data))
    blob = _DATA_BLOB()
    blob.cbData = len(data)
    blob.pbData = ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte))
    # buf muss bis nach dem Crypt*-Call am Leben bleiben, sonst sammelt der
    # GC den Puffer ein bevor die WinAPI ihn gelesen hat.
    blob._buf_keepalive = buf  # type: ignore[attr-defined]
    return blob


def _blob_out(blob: _DATA_BLOB) -> bytes:
    data = ctypes.string_at(blob.pbData, blob.cbData)
    _kernel32.LocalFree(blob.pbData)
    return data


def dpapi_encrypt(plaintext: str) -> str:
    """Verschlüsselt Klartext per CryptProtectData (User-Scope).
    Rückgabe: Base64-String fürs JSON. Leer-Input → Leer-Output.
    """
    if not plaintext:
        return ""
    in_blob = _blob_in(plaintext.encode("utf-8"))
    out_blob = _DATA_BLOB()
    ok = _crypt32.CryptProtectData(
        ctypes.byref(in_blob), None, None, None, None, 0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError(f"CryptProtectData fehlgeschlagen (Code {ctypes.get_last_error()})")
    return base64.b64encode(_blob_out(out_blob)).decode("ascii")


def dpapi_decrypt(cipher_b64: str) -> str:
    """Entschlüsselt den Base64-String. Leer-Input → Leer-Output."""
    if not cipher_b64:
        return ""
    in_blob = _blob_in(base64.b64decode(cipher_b64))
    out_blob = _DATA_BLOB()
    ok = _crypt32.CryptUnprotectData(
        ctypes.byref(in_blob), None, None, None, None, 0,
        ctypes.byref(out_blob),
    )
    if not ok:
        raise OSError(f"CryptUnprotectData fehlgeschlagen (Code {ctypes.get_last_error()})")
    return _blob_out(out_blob).decode("utf-8")


# --- Hotkey-Layer (Schritt 6) -----------------------------------------------
# AHK-v2-Notation: ^=Ctrl, !=Alt, +=Shift, #=Win, dann Tasten-Token.
# Hotkey-Umfang B (siehe Plan): F1–F24, einzelne Sondertasten, Modifier-Kombis
# mit Buchstabe/Zahl/F-Taste/Sondertaste. Kein Modifier-only, keine Maus-Tasten.

HOTKEY_MODIFIERS = "^!+#"
HOTKEY_MODIFIER_ORDER = ("^", "!", "+", "#")

_F_KEYS = frozenset(f"F{i}" for i in range(1, 25))
_SPECIAL_KEYS = frozenset({"CapsLock", "Pause", "Insert", "ScrollLock", "NumLock"})
_LETTER_KEYS = frozenset(chr(c) for c in range(ord("a"), ord("z") + 1))
_DIGIT_KEYS = frozenset(str(d) for d in range(10))

# Whitelist erlaubter Tasten-Tokens. Modifier-only ist nicht erlaubt — es muss
# ein Tasten-Token vorhanden sein.
ALLOWED_HOTKEY_KEYS: frozenset[str] = (
    _F_KEYS | _SPECIAL_KEYS | _LETTER_KEYS | _DIGIT_KEYS
)

# Windows-Reserved: Kombis, die mit OS-Funktionen kollidieren. Keys sind die
# normalisierte Spec (Modifier-Reihenfolge ^!+#), Werte ist die Begründung
# fürs UI.
WINDOWS_RESERVED_HOTKEYS: dict[str, str] = {
    "#l":       "Win+L sperrt den Bildschirm",
    "#e":       "Win+E öffnet den Datei-Explorer",
    "#r":       "Win+R öffnet den Ausführen-Dialog",
    "#d":       "Win+D zeigt den Desktop",
    "#i":       "Win+I öffnet die Einstellungen",
    "#x":       "Win+X öffnet das Quick-Link-Menü",
    "^Esc":     "Ctrl+Esc öffnet das Startmenü",
    "^!Delete": "Ctrl+Alt+Entf ist Windows-reserviert (Sicherheitsdialog)",
    # Alt+Tab und Ctrl+Shift+Esc enthalten Tasten, die nicht in unserer
    # Whitelist sind — kommen daher gar nicht erst in den Validator.
}


def _split_hotkey_spec(spec: str) -> tuple[str, str]:
    """Trennt Modifier-Prefix vom Tasten-Token. Rückgabe: (modifiers, key).
    Modifier in der Eingabe-Reihenfolge. Whitespace wird ignoriert."""
    s = (spec or "").strip()
    i = 0
    while i < len(s) and s[i] in HOTKEY_MODIFIERS:
        i += 1
    return s[:i], s[i:]


def normalize_hotkey(spec: str) -> str:
    """Normalisiert eine Hotkey-Spec für Vergleich/Konflikt-Detection.
    Modifier in fester Reihenfolge `^!+#`, Tasten-Token unverändert
    (case-sensitive für AHK). Leere/ungültige Specs → leerer String."""
    mods, key = _split_hotkey_spec(spec)
    if not key:
        return ""
    ordered = "".join(m for m in HOTKEY_MODIFIER_ORDER if m in mods)
    return ordered + key


def validate_hotkey(spec: str) -> tuple[bool, str]:
    """Prüft eine Hotkey-Spec gegen Hotkey-Umfang B + Windows-Reserved.
    Rückgabe: (ok, reason). reason leer bei ok, sonst kurze deutsche
    Begründung fürs UI."""
    if not spec or not spec.strip():
        return False, "leer"
    _, key = _split_hotkey_spec(spec)
    if not key:
        return False, "Modifier-only ist nicht erlaubt — drücke zusätzlich eine Taste"
    if key not in ALLOWED_HOTKEY_KEYS:
        return False, f"Taste '{key}' ist nicht zugelassen"
    norm = normalize_hotkey(spec)
    if norm in WINDOWS_RESERVED_HOTKEYS:
        return False, f"Windows-reserviert: {WINDOWS_RESERVED_HOTKEYS[norm]}"
    return True, ""


def _all_hotkey_slots(cfg: dict) -> list[tuple[str, str]]:
    """Liste belegter Hotkey-Slots: [(slot_label, normalized_spec), ...].
    Slot-Labels: 'main', 'cycle', 'mode:<mode_id>'. Leere Slots ausgelassen."""
    hk = (cfg or {}).get("hotkeys") or {}
    out: list[tuple[str, str]] = []
    main = hk.get("main") or ""
    if main:
        out.append(("main", normalize_hotkey(main)))
    cycle = hk.get("cycle") or ""
    if cycle:
        out.append(("cycle", normalize_hotkey(cycle)))
    per_mode = hk.get("per_mode") or {}
    for mode_id, spec in per_mode.items():
        if spec:
            out.append((f"mode:{mode_id}", normalize_hotkey(spec)))
    return out


def find_hotkey_conflicts(cfg: dict) -> list[tuple[str, str, str]]:
    """Doppelbelegungen über alle Hotkey-Slots.
    Rückgabe: [(slot_a, slot_b, normalized_spec), ...]."""
    seen: dict[str, str] = {}
    conflicts: list[tuple[str, str, str]] = []
    for slot, norm in _all_hotkey_slots(cfg):
        if not norm:
            continue
        if norm in seen:
            conflicts.append((seen[norm], slot, norm))
        else:
            seen[norm] = slot
    return conflicts


def cycle_loop_next(cfg: dict, current_mode: str) -> str | None:
    """Nächster Modus im cycle_loop nach current_mode (wrap-around).
    None, wenn cycle_loop leer ist. Wenn current_mode nicht im Loop steht:
    erster Loop-Eintrag (User hat Cycle gedrückt, ist aber im Default-Modus,
    der nicht im Loop ist → springt zum ersten Cycle-Modus)."""
    loop = list((cfg or {}).get("cycle_loop") or [])
    if not loop:
        return None
    if current_mode not in loop:
        return loop[0]
    idx = loop.index(current_mode)
    return loop[(idx + 1) % len(loop)]


# Mapping vom alten cfg["hotkey"]-Wert (kleinbuchstaben-IDs aus Phase 1–5)
# auf AHK-v2-Spec. Wird beim Load einmalig migriert, danach gedroppt.
_LEGACY_HOTKEY_MAP: dict[str, str] = {
    "capslock":   "CapsLock",
    "f9":         "F9",
    "ctrl_alt_r": "^!r",
    "pause":      "Pause",
}


# --- Load / Save / Helpers ---------------------------------------------------

def load_config() -> dict:
    """Lädt config.json. Fehlend oder kaputt → Defaults. Unbekannte Keys
    werden beibehalten (forward-compat).

    Migrationen:
    - Legacy `manual_prompt` (vor Session 5d) → `mode_overrides["manual"]["prompt"]`.
    - Legacy `hotkey` (vor Session 7) → `hotkeys.main` (mit Mapping
      kleinbuchstaben-ID → AHK-v2-Spec).
    """
    path = config_path()
    if not path.exists():
        return dict(DEFAULT_CONFIG)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_CONFIG)
    merged = dict(DEFAULT_CONFIG)
    merged.update(raw)
    # Migration legacy manual_prompt → mode_overrides["manual"]["prompt"]
    legacy_manual = (merged.get("manual_prompt") or "").strip()
    overrides = dict(merged.get("mode_overrides") or {})
    if legacy_manual and "manual" not in overrides:
        overrides["manual"] = {"prompt": legacy_manual}
        merged["mode_overrides"] = overrides
        merged["manual_prompt"] = ""
    elif merged.get("mode_overrides") is None:
        merged["mode_overrides"] = {}
    # Migration legacy hotkey → hotkeys.main
    hotkeys_block = dict(merged.get("hotkeys") or {})
    if not hotkeys_block.get("main"):
        legacy = (merged.get("hotkey") or "").strip().lower()
        hotkeys_block["main"] = _LEGACY_HOTKEY_MAP.get(legacy, "CapsLock")
    hotkeys_block.setdefault("cycle", None)
    if not isinstance(hotkeys_block.get("per_mode"), dict):
        hotkeys_block["per_mode"] = {}
    merged["hotkeys"] = hotkeys_block
    # Alten Single-Hotkey-Key droppen — wird beim nächsten save nicht mehr geschrieben
    merged.pop("hotkey", None)
    if not isinstance(merged.get("cycle_loop"), list):
        merged["cycle_loop"] = []
    return merged


def save_config(cfg: dict) -> None:
    """Schreibt cfg als JSON. api_key_encrypted MUSS bereits verschlüsselt
    sein (Klartext nie in die Datei). Nutze set_api_key() zum Setzen."""
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def set_api_key(cfg: dict, plain_key: str) -> None:
    cfg["api_key_encrypted"] = dpapi_encrypt(plain_key)


def get_api_key(cfg: dict) -> str:
    return dpapi_decrypt(cfg.get("api_key_encrypted", ""))


def get_mode_default(mode_id: str) -> dict:
    """MODES-Default für einen Modus. Unbekannter Modus → DEFAULT_MODE."""
    return MODES.get(mode_id) or MODES[DEFAULT_MODE]


def get_mode_override(cfg: dict, mode_id: str) -> dict:
    """User-Override für einen Modus oder leeres dict."""
    overrides = (cfg or {}).get("mode_overrides") or {}
    return overrides.get(mode_id) or {}


def get_mode_ui_name(mode_id: str, cfg: dict | None = None) -> str:
    """Anzeigename des Modus: User-Override > MODES-Default."""
    if cfg is not None:
        override = get_mode_override(cfg, mode_id).get("ui_name")
        if override:
            return override
    return get_mode_default(mode_id).get("ui_name", mode_id)


def get_mode_prompt(mode: str, cfg: dict | None = None) -> str | None:
    """System-Prompt für den Modus oder None (= Raw-Draft, kein Optimize-Call).
    Unbekannter Modus → Fallback auf Default-Modus.

    Auflösung:
      1. User-Override aus cfg["mode_overrides"][mode]["prompt"] (falls Key
         existiert). Leerer String → None (Raw-Draft-Verhalten).
      2. MODES[mode]["prompt"] als Default."""
    cfg = cfg or {}
    override = get_mode_override(cfg, mode)
    if "prompt" in override:
        prompt = override["prompt"]
        if isinstance(prompt, str) and not prompt.strip():
            return None
        return prompt
    return get_mode_default(mode).get("prompt")
