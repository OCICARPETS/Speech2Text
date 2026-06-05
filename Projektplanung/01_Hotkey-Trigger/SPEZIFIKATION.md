# SPEZIFIKATION: Hotkey-Trigger (AutoHotkey v2)

*Status: ✅ produktiv (Python-Tray seit v1.3, Mode-Switch-Toast v1.4) · Priorität: 1 · Erstellt: 2026-04-24 · Validiert: 2026-04-24 · Update: 2026-06-05*

---

## 1. Vision & Scope

Der **Hotkey-Trigger** ist die einzige Benutzeroberfläche des Tools. Das Feature übersetzt eine physikalische Tastenaktion (Caps Lock halten) in zwei Netzwerk-Pings an den lokalen Python-Daemon. Es ist bewusst klein gehalten: **nichts** soll hier Entscheidungen treffen oder Zustand halten — das gesamte Zustandsmodell lebt im Python-Daemon. AHK ist der „dummste" Teil des Systems: Taste runter → `POST /start`, Taste hoch → `POST /stop`. Alles andere ist Pythons Problem.

## 2. Enthaltene Anforderungen / Use Cases

- **A1:** Caps-Lock-Standardfunktion (Großschreib-Umschaltung) dauerhaft deaktivieren — auch beim Neustart des Skripts.
- **A2:** Bei `Capslock::` (Key-Down) einen asynchronen HTTP-POST an `http://127.0.0.1:17321/start` senden.
- **A3:** Bei `Capslock up::` (Key-Up) einen asynchronen HTTP-POST an `http://127.0.0.1:17321/stop` senden.
- **A4:** Mehrere Hotkey-Instanzen verhindern (`#SingleInstance Force`).
- **A5:** Bei unerreichbarem Daemon: stumm fehlschlagen, aber einmalig `TrayTip` mit Hinweis anzeigen.
- **A6:** Wildcard-Modifier (`*Capslock`) — damit das Skript auch feuert, wenn Caps Lock mit einem Modifier kombiniert angefasst wird.

## 3. Zielgruppe / Zielumgebung

- **Nutzer:** Daniel Franken (GF), ein Windows-Arbeitsplatz.
- **Plattform:** Windows 10/11 + AutoHotkey v2 (ab v2.0.0, typisch ab v2.0.11).
- **Voraussetzung:** Python-Daemon läuft bereits (sonst stumme Fehler beim Senden).

## 4. Abgrenzung

**Bewusst nicht im Scope dieses Features:**
- Keine Audio-Aufnahme (gehört zu `02_Audio-Daemon`).
- Keine Kommunikation mit OpenAI (gehört zu `03_KI-Pipeline`).
- Kein Text-Paste (gehört zu `04_Text-Ausgabe`).
- Kein Tray-Icon mit Status-Ampel — das ist ein Priorität-2-Feature.
- Kein Autostart — eigenes Priorität-2-Feature, gelöst über Windows-Mechanismen (Startup-Ordner / Task Scheduler), nicht über AHK.

## 5. Technische Skizze / Architektur

```
┌─────────────────┐        POST /start          ┌──────────────────┐
│   Caps Lock     │───────────────────────────▶│                  │
│   (physisch)    │                             │  Python-Daemon   │
│                 │        POST /stop           │  127.0.0.1:17321 │
│   AHK v2        │───────────────────────────▶│                  │
└─────────────────┘                             └──────────────────┘
       ↑
       │ SetCapsLockState "AlwaysOff"
       │ *Capslock::       → send("/start")
       │ *Capslock up::    → send("/stop")
```

### Kernfunktionen (Final — nach MVP-Validierung)

```ahk
SetCapsLockState "AlwaysOff"   ; Standard-Großschreibung deaktivieren

SendToDaemon(path) {
    req := ComObject("WinHttp.WinHttpRequest.5.1")
    req.Open("POST", "http://127.0.0.1:17321" . path, false)  ; sync!
    req.Send()
}

$CapsLock:: {                  ; $-Prefix = Hook-basiert (Pflicht in RDP)
    SendToDaemon("/start")
    KeyWait "CapsLock"         ; wartet auf Loslassen — kein Key-Repeat-Spam
    SendToDaemon("/stop")
}
```

### Sync statt Async (wichtige Korrektur gegenüber erstem Entwurf)

Ursprünglich war der POST **asynchron** geplant (`Open(url, true)`). Der Gedanke: Taste soll nicht hängen, wenn Daemon blockiert. Beim Live-Test stellte sich heraus: **bei async wird der ComObject-Handle am Funktionsende garbage-collected, bevor der Request rausgeht**. Der Daemon sieht den Call nie. Sync ist in der Praxis unmerklich schnell (< 5 ms), weil der Daemon sofort mit 200 OK antwortet und die schwere Arbeit im Worker-Thread abwickelt.

### Warum HTTP, nicht Named Pipe oder Socket
- AHK v2 hat sauberen Zugriff auf `WinHttp.WinHttpRequest.5.1` via COM.
- Python `http.server` ist stdlib — keine zusätzliche Abhängigkeit.
- Klare HTTP-Semantik hilft beim Debuggen (`Invoke-WebRequest http://127.0.0.1:17321/health`).

## 6. Umsetzungsplan

- [x] AHK v2-Syntax — `#Requires AutoHotkey v2.0`
- [x] `SetCapsLockState "AlwaysOff"` (unterbindet Großschreibung)
- [x] `#SingleInstance Force` gegen Doppel-Ladung
- [x] `$CapsLock::` mit Hook-Prefix (nicht `*`) + `KeyWait "CapsLock"`
- [x] `WinHttp` mit `Open(url, false)` (sync, nicht async)
- [x] Try/Catch um `SendToDaemon`, bei Fehler `TrayTip`
- [x] **End-to-End-Test 2026-04-24 auf OCI-DB2 (RDP):** Caps Lock → Aufnahme → Transkript → Optimierung → Auto-Paste ins Zielfenster erfolgreich. Diktat-Qualität: gut, Interpunktion passend, leichte Wort-Auslasser (z.B. Hilfsverben) selten aber gelegentlich.

## 7. Deployment

- Datei: `src/shortcut.ahk`
- Start: Doppelklick in Explorer (wenn AHK v2 installiert) oder über Autostart-Ordner.
- AHK v2 Download: https://www.autohotkey.com/download/ (Stand 2026-04-24)
- **Autostart:** Priorität-2 — gelöst per Shortcut zu `shortcut.ahk` im Windows-Startup-Ordner (`shell:startup`).

## 7b. Scope-Erweiterung Variante B (2026-04-24)

Während der Umsetzung von Variante B (Autostart + Komfort) ist das AHK-Skript deutlich gewachsen. Neue Verantwortungen:

### Status-Polling
`SetTimer PollHealth, 1000` — AHK macht einen `GET /health` pro Sekunde, setzt `A_IconTip` auf einen der vier Tooltip-Texte (offline/bereit/Aufnahme/verarbeite) und vergleicht `last_error_ts` gegen `LAST_SEEN_ERROR_TS`. Bei neuen Fehlern → `TrayTip` mit der Python-Meldung.

### Custom Tray-Menü
`A_TrayMenu.Delete()` entfernt die AHK-Standard-Einträge (Open/Reload/Exit). Eigene Einträge:
- `📋 Log öffnen` → `Run 'notepad.exe "...\daemon.log"'`
- `🔄 Daemon neu starten` → `POST /shutdown` + 500 ms Grace + `Run start-daemon-hidden.bat`
- `⚙️ Einstellungen… (folgt)` → disabled-Platzhalter für Feature `05_Einstellungsmenue`
- `❌ Beenden` → `POST /shutdown` + `ExitApp` (killt sowohl Daemon als auch AHK)

### Eigenes Tray-Icon
`TraySetIcon assets\speech2text.ico` — Electric-Blue-Kreis mit weißem „S2T"-Text, generiert per `assets/create-icon.ps1` (PowerShell + System.Drawing). Ersetzt das Standard-AHK-„H"-Logo, damit zwei parallel laufende AHK-Skripte visuell unterscheidbar sind.

### Autostart-Integration
`scripts/install-autostart.ps1` legt zwei Shortcuts in `shell:startup`: einen auf `start-daemon-hidden.bat`, einen auf `shortcut.ahk`. Beim nächsten Windows-Login starten Daemon (hidden, via pythonw) und Hotkey (AHK) automatisch.

## 7a. Gotchas (aus MVP-Test gelernt)

### RDP-Sessions erzwingen Hook-basierte Tastenerfassung
In einer RDP-Session greift `RegisterHotKey` (Default-Mechanismus hinter `*Capslock::`) nicht — nur der **Low-Level Keyboard Hook** bekommt die Events. Das `$`-Prefix zwingt AHK zur Hook-Variante. **Symptom ohne `$`:** Skript läuft, Hotkey-Definition korrekt, aber keine Reaktion auf Tastendruck. Hinweis: Lokal (Konsolen-Session, nicht RDP) funktioniert auch `*Capslock::`. Da wir sowohl lokal als auch RDP abdecken wollen, bleibt `$` Pflicht.

### `WinHttpRequest` async verschluckt den Request
`Open(url, true)` plus `Send()` in einem lokalen Scope: ComObject wird am Funktionsende zerstört, async-Send war noch nicht fertig. Der Daemon sieht den Call nicht. **Fix:** `Open(url, false)` (sync). Blocking ist unkritisch, Daemon antwortet in Millisekunden.

### Windows-Key-Repeat spammt `/start`
Bei gehaltener Taste feuert der Hotkey-Handler ~30x/Sekunde. Eine `up`-Variante (`$Capslock::` + `$Capslock up::`) führt dazu, dass der Daemon bei jedem Repeat `/start` bekommt (und korrekt mit „state=recording, ignoriert" antwortet — das Log ist aber zugespammt). **Fix:** `KeyWait "CapsLock"` innerhalb des einzelnen Hotkey-Handlers — AHK-Thread wartet intern auf Loslassen, dann `/stop`. Saubere Semantik, kein Spam.

### Caps-Lock-LED in RDP (kosmetisch)
Die LED am Client toggelt trotz `SetCapsLockState "AlwaysOff"` — RDP synchronisiert den Lock-State zwischen Client und Server. Großschreibung bleibt aber **funktional** deaktiviert (Server wins beim Text-Input). Auf lokalen Clients ohne RDP ist auch die LED aus. Akzeptiert, nicht zu fixen.

### CapsLock bleibt hängen bei Modifier-Druck (Python-Hook, v1.4 — 2026-06-05)
Mit CapsLock als Push-to-Talk-Hotkey (`(0, CapsLock)`) schlüpfte ein Druck **mit** Modifier (z.B. Ctrl+CapsLock, oder nach RDP-Reconnect ein stale `GetAsyncKeyState`-Modifier) durch den Hook: `_handle_event` suchte `(Ctrl, CapsLock)`, fand nichts und reichte das Event durch → Windows toggelte CapsLock **AN**. Da normale CapsLock-Drücke (mods=0) korrekt unterdrückt werden, ließ es sich danach nur per **Programm-Neustart** wieder ausschalten (Asymmetrie: geht an, aber nicht aus → Beweis, dass der Hook lebt und nur bei Modifier-Druck leakt). **Fix (`keyboard_hook.py`, vom User bestätigt — CapsLock-Verhalten ist laut `CLAUDE.md` bestätigungspflichtig):** (1) Lock-Tasten (`_LOCK_VKS` = CapsLock/NumLock/ScrollLock), modifier-los gebunden, werden **immer** abgefangen — Match via `(0, vk)` egal welcher Modifier gemeldet wird, gemerkte Bindung fürs KeyUp; **nur** Lock-Tasten (normale Tasten behalten den Modifier-Mismatch-Pass-Through). (2) Selbstheilung `_force_lock_off()` nach unterdrücktem Lock-Druck: `GetKeyState`-Toggle prüfen, bei „an" per `keybd_event` (LLKHF_INJECTED → vom eigenen Hook durchgereicht) ausschalten — ein hängendes CapsLock klärt sich bei der nächsten Nutzung selbst (der frühere Notausgang Ctrl+CapsLock entfällt durch Fix 1, daher ist Fix 2 Pflicht). Tests: `tests/test_keyboard_hook.py` Klasse `TestHandleEventLockKey`. Live validiert.

## 7c. v1.4 — Mode-Switch-Toast (Python-Tray, 2026-06-05)

Seit v1.3 ist der Hotkey-Trigger ein Python-Tray (`src/tray_app.py`, ersetzt `shortcut.ahk` — Transition dokumentiert in `Projektplanung/07_Veroeffentlichungs-Readiness/PLAN.md`). v1.4 ersetzt die Mode-Switch-Benachrichtigung beim Cycle-Hotkey durch ein eigenes, schnell verschwindendes Custom-Popup statt des trägen pystray-System-Toasts (~5 s, keine Queue).

**Neues Modul `src/toast.py` — `ToastController`:**
- Eigener Daemon-Thread `ToastUI` mit eigenem `tk.Tk()`-Mainloop; `pystray.Icon.run()` bleibt 1:1 auf dem Main-Thread (minimales Regressionsrisiko — Architektur-Entscheidung „Ansatz A" aus dem Multi-Agent-Design).
- `show(text, duration_ms)` ist von beliebigen Threads aufrufbar und macht NUR `queue.put_nowait` — alle Tk-Calls liegen ausschließlich im `ToastUI`-Thread (`_drain`/`_render`/`_hide`).
- **Coalesce:** schnelles Mehrfach-Cyclen aktualisiert denselben Toast und setzt den Hide-Timer via `after_cancel` zurück (kein Stapeln). Mode-Switch `TOAST_DURATION_MODE_MS = 1500`, Fehler/Info `TOAST_DURATION_INFO_MS = 4000`.
- Theme (dark/light) via `get_theme`-Callback aus `config.json`; `tkinter` wird LAZY erst im `ToastUI`-Thread importiert.

**`src/tray_app.py`:** `_cycle_action` → `_toast.show(..., TOAST_DURATION_MODE_MS)`; `_notify` führt jetzt **alle** Tray-Meldungen über das Popup (pystray.notify abgelöst, User-Entscheidung) + loggt System-/Fehlertext nach `tray.log` (nie Diktattext). Start/Stop in `run()`/`_action_exit`, `_toast_theme`-Helper.

**Build:** `scripts/build-tray.ps1` braucht `--collect-all tkinter` — das Tray-Bundle zog vorher KEIN tkinter (nur der Settings-Prozess). Exe 27,35 → 30,41 MB.

### Bekannte Fallen (v1.4)
- **`Tcl_AsyncDelete: async handler deleted by the wrong thread`** beim Beenden: tritt auf, wenn der Tcl-Interpreter vom Main-Thread abgeräumt wird, obwohl er im `ToastUI`-Thread erzeugt wurde. **Fix:** `stop()` macht KEINEN Tk-Aufruf vom Main-Thread, sondern setzt nur ein `Event`; der `ToastUI`-Thread beendet die Mainloop selbst (`_teardown_ui` via `_drain`) und gibt ALLE Tk-Referenzen im eigenen Thread frei (`self._root = self._win = self._label = None` im `_run_ui`-finally).
- **tkinter-Bundling:** ohne `--collect-all tkinter` läuft der Dev-Modus (System-Python hat tk), aber die gebaute Exe crasht beim `ToastUI`-Start. **Bundle-Smoke der gebauten Exe ist Pflicht** (Start mit totem Daemon-Ziel `S2T_DAEMON_URL=127.0.0.1:1`, `tray.log` auf `[Toast]`-Fehler prüfen).
- **Fokus-Klau:** Toplevel mit `overrideredirect` + `-topmost` + `-alpha 0.95`, KEIN `focus_set` — der Toast darf das aktive Eingabefenster während des Diktats nicht stören.
- **Onefile-Parent/Child:** `Start-Process` liefert die Bootloader-Parent-PID; zum sauberen Killen `Stop-Process -Name Speech2Text-Hotkey` (killt Parent + Child), nicht per einzelner PID.

## 8. Offene Punkte und Entscheidungen

- [ ] **Kurz-Tipp-Schutz?** Versehentliches Caps-Antippen (< 200 ms) produziert einen leeren Audio-Clip. Python ignoriert den bereits (`⚠ Keine Audiodaten aufgenommen`). Kein Blocker.
- [ ] **Akustisches Feedback?** Dezenter Ton bei Start/Stop/Fertig? Priorität 2.
- [ ] **Hotkey konfigurierbar?** Gelöst durch `05_Einstellungsmenue`.
- [ ] **Cross-Platform Mac/Linux?** AHK ist Windows-only. Für spätere Nutzung außerhalb OCI-Windows-Clients eigene Schicht nötig.

## 9. Historie & Verweise

- **Entstehung:** Briefing 2026-04-24 (siehe `BRIEFING.md`). Hotkey-Wahl: Ctrl+Alt+R → Caps Lock, zwischendurch F3/F9/Pause zur Fehleranalyse, nach Fixes (`$`, `sync=false`, `KeyWait`) wieder Caps Lock.
- **Erst-Validierung:** 2026-04-24 auf OCI-DB2 (Windows Server 2019, RDP-Session). User diktierte den Testsatz und danach einen produktiven Prompt — Transkription und KI-Optimierung gut, Auto-Paste funktioniert.
- **Zugehörige Dateien:** `src/shortcut.ahk`
- **Referenzen:**
  - AutoHotkey v2 Docs `SetCapsLockState`: https://www.autohotkey.com/docs/v2/lib/SetCapsLockState.htm (Abrufdatum 2026-04-24)
  - AHK v2 Hotkey-Prefixes (`$`, `*`, `~`): https://www.autohotkey.com/docs/v2/Hotkeys.htm#prefixes
  - AHK v2 `KeyWait`: https://www.autohotkey.com/docs/v2/lib/KeyWait.htm
  - WinHttp COM Reference: https://learn.microsoft.com/en-us/windows/win32/winhttp/winhttprequest
