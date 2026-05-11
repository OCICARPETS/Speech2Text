# SPEZIFIKATION: Einstellungsmenü

*Status: 🔜 Geplant · Priorität: 2 · Erstellt: 2026-04-24*

---

## 1. Vision & Scope

Ein **grafisches Einstellungsmenü**, das Speech2Text pro Windows-Nutzer konfigurierbar macht, ohne dass der Anwender Dateien editieren muss. Das Menü ist die notwendige Ergänzung zum geplanten Installer (`Projektplanung/06_Installer`) — auf einem neu installierten Client muss der Anwender seinen API-Key eintragen und das Paste-Verhalten anpassen können, ohne `.env`-Dateien anzulegen oder Python-Code zu öffnen.

Das Menü ist **keine Konsole und keine Webapp** — ein kleines natives Windows-Fenster, das per Tray-Icon-Rechtsklick oder eigenen Hotkey geöffnet wird, Änderungen sofort live übernimmt und schließt.

## 2. Enthaltene Anforderungen / Use Cases

- **A1 — OpenAI API-Key pro Nutzer:** Eingabefeld für den API-Key. Verschlüsselte Ablage in `%APPDATA%\Speech2Text\config.json` (Windows-DPAPI per `ctypes` → Dekrypt nur für den eingeloggten User möglich).
- **A2 — Modus-Auswahl (9 Modi, ersetzt bisherigen optimize-Toggle + Tonalität):** Ein einziges Dropdown steuert die komplette Verarbeitung nach der Transkription. „Raw Draft" liefert das reine Roh-Transkript (ohne `gpt-4o-mini`-Call), alle anderen Modi nutzen `gpt-4o-mini` mit einem mode-spezifischen System-Prompt. **Standard: `Polished Text`.**

    | # | UI-Name | Interner Key | System-Prompt |
    |---|---|---|---|
    | 1 | `Raw Draft` | `raw_draft` | *(kein `gpt-4o-mini`-Call — Rohtranskript 1:1)* — „Gib die Transkription absolut wortgetreu aus. Korrigiere nichts, füge nichts hinzu, entferne nichts." |
    | 2 | `Clean Dictation` | `clean_dictation` | „Entferne ausschließlich Füllwörter (äh, em, halt, so) und Wortwiederholungen. Behalte die Struktur exakt bei." |
    | 3 | `Polished Text` (Default) | `polished_text` | „Entferne Füllwörter und korrigiere Grammatik sowie Interpunktion. Der Text soll sauber, aber inhaltlich unverändert bleiben." |
    | 4 | `Smart Flow` | `smart_flow` | „Optimiere den Text für professionelle Lesbarkeit. Korrigiere Grammatik, entferne Füllwörter und glätte Satzübergänge, während der Kerngehalt präzise erhalten bleibt." |
    | 5 | `Mirror Tone` | `mirror_tone` | „Korrigiere Grammatik und entferne Füllwörter. Achte penibel darauf, die ursprüngliche Tonalität und den individuellen Sprachstil des Sprechers beizubehalten." |
    | 6 | `Warm & Friendly` | `warm_friendly` | „Korrigiere Grammatik und entferne Füllwörter. Schreibe den Text in einem besonders freundlichen, nahbaren und wertschätzenden Tonfall um." |
    | 7 | `Executive / Boss` | `executive` | „Korrigiere Grammatik und entferne Füllwörter. Formuliere den Text wie eine Führungskraft: klar, bestimmt, effizient und ergebnisorientiert." |
    | 8 | `Unleashed (Rage)` | `unleashed` | „Korrigiere Grammatik und entferne Füllwörter. Behalte den Sinn, aber formuliere den Text mit maximaler Intensität, Leidenschaft und einer aggressiven 'Biest'-Attitüde." |
    | 9 | `Claude Code Prompt` | `claude_code_prompt` | „Wandle die gesprochene Notiz in einen präzisen Prompt für Claude Code (CLI-Coding-Agent) um. Regeln: Imperativ statt Höflichkeitsform ('Refactor X' statt 'Könntest du bitte X'). Füllwörter, Selbstkorrekturen und Ähs entfernen; Sinn unverändert lassen. Datei-/Ordnerpfade, Funktions-, Variablen- und Klassennamen, Commands und Flags in \\`backticks\\` setzen. Wenn der Sprecher Kontext UND Aufgabe nennt: mit kurzen Fettdruck-Labels strukturieren ('**Kontext:**' / '**Aufgabe:**' / '**Constraints:**'). Bei reinen Einzeilern: als Fließtext lassen. Nichts hinzudichten: keine erfundenen Pfade, keine technischen Vermutungen, keine Beispiele, die der Sprecher nicht erwähnt hat. Alle konkreten Details (Zahlen, Namen, Versionen, Pfade) wörtlich übernehmen. Ergänzungen des Sprechers ('und dann vielleicht noch X') als 'optional: X' mitnehmen. Ausgabe ist der reine Prompt-Text — keine Meta-Einleitung, kein 'Hier ist dein Prompt:'." |

- **A3 — Paste-Modus:**
  - `Clipboard + Ctrl+V` (Standard, aktuelles Verhalten)
  - `Nur Clipboard` (User drückt selbst Ctrl+V)
  - `Nur SendInput` (Zeichenweise Tippen, langsamer aber funktioniert in Apps, die Ctrl+V blockieren)
- **A4 — Audio-Device:** Dropdown mit allen verfügbaren Input-Devices aus `sounddevice.query_devices()`. Default = „Windows-Standardgerät (dynamisch)" — bei Headset-Wechsel folgt das Tool dem Windows-Default.
- **A5 — Hotkey konfigurierbar:** Dropdown `Caps Lock` / `F9` / `Ctrl+Alt+R` / `Pause` — schreibt passende AHK-Config-Datei neu.
- **A6 — Sprache fest Deutsch:** `language="de"` ist hartkodiert, kein Einstellungs-Feld. (Entscheidung 2026-04-24 — keine Multi-Sprache-Unterstützung im MVP.)
- **A7 — Live-Test:** „Mikrofon testen"-Knopf — nimmt 3 s auf, spielt ab (`sounddevice.play`), zeigt Pegel.
- **A8 — Speichern + Live-Reload:** Klick auf „Speichern" schreibt Config und sendet `POST /reload-config` an den Daemon → keine Daemon-Restart nötig.

## 3. Zielgruppe / Zielumgebung

- **Nutzer:** Endanwender auf OCI-Arbeitsplätzen (Daniel + ggf. weitere Kollegen). Kein Entwickler-Kontext — klicken, nicht Datei-editieren.
- **Plattform:** Windows 10/11. Bei Installer-Bundle: Python nicht vorausgesetzt — GUI-Code ist Teil des PyInstaller-Bundles.

## 4. Abgrenzung

**Bewusst nicht im Scope:**
- **Kein Multi-Profil-Support** (ein User = eine Config). Wer zwischen „E-Mail-Modus" und „Code-Kommentar-Modus" wechseln will, nutzt den Tonalitäts-Dropdown.
- **Keine Historie / Statistik / Token-Kosten-Anzeige** (eigenes Priorität-3-Feature).
- **Keine Cloud-Sync der Config** — pro Gerät lokal.
- **Keine Webapp** — natives Fenster.

## 5. Technische Skizze / Architektur

### Tech-Wahl
- **GUI:** `tkinter` aus Python-Stdlib — keine Extra-Dependency, in PyInstaller trivial mit zu packen. Kein Qt/Electron-Overhead.
- **Config-Format:** JSON (lesbar, editierbar für Power-User).
- **Speicherort:** `%APPDATA%\Speech2Text\config.json` (pro Windows-User).
- **API-Key-Schutz:** `CryptProtectData` (DPAPI) via `ctypes` — Key wird im JSON nur als Base64-verschlüsselter Blob abgelegt. Nur der eingeloggte User kann entschlüsseln, nicht mal ein Admin auf dem gleichen System.
- **Live-Reload:** Daemon hat neuen Endpoint `POST /reload-config` — liest Config-Datei neu, lädt OpenAI-Client mit neuem Key, wechselt Prompt/Device.

### Config-Schema (Entwurf)

```json
{
  "api_key_encrypted": "base64-blob",
  "mode": "polished_text",
  "paste_mode": "clipboard_ctrl_v",
  "audio_device": null,
  "hotkey": "capslock"
}
```

**Mode-Werte:** `raw_draft` · `clean_dictation` · `polished_text` (Default) · `smart_flow` · `mirror_tone` · `warm_friendly` · `executive` · `unleashed` · `claude_code_prompt`.

**Sprache:** `language="de"` ist nicht Teil der Config — hartkodiert im Transcribe-Call.

### Startpunkte für Settings-Fenster
1. **Tray-Icon-Rechtsklick → „Einstellungen…"** (AHK setzt Tray-Menü-Eintrag, startet `.venv/Scripts/python.exe settings.py` bzw. `speech2text-settings.exe`).
2. **Eigener Hotkey** (z.B. `Ctrl+Alt+S` — konfigurierbar): öffnet das Fenster aus laufendem System.
3. **Aus Installer heraus:** Nach Setup-Abschluss „Einstellungen jetzt öffnen" — erzwingt API-Key-Eingabe, sonst läuft der Daemon sowieso nicht.

## 6. Umsetzungsplan

### Phase 1 — Config-Layer einziehen (Voraussetzung)
- [ ] `config.py` mit `load_config()`, `save_config()`, DPAPI-Helpers.
- [ ] `recorder.py` refactort: liest statt aus `.env` aus `config.json`. `.env` bleibt als Entwickler-Fallback (wenn keine Config existiert).
- [ ] `/reload-config` Endpoint hinzufügen.

### Phase 2 — Settings-GUI (`settings.py`)
- [ ] tkinter-Layout: 5 Eingabefelder (API-Key, Modus-Dropdown mit 9 Optionen, Paste-Modus, Audio-Device, Hotkey), „Speichern"-Button, „Mikrofon testen"-Button.
- [ ] API-Key-Feld: `show="*"` (Maskierung), „Anzeigen"-Toggle.
- [ ] Modus-Dropdown: zeigt UI-Namen aus A2-Tabelle, speichert internen Key. Default-Auswahl: `Polished Text`.
- [ ] Mikrofon-Test: 3 s Aufnahme + Pegel-Visualisierung + Wiedergabe.
- [ ] Speichern → Config schreiben + `POST /reload-config`.

### Phase 3 — AHK-Integration
- [ ] Tray-Menü-Eintrag „Einstellungen…" → startet `settings.py` bzw. `-settings.exe`.
- [ ] Hotkey für Settings (aus Config gelesen).
- [ ] AHK-Skript liest Config, um Haupt-Hotkey zu setzen (`capslock` / `F9` / etc.).

## 7. Deployment

- **Entwicklung:** `settings.py` neben `recorder.py`. Start per `.venv/Scripts/python.exe src/settings.py`.
- **Installer-Bundle (Priorität 2, siehe 06_Installer):** Eigener `speech2text-settings.exe` aus PyInstaller. Autostart wird NICHT auf Settings gesetzt — Settings öffnet sich nur bei erstem Start (wenn Config leer) oder manuell.

## 8. Offene Punkte und Entscheidungen

- [ ] **GUI-Framework endgültig tkinter?** Alternative: `CustomTkinter` (modernes Look&Feel, extra Dep ~5 MB). Für MVP tkinter — Look second.
- [ ] **API-Key validieren bei Speichern?** Test-Call an `client.models.list()` → zeigt sofort, ob Key gültig ist. Erhöht UX, braucht aber Internet beim Speichern.
- [x] **Audio-Device: Default dynamisch** (2026-04-24) — Windows-Standardgerät folgt bei Headset-Wechsel automatisch. Manuelle Wahl per Dropdown bleibt möglich.
- [x] **Modus-Prompts festgelegt** (2026-04-24) — 9 Modi siehe A2. Keine A/B-Tests geplant, User-Feedback im Betrieb entscheidet.
- [ ] **Multi-User auf Terminalserver?** Wenn mehrere Kollegen per RDP auf denselben Server → jeder hat eigenen `%APPDATA%`, also ok. Port 17321 kollidiert aber! Lösung: Daemon pro User mit Port-Offset (17321 + UID). Oder: Instanz wird beim Login gestartet (nicht als globaler Service). Klären, wenn Multi-User relevant wird.

## 9. Abhängigkeiten / Querverweise

- **Vorbedingung:** Config-Layer in `recorder.py` (Phase 1 dieses Features) muss vor dem Installer (`06_Installer`) fertig sein — der Installer soll keinen Nutzer zwingen, `.env` selbst zu schreiben.
- **Konsequenz für aktuelle Verbote:** „Kein pip install ohne Pin" und „kein Disk-Write von Audio" bleiben. **Neu:** API-Key in `config.json` ist DPAPI-verschlüsselt — Klartext-Key nur temporär im Daemon-Speicher.

## 10. Historie & Verweise

- **Entstehung:** User-Rückmeldung 2026-04-24 nach Installations-Check — Idee kam auf, weil pro lokaler Client ein eigener API-Key + eigene Präferenzen (Paste-Modus, Tonalität) sinnvoll sind.
- **Zugehörige Features:** `03_KI-Pipeline` (Tonalität-Prompts), `04_Text-Ausgabe` (Paste-Modus), `06_Installer` (API-Key-Eingabe-Fluss).
- **Referenzen:**
  - Windows DPAPI via Python: https://learn.microsoft.com/en-us/windows/win32/seccrypto/cryptprotectdata
  - tkinter Docs: https://docs.python.org/3/library/tkinter.html
