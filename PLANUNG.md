# PLANUNG.md — Speech2Text

*Letzte Aktualisierung: 2026-04-24*
*Status: aktiv · Kontext-Dateien: `CLAUDE.md` (Regeln), `Projektplanung/WORKFLOW.md` (Rituale), `tasks/current-task.md` (Tagesstand)*

---

## 1. Vision

Ein **Windows-Diktier-Tool**, das die Texteingabe radikal beschleunigt. Workflow: Caps-Lock gedrückt halten → frei sprechen → loslassen → nach ein bis zwei Sekunden liegt ein sauber formulierter, grammatikalisch korrekter Text in der Zwischenablage und wird direkt ins zuletzt aktive Fenster eingefügt.

Das Tool soll sich wie ein Teil des Betriebssystems anfühlen — keine App öffnen, kein Fenster aktivieren, kein Mausklick. Die einzige Interaktion ist das Halten von Caps Lock.

Technisch ist es ein Pilot für die OpenAI-Audio-APIs: Wenn die Qualität überzeugt, wird das Transkriptions-Modul später in die AussendienstAPP übernommen (Sprachnotizen zu Besuchsberichten).

## 2. Aktueller Stand (Ist-Zustand)

| Bereich | Status | Artefakt |
|---|---|---|
| Projektstruktur (CLAUDE.md, PLANUNG.md, .meta.json) | ✅ Fertig | dieser Ordner |
| Feature-Spezifikationen | ✅ Fertig | `Projektplanung/01_…06_…/SPEZIFIKATION.md` |
| Python-Daemon (`recorder.py`) | ✅ produktiv | `src/recorder.py` |
| AHK-Hotkey (`shortcut.ahk`) | ✅ produktiv | `src/shortcut.ahk` |
| Dependencies / venv | ✅ installiert | `.venv/`, `requirements.txt` |
| **End-to-End-Test auf OCI-DB2 (RDP)** | ✅ **validiert 2026-04-24** | Erster Live-Durchlauf erfolgreich, Tonqualität gut, KI-Optimierung sauber |
| Hidden-Modus + File-Log | ✅ umgesetzt | `scripts/start-daemon-hidden.bat`, `%APPDATA%\Speech2Text\daemon.log` |
| Tray-Status-Ampel (Tooltip-basiert) | ✅ umgesetzt | AHK pollt `/health` 1×/s |
| Fehler-Toast (TrayTip bei neuen Fehlern) | ✅ umgesetzt | Python meldet `last_error`/`last_error_ts` in `/health` |
| Custom Tray-Menü + Icon | ✅ umgesetzt | `assets/speech2text.ico` + AHK `A_TrayMenu` |
| `/shutdown`-Endpoint | ✅ umgesetzt | Hard-Exit via `os._exit(0)` |
| Autostart-Skripte | ✅ erstellt | `scripts/install-autostart.ps1` + `uninstall-autostart.ps1` |
| **Autostart-Final-Test (Logout/Login)** | ✅ validiert 2026-04-24 | Tray-Icon + Daemon + Caps Lock starten automatisch nach Login |
| Einstellungsmenü | 🔜 Nächster Scope | `Projektplanung/05_Einstellungsmenue/` (Variante A) |
| Installer / Distribution | 🔜 Geplant | `Projektplanung/06_Installer/` (Variante C, nach A) |

## 3. Roadmap

### Priorität 1 — Kurzfristig (MVP)

#### 3.1 Hotkey-Trigger ✅
AutoHotkey v2-Skript, Caps-Lock als Push-to-Talk. Standard-Großschreibung deaktiviert. HTTP-POST an lokalen Daemon (`/start` bei Down, `/stop` bei Up).
→ Details: `Projektplanung/01_Hotkey-Trigger/SPEZIFIKATION.md`

#### 3.2 Audio-Daemon ✅
Python-HTTP-Server auf `127.0.0.1:17321`, lauscht auf `/start` und `/stop`. Nimmt Audio im Speicher auf (16 kHz, int16, Mono), keine Disk-Persistenz.
→ Details: `Projektplanung/02_Audio-Daemon/SPEZIFIKATION.md`

#### 3.3 KI-Pipeline ✅
`gpt-4o-transcribe` für Rohtranskript, `gpt-4o-mini` für Grammatik- und Stil-Optimierung mit festem System-Prompt.
→ Details: `Projektplanung/03_KI-Pipeline/SPEZIFIKATION.md`

#### 3.4 Text-Ausgabe ✅
`pyperclip.copy()` in Zwischenablage + `pyautogui.hotkey("ctrl","v")` ins aktive Fenster.
→ Details: `Projektplanung/04_Text-Ausgabe/SPEZIFIKATION.md`

---

### Priorität 2 — Mittelfristig

#### 3.5 Autostart beim Windows-Login ✅
**Umgesetzt:** Startup-Ordner-Variante gewählt. `scripts/install-autostart.ps1` legt zwei `.lnk` in `shell:startup`: Daemon (hidden) + Hotkey. `scripts/uninstall-autostart.ps1` als Gegenstück.

**Validiert 2026-04-24:** Installation ausgeführt, Logout/Login-Durchlauf erfolgreich — Tray-Icon erscheint automatisch, Daemon läuft, Caps-Lock-Push-to-Talk funktioniert ohne manuelles Starten.

#### 3.6 Tray-Status-Ampel ✅ (simple-Variante, tooltip-basiert)
AHK pollt `/health` im 1-Sekunden-Takt und setzt `A_IconTip`:
- „Daemon offline" (Timeout oder Connection-Refused)
- „bereit (Caps Lock halten)" (state=idle)
- „🎤 Aufnahme läuft" (state=recording)
- „⏳ verarbeite …" (state=processing)

Farb-Icon-Wechsel (fancy-Variante) bewusst nicht umgesetzt — Tooltip reicht in der Praxis, spart Asset-Pflege.

#### 3.7 Fehler-Toast ✅
Python merkt sich `last_error` + `last_error_ts` bei jeder Exception im Worker (OpenAI, sounddevice) und bei leerer Transkription / fehlendem Audio. `/health` liefert beides mit. AHK merkt sich den zuletzt gesehenen Timestamp; bei steigendem Wert mit gefülltem `last_error` → `TrayTip` mit der Fehlermeldung.

Keine Spam-Gefahr: `LAST_SEEN_ERROR_TS` verhindert Wiederholungen; beim ersten Poll nach AHK-Start wird der TS nur initialisiert (keine alte Meldung aus vorheriger Session).

#### 3.8 Hidden-Daemon + Custom Tray-Menü + eigenes Tray-Icon ✅ (Scope-Erweiterung während Variante B)
Aus „Autostart" ergab sich die Folge-Frage, wie der Enduser den Daemon komfortabel beenden kann (ohne Task-Manager). Die Lösung wurde als Teil von Variante B mit umgesetzt:

- **Hidden-Modus:** Neue `start-daemon-hidden.bat` nutzt `pythonw.exe` statt `python.exe`. Kein CMD-Fenster. `recorder.py --hidden` leitet `stdout`/`stderr` auf `%APPDATA%\Speech2Text\daemon.log` um (primitive Rotation bei >1 MB: `daemon.log` → `daemon.1.log`).
- **Custom Tray-Menü (AHK):** Standard-AHK-Einträge (Open/Reload/Exit) durch eigenes Menü ersetzt — „📋 Log öffnen", „🔄 Daemon neu starten", „⚙️ Einstellungen… (folgt)" [disabled], „❌ Beenden".
- **`/shutdown`-Endpoint:** POST-Endpoint im Daemon ruft `os._exit(0)` in einem Delay-Thread auf. Hard-Exit nötig, weil sounddevice/PortAudio und openai-SDK Non-Daemon-Threads hinterlassen, die `server.shutdown()` nicht beenden → Zombie-`pythonw.exe`.
- **Eigenes Tray-Icon:** `assets/speech2text.ico` (32 px, Electric Blue Kreis + weißes „S2T"), generiert via `assets/create-icon.ps1`. AHK lädt es beim Start per `TraySetIcon`. Wirkt wie eine eigene App, nicht mehr wie „irgendein AHK-Skript".

#### 3.8 Einstellungsmenü 🔜
Grafisches Settings-Fenster (tkinter) mit per-User-Konfiguration. Öffnet beim Installer-Erststart oder per Tray-Rechtsklick / Hotkey. Löst das Problem „jeder Anwender hat einen eigenen API-Key und eigene Präferenzen".

**Konfigurierbar:**
- OpenAI API-Key (DPAPI-verschlüsselt in `%APPDATA%\Speech2Text\config.json`)
- Optimierung an/aus
- Tonalität (Professionell / Locker / Sachlich / E-Mail / Stichpunkt)
- Paste-Modus (Clipboard+Ctrl+V / Nur Clipboard / Nur SendInput)
- Audio-Device, Hotkey (Caps Lock / F9 / Ctrl+Alt+R / Pause), Sprache (DE/EN/Auto)

**Voraussetzung für Installer** — ohne Settings-GUI müsste jeder Anwender `.env` selbst schreiben.
→ Details: `Projektplanung/05_Einstellungsmenue/SPEZIFIKATION.md`

#### 3.9 Installer / Portable Distribution 🔜
Speech2Text auf beliebigen OCI-Windows-PCs installierbar machen — ohne Python-/AHK-Vorinstallation.

**Drei Bausteine:**
- **PyInstaller** verpackt `recorder.py` + `settings.py` zu `speech2text-daemon.exe` und `speech2text-settings.exe`.
- **Ahk2Exe** kompiliert `shortcut.ahk` zu `speech2text-hotkey.exe` (AHK-Runtime nicht auf Ziel-PC nötig).
- **Inno Setup** bündelt alles zu `Speech2Text-Setup.exe` mit Autostart-Option und Start-Menü-Einträgen. Beim Erststart öffnet sich automatisch das Settings-Fenster zur API-Key-Eingabe.

**Konsequenz für aktuelle Entwicklung:** venv konsequent nutzen, `requirements.txt` exakt und minimal. Config-Layer (aus 3.8) ist Vorbedingung.
→ Details: `Projektplanung/06_Installer/SPEZIFIKATION.md`

---

### Priorität 3 — Langfristig

#### 3.8 Kontext-bewusste Optimierung 🔜
Optimierungs-Prompt passt sich an das aktive Fenster an — E-Mail-Fenster → E-Mail-Stil (Grüße, höflicher Ton), Code-Editor → kein Schnörkel. Fenster-Titel via AHK an Daemon übergeben.

#### 3.9 Diktat-Historie 🔜
Letzte 20 Diktate lokal speichern (mit Opt-In), per Hotkey wieder aufrufbar. Muss DSGVO-sicher gelöst werden (nur auf lokaler Platte, verschlüsselt).

#### 3.10 Transfer in AussendienstAPP 🔜
Sprachnotiz-Feature beim Besuchsbericht: Knopf im iPhone-Browser → Audio → gleicher OpenAI-Stack → Notiz in `oci_app_besuchskopf`. Separate Projekt-Session.

---

## 4. Zentrale Entscheidungen

| Datum | Entscheidung | Begründung |
|-------|-------------|------------|
| 2026-04-24 | **Zwei-Modell-Pipeline** (`gpt-4o-transcribe` + `gpt-4o-mini`) statt `gpt-4o-audio-preview` in einem Call | Robuster (klare Trennung), bessere Kontrolle über Optimierungs-Prompt, fallback-freundlicher. User-Empfehlung bestätigt. |
| 2026-04-24 | **Push-to-Talk mit Caps Lock** (nicht Toggle, nicht Ctrl+Alt+R) | Haltegeste = klares „ich spreche jetzt"; Caps Lock ist praktisch ungenutzt und gut erreichbar. Standard-Großschreib-Funktion wird per `SetCapsLockState "AlwaysOff"` deaktiviert. |
| 2026-04-24 | **Python als persistenter Daemon** (HTTP auf `127.0.0.1:17321`) statt Prozess-Start pro Tastendruck | Python-Import-Zeit (~1-2 s) ist zu hoch für Push-to-Talk. Daemon hält OpenAI-Client und sounddevice-Stream warm, reagiert in < 50 ms. |
| 2026-04-24 | **Kommunikation AHK → Python via HTTP** (nicht Datei-Flag, nicht Socket-roh) | `WinHttp.WinHttpRequest.5.1` COM-Objekt ist in AHK v2 trivial nutzbar. Saubere Semantik (POST /start, POST /stop). Kein File-System-Race. |
| 2026-04-24 | **Auto-Paste via `pyautogui.hotkey("ctrl","v")`** (aus Python heraus, nicht aus AHK) | Einfacher als Callback AHK→Python→AHK; `pyautogui` braucht keine Admin-Rechte; Timing-kontrolliert (kurze Sleep vor Paste, damit Clipboard bereit). |
| 2026-04-24 | **Kein Disk-Cache für Audio** — alles im Speicher | Datenschutz. Audio landet nur in OpenAI, nicht auf der Platte. |
| 2026-04-24 | **Aufnahme: 16 kHz Mono int16** | Ausreichend für Sprache, minimiert Upload-Bandbreite an OpenAI, `gpt-4o-transcribe` unterstützt das Format. |
| 2026-04-24 | **`scipy` aus `requirements.txt` entfernt** | Code nutzt `wave` aus stdlib, kein `scipy.io.wavfile`. Spart ~80 MB Download + native Builds; hält Installer-Bundle schlank. |
| 2026-04-24 | **venv statt system-wide-Install** | Isolierte, reproduzierbare Dep-Liste ist Voraussetzung für PyInstaller-Installer. System-Python bleibt sauber. |
| 2026-04-24 | **AHK: `$`-Prefix statt `*`-Wildcard** bei Hotkeys | In RDP-Sessions greift `RegisterHotKey` nicht — nur der **Low-Level Keyboard Hook** erfasst Tasten. `$` erzwingt den Hook. Ohne `$` feuerten weder Caps Lock noch Pause noch F9. Entdeckt durch Vergleich mit `SQL Tastatur Makros.ahk`, das `$F3::` nutzt und funktionierte. |
| 2026-04-24 | **AHK: WinHttpRequest `sync=false` statt `async=true`** | Bei `Open(url, true)` (async) wird der ComObject-Handle am Funktionsende garbage-collected, bevor der Request rausgeht — Daemon sieht den Call nie. Synchron ist trotz Blocking unmerklich schnell, weil der Daemon in < 5 ms mit 200 OK antwortet (Verarbeitung läuft im Worker-Thread). |
| 2026-04-24 | **AHK: `KeyWait`-Pattern statt `up`-Variante** | Windows-Key-Repeat bei gehaltener Taste (~30 Events/s) hätte `/start` spammen lassen. `KeyWait` blockiert den Hotkey-Thread bis zum Loslassen, feuert `/start` und `/stop` je genau einmal. |
| 2026-04-24 | **Caps Lock als Hotkey bestätigt** (trotz LED-Kosmetik in RDP) | `SetCapsLockState "AlwaysOff"` unterbindet Großschreibung auf Server-Seite zuverlässig, ABER die Client-LED toggelt weiter (RDP-Lock-State-Sync). Funktional unkritisch, rein optisch irritierend. Auf lokalen Clients (kein RDP) wird auch die LED aus bleiben. |
| 2026-04-24 | **Daemon-Shutdown via `os._exit(0)` statt `server.shutdown()`** | sounddevice/PortAudio + openai-SDK hinterlassen Non-Daemon-Threads, die einen regulären Python-Exit blockieren — `pythonw.exe` bleibt als Zombie im Task-Manager. `os._exit` killt den Prozess hart. Kein Cleanup nötig: Audio ist im RAM, Clipboard gehört dem OS, Log-File ist line-buffered. |
| 2026-04-24 | **Architektur-Split bestätigt:** AHK = UI (Tray, Hotkey, Menü), Python = Backend (Audio, OpenAI) | Diskussion bei der Tray-Menü-Einführung ergab: Architektur passt, keine Alternative ohne Rückschritt. Python-Alternativen für Hotkeys (`keyboard`, `pynput`) hätten die gleichen RDP-Probleme + weniger Reife. Das Einstellungsmenü wird trotzdem in Python (tkinter) — dort wo's besser passt. |
| 2026-04-24 | **Hidden-Daemon mit File-Log** | Beim Autostart soll kein CMD-Fenster aufpoppen. `pythonw.exe` + stdout/stderr-Redirect auf `%APPDATA%\Speech2Text\daemon.log` mit primitiver Rotation (bei >1 MB → `daemon.1.log`). Sichtbare Variante (`start-daemon.bat`) bleibt für Debugging. |
| 2026-04-24 | **Tray-Icon: simple statt fancy** | 4 verschiedene farbige `.ico` für die States (fancy) wurden diskutiert, aber zugunsten der Tooltip-Variante verworfen — weniger Assets, gleicher Info-Gehalt (User hovert eh nur bei Bedarf). Eigenes Icon (Electric-Blue-Kreis mit „S2T") statt AHK-Standard-„H", für App-Feeling. |

---

## 5. Offene Fragen

- [x] ~~**Sprache festnageln?**~~ → **fest `language="de"`** (2026-04-24). Auto-Detect DE/EN als Prio-3-Long-List-Item notiert.
- [x] ~~**Optimierungs-Prompt anpassen?**~~ → **9-Modi-Dropdown im Einstellungsmenü** (2026-04-24), Details in `Projektplanung/05_Einstellungsmenue/SPEZIFIKATION.md` A2. Ersetzt auch Optimize-Toggle (Raw Draft deckt „aus" ab).
- [x] ~~**Autostart-Variante?**~~ → Startup-Ordner (Variante B umgesetzt).
- [x] ~~**Tray-Icon jetzt oder später?**~~ → jetzt, Variante B.
- [x] ~~**Audio-Gerät fest oder Default?**~~ → **Default dynamisch** (Windows-Standard), manuelle Wahl per Dropdown im Settings-Menü.
- [ ] **Kurz-Tipp-Schutz** (< 300 ms stiller Abort) — als separates Ticket nach Einstellungsmenü-Phase-1, siehe `02_Audio-Daemon/SPEZIFIKATION.md` §8.
- [ ] **Pre-Recording-Ringpuffer** gegen verschlucktes erstes Wort — separates Ticket nach Phase 1, siehe `02_Audio-Daemon/SPEZIFIKATION.md` §8.

---

## 6. Notizen

### Warum Caps Lock und nicht Ctrl+Alt+R
Ursprünglich war Ctrl+Alt+R vorgesehen (Standard bei Diktier-Tools). Nach Rücksprache mit Daniel: Caps-Lock hat zwei Vorteile — (a) eine Taste reicht, keine Akkord-Geste, (b) Caps Lock wird praktisch nie gebraucht und ist Daumenschonend. Die Standard-Großschreib-Funktion ist bei AHK v2 mit `SetCapsLockState "AlwaysOff"` sauber deaktivierbar — Caps Lock schaltet nicht mehr um, auch nicht versehentlich.

### Sicherheit / Datenschutz
- `.env` mit API-Key nie committen (steht in `.gitignore` — sobald Git eingerichtet ist).
- Audio wird an OpenAI geschickt. Laut OpenAI-DPA werden API-Daten nicht zum Modelltraining genutzt — also datenschutzrechtlich unkritisch für interne Texte. Für echte Kundendaten (Verträge, Rechnungen) trotzdem keine Diktate empfehlen, bis Enterprise-Account geklärt ist.

### Quellen
- OpenAI Audio API Docs: https://platform.openai.com/docs/guides/speech-to-text (Abrufdatum 2026-04-24)
- OpenAI gpt-4o-transcribe: https://platform.openai.com/docs/models/gpt-4o-transcribe (Abrufdatum 2026-04-24)
- AutoHotkey v2 `SetCapsLockState`: https://www.autohotkey.com/docs/v2/lib/SetCapsLockState.htm (Abrufdatum 2026-04-24)
- WinHttp.WinHttpRequest COM: https://learn.microsoft.com/en-us/windows/win32/winhttp/winhttprequest (Abrufdatum 2026-04-24)

---

**Status-Legende:** ✅ Erledigt | ⚠️ In Arbeit | 🔜 Geplant | ❌ Blockiert
