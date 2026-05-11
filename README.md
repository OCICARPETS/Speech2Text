# Speech2Text

Windows-Produktivitätstool — Caps Lock halten, sprechen, loslassen → optimierter Text erscheint im aktiven Fenster.

- **Transkription:** OpenAI `gpt-4o-transcribe`
- **Optimierung:** OpenAI `gpt-4o-mini` (Grammatik, Interpunktion, Füllwörter raus)
- **Hotkey:** Caps Lock (Standard-Großschreibung deaktiviert)
- **Ausgabe:** Zwischenablage + Auto-Paste (Ctrl+V)

> Doku & Architektur siehe `CLAUDE.md`, `PLANUNG.md`, `Projektplanung/`.

---

## Installation (einmalig)

### 1. Python 3.11+
```bash
python --version
```
Falls nicht installiert: https://www.python.org/downloads/

### 2. AutoHotkey v2
https://www.autohotkey.com/download/ (v2, nicht v1!)

### 3. Dependencies
```bash
cd "projekte/entwicklung/speech2text"
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 4. OpenAI-Key
```bash
copy .env.example .env
```
`.env` öffnen und `OPENAI_API_KEY=sk-...` eintragen.
API-Keys: https://platform.openai.com/api-keys

---

## Benutzung

### Schritt A — Daemon starten (muss laufen, solange du diktierst)
```bash
scripts\start-daemon.bat
```
Console bleibt offen. Zeigt Status-Meldungen bei jedem Diktat. Beenden: `Strg+C`.

### Schritt B — AHK-Hotkey laden
Doppelklick auf `src\shortcut.ahk` im Explorer.
(AHK v2 muss installiert sein. Das Skript läuft dann als Tray-Icon im Hintergrund.)

### Schritt C — Diktieren
1. Cursor in ein beliebiges Textfeld (Outlook, Word, Browser, VS Code, Teams, …).
2. **Caps Lock gedrückt halten** → Aufnahme läuft.
3. Sprechen.
4. **Loslassen** → nach ~1–2 s erscheint der optimierte Text an der Cursor-Position.

---

## Troubleshooting

| Symptom | Ursache / Fix |
|---|---|
| Caps-Lock feuert, aber nichts passiert | Daemon läuft nicht. `scripts\start-daemon.bat` prüfen. |
| `OPENAI_API_KEY fehlt` | `.env` nicht angelegt oder leer. `.env.example` → `.env` kopieren, Key eintragen. |
| `Port 17321 nicht verfügbar` | Daemon läuft bereits in anderem Fenster — oder anderer Prozess blockiert Port. |
| Caps-Lock-LED leuchtet weiter bei Großschreibung | Falscher Text-Editor? AHK muss geladen sein (Tray-Icon prüfen). |
| TrayTip „Daemon nicht erreichbar" | Daemon abgestürzt → Console öffnen, Fehler lesen. |
| Aufnahme leer / keine Audiodaten | Falsches Mikrofon als Default? Windows-Sound-Einstellungen prüfen. |
| Umlaute im Text falsch | Sollte nicht passieren (`language="de"`). Wenn doch: Daemon-Output ins Briefing-Chat posten. |

---

## Autostart bei Windows-Login (optional)

Siehe `PLANUNG.md` Abschnitt 3.5. Einfachste Variante:
1. `Win+R` → `shell:startup` (öffnet den Autostart-Ordner).
2. Rechtsklick → Verknüpfung zu `scripts\start-daemon.bat` anlegen.
3. Rechtsklick → Verknüpfung zu `src\shortcut.ahk` anlegen.

Beide starten beim nächsten Windows-Login automatisch.

---

## Struktur

```
speech2text/
├── CLAUDE.md                 → Regeln, Verbote, Doku-Wegweiser
├── PLANUNG.md                → Vision, Ist-Zustand, Roadmap, Entscheidungen
├── BRIEFING.md               → User-Antworten zum Projektstart
├── README.md                 → diese Datei (Quick-Start)
├── .env.example              → Template für Secrets
├── .gitignore
├── requirements.txt
├── .meta.json                → Dashboard-Metadaten
├── tasks/
│   └── current-task.md       → Tagesstand, zuerst lesen
├── scripts/
│   └── start-daemon.bat      → Daemon-Launcher
├── src/
│   ├── recorder.py           → Python-Daemon
│   └── shortcut.ahk          → AutoHotkey v2 Hotkey
└── Projektplanung/
    ├── WORKFLOW.md           → Session-Rituale
    ├── FEATURE_UEBERSICHT.md → Feature-Wunschliste
    ├── 01_Hotkey-Trigger/
    │   └── SPEZIFIKATION.md
    ├── 02_Audio-Daemon/
    │   └── SPEZIFIKATION.md
    ├── 03_KI-Pipeline/
    │   └── SPEZIFIKATION.md
    └── 04_Text-Ausgabe/
        └── SPEZIFIKATION.md
```
