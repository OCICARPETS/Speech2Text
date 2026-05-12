# Veröffentlichungs-Readiness v1.3 — Implementation Plan

> **Pfad-1-Auftrag aus 2026-05-12:** Was technisch nötig ist, damit Speech2Text
> verteilbar wird, OHNE dass strategische Entscheidungen (Branding, BYO-Key vs.
> Backend, Code-Signing, Monetarisierung) nötig werden. Branch:
> `v1.3-publish-readiness`. `master` bleibt unverändert auf v1.2 — der User
> nutzt v1.2 produktiv weiter.

**Goal:** AHK-Ablösung durch Python, Settings-Refactor, Erst-Start-Wizard,
Onboarding-Polish, SmartScreen-Doku, ZIP-Layout für externe Verteilung.

**Architektur:** Python-Tray-App (`src/tray_app.py`) ersetzt `src/shortcut.ahk`
1:1. Globale Hotkeys über Win32 Low-Level Keyboard Hook (WH_KEYBOARD_LL) via
ctypes — derselbe Mechanismus, den AHK intern nutzt, mit RDP-Kompatibilität
und CapsLock-Suppression. Tray-Icon + Menü via `pystray` (LGPL,
dynamisch-gelinkt). Eigener Polling-Thread für `/health`, eigener Hook-Thread
mit Win32-Message-Loop. Recorder bleibt unverändert; nur Onboarding-Erweiterung
in `/health` (last_dictation_ts).

**Tech-Stack:**
- ctypes (stdlib) — Win32 SetWindowsHookExW, GetMessageW, virtual-key-codes
- pystray>=0.19 — Tray-Icon + Menü (LGPL-3.0, dynamic linking ok)
- Pillow>=10 — Icon-Laden für pystray (HPND, MIT-kompatibel)
- urllib.request (stdlib) — Daemon-HTTP-Calls
- PyInstaller — bestehend, --noconsole für tray_app.py

---

## Ausgangs-Inventar (was muss alles ersetzt werden?)

`src/shortcut.ahk` (467 Zeilen) leistet:

1. **Tray-Icon + Tooltip** — dynamisch je nach `/health`-State
2. **Tray-Menü** — Log öffnen, Daemon-Restart, Settings öffnen, Beenden
3. **Auto-Daemon-Start** — wenn `/health` nicht antwortet, Daemon-Exe starten + warten bis bereit
4. **Globaler Low-Level-Hook** — `$`-Prefix erzwingt Hook-Mechanismus (RDP-fähig)
5. **Push-to-Talk** — Haupthotkey: KeyDown→`/start`, KeyWait, KeyUp→`/stop`
6. **Modus-Hotkeys** — wie Push-to-Talk, aber `/start` mit `{"mode":...}` Body
7. **Cycle-Hotkey** — Tap → POST `/cycle`, parse Response, TrayTip
8. **Pause/Resume** — Settings-GUI ruft `/pause-hotkeys` während Capture, AHK schaltet Hotkeys per Health-Poll ab/an
9. **Re-Bind bei Revision-Change** — `/health` liefert `hotkeys_revision`, bei Diff → `/hotkeys` neu lesen + binden
10. **CapsLock-Suppression** — `SetCapsLockState "AlwaysOff"` schaltet Großschreib-Toggle dauerhaft aus
11. **Fehler-Toast** — `/health` liefert `last_error_ts`, bei Zuwachs → TrayTip
12. **WinHttp-COM** — synchrone HTTP-Calls zum Daemon

**Lizenzproblem:** AHK v2 ist GPLv2. Kommerzielle Verbreitung von
`Hotkey.exe` (kompiliert via Ahk2Exe) erfordert mindestens Source-Angebot.
Für reine OCI-interne Verteilung ok, für externe Distribution Risiko.

---

## Architektur-Skizze Python-Ersatz

```
                     ┌─────────────────────┐
                     │ tray_app.py (main)  │
                     │  - pystray Loop     │
                     └──┬──────────┬───────┘
                        │          │
        ┌───────────────┘          └───────────────┐
        ▼                                          ▼
  ┌──────────────┐  Win32 Msg-Pump            ┌──────────────┐
  │ Hook-Thread  │  ◀───────────              │ Poll-Thread  │
  │  - LL-Hook   │  GetMessageW Loop          │  - 300ms     │
  │  - Dispatch  │                            │  - GET /hk   │
  └──────┬───────┘                            │  - GET /hlth │
         │ hotkey-event                       └──────┬───────┘
         ▼                                           │ revision/state
  ┌──────────────┐                                   ▼
  │ daemon_client│  POST /start, /stop, /cycle  ┌─────────────┐
  │ (urllib)     │                              │ tray_state  │
  └──────┬───────┘                              │ (tooltip,   │
         │                                      │  menu, hk)  │
         ▼                                      └─────────────┘
  http://127.0.0.1:17321 (recorder.py — unverändert)
```

**Thread-Sicherheit:**
- Hauptthread = pystray-Eventloop (blockierend)
- Hook-Thread = Win32-Message-Loop, ruft Callbacks an unsere Code-Layer (Lock pro hk-Map)
- Poll-Thread = `threading.Timer`-Loop, schreibt `tooltip`/`active_mode` zurück
- Hotkey-Map per `threading.Lock` geschützt; Re-Bind ist atomar (alte Map durch neue ersetzen)

**CapsLock-Suppression:** Im LL-Hook bei VK_CAPITAL gibt `CallNextHookEx` NICHT
weiter, sondern Return 1 → Windows sieht das Event nie, kein Toggle. Im
Hotkey-Manager-Layer wird parallel `/start`/`/stop` gefeuert.

**RDP-Kompatibilität:** Low-Level-Hook ist der Mechanismus, der in RDP-Sessions
funktioniert (siehe `PLANUNG.md` Zeile 139, "RegisterHotKey vs. Low-Level
Keyboard Hook"). Wir nutzen denselben Pfad — keine Regression.

---

## Datei-Struktur (was wird neu, was wird angefasst?)

| Datei | Aktion | Verantwortung |
|---|---|---|
| `src/tray_app.py` | **NEU** ~350 Z. | Tray-Loop, Auto-Daemon, Wizard-Trigger, Bootstrap |
| `src/keyboard_hook.py` | **NEU** ~250 Z. | Win32-LL-Hook, Spec-Parser, Hotkey-Manager-Klasse |
| `src/daemon_client.py` | **NEU** ~80 Z. | HTTP-Calls (GET/POST), Health-Parser, Auto-Start-Helper |
| `src/settings_hotkey_section.py` | **NEU** ~250 Z. | Hotkey-Slots + Treeview (aus settings.py extrahiert) |
| `src/settings.py` | **EDIT** | Hotkey-Section ausgelagert → Datei < 600 Zeilen |
| `src/recorder.py` | **EDIT minimal** | `last_dictation_ts` in `/health` ergänzen (für Onboarding-Hint) |
| `src/shortcut.ahk` | **DELETE** | Wird durch tray_app.py ersetzt |
| `scripts/build-tray.ps1` | **NEU** | PyInstaller --noconsole → Speech2Text-Hotkey.exe |
| `scripts/build-hotkey.ps1` | **DELETE** | Ahk2Exe-Variante obsolet |
| `scripts/build-hotkey.py` | **DELETE** | Ahk2Exe-Variante obsolet |
| `scripts/build-distribution.py` | **EDIT** | `shortcut.ahk` aus dist entfernen, `tray_app.py`-Build hinzu |
| `scripts/dist-templates/README.txt` | **EDIT** | SmartScreen-Hinweis, Lizenztexte |
| `scripts/dist-templates/install.bat` | **EDIT** | (ggf. nichts — die 3 .exe-Namen bleiben) |
| `scripts/dist-templates/LIZENZEN.txt` | **NEU** | Pflicht-Hinweis für pystray (LGPL) + Pillow + OpenAI |
| `requirements.txt` | **EDIT** | `pystray>=0.19`, `Pillow>=10` ergänzen |
| `tools/Ahk2Exe/` | **DELETE** | Nicht mehr gebraucht |
| `Projektplanung/01_Hotkey-Trigger/SPEZIFIKATION.md` | **EDIT-Anhang** | Historie-Eintrag "v1.3 AHK abgelöst" |

**Lizenz-Audit für `pystray` (LGPL-3.0):**
- Dynamische Linkung (Python-Import) ist LGPL-konform
- Auflagen: User muss pystray-Source erhalten können → Link auf
  github.com/moses-palmer/pystray + LIZENZEN.txt im ZIP
- Keine Pflicht zum Quelloffenen unseres Codes

---

## Implementation in Phasen (TDD wo sinnvoll, sonst direkter Build)

### Phase 1 — Spec-Parser (testbar ohne Win32)

**Datei:** `src/keyboard_hook.py` (Anfangsteil) + `tests/test_keyboard_hook.py`

- [ ] **Step 1.1: Test für AHK-Spec → (modifiers, vkcode) schreiben**

```python
# tests/test_keyboard_hook.py
import pytest
from keyboard_hook import parse_spec, MOD_CTRL, MOD_ALT, MOD_SHIFT, MOD_WIN

def test_simple_capslock():
    assert parse_spec("CapsLock") == (0, 0x14)

def test_f9():
    assert parse_spec("F9") == (0, 0x78)

def test_ctrl_alt_r():
    assert parse_spec("^!r") == (MOD_CTRL | MOD_ALT, 0x52)

def test_shift_win_f12():
    assert parse_spec("+#F12") == (MOD_SHIFT | MOD_WIN, 0x7B)

def test_digit():
    assert parse_spec("3") == (0, 0x33)

def test_invalid_returns_none():
    assert parse_spec("") is None
    assert parse_spec("Bogus") is None
```

- [ ] **Step 1.2: parse_spec implementieren**

```python
MOD_CTRL  = 1 << 0
MOD_ALT   = 1 << 1
MOD_SHIFT = 1 << 2
MOD_WIN   = 1 << 3

_MOD_CHARS = {"^": MOD_CTRL, "!": MOD_ALT, "+": MOD_SHIFT, "#": MOD_WIN}

# Virtual Key Codes (Win32 USER.h)
VK_CAPITAL = 0x14
VK_PAUSE   = 0x13
VK_INSERT  = 0x2D
VK_SCROLL  = 0x91
VK_NUMLOCK = 0x90

_KEY_MAP: dict[str, int] = {"CapsLock": VK_CAPITAL, "Pause": VK_PAUSE,
                            "Insert": VK_INSERT, "ScrollLock": VK_SCROLL,
                            "NumLock": VK_NUMLOCK}
for i in range(1, 25):
    _KEY_MAP[f"F{i}"] = 0x6F + i  # VK_F1 = 0x70 → 0x6F+1
for c in range(ord("A"), ord("Z") + 1):
    _KEY_MAP[chr(c)] = c
    _KEY_MAP[chr(c).lower()] = c
for d in range(10):
    _KEY_MAP[str(d)] = 0x30 + d


def parse_spec(spec: str) -> tuple[int, int] | None:
    """AHK-v2-Spec → (modifier_bitmask, vk_code). None bei ungültig."""
    if not spec:
        return None
    mods = 0
    i = 0
    while i < len(spec) and spec[i] in _MOD_CHARS:
        mods |= _MOD_CHARS[spec[i]]
        i += 1
    key = spec[i:]
    vk = _KEY_MAP.get(key)
    if vk is None:
        return None
    return (mods, vk)
```

- [ ] **Step 1.3: Tests grün — `python -m pytest tests/test_keyboard_hook.py -v`**

- [ ] **Step 1.4: Commit `feat(hotkey): AHK-Spec-Parser für Win32-Hook`**

### Phase 2 — Low-Level-Hook + Manager-Klasse

**Datei:** `src/keyboard_hook.py` (Erweiterung)

Architektur:
- `HotkeyManager` — public Klasse, hält Map `{(mods, vk): callback_on_press/release}`
- `start()` startet Hook-Thread mit Win32-Message-Loop
- `bind(spec, on_press, on_release)` — thread-safe
- `unbind_all()`
- `pause()` / `resume()` — temporäres Aus/An für Settings-Capture

LL-Hook-Callback:
- Modifier-State: VK_LCONTROL/RCONTROL/LMENU/RMENU/LSHIFT/RSHIFT/LWIN/RWIN via `GetAsyncKeyState`
- Key-Repeat-Filter: pro vk_code "currently_down"-Set, KeyDown nur feuern wenn nicht schon down
- Suppression: bei gebundenem Hotkey return 1 (nicht CallNextHookEx)
- Nicht-Hotkey-Events: CallNextHookEx (Standard)

- [ ] **Step 2.1: ctypes-Wrapper für SetWindowsHookExW + KBDLLHOOKSTRUCT**
- [ ] **Step 2.2: HotkeyManager.bind/unbind/pause/resume**
- [ ] **Step 2.3: Hook-Thread mit Message-Loop (GetMessageW)**
- [ ] **Step 2.4: Smoke-Test manuell: bind F12 mit print-Callback, F12 drücken → printed**
- [ ] **Step 2.5: Commit `feat(hotkey): Win32 Low-Level-Hook mit Push-to-Talk`**

### Phase 3 — Daemon-Client

**Datei:** `src/daemon_client.py`

- `health()` → dict | None
- `hotkeys()` → dict mit `revision`, `main`, `cycle`, `modes`
- `post(path, body=None)` → bool
- `start_mode(mode_id)` → bool (POST /start mit JSON-Body)
- `wait_alive(timeout=5.0)` → bool

Format: `/health` und `/hotkeys` liefern key=value pro Zeile. Parser ist trivial.

- [ ] **Step 3.1: daemon_client.py schreiben, Tests gegen Mock-HTTP-Server**
- [ ] **Step 3.2: Commit**

### Phase 4 — Tray-App

**Datei:** `src/tray_app.py`

- `bootstrap()`:
  1. Icon laden (`assets/speech2text.ico`)
  2. Daemon-Health prüfen, ggf. starten (Auto-Daemon-Start)
  3. Config laden — wenn API-Key fehlt: Settings-GUI öffnen, Tooltip "Bitte API-Key einrichten"
  4. `/hotkeys` lesen, HotkeyManager binden
  5. Poll-Thread starten (300ms)
  6. pystray.Icon.run() (blockierend)

- `Menu`: Log öffnen / Daemon neu starten / Einstellungen / Beenden

- `on_poll()`:
  - state → Tooltip-Update
  - revision-Diff → Re-Bind
  - hotkeys_paused-Flag → pause/resume
  - last_error_ts-Anstieg → `icon.notify(...)`
  - first_run_completed false UND last_dictation_ts==0 → Tooltip "Caps Lock drücken zum Diktieren"

- `make_handlers()` — pro Hotkey-Slot Callback-Factory wie AHK's MakePushToTalkHandler

- [ ] **Step 4.1: pystray-Icon + Menü**
- [ ] **Step 4.2: bootstrap() mit Health-Check + Auto-Daemon-Start**
- [ ] **Step 4.3: Poll-Loop**
- [ ] **Step 4.4: Hotkey-Bindings (main, cycle, per_mode)**
- [ ] **Step 4.5: Smoke-Test mit Mock-Daemon**
- [ ] **Step 4.6: Commit**

### Phase 5 — Recorder-Onboarding-Erweiterung

**Datei:** `src/recorder.py` (minimal-invasiv)

- `_last_dictation_ts: float` — wird im `_process()` nach erfolgreichem Diktat (vor `finally`) gesetzt
- `/health` liefert zusätzlich `last_dictation_ts=...`

- [ ] **Step 5.1: Feld + Update + `/health`-Zeile**
- [ ] **Step 5.2: Commit**

### Phase 6 — settings.py-Refactor

**Datei:** `src/settings_hotkey_section.py` + `src/settings.py`

- Klasse `HotkeySection`:
  - Konstruktor: `(parent, config, on_dirty)`
  - `build()` baut Widgets (Haupt-Slot, Cycle-Slot, Treeview)
  - `apply_to_config(cfg)` schreibt Werte zurück
  - `get_overrides_for_mode(mode_id)` — für Mode-Editor

- settings.py importiert + delegiert

- [ ] **Step 6.1: Section extrahieren**
- [ ] **Step 6.2: settings.py auf < 600 Zeilen prüfen**
- [ ] **Step 6.3: Manueller Test — Settings öffnen, Hotkey ändern, Speichern**
- [ ] **Step 6.4: Commit**

### Phase 7 — Erst-Start-Wizard + Onboarding-Polish

**Datei:** `src/tray_app.py`

- Beim Bootstrap: wenn `config.get("api_key_encrypted")` leer → `subprocess.Popen` Settings + Tooltip "Bitte API-Key einrichten"
- Wenn `first_run_completed=False` und `/health.last_dictation_ts>0` → Setze `first_run_completed=True` in config, persistiere

- [ ] **Step 7.1: Wizard-Trigger im Bootstrap**
- [ ] **Step 7.2: First-Run-Hint im Tooltip + Flag-Persistierung**
- [ ] **Step 7.3: Commit**

### Phase 8 — Build-Pipeline

**Datei:** `scripts/build-tray.ps1`

```powershell
param([switch]$Clean)
$proj = Split-Path -Parent $PSScriptRoot
if ($Clean) { Remove-Item -Recurse -Force "$proj\build\tray" -ErrorAction SilentlyContinue }
& "$proj\.venv\Scripts\pyinstaller.exe" `
    --name "Speech2Text-Hotkey" `
    --onefile --noconsole `
    --icon "$proj\assets\speech2text.ico" `
    --add-data "$proj\assets\speech2text.ico;assets" `
    --collect-all pystray `
    --collect-all PIL `
    --paths "$proj\src" `
    --workpath "$proj\build\tray\work" `
    --specpath "$proj\build\tray" `
    --distpath "$proj\build\dist" `
    "$proj\src\tray_app.py"
```

- [ ] **Step 8.1: build-tray.ps1 schreiben**
- [ ] **Step 8.2: Erst-Build durchlaufen lassen, Größe + Funktion prüfen**
- [ ] **Step 8.3: Alte build-hotkey.ps1 / build-hotkey.py / shortcut.ahk löschen**
- [ ] **Step 8.4: Commit**

### Phase 9 — Distribution-ZIP-Layout + SmartScreen-Doku

**Dateien:** `scripts/build-distribution.py`, `scripts/dist-templates/README.txt`, `scripts/dist-templates/LIZENZEN.txt`

Inhalt LIZENZEN.txt:
```
Speech2Text nutzt folgende Open-Source-Komponenten:

- pystray (LGPL-3.0)
  Source: https://github.com/moses-palmer/pystray
  Lizenztext: siehe lizenzen/pystray-LICENSE.txt

- Pillow (HPND/MIT-kompatibel)
  Source: https://github.com/python-pillow/Pillow

- OpenAI Python SDK (Apache-2.0)
- sounddevice (MIT) ...
```

README.txt-Erweiterung (SmartScreen):
```
Beim ersten Start meldet Windows ggf. „Ihr PC wurde durch Windows
geschützt" (SmartScreen). Klicke auf „Weitere Informationen" und
dann „Trotzdem ausführen". Speech2Text ist nicht code-signiert —
das vermeiden wir, weil eine EV-Zertifikat 200-400 €/Jahr kostet
und für ein internes Tool unverhältnismäßig ist.
```

- [ ] **Step 9.1: README.txt + LIZENZEN.txt schreiben**
- [ ] **Step 9.2: build-distribution.py: shortcut.ahk raus, neue Datei-Liste**
- [ ] **Step 9.3: Test-Build ZIP, manuell entpacken, README sichten**
- [ ] **Step 9.4: Commit**

### Phase 10 — E2E-Tests in isolierter Umgebung

**Vorgehen:**
1. Test-Bundle in `build/test-install/` entpacken (NICHT `%LocalAppData%`)
2. **v1.2-Daemon des Users LÄUFT WEITER auf Port 17321** — wir nutzen daher Mock-Server für Tray-Test
3. Headless-Tests:
   - `pytest tests/test_keyboard_hook.py` — Spec-Parser
   - `pytest tests/test_daemon_client.py` — HTTP-Layer gegen Mock
4. Manueller Mini-Live-Test (nur falls v1.2-Daemon ausgeschaltet werden darf):
   - v1.2-Daemon via `Invoke-WebRequest http://127.0.0.1:17321/shutdown` stoppen
   - Test-Bundle starten, F12 als Test-Hotkey nutzen
   - Diktat-Pipeline grün?
   - Tray-Menü-Aktionen
   - Pause/Resume-Test (via Settings-GUI Capture-Dialog)
   - Test-Bundle beenden, v1.2-Hotkey.exe + Daemon.exe aus Autostart erneut starten

**Aber:** User schläft, also setze ich auf Mock-Tests + nicht-intrusive manuelle Tray-Smoke-Tests (Tray erscheint, Menü reagiert) ohne globale Hotkeys live zu binden. Globale Hotkeys werde ich konservativ NUR mit F12 testen, weil das v1.2 nicht belegt. Wenn das funktioniert, ist die Architektur valide.

- [ ] **Step 10.1: Unit-Tests durchlaufen**
- [ ] **Step 10.2: Tray-Smoke gegen Mock-Server (Mock auf 17322)**
- [ ] **Step 10.3: F12-Hotkey-Bindung Live-Test (parallel zu laufendem v1.2)**
- [ ] **Step 10.4: Bug-Liste abarbeiten, neu bauen, erneut testen**
- [ ] **Step 10.5: Bei stabilem Stand: Branch-Push origin/v1.3-publish-readiness**

### Phase 11 — Doku + Final-Commit

- [ ] **Step 11.1: `tasks/current-task.md` mit Session-10-Block**
- [ ] **Step 11.2: `PLANUNG.md` Roadmap-Eintrag v1.3**
- [ ] **Step 11.3: `Projektplanung/FEATURE_UEBERSICHT.md` Long-List-Items abhaken**
- [ ] **Step 11.4: Branch-Push, KEIN merge auf master**

---

## Out-of-Scope (explizit nicht in v1.3)

- Branding / Produkt-Umbenennung
- BYO-Key-Architektur (Backend-Proxy-Variante)
- Code-Signing (EV-Cert)
- DSGVO-/AGB-Texte
- Microsoft Store / Website
- Monetarisierungs-Modell
- Auto-Update-Mechanismus (Updates kommen weiter als neue ZIP via GitHub Release)
- Drag&Drop für Cycle-Loop (UI-Polish, kein Blocker)

---

## Risiken + Mitigations

| Risiko | Mitigation |
|---|---|
| pystray-Tray-Icon erscheint auf manchen Windows-Builds nicht | Fallback: eigener Shell_NotifyIconW via ctypes — als Plan B vorbereitet |
| Low-Level-Hook wird vom v1.2-AHK-Hook gestört (beide aktiv) | Test mit F12-Hotkey statt CapsLock, weil v1.2 nur CapsLock belegt |
| Settings.exe v1.2 ruft `/pause-hotkeys` und v1.3-Tray reagiert nicht synchron | Polling-Intervall 300ms gleich wie AHK — identisches Verhalten |
| PyInstaller-Bundle wird wegen Defender quarantäniert | Bekanntes Phänomen (siehe Memory `feedback_av_atomic_subprocess.md`); im Build-Skript dokumentiert, Build im venv-Subprocess |
| pystray-LGPL-Compliance unklar | LIZENZEN.txt + Source-Link → erfüllt LGPL §6 |

---

## Self-Review

**Spec-Coverage:** Alle 6 Pfad-1-Punkte abgedeckt (AHK-Ablösung Phase 1-4+8,
settings.py-Refactor Phase 6, Wizard Phase 7, Onboarding-Polish Phase 5+7,
SmartScreen-Doku Phase 9, ZIP-Layout Phase 9).

**Placeholder-Scan:** Keine TBD/TODO im Plan; jede Phase hat konkrete
Datei-Pfade + Beispiel-Code.

**Type-Consistency:** parse_spec gibt `tuple[int, int] | None` zurück;
HotkeyManager-bind-Signatur konsumiert dasselbe Tupel; daemon_client-
Funktionen alle `dict | None` oder `bool`.

**Reihenfolge:** Spec-Parser zuerst (testbar), Hook zweitens (manuell),
daemon_client + tray_app drittens, dann Refactor + Wizard, zuletzt Build +
Tests.
