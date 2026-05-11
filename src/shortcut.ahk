; Speech2Text — dynamische Hotkey-Bindung + Tray-Menü (AutoHotkey v2)
;
; Hotkeys werden zur Laufzeit beim Daemon abgefragt (GET /hotkeys), gebunden
; via Hotkey()-Funktion und bei reload-config (sichtbar an /health-Feld
; hotkeys_revision) neu gebunden. Drei Hotkey-Typen:
;   - Haupt-Hotkey:   Push-to-Talk im aktiven Modus
;   - Cycle-Hotkey:   Tap, schaltet aktiven Modus durch /cycle
;   - Modus-Hotkeys:  Push-to-Talk in fixem Modus (POST /start mit mode-Body)
;
; Tray-Tooltip zeigt zusätzlich den aktiven Modus; bei Cycle-Wechsel popt
; ein TrayTip mit dem neuen Modusnamen.
;
; Wichtige Erkenntnisse aus dem MVP-Test (2026-04-24):
;   - $-Prefix ist Pflicht: Hook-basierte Tastenerfassung funktioniert in RDP,
;     RegisterHotKey (* ohne $) bleibt stumm.
;   - WinHttp synchron (Open(..., false)): bei async wird der ComObject-Handle
;     am Funktionsende zerstört, bevor der Request rausgeht.
;   - KeyWait statt up-Variante: verhindert Key-Repeat-Spam von Windows.

#Requires AutoHotkey v2.0
#SingleInstance Force

; Caps-Lock-Standardfunktion (Großschreibung) dauerhaft deaktivieren — auch
; wenn ein anderer Hotkey gebunden ist; CapsLock soll nie als Großschreib-
; Toggle wirken.
SetCapsLockState "AlwaysOff"

DAEMON_URL      := "http://127.0.0.1:17321"
LOG_PATH        := EnvGet("APPDATA") . "\Speech2Text\daemon.log"
SETTINGS_PY     := A_ScriptDir . "\settings.py"
PYTHONW_EXE     := A_ScriptDir . "\..\.venv\Scripts\pythonw.exe"

; Icon-Lookup: Bundle-Pfad zuerst, Dev-Setup als Fallback.
ICON_CANDIDATES := [
    A_ScriptDir . "\assets\speech2text.ico",
    A_ScriptDir . "\..\assets\speech2text.ico"
]
ICON_PATH := ""
for path in ICON_CANDIDATES {
    if FileExist(path) {
        ICON_PATH := path
        break
    }
}
if ICON_PATH != ""
    TraySetIcon ICON_PATH

; --- Auto-Daemon-Start -----------------------------------------------------

DAEMON_PATH_CANDIDATES := [
    A_ScriptDir . "\Speech2Text-Daemon.exe",
    A_ScriptDir . "\..\build\dist\Speech2Text-Daemon.exe",
    A_ScriptDir . "\..\scripts\start-daemon-hidden.bat"
]

DaemonStartCommand() {
    global DAEMON_PATH_CANDIDATES
    for path in DAEMON_PATH_CANDIDATES {
        if FileExist(path)
            return path
    }
    return ""
}

DaemonAlive() {
    global DAEMON_URL
    try {
        req := ComObject("WinHttp.WinHttpRequest.5.1")
        req.SetTimeouts(200, 200, 200, 200)
        req.Open("GET", DAEMON_URL . "/health", false)
        req.Send()
        return req.Status = 200
    } catch {
        return false
    }
}

EnsureDaemonRunning() {
    if DaemonAlive()
        return
    cmd := DaemonStartCommand()
    if cmd = "" {
        TrayTip "Speech2Text",
            "Daemon-Exe nicht gefunden — bitte Installation prüfen.",
            "Iconx"
        return
    }
    Run cmd,, "Hide"
    Loop 15 {
        Sleep 200
        if DaemonAlive()
            return
    }
    TrayTip "Speech2Text",
        "Daemon-Boot dauert länger als erwartet — siehe Log.",
        "Iconi"
}

EnsureDaemonRunning()

; --- HTTP-Helpers ----------------------------------------------------------

Post(path) {
    global DAEMON_URL
    try {
        req := ComObject("WinHttp.WinHttpRequest.5.1")
        req.SetTimeouts(300, 300, 300, 3000)
        req.Open("POST", DAEMON_URL . path, false)
        req.Send()
    } catch as e {
        TrayTip "Speech2Text", "Daemon nicht erreichbar:`n" . e.Message, "Iconx"
    }
}

PostJson(path, jsonBody) {
    global DAEMON_URL
    try {
        req := ComObject("WinHttp.WinHttpRequest.5.1")
        req.SetTimeouts(300, 300, 300, 3000)
        req.Open("POST", DAEMON_URL . path, false)
        req.SetRequestHeader("Content-Type", "application/json; charset=utf-8")
        req.Send(jsonBody)
    } catch as e {
        TrayTip "Speech2Text", "Daemon nicht erreichbar:`n" . e.Message, "Iconx"
    }
}

PostAndRead(path) {
    global DAEMON_URL
    try {
        req := ComObject("WinHttp.WinHttpRequest.5.1")
        req.SetTimeouts(300, 300, 300, 3000)
        req.Open("POST", DAEMON_URL . path, false)
        req.Send()
        if (req.Status = 200)
            return req.ResponseText
        return ""
    } catch {
        return ""
    }
}

GetText(path) {
    global DAEMON_URL
    try {
        req := ComObject("WinHttp.WinHttpRequest.5.1")
        req.SetTimeouts(300, 300, 300, 3000)
        req.Open("GET", DAEMON_URL . path, false)
        req.Send()
        if (req.Status = 200)
            return req.ResponseText
        return ""
    } catch {
        return ""
    }
}

; key=value-Body parsen → Map. Mehrere identische Keys: letzter gewinnt.
ParseKeyValueBody(body) {
    result := Map()
    Loop Parse, body, "`n", "`r" {
        line := A_LoopField
        eq := InStr(line, "=")
        if eq > 0 {
            k := SubStr(line, 1, eq - 1)
            v := SubStr(line, eq + 1)
            result[k] := v
        }
    }
    return result
}

ParseValue(body, key) {
    if RegExMatch(body, "m)^" . key . "=(.*)$", &m)
        return m[1]
    return ""
}

; --- Hotkey-Binding --------------------------------------------------------
; Wir tracken die zur Laufzeit gebundenen Specs in einer Liste, damit wir
; sie beim Re-Bind sauber via Hotkey "<spec>", "Off" deaktivieren können.

global BoundHotkeys := []
global HOTKEYS_REVISION := -1
global HOTKEYS_PAUSED := false

; Letzter Token nach den Modifier-Chars ^!+#. Beispiele:
;   "^!r"      → "r"
;   "F9"       → "F9"
;   "+#CapsLock" → "CapsLock"
LastKeyOf(spec) {
    i := 1
    Loop Parse, spec {
        c := A_LoopField
        if (c != "^" && c != "!" && c != "+" && c != "#")
            return SubStr(spec, i)
        i++
    }
    return ""
}

UnbindAllHotkeys() {
    global BoundHotkeys
    for spec in BoundHotkeys {
        try {
            Hotkey "$" . spec, "Off"
        }
    }
    BoundHotkeys := []
}

; Push-to-Talk-Handler-Factory: bindet einen Modus-id an einen Closure-
; Handler. Modus = "" → Haupt-Hotkey ohne mode-Override.
MakePushToTalkHandler(mode) {
    return (thisHotkey) => HandlePushToTalk(thisHotkey, mode)
}

HandlePushToTalk(thisHotkey, mode) {
    ; thisHotkey hat $-Prefix → strippen für LastKeyOf.
    spec := SubStr(thisHotkey, 1, 1) = "$" ? SubStr(thisHotkey, 2) : thisHotkey
    if mode = "" {
        Post("/start")
    } else {
        ; JSON-Body mit dem mode_id (Doppel-Quotes als "" escapen — mode_id
        ; ist immer ASCII identifier, aber sicher ist sicher).
        safe := StrReplace(mode, '"', '\"')
        PostJson("/start", '{"mode":"' . safe . '"}')
    }
    KeyWait LastKeyOf(spec)
    Post("/stop")
}

CycleHandler(thisHotkey) {
    body := PostAndRead("/cycle")
    if body = "" {
        TrayTip "Speech2Text",
            "Cycle-Liste ist leer — in den Einstellungen Modi für den "
            . "Cycle aktivieren.", "Iconi"
        return
    }
    ui := ParseValue(body, "ui_name")
    if ui != ""
        TrayTip "Modus: " . ui, "Speech2Text", 1
}

; Bindet einen Hotkey + setzt explizit "On". Wichtig: Beim Re-Bind hatten
; wir vorher per UnbindAllHotkeys() den State auf "Off" gesetzt — eine
; nachfolgende `Hotkey ..., NewAction` ändert nur die Action, NICHT den
; State. Ohne explizites "On" bleiben re-gebundene Hotkeys tot.
BindOne(spec, handler, slotLabel) {
    global BoundHotkeys
    try {
        Hotkey "$" . spec, handler
        Hotkey "$" . spec, "On"
        BoundHotkeys.Push(spec)
        return true
    } catch as e {
        TrayTip "Speech2Text",
            slotLabel . " '" . spec . "' konnte nicht gebunden werden:`n"
            . e.Message, "Iconx"
        return false
    }
}

; Bindet Hotkeys gemäß Daemon-Antwort. Idempotent — vorhandene Bindings
; werden zuerst abgehängt.
BindHotkeysFromDaemon() {
    global BoundHotkeys, HOTKEYS_REVISION
    body := GetText("/hotkeys")
    if body = "" {
        ; Daemon antwortet nicht — Hotkeys lassen wir unangetastet, der
        ; Health-Poll wird's beim nächsten Mal versuchen.
        return false
    }
    UnbindAllHotkeys()
    fields := ParseKeyValueBody(body)

    main := fields.Has("main") ? fields["main"] : ""
    if main != ""
        BindOne(main, MakePushToTalkHandler(""), "Haupt-Hotkey")

    cycle := fields.Has("cycle") ? fields["cycle"] : ""
    if cycle != ""
        BindOne(cycle, CycleHandler, "Cycle-Hotkey")

    count := fields.Has("mode_count") ? Integer(fields["mode_count"]) : 0
    Loop count {
        i := A_Index - 1
        idKey := "mode." . i . ".id"
        spKey := "mode." . i . ".spec"
        if !fields.Has(idKey) || !fields.Has(spKey)
            continue
        mid  := fields[idKey]
        spec := fields[spKey]
        if spec = ""
            continue
        BindOne(spec, MakePushToTalkHandler(mid), "Modus-Hotkey (" . mid . ")")
    }

    rev := fields.Has("revision") ? fields["revision"] : ""
    if rev != ""
        HOTKEYS_REVISION := Integer(rev)
    return true
}

BindHotkeysFromDaemon()

; --- Tray-Tooltip + Modus-Tracking + Re-Bind-on-Reload ---------------------

TIP_OFFLINE    := "Speech2Text · Daemon offline"
TIP_IDLE       := "Speech2Text · bereit"
TIP_RECORDING  := "Speech2Text · 🎤 Aufnahme läuft"
TIP_PROCESSING := "Speech2Text · ⏳ verarbeite …"

A_IconTip := TIP_OFFLINE
LAST_SEEN_ERROR_TS := -1.0

PollHealth() {
    global DAEMON_URL, TIP_OFFLINE, TIP_IDLE, TIP_RECORDING, TIP_PROCESSING
    global LAST_SEEN_ERROR_TS, HOTKEYS_REVISION, HOTKEYS_PAUSED, BoundHotkeys
    body := GetText("/health")
    if body = "" {
        A_IconTip := TIP_OFFLINE
        return
    }
    state := ""
    if InStr(body, "state=recording")
        state := "recording"
    else if InStr(body, "state=processing")
        state := "processing"
    else
        state := "idle"

    activeUi := ParseValue(body, "active_mode_ui_name")
    base := state = "recording" ? TIP_RECORDING
          : state = "processing" ? TIP_PROCESSING
          : TIP_IDLE
    A_IconTip := activeUi != "" ? base . " (Modus: " . activeUi . ")" : base

    ; Fehler-Toast bei neuem last_error
    ts_str := ParseValue(body, "last_error_ts")
    err    := ParseValue(body, "last_error")
    ts := ts_str = "" ? 0.0 : ts_str + 0.0
    if (LAST_SEEN_ERROR_TS < 0.0) {
        LAST_SEEN_ERROR_TS := ts
    } else if (ts > LAST_SEEN_ERROR_TS && err != "") {
        TrayTip "Speech2Text", err, "Iconx"
        LAST_SEEN_ERROR_TS := ts
    }

    ; Pause-Flag: Settings-GUI hält während Capture-Dialog Hotkeys an,
    ; damit globale Hooks die Erfassung nicht abfangen. Pause/Resume sind
    ; idempotent.
    paused := InStr(body, "hotkeys_paused=on") > 0
    if (paused && !HOTKEYS_PAUSED) {
        UnbindAllHotkeys()
        HOTKEYS_PAUSED := true
    } else if (!paused && HOTKEYS_PAUSED) {
        HOTKEYS_PAUSED := false
        BindHotkeysFromDaemon()
    }

    ; Re-Bind, wenn der Daemon eine neue Hotkey-Revision meldet (passiert
    ; nach POST /reload-config aus der Settings-GUI). Während Pause kein
    ; Re-Bind — das wird beim Resume nachgeholt.
    if !HOTKEYS_PAUSED {
        rev_str := ParseValue(body, "hotkeys_revision")
        if rev_str != "" {
            rev := Integer(rev_str)
            if (HOTKEYS_REVISION >= 0 && rev != HOTKEYS_REVISION) {
                BindHotkeysFromDaemon()
            }
        }
    }
}

PollHealth()
; Polling-Intervall: 300 ms. Damit liegt die maximale Latenz zwischen
; /pause-hotkeys-Call (Settings-GUI) und AHK-Reaktion bei < 300 ms — die
; Settings-GUI wartet zur Sicherheit ~400 ms vor dem Capture-Open.
SetTimer PollHealth, 300

; --- Tray-Menü (Rechtsklick) -----------------------------------------------

MENU_LABEL_LOG       := "📋 Log öffnen"
MENU_LABEL_RESTART   := "🔄 Daemon neu starten"
MENU_LABEL_SETTINGS  := "⚙️ Einstellungen…"
MENU_LABEL_EXIT      := "❌ Beenden"

A_TrayMenu.Delete()
A_TrayMenu.Add(MENU_LABEL_LOG,      (*) => OpenLog())
A_TrayMenu.Add(MENU_LABEL_RESTART,  (*) => RestartDaemon())
A_TrayMenu.Add()
A_TrayMenu.Add(MENU_LABEL_SETTINGS, (*) => OpenSettings())
A_TrayMenu.Add()
A_TrayMenu.Add(MENU_LABEL_EXIT,     (*) => ExitAll())

OpenLog() {
    global LOG_PATH
    if FileExist(LOG_PATH) {
        Run 'notepad.exe "' . LOG_PATH . '"'
    } else {
        MsgBox "Log-Datei existiert noch nicht:`n" . LOG_PATH
            . "`n`nEntsteht beim ersten Start des hidden-Daemons.",
            "Speech2Text", "Iconi"
    }
}

SETTINGS_PATH_CANDIDATES := [
    A_ScriptDir . "\Speech2Text-Settings.exe",
    A_ScriptDir . "\..\build\dist\Speech2Text-Settings.exe"
]

OpenSettings() {
    global SETTINGS_PATH_CANDIDATES, PYTHONW_EXE, SETTINGS_PY
    for path in SETTINGS_PATH_CANDIDATES {
        if FileExist(path) {
            Run '"' . path . '"',, "Hide"
            return
        }
    }
    if FileExist(PYTHONW_EXE) && FileExist(SETTINGS_PY) {
        Run '"' . PYTHONW_EXE . '" "' . SETTINGS_PY . '"',, "Hide"
        return
    }
    MsgBox "Settings-Komponente nicht gefunden.`n`nGesucht:`n"
        . "  • Speech2Text-Settings.exe (Bundle)`n"
        . "  • " . PYTHONW_EXE . " + " . SETTINGS_PY . " (Dev)`n`n"
        . "Build mit: scripts\build-settings.ps1",
        "Speech2Text", "Iconx"
}

RequestShutdown() {
    global DAEMON_URL
    try {
        req := ComObject("WinHttp.WinHttpRequest.5.1")
        req.SetTimeouts(500, 500, 500, 2000)
        req.Open("POST", DAEMON_URL . "/shutdown", false)
        req.Send()
        return true
    } catch {
        return false
    }
}

RestartDaemon() {
    RequestShutdown()
    Sleep 500
    cmd := DaemonStartCommand()
    if cmd != "" {
        Run cmd,, "Hide"
        TrayTip "Speech2Text", "Daemon wird neu gestartet…", "Iconi"
        ; Nach Daemon-Start kurz warten und Hotkeys neu binden
        SetTimer () => BindHotkeysFromDaemon(), -1500
    } else {
        TrayTip "Speech2Text",
            "Daemon-Exe nicht gefunden — bitte Installation prüfen.",
            "Iconx"
    }
}

ExitAll() {
    UnbindAllHotkeys()
    RequestShutdown()
    ExitApp
}
