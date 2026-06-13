# Feature-Übersicht — Speech2Text

> Bearbeitbare **Wunschliste** / Gesamtübersicht aller Features mit aktuellem Stand.
> Letzte Aktualisierung: 2026-04-24
>
> **Zweck:** Kompakte Sicht auf alle Features. Technische Tiefe liegt pro Feature in `NN_.../SPEZIFIKATION.md`.
>
> **Priorität:** 1 = MVP-Kern, 2 = mittelfristig, 3 = langfristig/optional.

## Aktive Feature-Ordner

| Ordner | Thema | Priorität | Status |
|---|---|---|---|
| `01_Hotkey-Trigger` | AutoHotkey v2 — Caps Lock Push-to-Talk, HTTP-Ping an Daemon | 1 | ✅ MVP |
| `02_Audio-Daemon` | Python-Daemon, HTTP-Server, sounddevice-Aufnahme im Speicher | 1 | ✅ MVP |
| `03_KI-Pipeline` | `gpt-4o-transcribe` → `gpt-4o-mini` Optimierung | 1 | ✅ MVP |
| `04_Text-Ausgabe` | `pyperclip` + `pyautogui` (Ctrl+V) ins aktive Fenster | 1 | ✅ MVP |
| `05_Einstellungsmenue` | tkinter-GUI für per-User Config (API-Key DPAPI, Tonalität, Paste-Modus, Hotkey, Sprache) | 2 | 🔜 |
| `06_Installer` | PyInstaller + Ahk2Exe + Inno Setup → `Speech2Text-Setup.exe` für andere OCI-PCs | 2 | 🔜 |
| `08_Multi-User-Terminal-Server` | Multi-Session: Port-pro-Session (Port 0 + per-User-`daemon.port`) + Named-Mutex-Single-Instance — schließt den Cross-Session-Leak (maschinenweiter Port 17321) | 2 | ✅ Fertig (2026-06) |

Für den **Tagesstand** und laufende Arbeit siehe `tasks/current-task.md`.

---

### 01 — Hotkey-Trigger
**Priorität:** 1 (MVP)
**Aktueller Stand:** ✅ Code geschrieben, ungetestet
**Kurzbeschreibung:** AutoHotkey v2-Skript. Deaktiviert Caps-Lock-Standardverhalten dauerhaft. Push-to-Talk: `Capslock::` → `POST /start`, `Capslock up::` → `POST /stop`. Kommunikation via `WinHttp.WinHttpRequest.5.1` COM-Objekt.
**Meine Ideen/Änderungen:**
1. Tray-Icon mit Status-Ampel (Priorität 2)
2. Kurz-Tipp-Schutz: < 200 ms Caps-Lock-Antippen ignorieren
3. Akustisches Feedback (kurzer Ton bei Start/Stop)?
→ Details: `01_Hotkey-Trigger/SPEZIFIKATION.md`

---

### 02 — Audio-Daemon
**Priorität:** 1 (MVP)
**Aktueller Stand:** ✅ Code geschrieben, ungetestet
**Kurzbeschreibung:** Python-HTTP-Server (`http.server` stdlib) auf `127.0.0.1:17321`. State-Machine IDLE → RECORDING → PROCESSING → IDLE. Audio wird mit `sounddevice` in 16 kHz Mono int16 aufgenommen, nur im RAM gehalten.
**Meine Ideen/Änderungen:**
1. Audio-Gerät wählbar machen (Config-Datei oder Env)
2. Max-Dauer-Limit (z.B. 60 s) mit automatischem Stop
3. Live-VU-Meter in Console?
→ Details: `02_Audio-Daemon/SPEZIFIKATION.md`

---

### 03 — KI-Pipeline
**Priorität:** 1 (MVP)
**Aktueller Stand:** ✅ Code geschrieben, ungetestet
**Kurzbeschreibung:** Zwei-Schritt: (1) `gpt-4o-transcribe` nimmt WAV-Bytes und liefert deutsches Roh-Transkript; (2) `gpt-4o-mini` bekommt Rohtext + festen System-Prompt (Grammatik, Interpunktion, Füllwörter entfernen) und liefert polierten Text.
**Meine Ideen/Änderungen:**
1. Modus-Schalter (E-Mail / Notiz / Stichpunkt) via zweitem Hotkey
2. Kontext-Injection: aktives Fenstertitel in Optimierungs-Prompt
3. Temperatur konfigurierbar
→ Details: `03_KI-Pipeline/SPEZIFIKATION.md`

---

### 04 — Text-Ausgabe
**Priorität:** 1 (MVP)
**Aktueller Stand:** ✅ Code geschrieben, ungetestet
**Kurzbeschreibung:** Nach Optimierung → `pyperclip.copy(text)` in Windows-Zwischenablage → kurze Sleep (50 ms) → `pyautogui.hotkey("ctrl","v")` in aktives Fenster.
**Meine Ideen/Änderungen:**
1. Auto-Paste abschaltbar (manche Textfelder reagieren komisch auf SendInput)
2. Opt-In: vorigen Clipboard-Inhalt restaurieren nach Paste
3. Fallback: wenn Paste fehlschlägt, TrayTip mit „Text ist in Zwischenablage"
→ Details: `04_Text-Ausgabe/SPEZIFIKATION.md`

---

## Zusätzliche Use Cases / Ideen (Long-List)

- [x] **Autostart bei Windows-Login** — Startup-Ordner-Variante via PowerShell-Install-Skript, Logout/Login-Test am 2026-04-24 validiert
- [x] **Tray-Status-Ampel** — Tooltip-basiert (offline/bereit/Aufnahme/verarbeite), AHK pollt `/health` 1×/s
- [x] **Fehler-Toast** — TrayTip bei neuen Pipeline-Fehlern, Python schreibt `last_error`+`ts` in `/health`
- [x] **Custom Tray-Menü** — Log öffnen, Daemon neu starten, Beenden; Einstellungen-Platzhalter
- [x] **Eigenes Tray-Icon** — Electric-Blue-Kreis mit „S2T" (`assets/speech2text.ico`), generiert via `create-icon.ps1`
- [x] **Hidden-Daemon + File-Log** — `pythonw.exe` + stdout/stderr → `%APPDATA%\Speech2Text\daemon.log`
- [x] **`/shutdown`-Endpoint + Hard-Exit** — `os._exit(0)` wegen sounddevice/openai Non-Daemon-Threads
- [x] **Mode-Switch-Toast (Custom-Popup)** — eigenes Tk-Toast unten rechts statt pystray-System-Toast: 1,5 s, Coalesce/Timer-Reset, theme-aware, alle Tray-Meldungen darüber (`src/toast.py`, v1.4 2026-06-05). Details `01_Hotkey-Trigger/SPEZIFIKATION.md` §7c.
- [x] **Ad-hoc Mode-Umbenennung in der Liste** — Modus-Dropdown aktualisiert sich bei Anwenden/Speichern (`_refresh_mode_list` in `src/settings.py`, v1.4 2026-06-05). Details `05_Einstellungsmenue/SPEZIFIKATION.md` §8.
- [x] **Multi-User / Terminal-Server-Tauglichkeit** — Port-pro-Session (Daemon bindet Port 0, hinterlegt ihn in per-User-`daemon.port`), Single-Instance via Named Mutex `Local\…`; behebt den maschinenweiten Port-17321-Cross-Session-Leak (Ansatz B, 2026-06-13). Details `08_Multi-User-Terminal-Server/SPEZIFIKATION.md`.
- [ ] **Kontext-bewusste Optimierung** — pro Fenstertitel anderer Prompt-Hint (Prio 3)
- [ ] **Diktat-Historie** — letzte 20 Diktate lokal (opt-in, verschlüsselt) (Prio 3)
- [ ] **Transfer in AussendienstAPP** — Sprachnotiz-Feature am iPhone-Browser (eigenes Projekt, Prio 3)
- [ ] **Multi-Sprache** — Auto-Detect DE/EN statt `language="de"` fest *(2026-04-24: bewusst verschoben — DE bleibt fest im MVP)*
- [ ] **Akustisches Feedback** — dezenter Ton bei Start/Stop/Fertig
- [ ] **Pre-Recording-Ringpuffer** — Daemon hält ~500 ms Audio permanent gepuffert, hängt bei `/start` die letzten 300–500 ms vor die Aufnahme → kein verschlucktes erstes Wort (Details in `02_Audio-Daemon/SPEZIFIKATION.md` §8)
- [ ] **Kurz-Tipp-Schutz (server-seitig)** — Worker verwirft Aufnahmen < 300 ms still (kein OpenAI-Call, kein Toast) gegen versehentliches Caps-Lock-Antippen
- [ ] **API-Kosten-Zähler** — kumulierte Token-Kosten im Tray anzeigen
