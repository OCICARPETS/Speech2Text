"""Speech2Text Tray-App (Python-Ersatz für shortcut.ahk, v1.3).

Architektur:
  - pystray-Icon + Menü (Tray-UI)
  - HotkeyManager-Thread für globale Tastenerfassung (Win32 LL-Hook)
  - Poll-Thread für /health (300 ms): Tooltip, Fehler-Toast, Re-Bind
  - daemon_client für HTTP-Calls

Beim Start:
  1. Icon laden
  2. Daemon-Auto-Start (falls nicht erreichbar)
  3. Bei fehlendem API-Key: Settings-GUI öffnen (Wizard) + Hinweis-Tooltip
  4. Hotkeys vom Daemon laden + binden
  5. Polling-Loop + pystray-Eventloop

Beim Beenden (Tray-Menü „❌ Beenden"):
  1. /shutdown an Daemon
  2. HotkeyManager.stop()
  3. pystray-Icon.stop()
"""
from __future__ import annotations

import _arch_fix  # noqa: F401  # ARM64-Windows: vor pystray/PIL laden

import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from PIL import Image
import pystray

import config as cfg_mod
import daemon_client as dc
from keyboard_hook import HotkeyManager

# --- Konstanten -------------------------------------------------------------

POLL_INTERVAL_S = 0.30        # AHK-Vorgänger: 300 ms — identisch übernommen
DAEMON_BOOT_TIMEOUT_S = 8.0   # so lange warten wir auf /health beim Auto-Start
DAEMON_RETRY_INTERVAL_S = 6.0 # Im Polling: alle 6 s neu versuchen, falls Daemon weg

TIP_OFFLINE    = "Speech2Text · Daemon offline"
TIP_IDLE       = "Speech2Text · bereit"
TIP_RECORDING  = "Speech2Text · 🎤 Aufnahme läuft"
TIP_PROCESSING = "Speech2Text · ⏳ verarbeite …"
TIP_NEEDS_KEY  = "Speech2Text · API-Key fehlt — Einstellungen öffnen"

LOG_MAX_BYTES = 1_000_000


# --- Pfad-Auflösung (Bundle vs. Dev) ---------------------------------------

def _script_dir() -> Path:
    """Verzeichnis der laufenden Exe (Bundle) oder dieser .py (Dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _icon_path() -> Path | None:
    here = _script_dir()
    candidates = [
        here / "assets" / "speech2text.ico",
        here.parent / "assets" / "speech2text.ico",
    ]
    # Im PyInstaller-onefile-Bundle landet --add-data unter _MEIPASS/<dest>.
    mei = getattr(sys, "_MEIPASS", None)
    if mei:
        candidates.insert(0, Path(mei) / "assets" / "speech2text.ico")
    for p in candidates:
        if p.exists():
            return p
    return None


def _daemon_exe_path() -> Path | None:
    here = _script_dir()
    candidates = [
        here / "Speech2Text-Daemon.exe",
        here.parent / "build" / "dist" / "Speech2Text-Daemon.exe",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _settings_exe_path() -> Path | None:
    here = _script_dir()
    candidates = [
        here / "Speech2Text-Settings.exe",
        here.parent / "build" / "dist" / "Speech2Text-Settings.exe",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _settings_py_path() -> Path | None:
    """Dev-Fallback: pythonw + settings.py."""
    here = _script_dir()
    candidates = [
        here / "settings.py",
        here.parent / "src" / "settings.py",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _venv_pythonw_path() -> Path | None:
    here = _script_dir()
    candidates = [
        here.parent / ".venv" / "Scripts" / "pythonw.exe",
        here.parent.parent / ".venv" / "Scripts" / "pythonw.exe",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _log_path() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) / "Speech2Text" if appdata else Path.home() / ".speech2text"
    return base / "tray.log"


def _setup_hidden_logging() -> Path:
    """stdout/stderr auf %APPDATA%/Speech2Text/tray.log umleiten.
    Identisches Pattern wie recorder._setup_hidden_logging — gleiche Rotation."""
    path = _log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > LOG_MAX_BYTES:
        backup = path.parent / "tray.1.log"
        if backup.exists():
            backup.unlink()
        path.rename(backup)
    f = open(path, "a", encoding="utf-8", errors="replace", buffering=1)
    sys.stdout = f
    sys.stderr = f
    return path


# --- TrayApp ---------------------------------------------------------------

class TrayApp:
    def __init__(self) -> None:
        self._icon: pystray.Icon | None = None
        self._hk = HotkeyManager()
        self._stop_event = threading.Event()
        self._poll_thread: threading.Thread | None = None

        # State aus letzem /health (für Diff-Detektion)
        self._last_error_ts_seen: float | None = None
        self._last_revision: int = -1
        self._last_paused: bool = False
        self._daemon_last_retry: float = 0.0
        self._wizard_opened: bool = False
        self._first_run_complete: bool = False

        # Cached Hotkey-Anzeige (für First-Run-Hint im Tooltip)
        self._main_hotkey_display: str = "Caps Lock"

    # -- Public --------------------------------------------------------------

    def run(self) -> int:
        icon_path = _icon_path()
        if icon_path is None:
            print("❌  Tray-Icon nicht gefunden", file=sys.stderr)
            return 1
        try:
            img = Image.open(icon_path)
        except Exception as e:  # noqa: BLE001
            print(f"❌  Icon-Load-Fehler: {type(e).__name__}: {e}", file=sys.stderr)
            return 1

        menu = pystray.Menu(
            pystray.MenuItem("📋 Log öffnen", self._action_open_log),
            pystray.MenuItem("🔄 Daemon neu starten", self._action_restart_daemon),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙️  Einstellungen…", self._action_open_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("❌ Beenden", self._action_exit),
        )
        self._icon = pystray.Icon(
            "speech2text", img, TIP_OFFLINE, menu,
        )

        self._hk.start()

        # Bootstrap + Poll in eigenem Thread, damit pystray.run() blockieren darf
        bootstrap_thread = threading.Thread(
            target=self._bootstrap_and_poll, daemon=True, name="TrayBootstrap"
        )
        bootstrap_thread.start()

        try:
            self._icon.run()
        finally:
            self._stop_event.set()
            self._hk.stop()
        return 0

    # -- Bootstrap -----------------------------------------------------------

    def _bootstrap_and_poll(self) -> None:
        try:
            self._bootstrap()
        except Exception as e:  # noqa: BLE001
            print(f"[Tray] Bootstrap-Fehler: {type(e).__name__}: {e}",
                  file=sys.stderr)
        self._poll_loop()

    def _bootstrap(self) -> None:
        cfg = cfg_mod.load_config()
        # 1) API-Key-Check (Wizard) — vor Daemon-Start, weil Daemon ohne Key
        #    direkt aussteigt (recorder.py main() return 2).
        api_key = cfg_mod.get_api_key(cfg)
        if not api_key:
            print("[Tray] API-Key fehlt — Settings öffnen", flush=True)
            self._wizard_opened = True
            self._set_tooltip(TIP_NEEDS_KEY)
            self._open_settings_async()
            # Wir starten den Daemon NICHT in dieser Phase — Settings.save
            # schreibt Key + ruft /reload-config (das schlägt fehl, weil
            # Daemon weg ist). Im Poll-Loop merkt der Tray: Daemon off → starten.
            return

        # 2) Daemon erreichbar? Wenn nein: Auto-Start.
        if dc.health() is None:
            self._start_daemon_blocking()

        # 3) Hotkeys laden + binden
        self._rebind_hotkeys()

        # 4) First-Run-Flag aus Config
        self._first_run_complete = bool(cfg.get("first_run_completed", False))

    def _start_daemon_blocking(self) -> None:
        exe = _daemon_exe_path()
        if exe is None:
            print("[Tray] Daemon-Exe nicht gefunden — kann nicht starten",
                  file=sys.stderr)
            return
        print(f"[Tray] Daemon-Auto-Start: {exe}", flush=True)
        try:
            # CREATE_NO_WINDOW (0x08000000) damit kein Console-Fenster aufpoppt,
            # falls die Exe doch eine Console hat (sollte sie als
            # PyInstaller-noconsole nicht, aber defensive).
            subprocess.Popen(
                [str(exe)], cwd=str(exe.parent), close_fds=True,
                creationflags=0x08000000,
            )
        except OSError as e:
            print(f"[Tray] Daemon-Start-OSError: {e}", file=sys.stderr)
            return
        # Auf /health warten
        ok = dc.wait_alive(timeout_s=DAEMON_BOOT_TIMEOUT_S, poll_interval_s=0.25)
        if not ok:
            print("[Tray] Daemon-Start: Timeout (kein /health-Response)",
                  file=sys.stderr)

    # -- Hotkeys -------------------------------------------------------------

    def _rebind_hotkeys(self) -> None:
        hk = dc.hotkeys()
        if hk is None:
            print("[Tray] /hotkeys nicht erreichbar — Hotkeys bleiben unverändert",
                  flush=True)
            return
        self._hk.unbind_all()
        # Haupt-Hotkey
        main_spec = hk["main"]
        if main_spec:
            self._hk.bind(main_spec,
                          on_press=self._make_press_handler(None),
                          on_release=self._make_release_handler())
            self._main_hotkey_display = _spec_to_display(main_spec)
        # Cycle-Hotkey (Tap)
        cycle_spec = hk["cycle"]
        if cycle_spec:
            self._hk.bind(cycle_spec, on_press=self._cycle_action, on_release=None)
        # Modus-Hotkeys (Push-to-Talk im fixen Modus)
        for m in hk["modes"]:
            spec = m["hotkey"]
            mid = m["mode_id"]
            if not spec or not mid:
                continue
            self._hk.bind(spec,
                          on_press=self._make_press_handler(mid),
                          on_release=self._make_release_handler())
        self._last_revision = hk["revision"]
        print(f"[Tray] Hotkeys gebunden (revision={hk['revision']}, "
              f"main={main_spec!r}, cycle={cycle_spec!r}, "
              f"modi={len(hk['modes'])})", flush=True)

    def _make_press_handler(self, mode_id: str | None):
        def handler() -> None:
            dc.start_mode(mode_id)
        return handler

    def _make_release_handler(self):
        def handler() -> None:
            dc.stop()
        return handler

    def _cycle_action(self) -> None:
        r = dc.cycle()
        if r is None:
            self._notify("Speech2Text",
                         "Cycle-Liste ist leer — bitte in den Einstellungen "
                         "Modi aktivieren.")
            return
        _, ui = r
        self._notify("Speech2Text", f"Modus: {ui}")

    # -- Poll-Loop -----------------------------------------------------------

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._poll_tick()
            except Exception as e:  # noqa: BLE001
                print(f"[Tray] Poll-Fehler: {type(e).__name__}: {e}",
                      file=sys.stderr)
            self._stop_event.wait(POLL_INTERVAL_S)

    def _poll_tick(self) -> None:
        h = dc.health()
        if h is None:
            self._set_tooltip(TIP_OFFLINE)
            # Daemon nicht erreichbar: alle DAEMON_RETRY_INTERVAL_S erneut starten
            now = time.monotonic()
            if (not self._wizard_opened
                    and now - self._daemon_last_retry > DAEMON_RETRY_INTERVAL_S):
                self._daemon_last_retry = now
                exe = _daemon_exe_path()
                if exe is not None:
                    print("[Tray] Daemon weg — versuche Restart", flush=True)
                    self._start_daemon_blocking()
                    self._rebind_hotkeys()
            return

        # Wizard-Phase abschließen: API-Key wurde gerade gespeichert?
        # → /health antwortet ja, also Settings hat ggf. Daemon noch nicht
        # gestartet. Wir starten ihn hier garantiert nicht erneut, weil er
        # bereits läuft (sonst hätte /health nicht geantwortet).
        if self._wizard_opened:
            self._wizard_opened = False
            self._rebind_hotkeys()

        state = h.get("state", "idle")
        active_ui = h.get("active_mode_ui_name", "")
        last_dictation_ts = float(h.get("last_dictation_ts", "0") or "0")

        # Tooltip-State
        base = (TIP_RECORDING if state == "recording"
                else TIP_PROCESSING if state == "processing"
                else TIP_IDLE)
        if active_ui:
            base = f"{base} (Modus: {active_ui})"
        # First-Run-Hint: noch nie diktiert + nicht bestätigt
        if not self._first_run_complete and last_dictation_ts <= 0.0:
            base = (f"Speech2Text · {self._main_hotkey_display} halten, "
                    "um zu diktieren")
        elif (not self._first_run_complete and last_dictation_ts > 0.0):
            # Erstes Diktat fertig — Flag persistieren, damit's beim Restart hält
            self._first_run_complete = True
            self._persist_first_run_done()
        self._set_tooltip(base)

        # Fehler-Toast (TS-Diff erkennen)
        try:
            err_ts = float(h.get("last_error_ts", "0") or "0")
        except ValueError:
            err_ts = 0.0
        err_msg = h.get("last_error", "")
        if self._last_error_ts_seen is None:
            # Erster Poll: aktuellen Stand merken, nicht für „alte" Fehler toasten
            self._last_error_ts_seen = err_ts
        elif err_ts > self._last_error_ts_seen and err_msg:
            self._notify("Speech2Text", err_msg)
            self._last_error_ts_seen = err_ts

        # Pause/Resume
        paused = h.get("hotkeys_paused", "off") == "on"
        if paused and not self._last_paused:
            self._hk.pause()
            self._last_paused = True
        elif not paused and self._last_paused:
            self._hk.resume()
            self._last_paused = False
            self._rebind_hotkeys()  # Capture könnte Bindings geändert haben

        # Revision-Diff → Re-Bind
        try:
            rev = int(h.get("hotkeys_revision", "0") or "0")
        except ValueError:
            rev = 0
        if not self._last_paused and rev != self._last_revision:
            self._rebind_hotkeys()

    # -- Menü-Aktionen -------------------------------------------------------

    def _action_open_log(self, _icon=None, _item=None) -> None:
        # Daemon-Log liegt in tray.log's Schwester-Datei
        log_dir = _log_path().parent
        daemon_log = log_dir / "daemon.log"
        # Wenn kein daemon.log da, fallback tray.log
        target = daemon_log if daemon_log.exists() else _log_path()
        if not target.exists():
            self._notify("Speech2Text",
                         f"Log-Datei existiert noch nicht:\n{target}")
            return
        try:
            os.startfile(str(target))  # nosec — User-initiierte Aktion
        except OSError as e:
            self._notify("Speech2Text", f"Log konnte nicht geöffnet werden: {e}")

    def _action_restart_daemon(self, _icon=None, _item=None) -> None:
        dc.shutdown()  # antwortet schnell, killt sich dann selbst
        time.sleep(0.6)
        self._start_daemon_blocking()
        self._notify("Speech2Text", "Daemon wird neu gestartet…")

    def _action_open_settings(self, _icon=None, _item=None) -> None:
        self._open_settings_async()

    def _action_exit(self, _icon=None, _item=None) -> None:
        dc.shutdown()
        self._stop_event.set()
        self._hk.stop()
        if self._icon is not None:
            self._icon.stop()

    # -- Helpers -------------------------------------------------------------

    def _set_tooltip(self, text: str) -> None:
        if self._icon is not None:
            self._icon.title = text

    def _notify(self, title: str, message: str) -> None:
        if self._icon is None:
            return
        try:
            self._icon.notify(message, title)
        except Exception as e:  # noqa: BLE001
            print(f"[Tray] notify-Fehler: {type(e).__name__}: {e}",
                  file=sys.stderr)

    def _open_settings_async(self) -> None:
        # Settings-Exe bevorzugt, sonst venv-pythonw + settings.py
        exe = _settings_exe_path()
        if exe is not None:
            try:
                subprocess.Popen([str(exe)], cwd=str(exe.parent),
                                 creationflags=0x08000000)
                return
            except OSError as e:
                print(f"[Tray] Settings-Exe-Fehler: {e}", file=sys.stderr)

        pyw = _venv_pythonw_path()
        settings_py = _settings_py_path()
        if pyw is not None and settings_py is not None:
            try:
                subprocess.Popen([str(pyw), str(settings_py)],
                                 cwd=str(settings_py.parent),
                                 creationflags=0x08000000)
                return
            except OSError as e:
                print(f"[Tray] Settings-Dev-Fehler: {e}", file=sys.stderr)

        self._notify("Speech2Text", "Einstellungen können nicht geöffnet werden")

    def _persist_first_run_done(self) -> None:
        try:
            cfg = cfg_mod.load_config()
            cfg["first_run_completed"] = True
            cfg_mod.save_config(cfg)
        except Exception as e:  # noqa: BLE001
            print(f"[Tray] first_run-Persist-Fehler: {type(e).__name__}: {e}",
                  file=sys.stderr)


# --- Spec-Anzeige (Helper) --------------------------------------------------

_MOD_DISPLAY = {"^": "Ctrl", "!": "Alt", "+": "Shift", "#": "Win"}
_KEY_DISPLAY = {"CapsLock": "Caps Lock", "ScrollLock": "Scroll Lock"}


def _spec_to_display(spec: str) -> str:
    """`^!r` → `Ctrl + Alt + R`, `CapsLock` → `Caps Lock`. Für Tooltip-Hinweis."""
    if not spec:
        return ""
    mods: list[str] = []
    i = 0
    while i < len(spec) and spec[i] in _MOD_DISPLAY:
        mods.append(_MOD_DISPLAY[spec[i]])
        i += 1
    key = spec[i:]
    key_disp = _KEY_DISPLAY.get(key, key.upper() if len(key) == 1 else key)
    parts = mods + [key_disp]
    return " + ".join(parts)


# --- Entry-Point ------------------------------------------------------------

def main() -> int:
    # UTF-8 Konsole wie recorder.py
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass

    hidden = "--hidden" in sys.argv or getattr(sys, "frozen", False)
    if hidden:
        log_file = _setup_hidden_logging()
        print(f"=== Speech2Text Tray gestartet (hidden) "
              f"— {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
        print(f"    Log: {log_file}")

    app = TrayApp()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())
