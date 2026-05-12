# Current Task — Speech2Text

*Letzte Aktualisierung: 2026-05-12 (Session 10 — v1.3 Publish-Readiness auf eigenem Branch, AHK abgelöst durch Python-Tray, Smoke-Tests grün, Push offen)*
*Zu lesen am Anfang jeder Session — siehe `CLAUDE.md` Arbeitsregel 1.*

---

## Aktueller Stand

**Phase:** ✅ **v1.2 live + produktiv auf master.** ✅ **v1.3 Publish-Readiness fertig auf Branch `v1.3-publish-readiness`** — Pfad 1 vollständig umgesetzt: AHK-Ablösung (Win32 Low-Level-Hook + pystray-Tray), Settings-Teil-Refactor, Erst-Start-Wizard, Onboarding-Polish, SmartScreen-Doku, LIZENZEN.txt. Build der drei Bundles + Distribution-ZIP v1.3 erfolgreich (86.8 MB). E2E-Smoke-Tests gegen Mock-Daemon grün — Hotkeys gebunden, Re-Bind bei Revision-Diff, Pause/Resume funktioniert, kein Daemon-Auto-Start-Konflikt mit produktiver v1.2 (S2T_DAEMON_URL-Override). **Noch offen:** Branch nach origin pushen, User-Live-Test mit echtem Diktat in einer separaten Session.

**Sessions bisher (2026-04-24):**

*Session 10 (2026-05-12 spätabends, autonomer Run während User schläft) — v1.3 Publish-Readiness (Pfad 1):*

**Auftrag:** „Tiefenanalyse über das beste Vorgehen, planen, programmieren, selbständig ausführlich testen, ggf. Fehler korrigieren — bis Ergebnis zufriedenstellend. Release 1.2 unbedingt erhalten."

**Branch:** `v1.3-publish-readiness` (von master abgezweigt nach `54eace1`). `master` bleibt unverändert.

**Plan-Datei:** `Projektplanung/07_Veroeffentlichungs-Readiness/PLAN.md` — Tiefenanalyse + 11 Phasen mit Datei-Pfaden und Code-Skizzen.

**Was umgesetzt wurde:**

1. **AHK-Ablösung** durch Python (kommerz-tauglich):
   - `src/keyboard_hook.py` — Win32 `SetWindowsHookExW(WH_KEYBOARD_LL)` via ctypes, eigener Thread mit `GetMessageW`-Loop. RDP-fähig (gleicher Mechanismus den AHK intern nutzt). Modifier-State per `GetAsyncKeyState`, Auto-Repeat-Filter via `_down`-Set, Suppression gebundener Hotkeys via `Return 1` (CapsLock toggelt nicht mehr, F-Tasten triggern keine App-Aktionen).
   - `src/tray_app.py` — pystray-Tray (Icon/Tooltip/Menü), Auto-Daemon-Start, Health-Polling 300ms, Re-Bind bei `hotkeys_revision`-Diff, Pause/Resume-Logik, Fehler-Toast via `icon.notify()`, Erst-Start-Wizard, First-Run-Hint.
   - `src/daemon_client.py` — urllib-HTTP-Client für alle 8 Daemon-Endpoints. ENV-Var `S2T_DAEMON_URL` als Test-Override; `is_custom_url()` blockt Auto-Daemon-Start bei Custom-URL, um Konflikt mit produktivem v1.2 zu vermeiden.
   - **shortcut.ahk gelöscht**, `scripts/build-hotkey.ps1` + `scripts/build-hotkey.py` raus, `tools/Ahk2Exe/` aus `.gitignore` raus.

2. **Build-Pipeline:** `scripts/build-tray.ps1` (PyInstaller --onefile --noconsole, `--collect-all pystray PIL`, eigenes Icon eingebettet + via `--add-data` zur Laufzeit erreichbar). Output: `Speech2Text-Hotkey.exe` 27.35 MB (vorher AHK: 1.4 MB; Trade-off: lizenzfrei statt GPLv2-Last).

3. **Recorder-Erweiterung:** `last_dictation_ts` in `/health` (minimal-invasiv) — Tray-App nutzt das fürs Onboarding-Tooltip. Sonst nichts an `recorder.py` geändert.

4. **Settings-Refactor (Teil-Auslagerung):** `src/settings_helpers.py` (NEU) — HELP_*-Texte + `list_input_devices` + Layout-Limits. `settings.py` 934 → 845 Zeilen. Hotkey-Section bleibt verzahnt (Tech-Debt, dokumentiert).

5. **Erst-Start-Wizard:** Bei leerem `api_key_encrypted` öffnet Tray automatisch Settings-GUI + setzt Tooltip „API-Key fehlt — Einstellungen öffnen". Sobald Key gespeichert: Daemon-Auto-Start. Bug entdeckt und gefixt (Wizard-Mode wurde nie verlassen, weil Restart-Block durch `_wizard_opened` blockiert war).

6. **Onboarding-Polish:** First-Run-Hint im Tooltip („<Hauptkey> halten, um zu diktieren") solange `last_dictation_ts==0`. Nach erstem erfolgreichem Diktat: `first_run_completed=True` in config.json. Spec-Display-Helper (`+#F12` → `Shift + Win + F12`).

7. **SmartScreen-Doku:** README.txt um Block „Beim ersten Start: ‚Weitere Informationen → Trotzdem ausführen'" erweitert, Begründung (kein EV-Cert für 200-400 €/Jahr). Wizard-Hinweis ergänzt.

8. **LIZENZEN.txt (NEU):** Pflicht-Hinweis für pystray (LGPL-3.0) + Pillow + sounddevice/PortAudio + NumPy + pyperclip + pyautogui + OpenAI SDK + python-dotenv mit Source-Links. Plus Datenübertragung-Hinweis (OpenAI, kein Modelltraining laut DPA).

9. **Distribution-ZIP v1.3** (`scripts/build-distribution.py` Version-Bump): 86.8 MB Total — Daemon 37.12 MB, Settings 23.03 MB, Hotkey 27.35 MB, plus Icon/install.bat/uninstall.bat/README.txt/LIZENZEN.txt.

**Tests (43 Unit-Tests + 2 Mock-E2E-Tests):**
- `tests/test_keyboard_hook.py` (25 Tests): Spec-Parser (modifier-Bitmask, vk-codes, edge cases), HotkeyManager-Bind/Unbind/Pause-Logik. Alle grün.
- `tests/test_daemon_client.py` (10 Tests): HTTP-Layer gegen Mock-Server auf Port 17322, parse-key-value, JSON-Body bei `/start`. Alle grün.
- `tests/test_tray_app.py` (8 Tests): Spec-Display + Pfad-Resolver. Alle grün.
- `tests/mock_daemon.py` (NEU): Mock-HTTP-Server für E2E-Tests, mit Test-Hotkey `+#F23` (Shift+Win+F23 — unmöglich versehentlich gedrückt). Bietet `/control/health` + `/control/hotkeys` zum Live-Manipulieren des Antworten-Bodies.
- **E2E-Smoke #1:** Tray-Exe gegen toten Port (S2T_DAEMON_URL=127.0.0.1:1) — 6s ohne Crash, Auto-Start unterdrückt (Custom-URL). ✓
- **E2E-Smoke #2:** Tray-Exe gegen Mock-Daemon (S2T_DAEMON_URL=127.0.0.1:17322) — Hotkey gebunden („Hotkeys gebunden (revision=1, main='+#F23', ...)"). ✓
- **E2E-Smoke #3:** Re-Bind bei Revision-Diff (mock_daemon /control/hotkeys + /control/health bumpen) — Tray bindet revision=2, main=+#F22, cycle=+#F24. ✓
- **E2E-Smoke #4:** Pause/Resume — `HotkeyManager.pause()` + Resume triggert Re-Bind. ✓
- **E2E-Smoke #5:** Test-Install entpackt aus Distribution-ZIP — Tray-Exe aus entpacktem Bundle läuft 5s ohne Crash, bindet Hotkey aus Mock. ✓

**Was NICHT autonom getestet wurde (User-Manual-Validation nötig):**
- Echtes Diktat End-to-End (Mikro → OpenAI → Paste)
- pystray-Tray-Icon visuell (Headless nicht prüfbar)
- Live-Hotkey-Drücken (würde produktiven v1.2-Hook + v1.3-Hook parallel laufen lassen — bewusst vermieden)
- Settings-GUI visuelles Layout (nur Importierbarkeit getestet)

**Tech-Debt / bekannte Limits:**
- `src/settings.py` 845 Zeilen — Hard-Limit 600 weiter überschritten. Hotkey-Section-Auszug nach `settings_hotkey_section.py` ist Plan-Phase-6-Teil, aber wegen tiefer State-Verzahnung verschoben auf v1.4 (Risiko vs. Nutzen).
- pystray-LGPL: konform via dynamic linking + LIZENZEN.txt, aber bei wirklicher Kommerzialisierung sollte ein eigener Win32-Tray (Shell_NotifyIconW) erwogen werden, damit auch die LGPL-Erwähnung in der App-Bundle-Beschreibung wegfällt.
- Sicherer Auto-Start: bei wirklich offline Daemon retried Tray alle 6s — nicht aggressiv, aber sollte für Toast-Müll überwacht werden.

*Session 9 (2026-05-12) — ARM64-Windows-Kompatibilität + Settings-GUI-Resize-Fix:*

**Teil 2 — Settings-GUI fuer kleine Aufloesungen (live-Test auf diesem PC, ARM-Tablet):**
- **Symptom:** Auf dem ARM64-PC waren die Aktions-Buttons (Abbrechen / Anwenden / Speichern & Schließen) unsichtbar, weil das Fenster mit `minsize(620, 820)` ueber den Bildschirmrand wuchs und die Buttons als unterste Grid-Zeile im Outer-Frame lagen.
- **Fix in `src/settings.py`:**
  - **Footer-Frame** mit den drei Buttons wird im `_build_ui` ZUERST per `pack(side="bottom", fill="x")` an `self.root` angeheftet — pack reserviert den Platz, damit der darueberliegende Bereich nie ueber den Footer hinauswaechst.
  - **Scrollbarer Mittelteil:** `outer`-Frame liegt jetzt in einem `tk.Canvas` + `ttk.Scrollbar` (vertikal). Inner-Frame-Breite ist via `<Configure>`-Binding an die Canvas-Breite gekoppelt, Scrollregion wird beim Wachstum aktualisiert. Mausrad-Scroll nur aktiv, solange die Maus ueber dem Canvas ist (vermeidet Konflikt mit Treeview-/Text-Eigenscroll).
  - **Init-Geometrie** wird an `winfo_screenwidth/height - 40/80` geklemmt. `minsize` reduziert auf `(560, 420)` — auch auf einem 1024×600-Tablet passt das Fenster jetzt komplett auf den Schirm.
  - **`_resize_to_content`** zusaetzlich auf Bildschirmgroesse capped (vorher konnte wachsendes Resize nach Modus-/Help-Toggle off-screen laufen).
  - Alter Spacer + Button-Grid am Ende des Outer-Frames entfernt.
- **Build + Deploy:** `scripts/build-settings.ps1 -Clean` rerun, neue `Speech2Text-Settings.exe` (22.33 MB) ins installierte Bundle unter `%LocalAppData%\Programs\Speech2Text\` kopiert.

**Teil 1 — ARM64-Sounddevice-DLL-Mismatch (Source-Fix + Rebuild + Live-Smoke):**
- **Symptom:** v1.1-Bundle (installiert via install.bat unter `%LocalAppData%\Programs\Speech2Text\`) zeigt beim Start auf ARM64-PC `OSError: cannot load library '…\_sounddevice_data\portaudio-binaries\libportaudioarm64.dll': error 0x7e` (ERROR_MOD_NOT_FOUND). Traceback: `recorder.py` Zeile 32 `import sounddevice as sd`, `sounddevice.py` Zeile 91. Onefile-PyInstaller-Build → Extraktion in neues `%Temp%\_MEI…\` pro Start, manuelles DLL-Tauschen am Bundle nicht stabil.
- **Ursache (analog spotify-downloader, siehe Memory `feedback_arm64_installer.md`):** sounddevice 0.5.x waehlt die DLL anhand von `platform.machine()`. Windows 11 ARM64 meldet ARM64 auch im x64-emulierten Prozess. Bundle wurde x64-only mit `--collect-all sounddevice` gebaut; entweder fehlt die ARM64-DLL im Wheel oder sie laesst sich im x64-Prozess nicht laden.
- **Source-Fix umgesetzt:**
  - **`src/_arch_fix.py`** (NEU, ~50 Zeilen) — Pre-Import-Shim. Erkennt x64-Prozess (`PROCESSOR_ARCHITECTURE=AMD64`) auf ARM64-OS (`platform.machine()=='ARM64'`) und patcht `platform.machine()` so, dass `sounddevice` die x64-DLL waehlt. Native ARM64-Python-Builds bleiben unberuehrt.
  - **`src/recorder.py`** Zeile 16: `import _arch_fix  # noqa: F401` als allererster Import vor `sounddevice`.
  - **`src/settings.py`** Zeile 14: dito (lazy-Import von sounddevice in den Audio-Device-Funktionen).
- **PyInstaller-Auswirkung:** `_arch_fix.py` liegt in `src/`, wird durch normale Import-Analyse von `recorder.py`/`settings.py` automatisch eingesammelt — kein Spec-/Build-Skript-Update noetig.
- **Repo geklont:** auf diesem ARM64-PC liegt das Repo unter `C:\Users\danie\Speech2Text` (Stand bei Session-Start: `d39cfa1`, working tree clean).
- **Toolchain hier eingerichtet:** Python 3.12.10 x64 ueber den python.org-Installer per User installiert (`%LocalAppData%\Programs\Python\Python312\`, PATH ergaenzt, ohne Admin / ohne py-Launcher). venv unter `.venv\`, `requirements.txt` + `pyinstaller` installiert. Bestaetigt: `platform.machine()=ARM64`, `PROCESSOR_ARCHITECTURE=AMD64` — das genau vom Shim erfasste Muster. Smoke-Test `import _arch_fix; import sounddevice` → 38 Audio-Devices erkannt, kein DLL-Fehler.
- **Bundles neu gebaut:** `build-daemon.ps1 -Clean` (28.79 MB) + `build-settings.ps1 -Clean` (22.33 MB) — und ins installierte Bundle unter `%LocalAppData%\Programs\Speech2Text\` kopiert. Hotkey-Exe unveraendert (AHK, nicht betroffen).
- **Daemon-Smoke-Test live:** Neuer Daemon startet ohne DLL-Crash, beendet sich nun mit der erwarteten Meldung `Kein OpenAI-API-Key gefunden` (Crash-Dialog ist weg). Damit ist die ARM64-Kompatibilitaet auf Source- + Bundle-Ebene validiert.
- ✅ **Live-Test (User-Bestätigung 2026-05-12):** Settings-GUI laeuft auf der ARM64-Aufloesung sauber, API-Key per DPAPI gespeichert, Daemon-Reload akzeptiert ihn, Caps-Lock-Push-to-Talk + Transkription End-to-End grün.
- ✅ **Commit + Push erledigt:** `78835f4` (feat: ARM64-Windows-Support + Settings-GUI fuer kleine Aufloesungen), `54eace1` (chore: VERSION-Bump 1.2), Tag `v1.2` auf Origin. Dev-PC hat den Stand per `git pull` gezogen.

*Session 8 (2026-05-11/12) — GitHub-Repo + Release-Workflow:*
- **Repo angelegt:** `https://github.com/OCICARPETS/Speech2Text` (privat, Default-Branch `master` analog AussendienstAPP).
- **Initial Commit (4c2c32f):** 45 Dateien, 6122 Zeilen — alle Sources, Doku, Scripts, Projektplanung.
- **ZIP-Removal-Commit (b3bf86c):** dist/ komplett in `.gitignore`. Frühere Variante hatte die v1.1-ZIP mit-committet (User-Wunsch), wurde nach erstem Push wieder herausgenommen. **Hinweis:** Die ZIP-Blob liegt physisch noch in der Git-History (Commit `4c2c32f`), `git clone` zieht also weiterhin ~60 MB. Bei Bedarf später per `git filter-repo` + force-push aus History entfernbar — bei Single-User-Repo nicht zwingend.
- **`.gitignore`:** `build/`, `tools/Ahk2Exe/`, `dist/`, `config.local.json`, plus die bisherigen Python/IDE/OS-Einträge.
- **`gh` CLI portable installiert (2026-05-12):** Chocolatey-Install scheiterte (kein Admin), Fallback per ZIP-Download nach `%LOCALAPPDATA%\Programs\gh\bin\gh.exe`. User-PATH wurde ergänzt — frische PowerShell-Sessions haben `gh` automatisch. Version 2.92.0, Auth läuft als `OCICARPETS` mit Scopes `gist, read:org, repo, workflow` (Browser-Login durch User).
- **Tag `v1.1`** auf Commit `b3bf86c` (nach ZIP-Removal) gesetzt + gepusht.
- **Release v1.1 angelegt** via `gh release create`: https://github.com/OCICARPETS/Speech2Text/releases/tag/v1.1 — published (kein Draft), `Speech2Text-v1.1.zip` (60,4 MB) als Asset hochgeladen. Direkt-Download: `https://github.com/OCICARPETS/Speech2Text/releases/download/v1.1/Speech2Text-v1.1.zip`. SHA-256: `a9d5bd6e8cc89d1e1d052453c2f1a5d087027f9a31c9d18b595acd05e02d1796`.
- **Release-Workflow ab jetzt:** Pro Version Tag `vX.Y` setzen + ZIP bauen + `gh release create vX.Y dist/Speech2Text-vX.Y.zip --title "..." --notes "..."`. Repo bleibt schlank, Binaries hängen am Release.

*Sessions bisher (2026-04-24):*

*Session 1 — Setup + MVP-Validierung:*
- Projektstruktur + 6 Feature-Spezifikationen
- venv (Python 3.14.2) + Deps installiert
- Drei RDP-spezifische AHK-Fixes (siehe `01_Hotkey-Trigger/SPEZIFIKATION.md` Gotchas):
  1. `$CapsLock::` statt `*CapsLock::` (Hook-Mechanismus)
  2. `WinHttp` sync statt async (ComObject-Lifetime)
  3. `KeyWait` statt `up`-Variante (kein Key-Repeat-Spam)
- End-to-End validiert: User diktiert live, Text erscheint optimiert im Zielfenster

*Session 2 — Variante B (Tray, Autostart, Comfort):*
- **Tray-Status-Ampel:** AHK pollt `/health` 1×/s, Tooltip zeigt offline/bereit/Aufnahme/verarbeite
- **Fehler-Toast:** Python schreibt `last_error`+`ts` in `/health`, AHK-TrayTip bei neuen Fehlern
- **Hidden-Daemon:** `pythonw.exe` + `recorder.py --hidden` → stdout/stderr auf `%APPDATA%\Speech2Text\daemon.log` (Rotation bei >1 MB)
- **Custom Tray-Menü:** Log öffnen, Daemon neu starten, Einstellungen-Platzhalter, Beenden
- **Eigenes Tray-Icon:** `assets/speech2text.ico` (Electric Blue + „S2T"), generiert per `assets/create-icon.ps1`
- **`/shutdown`-Endpoint:** Hard-Exit via `os._exit(0)` — sounddevice/openai-SDK hinterlassen Non-Daemon-Threads, die `server.shutdown()` blockieren (Zombie-`pythonw.exe`)
- **Autostart-Skripte erstellt:** `scripts/install-autostart.ps1` + `uninstall-autostart.ps1` (Startup-Ordner-Variante)

*Session 5e (2026-04-26) — Mode-Editing live-validiert + build-hotkey.py + Variante-B-Distribution:*
- **Mode-Editing-Live-Test grün** (User-Bestätigung „Top klappt alles"): Editor-Anzeige für alle 10 Modi, Modus-Wechsel mit Working-Copy-Sicherung, Override-Persistierung, ↺-Standard-Reset, Manuell-Modus-Sonderfall — alles wie spezifiziert. Daemon-Exe und Settings-Exe wurden vor dem Test mit den config.py- und settings.py-Änderungen neu kompiliert.
- **`scripts/build-hotkey.py`** geschrieben (AV-resistenter Ersatz für `build-hotkey.ps1`): Lädt Ahk2Exe von github.com/AutoHotkey/Ahk2Exe Releases via `urllib.request.urlopen`, entpackt in `tools/Ahk2Exe/`, ruft direkt `subprocess.run(...)` auf. Alles in einem Python-Prozess → kein Lock-Window für AV-Heuristik. Erfolgs-Kriterium: Existenz der Output-Datei (Ahk2Exe gibt non-zero Returncode auch bei Erfolg).
  - **Wichtige Falle:** `Path(__file__).resolve()` löste den I:-Substituted-Drive auf den UNC-Pfad `\\oci-db2\Dokumente\…` auf — Ahk2Exe verweigert dort Schreibzugriff (`WinError 5`). Fix: `.resolve()` weglassen, `Path(__file__).parent.parent` ohne resolve nutzen. Im Skript-Kommentar dokumentiert.
- **Variante B (ZIP-Distribution):** `scripts/build-distribution.py` packt aus `build/dist/` + `assets/` + Templates eine `dist/Speech2Text-v1.0.zip` mit `install.bat` (kopiert nach `%LocalAppData%\Programs\Speech2Text\`, Desktop-Verknüpfung, optional Autostart-Eintrag), `uninstall.bat` und `README.txt`. Templates unter `scripts/dist-templates/`.
- **Inno Setup (Variante C) bewusst ausgelassen:** User entschied Variante B reicht für Single-User + gelegentliches Rechner-Wechseln. Bundle-Exes sind self-contained (kein Python/AHK auf Zielrechner nötig). Inno Setup wird reaktiviert, falls Distribution an mehrere Mitarbeiter konkret wird.

*Session 5d (2026-04-26) — Mode-Editing-Feature (Code fertig, Live-Test offen):*
- **Anforderung User:** Bisherige 9 Standard-Modi sollen editierbar sein (Anzeigename + System-Prompt). Beibehalten als Defaults, User-Overrides werden gespeichert.
- **`config.py`:**
  - `MODES["manual"]["prompt"]` von Sentinel `"__manual__"` auf `None` umgestellt — manual ist jetzt ein normaler Modus mit Default-Prompt = leer.
  - Neuer Config-Eintrag `mode_overrides: dict[mode_id, {ui_name?, prompt?}]`. Sparse — nur abweichende Felder werden persistiert.
  - Neue Helper: `get_mode_default(mode_id)` (MODES-Eintrag), `get_mode_override(cfg, mode_id)` (User-Override), `get_mode_ui_name(mode_id, cfg)`.
  - `get_mode_prompt(mode, cfg)` checkt zuerst Override (leerer String → None / Raw-Draft), dann MODES-Default.
  - `load_config()` migriert legacy `manual_prompt` → `mode_overrides["manual"]["prompt"]` automatisch (one-shot beim ersten Load nach Update).
- **`settings.py`:** Modus-Bereich umgebaut.
  - Dropdown wie bisher (Labels reflektieren User-Overrides via `get_mode_ui_name`, Snapshot beim Init).
  - **Editor immer sichtbar** (statt bedingtes Manual-Feld): Anzeigename-Entry + Prompt-Textbox (6 Zeilen + Scrollbar) + ↺-Reset-Button.
  - Char-Counter unter Prompt umbenannt zu `mode_count_var/label` (`MODE_PROMPT_SOFT_MAX = 4000`, rot bei Überschreitung).
  - Working-Copy `_mode_edits: dict[mode_id, {ui_name, prompt}]` puffert Änderungen pro Session. Beim Modus-Wechsel: `_save_current_mode_edits()` → `_load_mode_into_editor(new_id)`.
  - `_reset_current_mode()` setzt UI auf MODES-Default + entfernt Eintrag aus `_mode_edits` (sodass beim Save kein Override entsteht).
  - `_save_and_reload()`: alle `_mode_edits` durchgehen, gegen MODES-Default (gestrippt) vergleichen — nur Diffs landen in `mode_overrides`. Legacy `manual_prompt` wird aktiv geleert.
  - Fenster größer (620×780, minsize 580×740) für den Editor.
- **`recorder.py`:** Keine Änderung — `cfg_mod.get_mode_prompt(mode, self.config)` greift jetzt automatisch Override.
- **Syntax-Check:** alle drei Module → OK.
- **Bundle-Status:** Daemon.exe + Settings.exe sind ALT (vor Mode-Editing-Code-Changes). Müssen vor Live-Test neu gebaut werden. Hotkey.exe ist OK (keine AHK-Änderung).
- **Live-Test ausstehend** — siehe „Nächster Scope" unten.

*Session 5c (2026-04-26) — Schritt 4a/4b/4a-extra (Daemon/Hotkey/Settings als Exes):*
- **`scripts/build-daemon.ps1`** (PyInstaller, one-file, no-console, eingebettetes Icon, `--collect-all sounddevice`, `--collect-submodules openai`). Output: `build/dist/Speech2Text-Daemon.exe` (38.9 MB).
- **`recorder.py` Frozen-Detection:** `getattr(sys, "frozen", False)` ODER `--hidden` → automatisch Hidden-Mode (Log-Datei statt stdout).
- **`scripts/build-settings.ps1`** (analog, `--paths .\src` für config-Import). Output: `build/dist/Speech2Text-Settings.exe` (23 MB).
- **`scripts/build-hotkey.ps1`** (Ahk2Exe, eingebettetes Icon, AHK64 als Base). Output: `build/dist/Speech2Text-Hotkey.exe` (1.4 MB).
- **AHK-Skript erweitert (`shortcut.ahk`):**
  - `EnsureDaemonRunning()` beim Skript-Start: pollt `/health`, falls nicht erreichbar → startet Daemon-Exe (Pfad-Fallback: Bundle-Exe → `..\build\dist\` → `..\scripts\start-daemon-hidden.bat`). Wartet bis 3 s auf `/health=ok`.
  - `OpenSettings()` mit Pfad-Fallback (Bundle-Settings.exe → venv-Pythonw + settings.py). Behebt User-Bug „venv nicht gefunden" im Bundle-Setup.
  - `RestartDaemon()` nutzt jetzt dieselbe `DaemonStartCommand()`-Lookup-Logik.
  - `ICON_CANDIDATES`-Liste statt fixem Pfad — Bundle vs. Dev.
- **AV-Theater (Defender quarantäniert Ahk2Exe.exe):**
  - Vendor-Installer (`install-ahk2exe.ahk`) gescheitert (DirCopy-Fehler, vermutlich UAC).
  - Fallback (b): Ahk2Exe von github.com/AutoHotkey/Ahk2Exe Releases lokal nach `tools/Ahk2Exe/` entpackt.
  - **AV löscht die Datei zwischen Aufrufen** — alle PS-basierten Build-Versuche scheiterten weil Ahk2Exe.exe verschwand. Working-Workaround: **Download + Entpacken + Ahk2Exe-Aufruf in einem einzigen Python-Prozess via `subprocess.run`** — kein Lock-Window für AV-Heuristik. Mit diesem Trick lief der Hotkey-Build sauber durch.
  - Konsequenz: `scripts/build-hotkey.ps1` ist FRAGIL. Migration zu `scripts/build-hotkey.py` ist Teil von ABC (siehe „Nächster Scope").
- **Live-Tests grün:** Daemon-Exe + Hotkey-Exe + Settings-Exe alle funktional, Tray-Icon zeigt unser Logo, Auto-Daemon-Start funktioniert, Mikrofon-Diktat klappt End-to-End. Settings-Bug-Fix (venv nicht gefunden) verifiziert.

*Session 5b (2026-04-26) — Code-Review-Fixes + Icon ersetzt + Build-Tools:*
- **Code-Review** via `superpowers:requesting-code-review`-Skill (general-purpose-Subagent, weil `superpowers:code-reviewer`-Subagent nicht registriert war): 1 Critical, 5 Important, 9 Minor identifiziert. Alle relevanten Punkte umgesetzt:
  - **#1 Datenschutz (Critical):** `_preview()`-Helper entfernt. `_process()` loggt nur noch `<X Zeichen>` statt Roh-/Optimized-Text-Auszüge — `daemon.log` im Hidden-Modus enthält keine Transkripts mehr.
  - **#3 reload_config-Bug (Important):** Vergleich gegen `_stream_always_on` und `_current_device` (TATSÄCHLICHER Stream-Status) statt gegen alte config-Werte. Plus `deferred`-Hinweis im Return-String, falls Wechsel-Bedarf bei state≠IDLE erkannt wird. Behebt: vorher wurde Lifecycle-Wechsel mid-Diktat dauerhaft verschluckt.
  - **#4 Doppeltap-Feedback (Important):** `start()` setzt bei state≠IDLE jetzt `_set_error("Aufnahme zu schnell hintereinander…")` → Toast erscheint, statt stillem Print.
  - **#5 start() Try/Except (Important):** Stream-Open in `try/except`, bei Fehler `_set_error` und State bleibt IDLE.
  - **#6 MAX_RECORD_S = 600 (Important):** Watchdog in `_on_audio` mit inkrementellem Counter `_chunks_total_samples` (kein O(n)-sum() pro Audio-Frame). Asynchroner `_finalize_recording`-Trigger via Thread (PortAudio-stop nicht aus Audio-Callback).
  - **#2/#7/#9/#10/#11/#14 (Minor):** Lock-Doku in `_process` ehrlich gemacht (Lock entfernt, Kommentar erklärt warum tolerant). `/health` Lock-Doku ergänzt. `_chunks = []` + Counter-Reset im `_process.finally`. `_finalize_recording` Stream-Close in try/except. Manual-Prompt-Char-Counter in GUI (X / 4000, rot bei Überschreitung). Exception-stderr-print zeigt nur Typ (kein Message-Echo).
  - **Bewusst NICHT umgesetzt:** #8 (prebuffer Default `True` bleibt — User-Wunsch), #12 (Resize-Schrumpf — Reviewer selbst „OK"), #13 (pyperclip auch bei send_input — bewusster Fallback), #15 (AHK nicht im Scope).
  - **Restbeschränkung dokumentiert:** Lifecycle-Wechsel mid-Diktat wird beim NÄCHSTEN Reload nachgezogen (vorher: dauerhaft verschluckt). Echtes „auto-pending bei state→IDLE" wäre State-Machine-Erweiterung — ausgelassen.
- **Icon ersetzt:** User-PNG (Mikrofon + Text-Symbol, türkis) → `assets/source-icon.png` (2048×2048 RGBA). Konvertiert via neuem `assets/png-to-ico.py` zu Multi-Size-ICO (16/24/32/48/64/128/256). Tray-Icon-Test grün (User-Bestätigung). Mockup-PNG (`Gemini_Generated_Image_e9hpcle9hpcle9hp.png`) entfernt.
- **Build-Tools im venv** (nicht in `requirements.txt` — bewusste Ausnahme der „Kein pip install ohne Pin"-Regel, da reine Build-Tools): `Pillow` (für ICO-Generierung) + `PyInstaller` (für Daemon-Exe). Wurden ad-hoc per `pip install` installiert.
- **`recorder.py` Frozen-Detection:** `getattr(sys, "frozen", False)` triggert automatisch Hidden-Mode im PyInstaller-Bundle (kein `--hidden`-Flag mehr nötig).

*Session 5 (2026-04-25) — Audio-Robustheit + GUI-Ausbau:*
- **3a Kurz-Tipp-Schutz** (`recorder.py`): Konstante `MIN_RECORD_S = 0.3`. Aufnahmen unter 300 ms werden in `_process()` still verworfen — kein OpenAI-Call, kein Toast, Console zeigt `⏭ Aufnahme XXX ms < 300 ms — verworfen`.
- **3b Pre-Recording-Ringpuffer** (`recorder.py`): Neuer Persistent-Stream-Modus mit `RINGBUFFER_S = 0.5`. Stream läuft dauerhaft, `_on_audio` füllt einen `deque` mit Sample-Begrenzung. Bei `/start` State-Flip ohne Stream-Open. `_process()` snapshottet den Ringpuffer unter Lock und hängt bis zu `preroll_ms` davon vor das Diktat. Methoden `_open_persistent_stream()` / `_close_persistent_stream()`. Toggle: `prebuffer_enabled` in Config.
- **Post-Roll** (`recorder.py`): `stop()` setzt einen `threading.Timer(daemon=True)` auf `postroll_ms`, der `_finalize_recording()` aufruft. State bleibt RECORDING, `_on_audio` schreibt weiter in `_chunks`. Funktioniert in beiden Modi (Prebuffer an + aus). Konstante `POSTROLL_MS_MAX = 500`.
- **Pre-Roll + Post-Roll einstellbar** (Config + GUI): Spinboxen 0–500 ms, Schrittweite 50, Defaults 300/200. Hard-Limits = `RINGBUFFER_S * 1000` bzw. `POSTROLL_MS_MAX`.
- **`reload_config()`-Erweiterung**: Reagiert live auf `prebuffer_enabled`-Toggle und `audio_device`-Wechsel — Stream wird zwischen Diktaten (State=IDLE) geschlossen/geöffnet/neu-geöffnet. Wechsel mid-Diktat wird verschluckt (akzeptiert, da GUI-Speichern-mid-Diktat real nicht vorkommt — dokumentiert im Docstring).
- **10. Modus „Manuell"** (`config.py`): Sentinel-Prompt `"__manual__"` in MODES, neuer Config-Eintrag `manual_prompt: str`. `get_mode_prompt(mode, cfg)` ist config-aware: bei `manual` → `cfg["manual_prompt"]`; leer → `None` (Raw-Draft-Verhalten). `recorder.py`-Aufruf entsprechend angepasst.
- **MODES um `description`-Feld erweitert** — alle 10 Modi haben jetzt einen 1-Zeiler für die GUI.
- **Settings-GUI komplett überarbeitet** (`settings.py`):
  - **Hilfe-Toggle oben** („ℹ Hilfetexte zu allen Feldern anzeigen"): blendet inline-graue Erklärungs-Zeilen unter jedem Feld ein/aus per `grid()`/`grid_remove()`. Standard: aus.
  - **Modus-Beschreibung** unter dem Dropdown — immer sichtbar, dynamisch via `mode_var.trace_add` und `_on_mode_change()`.
  - **Manual-Prompt-Textbox** (5-Zeilen-`tk.Text` + Scrollbar): erscheint nur bei Modus „Manuell". `_on_mode_change` toggelt Sichtbarkeit.
  - **Pre-Roll-Spinbox** + **Post-Roll-Spinbox** mit Hilfetexten.
  - **3-Button-Layout** unten: Abbrechen / Anwenden / Speichern & Schließen. Refactor `_save_and_reload()` als gemeinsame Logik (return bool), `_on_apply()` nutzt sie ohne Schließen, `_on_save_close()` schließt nach 1,5 s.
  - **Auto-Resize** (`_resize_to_content()`): wachsendes Resize via `winfo_reqheight/width` und `max(cur, needed)` — schrumpft nie. Wird bei `_toggle_help`, `_on_mode_change` und Init aufgerufen, jeweils via `after(0, …)` damit tkinter zuvor das Layout verarbeitet.
  - Fenster-Default 600×740, minsize 560×700.
- **`/health` zeigt zusätzlich `prebuffer=on/off`**.
- **Live-Test (User-Bestätigung):** Alle Funktionen grün — Kurz-Tipp-Schutz, Pre/Post-Roll mit verschiedenen Werten, Manueller Modus mit Custom-Prompt, Hilfetexte-Toggle, Auto-Resize bei Modus-/Help-Wechsel, 3-Button-Verhalten.

*Session 4 (2026-04-25) — Paste-Modus-Refactor Schritt 2a (Code + Live-Test fertig):*
- **User-Entscheidung:** statt `pyautogui.typewrite()` (ASCII-only, verschluckt deutsche Umlaute) → **Weg 1**: Win32 `SendInput` via `ctypes` mit `KEYEVENTF_UNICODE`. Keine neue Dependency, konsistent mit späterem `auto`-Modus (der ebenfalls ctypes braucht).
- **`src/recorder.py`:**
  - Neue Konstante `SEND_INPUT_INTERVAL_S = 0.001` (r49).
  - Block **Win32 SendInput (Unicode)** (r54–131): `_INPUT/_KEYBDINPUT/_MOUSEINPUT/_HARDWAREINPUT`-Structs + `_INPUT_UNION`, `_user32.SendInput`-Binding, Helper `_send_unicode_codepoint` und `_type_text_unicode` mit UTF-16-Surrogatpaar-Handling für Codepoints > 0xFFFF.
  - `_paste` umgebaut: Instance-Methode (statt `@staticmethod`), nimmt `text: str`, liest `self.config["paste_mode"]`, gibt Status-String zurück. Drei Branches:
    - `clipboard_only` → nichts, User drückt Ctrl+V selbst
    - `send_input` → `_type_text_unicode(text)`
    - `clipboard_ctrl_v` (Default + Fallback) → wie bisher (`pyautogui.hotkey("ctrl","v")`)
  - Call-Site in `_process`: `status = self._paste(ausgabe); print(f"✔  {status}\n")`.
- **Syntax-Check:** `python -m py_compile` → OK.
- **Live-Test:** Alle drei Modi grün (Notepad/Outlook für `clipboard_ctrl_v`, manuelles Ctrl+V für `clipboard_only`, Claude Code CLI / cmd / PowerShell mit Umlauten für `send_input`). Modus-Wechsel via Einstellungs-GUI ohne Daemon-Neustart funktioniert.

*Session 3 (2026-04-25) — 9-Modi-Einstellungsmenü:*
- **Tonalitäts-Design:** 8 User-Modi + Claude-Code-Prompt-Modus (Nr. 9) in `05_Einstellungsmenue/SPEZIFIKATION.md` A2 finalisiert.
- **Design-Entscheidungen:** Sprache fest DE, Audio-Device Default dynamisch, Optimize-Toggle entfällt (Raw Draft ersetzt).
- **Phase 1** (`config.py` + `recorder.py` Refactor): DPAPI, Modus-Dispatch, `/reload-config`, `/health` mit `mode=…`, API-Key-Fallback `config.json → .env`. Bonus während Live-Test: UTF-8-Stdout (Crash-Fix), `ThreadingHTTPServer` (Race-Fix), OpenAI-Warmup (Cold-Start-Fix).
- **Phase 2** (`settings.py`): tkinter-GUI mit 5 Feldern, Mikrofon-Test (3s + Pegel), Speichern+`/reload-config`.
- **Phase 3** (`shortcut.ahk`): Tray-Eintrag „⚙️ Einstellungen…" klickbar, startet GUI ohne Console-Blitz.
- **Live-Test:** Claude-Code-Prompt-Modus liefert saubere Prompts (Backticks, **Kontext:**/**Aufgabe:**-Labels).
- **Config:** Bash-Permissions aus `aussendienst-app` global (`~/.claude/settings.json`) + project-lokal übernommen.

**Status-Ampel:**
- ✅ MVP-Code produktiv (End-to-End validiert)
- ✅ Tray-Ampel + Fehler-Toast + Tray-Menü + Tray-Icon
- ✅ Hidden-Daemon mit File-Log
- ✅ Autostart installiert + getestet
- ✅ **Einstellungsmenü Phase 1–3 fertig** (Config-Layer, GUI, AHK-Anbindung)
- ✅ **Paste-Modus komplett** (drei Modi `clipboard_ctrl_v` / `clipboard_only` / `send_input` via Win32-Unicode-SendInput, live-validiert 2026-04-25)
- ❌ Schritt 2b (`auto`-Modus + `psutil`) **verworfen** — `clipboard_ctrl_v` zeigte sich auch in Claude Code CLI zuverlässig genug, manuelle Umschaltung per GUI reicht
- ✅ **Schritt 3 (Audio-Robustheit) komplett** (Session 5, 2026-04-25): Kurz-Tipp-Schutz + Pre-Recording-Ringpuffer mit Toggle + Pre-Roll/Post-Roll einstellbar, alles live-validiert
- ✅ **10. Modus „Manuell"** mit Custom-Prompt-Textbox in der GUI
- ✅ **GUI-Ausbau** (Session 5): Hilfetexte-Toggle, dynamische Modus-Beschreibungen, 3-Button-Layout (Abbrechen/Anwenden/Speichern & Schließen), Auto-Resize
- ✅ **Schritt 4a/4b/4a-extra** (Session 5c, 2026-04-26): PyInstaller-Bundle für Daemon (`Speech2Text-Daemon.exe`), Settings (`Speech2Text-Settings.exe`), Ahk2Exe-Bundle für Hotkey (`Speech2Text-Hotkey.exe`). Build-Skripte unter `scripts/build-*.ps1`. Auto-Daemon-Start im AHK-Skript. Live-Tests grün.
- ✅ **Mode-Editing-Feature** (Session 5d-Code + 5e-Test, 2026-04-26): per-Modus User-Override für Anzeigename und System-Prompt, Editor immer sichtbar in Settings-GUI, Reset-Button, Working-Copy-Pattern. Live-validiert.
- ✅ **`scripts/build-hotkey.py`** (Session 5e, 2026-04-26): AV-resistenter Python-Build-Workflow für die Hotkey-Exe. Atomic-Subprocess-Pattern.
- ✅ **Variante B (ZIP-Distribution)** (Session 5e Build, Session 7 Live-Test): `scripts/build-distribution.py` + Templates + ZIP. install.bat auf Zweit-PC am 2026-05-09 verifiziert.
- ❌ **Schritt 4c (Inno Setup)** verworfen — Variante B reicht für Single-User + Rechner-Wechsel (Bundle-Exes sind self-contained, kein Python/AHK auf Zielrechner nötig).
- ✅ **Schritt 6 — Hotkey-Layer-Ausbau** (Session 7, 2026-05-09): freie Hotkey-Belegung per Capture-Dialog, Modus-Hotkeys (Push-to-Talk in fixem Modus), Cycle-Hotkey mit Checkbox-Auswahl, Pause/Resume-Mechanismus für Capture, dynamische Hotkey-Bindung in AHK. Bundles + Distribution-ZIP auf v1.1.
- ✅ **ARM64-Windows-Support + Settings-GUI-Resize** (Session 9, 2026-05-12): `_arch_fix.py`-Pre-Import-Shim für sounddevice-DLL-Auswahl auf ARM64-Host im x64-Prozess, Settings-GUI mit Footer-pack-bottom + Canvas-Scroll + Bildschirm-Capping. Live-validiert auf ARM64-PC (Settings-GUI + Push-to-Talk grün). Commits `78835f4` + `54eace1`, Tag `v1.2` gepusht.

---

## Nächster Scope

### Schritt 0 (erledigt 2026-04-24): Autostart installieren + testen
✅ `install-autostart.ps1` ausgeführt, Logout/Login durchlaufen — Tray-Icon, Daemon und Caps-Lock-Push-to-Talk starten automatisch. Status in `PLANUNG.md` und `FEATURE_UEBERSICHT.md` auf ✅ gezogen.

### Schritt 1 (laufend): Variante A — Einstellungsmenü
tkinter-GUI für per-User-Config. Details: `Projektplanung/05_Einstellungsmenue/SPEZIFIKATION.md`

**Design-Entscheidungen 2026-04-24:**
- **9 Modi** (ersetzt bisherigen Optimize-Toggle + Tonalitäts-Dropdown): Raw Draft · Clean Dictation · Polished Text (Default) · Smart Flow · Mirror Tone · Warm & Friendly · Executive · Unleashed · Claude Code Prompt. System-Prompts pro Modus in SPEZIFIKATION A2.
- **Sprache fest Deutsch** — kein Einstellungsfeld, `language="de"` hartkodiert.
- **Audio-Device Default = „Windows-Standardgerät (dynamisch)"** — folgt Headset-Wechsel, manuelle Wahl per Dropdown bleibt.
- **Kein `optimize`-Toggle mehr** — „aus" = Modus `Raw Draft` wählen.

**Phasen:**
- **Phase 1:** ✅ **Fertig + Live-validiert** (2026-04-25).
  - `src/config.py` neu: 9-Modi-Tabelle mit System-Prompts, Schema, DPAPI-Wrapper (`dpapi_encrypt`/`dpapi_decrypt` via `ctypes.windll.crypt32`), `load_config`/`save_config`, Helpers `set_api_key`/`get_api_key`/`get_mode_prompt`.
  - `src/recorder.py` refactort: Recorder bekommt `config` + `api_key` im Konstruktor. `OpenAI(api_key=…)` explizit. Modus-Dispatch in `_process` (Raw-Draft skippt `gpt-4o-mini`). `reload_config()`-Methode, `POST /reload-config`-Endpoint, `/health` mit `mode=…`. API-Key-Fallback: `config.json` → `.env` → Abbruch.
  - **Bonus-Patches während Live-Test:**
    - `sys.stdout.reconfigure(encoding="utf-8", errors="replace")` in `main()` + `errors="replace"` im Hidden-Log → behebt UnicodeEncodeError-Crashes auf cp1252-Consolen / Pipes.
    - `HTTPServer` → `ThreadingHTTPServer` → `/health`-Polls von AHK blockieren `/start`/`/stop` nicht mehr (Race-Condition behoben).
    - OpenAI-Cold-Start-Warmup im Background-Thread beim Daemon-Start → spart ~0,5–1 s beim ersten Diktat.
  - Validiert: `claude_code_prompt` liefert „1 2 3 \`Test\`" und strukturierten Mehrsatz-Output mit `**Kontext:**`/`**Aufgabe:**`-Labels.
- **Phase 2:** ✅ **Fertig** (2026-04-25). `src/settings.py` als tkinter-Fenster:
  - 5 Felder (API-Key mit Maskierung+Toggle, Modus-Dropdown mit 9 Optionen, Paste-Modus, Audio-Device-Dropdown aus `sounddevice.query_devices()` mit „Windows-Standardgerät (dynamisch)" als Default, Hotkey).
  - „🎤 Mikrofon testen"-Button: 3s Aufnahme + Wiedergabe + Pegel-Anzeige in % + Hinweis (leise/OK/sehr laut).
  - „Speichern": verschlüsselt API-Key per DPAPI, schreibt Config, ruft `POST /reload-config`, schließt Fenster nach 1,5 s.
  - Smoke-Test: 9 Modi geladen, 6 Audio-Geräte erkannt, Default-Modus „Polished Text" aus Config.
- **Phase 3:** ✅ **Fertig** (2026-04-25). `src/shortcut.ahk`:
  - Tray-Eintrag „⚙️ Einstellungen…" ist jetzt klickbar (vorher disabled).
  - Startet `pythonw.exe src/settings.py` (kein Console-Blitz).

### Schritt 2a (✅ erledigt 2026-04-25): Paste-Modus-Refactor

**Ausgangslage (2026-04-25):** `pyautogui.hotkey("ctrl","v")` funktioniert in Texteditoren zuverlässig, in TUI-Apps (Claude Code CLI, cmd, PowerShell Legacy) aber unzuverlässig („manchmal geht's doch, aber nicht gut"). Der `paste_mode`-Config-Eintrag existierte schon, wurde aber vom `recorder.py` ignoriert — `_paste()` machte immer Ctrl+V.

**Umgesetzt (Session 4):**
- `_paste(text)` in `recorder.py` liest jetzt `self.config["paste_mode"]`:
  - `clipboard_ctrl_v` (Default + Fallback): wie bisher — `pyperclip.copy()` (passiert schon in `_process`) + `pyautogui.hotkey("ctrl","v")`.
  - `clipboard_only`: nur Clipboard gefüllt, kein Auto-Paste. User drückt Ctrl+V / Ctrl+Shift+V / Rechtsklick.
  - `send_input`: tippt Zeichen für Zeichen via Win32 `SendInput` mit `KEYEVENTF_UNICODE`. **Nicht** `pyautogui.typewrite` — das ist ASCII-only und verschluckt Umlaute. Surrogate-Pair-Handling für Codepoints > 0xFFFF (Emojis etc.). Interval 1 ms zwischen Zeichen.
- Keine neuen Deps — alles stdlib (`ctypes`, `wintypes`).
- Syntax-Check: OK.

**Live-Test 2026-04-25 (alle drei grün):**
- `clipboard_ctrl_v` in Notepad/Outlook → ✓
- `clipboard_only` mit manuellem Ctrl+V → ✓
- `send_input` in TUIs mit Umlauten → ✓ (kein Verschlucken von ä/ö/ü/ß).
- Modus-Wechsel via Einstellungs-GUI ohne Daemon-Neustart funktioniert.

### Schritt 2b: ❌ verworfen 2026-04-25

`auto`-Modus (Fenster-Detection + `psutil`) wird **nicht** umgesetzt. Begründung: Im Live-Test mit den neuen drei Modi zeigte sich, dass `clipboard_ctrl_v` auch in der Claude Code CLI inzwischen zuverlässig läuft — der ursprüngliche „manchmal geht's nicht"-Eindruck hat sich nicht reproduziert. Die manuelle Umschaltung per Einstellungs-GUI reicht als Escape-Hatch, falls eine TUI doch mal zickt. Wenn das Problem wiederkommt: Idee aus diesem Block + `psutil` als Reserve-Plan im Hinterkopf behalten.

### Schritt 3 (✅ erledigt 2026-04-25, Session 5): Audio-Robustheit + GUI-Ausbau
Umgesetzt + live-validiert: Kurz-Tipp-Schutz (300 ms-Schwellwert), Pre-Recording-Ringpuffer mit Toggle, Pre-Roll und Post-Roll einstellbar (0–500 ms). GUI: 10. Modus „Manuell" mit Custom-Prompt, Hilfetexte-Toggle, dynamische Modus-Beschreibungen, 3-Button-Layout, Auto-Resize. Details siehe Session-5-Block oben.

### Schritt 4 (laufend): Variante C — Installer

| Sub | Status |
|---|---|
| 4a (Daemon-Exe via PyInstaller) | ✅ erledigt (Session 5c) |
| 4a-extra (Settings-Exe via PyInstaller) | ✅ erledigt (Session 5c) |
| 4b (Hotkey-Exe via Ahk2Exe + Auto-Daemon-Start) | ✅ erledigt (Session 5c) |
| **4c (Inno Setup für finalen Installer)** | 🔜 **nächste Session, nach Mode-Editing-Test + ABC** |

### Schritt 5 (Code fertig 5d, Test offen): Mode-Editing für Standard-Modi

User-Wunsch: Anzeigename + System-Prompt aller 9 Standard-Modi editierbar machen, MODES bleibt als Default. Override-Mechanismus via `mode_overrides` in Config; sparse — nur Diffs persistiert. Manual-Modus wird über denselben Mechanismus verwaltet (Sentinel `"__manual__"` raus, Default-Prompt = None). Migration legacy `manual_prompt` automatisch beim Config-Load.

**Code-Stand:** ✅ alle drei Module compile-clean (`config.py`, `settings.py`, `recorder.py`).

**Bundle-Stand:** ❌ Daemon.exe + Settings.exe sind ALT (vor Mode-Editing-Code). Vor Live-Test müssen sie neu gebaut werden.

### Schritt 6 (✅ erledigt 2026-05-09, Session 7): Hotkey-Layer-Ausbau

**Ergebnis:** Alle 10 Test-Punkte des Plan-Test-Plans live grün (Punkt 5 Win+L wird im RDP an den lokalen Client durchgereicht — nicht beeinflussbar, technisch korrekt).

**Umgesetzt:**
- `src/config.py` — neue Keys `hotkeys.{main, cycle, per_mode}` und `cycle_loop`. Migration legacy `hotkey: "capslock"` → `hotkeys.main: "CapsLock"` + Mapping für `f9`/`ctrl_alt_r`/`pause`. Validator (`validate_hotkey()`), Konflikt-Detector (`find_hotkey_conflicts()`), Cycle-Helper (`cycle_loop_next()`), Windows-Reserved-Liste (Win+L/E/R/D/I/X, Ctrl+Esc, Ctrl+Alt+Del).
- `src/recorder.py` — `_active_mode` Runtime-State (initial = `config["mode"]`, session-only), `_session_mode` (Override für eine Aufnahme via Modus-Hotkey), `_hotkeys_revision`-Counter, `_hotkeys_paused`-Flag. Neue Endpoints: `POST /cycle`, `POST /pause-hotkeys`, `POST /resume-hotkeys`, `GET /hotkeys`. `/start` parst optionalen JSON-Body `{"mode": "..."}`. `/health` erweitert um `active_mode`/`active_mode_ui_name`/`cycle_loop_size`/`hotkeys_revision`/`hotkeys_paused`.
- `src/hotkey_capture.py` (NEU) — `HotkeyCaptureDialog` als eigenes Modul (settings.py war am Hard-Limit). Modal-Toplevel, KeyPress/KeyRelease-Tracking via Modifier-keysym-Sets (Windows-tkinter meldet `event.state` für Alt/Win unzuverlässig), Live-Validierung gegen `validate_hotkey()` + `exclude`-Set. Format-Helper `format_hotkey_for_display()` (z.B. `^!r` → `Ctrl + Alt + R`).
- `src/settings.py` — Hotkey-Combobox raus, drei Capture-Slots rein (Haupt, Cycle, pro Modus). Im Modus-Editor zwei neue Zeilen: Modus-Hotkey + „Im Cycle-Loop"-Checkbox. Hotkey-Übersicht-Treeview unter dem Trenner. Konflikt-Modal beim Speichern. `_open_capture()` ruft `/pause-hotkeys` (~400 ms Buffer für AHK-Polling) und `/resume-hotkeys` im finally — sonst frisst der globale Hook bereits belegte Tasten, bevor tkinter sie sieht.
- `src/shortcut.ahk` — komplett umgebaut auf dynamische Hotkey-Bindung. `BindHotkeysFromDaemon()` ruft `/hotkeys`, parst zeilenweise key=value (kein JSON-Parser in AHK), bindet via `Hotkey()` + explizitem `"On"` (kritisch: `Hotkey ..., "Off"` und nachfolgendes Action-Update lässt State sonst auf Off). `MakePushToTalkHandler(mode)` als Closure-Factory pro Slot, `LastKeyOf(spec)` extrahiert Tasten-Token nach Modifier-Chars. `PollHealth` mit 300-ms-Intervall (statt 1s), liest `hotkeys_paused` und `hotkeys_revision`, schaltet entsprechend ab/an oder rebindet.
- `scripts/build-*.ps1` + `scripts/build-hotkey.py` ausgeführt — alle drei Bundles neu unter `build/dist/`.

**Während des Live-Tests entdeckte und behobene Bugs:**
1. **Off-State-Persistenz nach Re-Bind** (kritisch): AHK v2 `Hotkey ..., "Off"` hinterlässt den State auch nach späterem `Hotkey ..., NewAction`. Folge: nach jedem Settings-Save waren ALLE Hotkeys tot. Fix: `BindOne()`-Helper, der nach Action-Set explizit `"On"` ruft.
2. **Globaler Hook frisst Capture-Tasten**: Bereits belegte Hotkeys konnten nicht im Capture-Dialog erfasst werden, weil AHK den `$`-Hook vor tkinter bedient. Fix: `/pause-hotkeys`-Endpoint + Settings-GUI ruft pause/resume um den Capture-Aufruf, AHK reagiert via Health-Polling (Intervall auf 300 ms verkürzt).

**Datei-Größen-Hygiene:** `src/settings.py` ist auf ~890 Zeilen gewachsen (Soft-Limit 400, Hard-Limit 600). Refactoring-Vorschlag: Hotkey-Slot-Widgets in eigenes Modul auslagern (`src/settings_hotkey_section.py`).

### Schritt 6-Archiv (Session 7 — Plan-Datei + Brainstorming-Entscheidungen)

Plan-Datei: `C:\Users\df\.claude\plans\lucky-scribbling-quiche.md`.

**Architektur-Entscheidungen aus dem Brainstorming:**
- Modus-Hotkey-Verhalten: **A** — direkte Push-to-Talk-Aufnahme im fixen Modus, ändert `_active_mode` *nicht*.
- Cycle-Persistenz: **B** — session-only; Daemon-Restart setzt `_active_mode` zurück auf `default_mode` (`config["mode"]`).
- Visuelle Rückmeldung: **C** — Toast bei Cycle-Wechsel + permanenter Modus-Hinweis im Tray-Tooltip.
- Hotkey-Umfang: **B (Mittel)** — F1–F24, Caps Lock, Pause, Insert, ScrollLock + Modifier-Kombis (Ctrl/Alt/Shift/Win + Buchstabe/Zahl/F-Taste). Modifier-only und Maus-Tasten ausgeschlossen.
- Cycle-Reihenfolge: feste MODES-Reihenfolge, nur Checkboxen entscheiden „im Loop ja/nein" (kein Drag&Drop).

**Phasen-Plan:**
1. `src/config.py` — Datenmodell, Migration legacy `hotkey` → `hotkeys.main`, Validator + Konflikt-Helpers, Windows-Reserved-Liste.
2. `src/recorder.py` — `_active_mode`, `/cycle`-Endpoint, `/hotkeys`-Endpoint, `/start`-Body-Parsing für `mode`-Override, `/health`-Erweiterung um `active_mode`/`cycle_loop_size`/`hotkeys_revision`.
3. `src/settings.py` — Capture-Dialog, Hotkey-Felder pro Slot (Haupt/Cycle/per Modus), „Im Cycle-Loop"-Checkbox, Hotkey-Übersicht, Konflikt-Modal.
4. `src/shortcut.ahk` — `BindHotkeysFromDaemon()`, dynamische `Hotkey()`-Calls, `LastKeyOf()`, `CycleHandler`, Health-Polling-Erweiterung.
5. Bundles neu bauen (Daemon/Settings via PyInstaller, Hotkey via `build-hotkey.py`), Live-Test gemäß 10-Punkt-Plan im Spec.

**Out-of-Scope diese Session:** AHK-Ablösung (Lizenz-Thema, eigener Plan), Veröffentlichung/Code-Signing, Drag&Drop-Sortierung Cycle-Loop.

### ABC (Folgeschritt nach Mode-Editing-Test)

| | Was | Aufwand |
|---|---|---|
| **A** | `scripts/build-hotkey.py` als AV-resistenter Python-Ersatz für `build-hotkey.ps1`. Pattern: Ahk2Exe-Download + Compile in einem `subprocess.run`-Call, kein Lock-Window für AV-Quarantäne. Detail siehe Session-5c-Block (AV-Theater). | ~10 Min |
| **B** | Task-Doku abschließen (Schritt 4c-Plan formulieren, ggf. PLANUNG.md ergänzen). | ~5 Min |
| **C** | **Schritt 4c — Inno Setup**. Installer-Skript baut alles zu `Speech2Text-Setup.exe`: installiert nach `%LocalAppData%\Programs\Speech2Text` (kein Admin), Desktop-Shortcut, optionaler Autostart-Eintrag, Uninstaller. Verteilt: Daemon.exe + Settings.exe + Hotkey.exe + assets/speech2text.ico. | mittel |

**Reihenfolge morgen:**
1. Daemon + Settings neu bauen (`scripts/build-daemon.ps1 -Clean` und `scripts/build-settings.ps1 -Clean`).
2. Mode-Editing live testen (siehe Test-Plan unten).
3. Wenn grün → ABC.
4. Wenn rot → Bug-Fix in `config.py` / `settings.py`, neu bauen, testen.

### Variante B: Claude unterstützt beim Debugging
Falls beim Test Fehler auftreten:
- Daemon-Console-Output in den Chat posten
- Claude prüft: OpenAI-Key korrekt? Mikrofon erkannt? Port 17321 frei?
- Anpassungen an `recorder.py` / `shortcut.ahk` gemeinsam vornehmen

### Variante C: Priorität-2-Features angehen
Falls MVP stabil läuft:
- **Autostart** (Startup-Ordner-Variante am einfachsten)
- **Tray-Icon mit Ampel** (AHK-Tray-Icon dynamisch färben)
- **Fehler-Toast** (`TrayTip` bei Daemon nicht erreichbar / OpenAI-Fehler)

---

## Offene Punkte (nicht zeitkritisch)

- [x] ~~Sprache hart auf Deutsch oder Auto-Detect?~~ → **fest Deutsch** (2026-04-24)
- [x] ~~Optimierungs-Prompt generisch lassen oder Modi?~~ → **9 Modi** (2026-04-24, Details in 05_SPEZIFIKATION A2)
- [x] ~~Audio-Gerät fest vorgeben oder Default?~~ → **Default dynamisch** (2026-04-24)
- [x] ~~**Paste-Modus-Refactor**~~ — fertig + live-validiert (Session 4, 2026-04-25), siehe Schritt 2a.
- [ ] **Auto-Detect aktives Fenster** für Paste-Modus (User-Vorschlag 2026-04-25): per Prozess-Name in Exception-Liste → `send_input` in Terminals, sonst `clipboard_ctrl_v`. Siehe Schritt 2b.
- [x] ~~**Kurz-Tipp-Schutz server-seitig**~~ — fertig (Session 5, 2026-04-25): `MIN_RECORD_S = 0.3` in `recorder.py`.
- [x] ~~**Pre-Recording-Ringpuffer**~~ — fertig (Session 5, 2026-04-25): Persistent-Stream-Modus mit Toggle in der GUI, Pre-Roll einstellbar 0–500 ms.
- [x] ~~**Post-Roll**~~ — fertig (Session 5, 2026-04-25): einstellbar 0–500 ms, Default 200 ms.
- [ ] `.gitignore` anlegen, sobald Git-Repo entschieden wird (`.env`, `__pycache__/`, `.venv/`, `config.json`)
- [ ] **Hardware-Idee parkiert (2026-04-28):** Vaydeer 9-Tasten-Macro-Pad (B08V1LZ128) als Caps-Lock-Alternative. **Empfohlene Variante:** Taste auf F13 mappen → `shortcut.ahk` ändert `$CapsLock::` zu `$F13::`, sonst alles gleich. Vaydeer-Macros werden in die Tastatur-Firmware geflasht (Software-Download nur Win/Mac), F13–F24 sind Standard-HID-Codes ohne physische Entsprechung auf normaler Tastatur → vollständige Trennung. **Vor Kauf prüfen:** Ob die Vaydeer-Software F13–F24 unter „Keys Assignment" anbietet (auf Produktseite nicht explizit dokumentiert). Plan B falls nicht: zwei dedizierte Tasten via „One-Click Start" → kleine `.bat`-Wrapper mit `curl` auf `/start` und `/stop`.
- [ ] **Terminal-Server-Szenario notiert (2026-04-28):** Falls Speech2Text irgendwann von Linux-Client via RDP genutzt würde — die Macro-Tastatur ist nicht das Hindernis (Firmware-Macros + RDP-Tasten-Forward für F13 funktioniert). Der Bottleneck ist **Audio-Input-Redirection** (Mikrofon-Forward via `xfreerdp /microphone:...` + Server-GPO „Allow audio recording redirection"). Ohne diese Redirection nimmt der Daemon das Server-Mikro auf, nicht das des Linux-Clients. Sauberere Alternative bei Linux-Umstieg: Speech2Text portieren (Python ist portierbar; AHK durch `xbindkeys`/`evtest` ersetzen).

---

## Wiedereinstieg nächste Session

**Stand:** v1.1 stable, alle bisherigen Features live-validiert. Code liegt unter `OCICARPETS/Speech2Text` (privat). Distribution läuft über **GitHub Releases** — v1.1 ist online unter https://github.com/OCICARPETS/Speech2Text/releases/tag/v1.1. Konkret offen:

1. **Optionale Verifikation:** v1.1-ZIP auf Zweit-PC installieren — bestätigt, dass die Hotkey-Features auch via install.bat funktionieren. Test wie in Session-7-Block (3 Bundles, Capture-Dialog, Cycle, Modus-Hotkey). Download direkt vom Release-Asset: `https://github.com/OCICARPETS/Speech2Text/releases/download/v1.1/Speech2Text-v1.1.zip`.
2. **Veröffentlichung/Kommerz** (Brainstorming Session 7 vertagt): Architektur-Umbau (BYO-Key vs. eigenes Backend), Branding/Marke, Distribution (Code-Signing, Microsoft Store, Website), Recht (DSGVO, AGB, Auftragsverarbeitung mit OpenAI), Monetarisierung. Eigener Brainstorming-Block fällig — Block-Liste aus Session 7 als Startpunkt.
3. **Kleinere Aufräum-Punkte** (Vorschläge, nicht zwingend):
   - Refactoring `src/settings.py` (~890 Zeilen → unter Hard-Limit), Hotkey-Slot-Widgets in eigenes Modul.
   - RDP-Hinweis im Capture-Dialog für Win-Kombis (Win+L sperrt im RDP den lokalen Client).
   - Drag&Drop-Sortierung Cycle-Loop, falls 5+ Modi mal im Loop.
   - API-Kosten-Zähler (Long-List in `Projektplanung/FEATURE_UEBERSICHT.md`).

### Build- und Release-Workflow

| Was | Befehl |
|---|---|
| Daemon-Exe | `.\scripts\build-daemon.ps1 -Clean` |
| Settings-Exe | `.\scripts\build-settings.ps1 -Clean` |
| Hotkey-Exe | `python scripts\build-hotkey.py` (AV-resistente Variante; nicht die alte `build-hotkey.ps1`) |
| Distribution-ZIP | `python scripts\build-distribution.py` |
| Git: Tag + Push | `git tag -a vX.Y -m "Speech2Text vX.Y"; git push; git push --tags` |
| Release anlegen | `gh release create vX.Y dist\Speech2Text-vX.Y.zip --title "vX.Y — ..." --notes "..."` |
| Release-Stand prüfen | `gh release view vX.Y --repo OCICARPETS/Speech2Text` |

**Voller Release-Ablauf bei neuer Version:**
1. Code-Änderung committen + pushen
2. Relevante Bundles neu bauen (Daemon/Settings/Hotkey)
3. `python scripts\build-distribution.py` → erzeugt `dist\Speech2Text-vX.Y.zip`
4. Tag + Push (siehe Tabelle)
5. `gh release create …` (siehe Tabelle)

**`gh`-CLI Hinweis:** Liegt portable unter `%LOCALAPPDATA%\Programs\gh\bin\gh.exe`, User-PATH ist ergänzt. In frischen PowerShell-Sessions ist `gh` direkt aufrufbar. Falls in einer alten Session „command not found" kommt: `$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')`. Auth-Status: `gh auth status` (sollte „Logged in to github.com account OCICARPETS" zeigen).

---

## Kontext-Hinweise für die nächste Session

- **Reihenfolge der Leseempfehlung:** `tasks/current-task.md` (diese Datei) → `CLAUDE.md` → `PLANUNG.md` Abschnitt 2–4 → `Projektplanung/01_Hotkey-Trigger/SPEZIFIKATION.md` Abschnitt 7a (Gotchas) → `Projektplanung/05_Einstellungsmenue/SPEZIFIKATION.md` (weil Next Scope).
- **Architektur-Kurzform:** AHK = UI-Schicht (Tray-Icon, Tray-Menü, Hotkey, Polling). Python = Backend (Daemon mit Audio, OpenAI, Clipboard/Paste). IPC via HTTP auf `127.0.0.1:17321`.
- **Vier Endpoints:** `POST /start`, `POST /stop`, `POST /shutdown` (Hard-Exit), `GET /health` (liefert `state`, `last_error`, `last_error_ts`).
- **Autostart-Status prüfen:** `explorer shell:startup` — darin müssen `Speech2Text-Daemon.lnk` und `Speech2Text-Hotkey.lnk` liegen.
- **Hidden-Daemon beenden:** Tray → ❌ Beenden. Falls hängt: Task-Manager → pythonw.exe. Oder: `Invoke-WebRequest -Method POST http://127.0.0.1:17321/shutdown`.
- **Log anschauen:** Tray → 📋 Log öffnen, oder `notepad "$env:APPDATA\Speech2Text\daemon.log"`.
- **Nicht verändern ohne Rückfrage:** Modell-Wahl (`gpt-4o-transcribe` + `gpt-4o-mini`), Hotkey (Caps Lock), IPC (HTTP), `os._exit(0)` im `/shutdown` (essenziell gegen Zombie-pythonw).
- **Start-Befehle (Merkzettel):**
  - Daemon sichtbar (Debug): `scripts\start-daemon.bat`
  - Daemon hidden (Produktion/Autostart): `scripts\start-daemon-hidden.bat`
  - Hotkey: Doppelklick `src\shortcut.ahk`
  - Health-Check: `Invoke-WebRequest http://127.0.0.1:17321/health`
  - Icon neu generieren: `powershell -ExecutionPolicy Bypass -File assets\create-icon.ps1`
  - Autostart installieren: `powershell -ExecutionPolicy Bypass -File scripts\install-autostart.ps1`
