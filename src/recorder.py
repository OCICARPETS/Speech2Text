"""Speech2Text Daemon — Push-to-Talk Transkription + KI-Optimierung.

Architektur:
  AHK (Caps Lock) → HTTP POST /start|/stop → dieser Daemon
  → sounddevice nimmt Audio auf (im Speicher)
  → OpenAI gpt-4o-transcribe → Rohtranskript
  → OpenAI gpt-4o-mini → optimierter Text
  → Zwischenablage + Auto-Paste ins aktive Fenster

Start:
  python src/recorder.py
  (oder scripts/start-daemon.bat)
"""
from __future__ import annotations

import _arch_fix  # noqa: F401  # ARM64-Windows: patcht platform.machine() vor sounddevice-Import

import ctypes
import io
import json
import os
import sys
import threading
import time
import wave
from collections import deque
from ctypes import wintypes
from enum import Enum
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pyperclip
import sounddevice as sd
from dotenv import load_dotenv
from openai import OpenAI

import config as cfg_mod
import handshake

# --- Konfiguration ----------------------------------------------------------

HOST = "127.0.0.1"
# Der Daemon bindet Port 0 (OS wählt einen freien, session-exklusiven Port) und
# hinterlegt ihn via handshake.write_port; der Tray liest ihn dort. Kein fester
# Port mehr (Multi-Session, Ansatz B). Fallback-Port: handshake.DEFAULT_PORT.

SAMPLE_RATE = 16000   # Hz — ausreichend für Sprache, minimiert Upload
CHANNELS = 1          # Mono
DTYPE = "int16"

MODEL_TRANSCRIBE = "gpt-4o-transcribe"
MODEL_OPTIMIZE = "gpt-4o-mini"

PASTE_DELAY_S = 0.05  # Windows-Clipboard braucht eine Minimal-Pause vor Ctrl+V
SEND_INPUT_INTERVAL_S = 0.001  # Sleep zwischen Zeichen bei send_input-Modus

# 3a — Kurz-Tipp-Schutz: Aufnahmen unter dieser Dauer werden still verworfen
# (kein OpenAI-Call, kein Toast). Misst NUR das aktive Diktat (ohne Pre-Roll).
MIN_RECORD_S = 0.3

# 3b — Pre-Recording-Ringpuffer: Daemon hält Stream dauerhaft offen, puffert
# rolling RINGBUFFER_S, hängt bei /start preroll_ms (aus Config) vor das Diktat.
RINGBUFFER_S = 0.5
PREROLL_MS_MAX = int(RINGBUFFER_S * 1000)  # Hard-Limit = Ringpuffer-Größe

# Post-Roll: bis zu POSTROLL_MS_MAX nach Tasten-Loslassen weiter aufnehmen.
# Erhöht die Latenz bis zum fertigen Text um postroll_ms.
POSTROLL_MS_MAX = 500

# Watchdog gegen klemmenden Hotkey / vergessenen Stop: nach dieser Dauer
# wird die Aufnahme automatisch beendet (verhindert stundenlange Audio-
# Puffer im RAM und versehentliche OpenAI-Mehrkosten).
MAX_RECORD_S = 600

# --- Stream-Health-Watchdog (RDP-Reconnect-Fix) ----------------------------
# Der persistente Prebuffer-Stream kann sterben, wenn das Audio-Gerät
# verschwindet — auf Terminal-Servern passiert das bei RDP-Disconnect, weil das
# Mikrofon session-redirected ist. PortAudio meldet dann '[audio status] input
# overflow' und ruft `_on_audio` nicht mehr auf. Ohne Gegenmaßnahme nimmt der
# Daemon weiter "auf", bekommt aber nur leere Chunks → "Keine Audiodaten".
# Der Watchdog erkennt den Stillstand (kein Callback seit STREAM_STALE_S) und
# öffnet den Stream automatisch neu (mit Retry, bis wieder Frames kommen).
STREAM_STALE_S = 2.0              # kein _on_audio-Callback so lange ⇒ Stream tot
STREAM_WATCHDOG_INTERVAL_S = 1.0  # Prüf-Intervall des Watchdog-Threads


def _stream_is_stale(now: float, last_audio_ts: float, stale_s: float) -> bool:
    """True, wenn seit dem letzten Audio-Callback länger als stale_s vergangen
    ist (Stream liefert keine Frames mehr). Pure Funktion → ohne Gerät testbar."""
    return (now - last_audio_ts) > stale_s


def _should_reopen_stream(now: float, last_audio_ts: float, stale_s: float,
                          want_prebuffer: bool, stream_always_on: bool,
                          state_is_idle: bool) -> bool:
    """Watchdog-Entscheidung: persistenten Stream (neu) öffnen? Pure Funktion
    → ohne PortAudio testbar.

    Reopen nur bei IDLE (nie mitten in Recording/Processing) und nur wenn
    Prebuffer gewünscht ist. Dann: entweder ist kein Stream offen (z.B.
    Open-Fail beim Start) ODER der offene Stream ist stale (tot).
    """
    if not state_is_idle:
        return False
    if not want_prebuffer:
        return False
    if not stream_always_on:
        return True
    return _stream_is_stale(now, last_audio_ts, stale_s)


LOG_MAX_BYTES = 1_000_000  # bei >1 MB wird daemon.log zu daemon.1.log rotiert


# --- Win32 SendInput (Unicode) ----------------------------------------------
# Nutzen: im Paste-Modus `send_input` tippen wir Zeichen für Zeichen via
# SendInput mit KEYEVENTF_UNICODE. Damit kommen Umlaute (ä/ö/ü/ß) korrekt
# durch und der Text landet auch in TUIs (cmd, PowerShell, Claude Code CLI),
# wo Clipboard+Ctrl+V unzuverlässig ist. Reine stdlib (ctypes), keine Deps.

_INPUT_KEYBOARD = 1
_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]


_user32 = ctypes.WinDLL("user32", use_last_error=True)
_user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int)
_user32.SendInput.restype = wintypes.UINT


def _send_unicode_codepoint(scan: int) -> None:
    down = _INPUT(type=_INPUT_KEYBOARD)
    down.u.ki = _KEYBDINPUT(wVk=0, wScan=scan, dwFlags=_KEYEVENTF_UNICODE,
                            time=0, dwExtraInfo=None)
    up = _INPUT(type=_INPUT_KEYBOARD)
    up.u.ki = _KEYBDINPUT(wVk=0, wScan=scan,
                          dwFlags=_KEYEVENTF_UNICODE | _KEYEVENTF_KEYUP,
                          time=0, dwExtraInfo=None)
    arr = (_INPUT * 2)(down, up)
    _user32.SendInput(2, arr, ctypes.sizeof(_INPUT))


def _type_text_unicode(text: str, interval: float = SEND_INPUT_INTERVAL_S) -> None:
    """Tippt `text` Zeichen für Zeichen via SendInput (Unicode). Codepoints
    > 0xFFFF werden als UTF-16-Surrogatpaar gesendet (Emojis etc.)."""
    for ch in text:
        cp = ord(ch)
        if cp > 0xFFFF:
            cp -= 0x10000
            _send_unicode_codepoint(0xD800 + (cp >> 10))
            _send_unicode_codepoint(0xDC00 + (cp & 0x3FF))
        else:
            _send_unicode_codepoint(cp)
        if interval > 0:
            time.sleep(interval)


# --- State ------------------------------------------------------------------

class State(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"


# --- Recorder ---------------------------------------------------------------

class Recorder:
    """Hält Audio-Zustand + OpenAI-Client. Thread-safe per Lock.

    Config-Zugriff nur über self.config (dict, siehe config.py). Modus und
    API-Key lassen sich per reload_config() live tauschen, ohne Daemon-Restart.
    """

    def __init__(self, config: dict, api_key: str) -> None:
        self.state: State = State.IDLE
        self.last_error: str = ""
        self.last_error_ts: float = 0.0
        # Onboarding-Hint (v1.3): wird auf time.time() gesetzt nach dem
        # ersten erfolgreichen Diktat (Paste-Status erfolgreich). 0.0 = nie
        # diktiert → Tray-App zeigt First-Run-Hint im Tooltip.
        self.last_dictation_ts: float = 0.0
        self._lock = threading.Lock()
        self._stream: sd.InputStream | None = None
        self._chunks: list[np.ndarray] = []
        # Inkrementeller Counter für die aktive Aufnahme — Watchdog gegen
        # klemmenden Hotkey, vermeidet O(n)-sum() im Audio-Callback (16/s).
        self._chunks_total_samples = 0
        # Ringpuffer als deque für thread-safe append/popleft (CPython/GIL).
        # Wird im Audio-Thread (`_on_audio`) befüllt, im Worker (`_process`)
        # per Snapshot gelesen.
        self._ringbuffer: deque[np.ndarray] = deque()
        self._ringbuffer_max_samples = int(RINGBUFFER_S * SAMPLE_RATE)
        self._stream_always_on = False
        # Audio-Device des aktiven Persistent-Streams (None wenn keiner offen).
        # Quelle für Lifecycle-Vergleiche in reload_config — wir vergleichen
        # gegen den TATSÄCHLICHEN Stream-Status, nicht gegen alte config-Werte.
        self._current_device: int | None = None
        # Stream-Health-Watchdog (RDP-Reconnect-Fix):
        #   _last_audio_ts:     Zeit des letzten _on_audio-Callbacks (Lebens-
        #                       zeichen). Wird in _open_persistent_stream auf
        #                       now gesetzt → Grace-Period für den 1. Callback.
        #   _stream_recovering: True während laufender Reopen-Versuche
        #                       (Throttle für Log/Toast, kein Spam pro Tick).
        self._last_audio_ts: float = 0.0
        self._stream_recovering: bool = False
        self._watchdog_thread: threading.Thread | None = None
        # Aktiver Post-Roll-Timer (None wenn keiner läuft). Cancel-Handle
        # für Doppeltap-Reentrancy in start().
        self._postroll_timer: threading.Timer | None = None
        self.config: dict = config
        # Schritt 6: Cycle-Hotkey-Layer.
        #   _active_mode:   aktuell aktiver Modus (Cycle-änderbar, session-only).
        #                   Initial = config["mode"], setzt beim Daemon-Restart
        #                   zurück auf den Config-Default (B-Entscheidung).
        #   _session_mode:  Override für die laufende Aufnahme (gesetzt von
        #                   einem Modus-spezifischen Hotkey via /start mode-Body).
        #                   Wird in _process() bevorzugt, danach in finally
        #                   zurückgesetzt. Ändert _active_mode NICHT.
        #   _hotkeys_revision: monoton steigender Counter, bei jedem
        #                   reload_config() inkrementiert. AHK pollt /health,
        #                   ändert sich der Wert → re-bind via /hotkeys.
        self._active_mode: str = config.get("mode", cfg_mod.DEFAULT_MODE)
        self._session_mode: str | None = None
        self._hotkeys_revision: int = 0
        # Pause-Flag: während die Settings-GUI einen Hotkey-Capture-Dialog
        # offen hat, soll AHK alle Hotkeys vorübergehend abschalten — sonst
        # frisst der globale Hook bereits belegte Tasten, bevor tkinter sie
        # sieht. Settings ruft /pause-hotkeys vor Capture-Open + /resume-
        # hotkeys danach. AHK pollt das Flag in /health.
        self._hotkeys_paused: bool = False
        self._client = OpenAI(api_key=api_key)
        # Falls Prebuffer im Config aktiv: Stream sofort nach Init öffnen.
        # Fehler nicht-fatal — Recorder bleibt nutzbar im On-Demand-Modus.
        if bool(self.config.get("prebuffer_enabled", True)):
            self._open_persistent_stream()
        # Watchdog IMMER starten — greift, sobald Prebuffer aktiv ist und der
        # Stream stirbt (oder beim Start gar nicht öffnen konnte, weil das
        # Gerät noch nicht da war). Self-Healing gegen RDP-Reconnect.
        self._watchdog_thread = threading.Thread(
            target=self._stream_watchdog_loop, daemon=True, name="StreamWatchdog",
        )
        self._watchdog_thread.start()

    # --- Stream-Lifecycle (Persistent-Modus) ------------------------------
    # Im Prebuffer-Modus läuft der Mikrofon-Stream dauerhaft. Open/Close
    # werden nur zwischen Diktaten (State=IDLE) angefasst, nie während
    # RECORDING/PROCESSING. Für On-Demand-Betrieb (Prebuffer aus) gilt der
    # alte Pfad in start()/stop().

    def _open_persistent_stream(self, verbose: bool = True) -> None:
        device = self.config.get("audio_device")
        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                dtype=DTYPE,
                callback=self._on_audio,
                device=device,
            )
            self._stream.start()
            self._stream_always_on = True
            self._current_device = device
            self._ringbuffer.clear()
            # Grace-Period: frischen Stream nicht sofort als stale werten —
            # der Watchdog gibt ihm bis STREAM_STALE_S Zeit für den 1. Callback.
            self._last_audio_ts = time.time()
            if verbose:
                print(f"🎙  Prebuffer-Stream geöffnet (device={device}, "
                      f"ringbuffer={RINGBUFFER_S*1000:.0f} ms)")
        except Exception as e:  # noqa: BLE001
            self._stream = None
            self._stream_always_on = False
            self._current_device = None
            err = f"Persistent-Stream konnte nicht geöffnet werden: {type(e).__name__}: {e}"
            if verbose:
                # Im Watchdog-Retry NICHT pro Versuch toasten/spammen — dort
                # wird verbose=False übergeben (Throttle via _stream_recovering).
                print(f"❌  {err}", file=sys.stderr)
                self._set_error(err)

    def _close_persistent_stream(self, verbose: bool = True) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:  # noqa: BLE001
                if verbose:
                    print(f"⚠  Stream-Close-Fehler: {e}", file=sys.stderr)
            self._stream = None
        self._stream_always_on = False
        self._current_device = None
        self._ringbuffer.clear()
        if verbose:
            print("🎙  Prebuffer-Stream geschlossen")

    def _reinit_portaudio(self, verbose: bool = True) -> None:
        """PortAudio terminieren + neu initialisieren, damit die GERÄTELISTE
        neu eingelesen wird.

        Hintergrund: PortAudio cached die Geräteliste beim `Pa_Initialize`.
        Startet der Daemon ohne Aufnahmegerät (z. B. Autostart nach Reboot,
        BEVOR das per RDP durchgereichte „Remoteaudio"-Gerät registriert ist),
        bleibt der Default-Input intern dauerhaft -1 → `sd.InputStream(
        device=None)` wirft „Error querying device -1", egal wie oft man nur
        den *Stream* neu öffnet. Erst `sd._terminate()` + `sd._initialize()`
        liest die Geräteliste neu ein.

        NUR aufrufen, wenn KEIN Stream offen ist (sonst reißt terminate den
        laufenden Stream weg) — Watchdog/start() rufen es im IDLE-Zustand
        zwischen close und open auf.
        """
        try:
            sd._terminate()
            sd._initialize()
            if verbose:
                print("🔄  PortAudio neu initialisiert (Geräteliste aktualisiert)")
        except Exception as e:  # noqa: BLE001
            # Reinit-Fehler darf die Recovery nicht abbrechen — der folgende
            # Open-Versuch zeigt ohnehin, ob wieder ein Gerät da ist.
            if verbose:
                print(f"⚠  PortAudio-Reinit-Fehler: {type(e).__name__}: {e}",
                      file=sys.stderr)

    def _open_ondemand_stream(self, device) -> bool:
        """On-Demand-Stream (Prebuffer aus) für eine einzelne Aufnahme öffnen.

        Fix(2): scheitert das Öffnen (z. B. Default-Input -1, weil das Gerät
        beim PortAudio-Init noch nicht da war), EINMAL PortAudio neu
        initialisieren (Geräteliste auffrischen) und genau einmal erneut
        versuchen. Rückgabe: True wenn der Stream läuft, sonst False
        (`last_error` ist dann gesetzt, State bleibt beim Aufrufer IDLE).
        """
        for attempt in (1, 2):
            try:
                self._stream = sd.InputStream(
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype=DTYPE,
                    callback=self._on_audio,
                    device=device,
                )
                self._stream.start()
                return True
            except Exception as e:  # noqa: BLE001
                self._stream = None
                if attempt == 1:
                    print(f"⚠  Mikro-Open fehlgeschlagen ({type(e).__name__}) — "
                          f"PortAudio-Reinit + Retry…", file=sys.stderr)
                    self._reinit_portaudio(verbose=False)
                    continue
                err = (f"Mikrofon konnte nicht geöffnet werden: "
                       f"{type(e).__name__}: {e}")
                print(f"❌  {err}", file=sys.stderr)
                self._set_error(err)
                return False
        return False

    # --- Stream-Watchdog (Self-Healing gegen RDP-Reconnect) ---------------

    def _stream_watchdog_loop(self) -> None:
        """Hintergrund-Thread: prüft periodisch, ob der persistente Stream noch
        Frames liefert, und öffnet ihn bei Stillstand neu."""
        while True:
            time.sleep(STREAM_WATCHDOG_INTERVAL_S)
            try:
                self._maybe_recover_stream()
            except Exception as e:  # noqa: BLE001
                print(f"⚠  Stream-Watchdog-Fehler: {type(e).__name__}: {e}",
                      file=sys.stderr)

    def _maybe_recover_stream(self) -> None:
        now = time.time()
        with self._lock:
            want = bool(self.config.get("prebuffer_enabled", True))
            idle = self.state is State.IDLE
            # Recovering-Flag zurücksetzen, sobald wieder ein gesunder Stream da
            # ist (offen + nicht stale) → ein späterer Ausfall toastet erneut.
            if (self._stream_recovering and self._stream_always_on
                    and not _stream_is_stale(now, self._last_audio_ts,
                                             STREAM_STALE_S)):
                self._stream_recovering = False
            if not _should_reopen_stream(now, self._last_audio_ts, STREAM_STALE_S,
                                         want, self._stream_always_on, idle):
                return
            first = not self._stream_recovering
            self._stream_recovering = True
            if first:
                age = (now - self._last_audio_ts) if self._stream_always_on else -1.0
                print(f"🔁  Audio-Stream reagiert nicht (age={age:.1f}s) — "
                      f"verbinde neu…", file=sys.stderr)
                # Einmal-Toast für den User: nicht ins Leere sprechen.
                self._set_error(
                    "Mikrofon verloren — verbinde neu, gleich wieder bereit…")
            self._close_persistent_stream(verbose=False)
            # Geräteliste neu einlesen (Fix): close+open allein heilt NICHT,
            # wenn PortAudio device-los initialisiert wurde (Default-Input -1).
            self._reinit_portaudio(verbose=False)
            self._open_persistent_stream(verbose=False)

    def reload_config(self) -> str:
        """Liest Config neu, tauscht OpenAI-Client wenn API-Key sich ändert,
        passt Stream-Lifecycle an (prebuffer_enabled / audio_device).

        Lifecycle-Wechsel nur bei State=IDLE. Wird ein Reload mid-Diktat
        ausgelöst (selten — GUI schließt nach Save), bleibt der Wunsch in
        der `self.config` gespeichert. Wir vergleichen beim NÄCHSTEN Reload
        nicht gegen die alte Config (die wäre dann schon der gewünschte
        Wert), sondern gegen den TATSÄCHLICHEN Stream-Status — `self.
        _stream_always_on` und `self._current_device`. Damit wird der
        Wechsel beim nächsten reload-config oder Daemon-Restart sicher
        nachgezogen. (Behobener Bug: vorher gegen alte config-Werte
        verglichen → zweiter Reload sah „kein Wechsel" und verschluckte
        den Lifecycle dauerhaft.)

        Rückgabe: kurze Status-Info für den HTTP-Response."""
        new_cfg = cfg_mod.load_config()
        new_key = cfg_mod.get_api_key(new_cfg) or os.getenv("OPENAI_API_KEY", "")
        old_key = self._client.api_key if hasattr(self._client, "api_key") else None
        key_refreshed = False
        deferred = False
        with self._lock:
            self.config = new_cfg
            if new_key and new_key != old_key:
                self._client = OpenAI(api_key=new_key)
                key_refreshed = True
            want_stream = bool(new_cfg.get("prebuffer_enabled", True))
            want_device = new_cfg.get("audio_device")
            if self.state is State.IDLE:
                # Vergleiche gegen TATSÄCHLICHEN Stream-Status, nicht gegen
                # alte config-Werte — sonst werden mid-Diktat-Wechsel beim
                # zweiten Reload nicht nachgezogen.
                if self._stream_always_on and not want_stream:
                    self._close_persistent_stream()
                elif not self._stream_always_on and want_stream:
                    self._open_persistent_stream()
                elif (self._stream_always_on and want_stream
                      and self._current_device != want_device):
                    self._close_persistent_stream()
                    self._open_persistent_stream()
            else:
                # Wechsel-Bedarf erkennen, aber erst beim nächsten IDLE
                # ziehen. Status-Return weist darauf hin, damit GUI das
                # anzeigen kann.
                if (self._stream_always_on != want_stream
                        or (want_stream and self._current_device != want_device)):
                    deferred = True
        # Hotkey-Layer (Schritt 6): jedes reload_config bumpt die Revision.
        # AHK pollt /health, vergleicht, bei Änderung neu binden via /hotkeys.
        # Kein Diff nötig — re-binden ist günstig, simpel und idempotent.
        self._hotkeys_revision += 1
        suffix = ", key refreshed" if key_refreshed else ""
        if deferred:
            suffix += ", stream change deferred to next idle"
        return (f"reloaded (mode={new_cfg.get('mode')}, "
                f"prebuffer={'on' if want_stream else 'off'}{suffix})")

    # --- Cycle-Hotkey -----------------------------------------------------

    def cycle_active_mode(self) -> tuple[str, str] | None:
        """Rotiert _active_mode durch cycle_loop weiter (wrap-around).
        Rückgabe: (mode_id, ui_name) bei Erfolg, None wenn cycle_loop leer.
        Ändert _active_mode nur, wenn cycle_loop mindestens einen Eintrag hat.
        """
        with self._lock:
            nxt = cfg_mod.cycle_loop_next(self.config, self._active_mode)
            if nxt is None:
                return None
            self._active_mode = nxt
            ui = cfg_mod.get_mode_ui_name(nxt, self.config)
        print(f"↻  Cycle → {nxt} ({ui})")
        return (nxt, ui)

    # --- Pause-Mechanismus für AHK-Hotkeys --------------------------------

    def set_hotkeys_paused(self, paused: bool) -> None:
        """Setzt das hotkeys_paused-Flag. AHK pollt /health und schaltet
        Hotkeys aus/ein. Idempotent — mehrfacher Aufruf ist harmlos."""
        with self._lock:
            self._hotkeys_paused = bool(paused)

    # --- Hotkey-Belegung für AHK ------------------------------------------

    def get_hotkeys(self) -> dict:
        """Liefert die effektive Hotkey-Belegung im Format für AHK.
        Wird via GET /hotkeys vom AHK-Skript abgefragt — beim Start und
        nach Revisionsänderung."""
        hk = self.config.get("hotkeys") or {}
        per_mode = hk.get("per_mode") or {}
        return {
            "main": hk.get("main") or "CapsLock",
            "cycle": hk.get("cycle"),
            "modes": [
                {
                    "hotkey": spec,
                    "mode_id": mid,
                    "ui_name": cfg_mod.get_mode_ui_name(mid, self.config),
                }
                for mid, spec in per_mode.items()
                if spec
            ],
            "revision": self._hotkeys_revision,
        }

    def _set_error(self, msg: str) -> None:
        # Newlines/CR raus, damit die /health-Zeilenstruktur nicht bricht
        clean = msg.replace("\n", " ").replace("\r", " ").strip()
        self.last_error = clean[:200]
        self.last_error_ts = time.time()

    def start(self, mode_override: str | None = None) -> None:
        """Startet eine Aufnahme. mode_override (von /start mit JSON-Body)
        fixiert den Modus für genau diese Aufnahme — wird in _process()
        bevorzugt, danach zurückgesetzt. None = nutze den aktiven Modus."""
        with self._lock:
            if self.state is not State.IDLE:
                # Doppeltap im Post-Roll-Fenster oder während PROCESSING:
                # User merkt sonst nichts. Toast über _set_error → /health.
                msg = (f"Aufnahme zu schnell hintereinander "
                       f"(State={self.state.value}). Bitte kurz warten.")
                print(f"⚠  {msg}")
                self._set_error(msg)
                return
            # RDP-Reconnect-Schutz: ist der Prebuffer-Stream tot (liefert keine
            # Frames mehr)? Fix(2): NICHT nur abweisen, sondern SOFORT eine
            # Recovery versuchen (PortAudio neu initialisieren + Stream neu
            # öffnen) — oft klappt dann schon dieser Tastendruck. Erst wenn die
            # Sofort-Recovery nicht greift, abweisen und dem Watchdog überlassen
            # (kein Ins-Leere-Aufnehmen — der User spräche sonst umsonst).
            if (self._stream_always_on
                    and _stream_is_stale(time.time(), self._last_audio_ts,
                                         STREAM_STALE_S)):
                print("⚠  Mikrofon reagiert beim Druck nicht — Sofort-Recovery…",
                      file=sys.stderr)
                self._close_persistent_stream(verbose=False)
                self._reinit_portaudio(verbose=False)
                self._open_persistent_stream(verbose=False)
                if not self._stream_always_on:
                    # Reopen scheiterte (Gerät noch weg) — Watchdog macht weiter.
                    msg = ("Mikrofon wird neu verbunden — "
                           "bitte gleich nochmal drücken.")
                    print(f"⚠  {msg}")
                    self._set_error(msg)
                    # Verhindert einen doppelten „verloren"-Toast aus dem Watchdog.
                    self._stream_recovering = True
                    return
                # Stream wieder offen → unten normal als Prebuffer aufnehmen.
            # Mode-Override für diese Session merken (None = aktiver Modus).
            # Liegt im Lock, damit _process keinen halben Wert sieht.
            self._session_mode = mode_override if mode_override in cfg_mod.MODES else None
            # Reihenfolge: erst chunks leeren, dann state=RECORDING.
            # _on_audio liest state ohne Lock — schreibt nur, wenn er
            # RECORDING sieht. Andersrum würde ein Audio-Frame kurz vor
            # dem Clear in der alten Liste landen.
            self._chunks = []
            self._chunks_total_samples = 0
            if self._stream_always_on:
                # Prebuffer-Modus: Stream läuft schon, _on_audio wird ab
                # jetzt zusätzlich in _chunks schreiben.
                self.state = State.RECORDING
                print("▶  Aufnahme gestartet (prebuffer)")
            else:
                # On-Demand-Modus: Stream pro Diktat öffnen. _open_ondemand_stream
                # kapselt Try + PortAudio-Reinit-Retry (Fix(2)) — sonst HTTP-500
                # statt sauberer Toast-Meldung, und ein device=-1 nach Reboot
                # endete in einer Dauer-Fehlermeldung.
                device = self.config.get("audio_device")
                if not self._open_ondemand_stream(device):
                    return  # Fehler ist gesetzt, State bleibt IDLE
                self.state = State.RECORDING
                print("▶  Aufnahme gestartet")

    def _on_audio(self, indata, frames, time_info, status):  # noqa: ARG002
        # Lebenszeichen für den Stream-Watchdog: jeder Callback = Stream lebt.
        # (Läuft im PortAudio-Thread; einfacher float-Write, lock-frei ok.)
        self._last_audio_ts = time.time()
        if status:
            # status meldet Buffer-Overflows o.ä. — nur loggen, nicht abbrechen
            print(f"[audio status] {status}", file=sys.stderr)
        # indata-Buffer wird von sounddevice recycled → copy() pflicht
        chunk = indata.copy()
        # Prebuffer-Modus: Ringpuffer immer befüllen, Größe begrenzen.
        # deque.append + popleft sind in CPython thread-safe (GIL).
        if self._stream_always_on:
            self._ringbuffer.append(chunk)
            total = sum(c.shape[0] for c in self._ringbuffer)
            while (len(self._ringbuffer) > 1
                   and total > self._ringbuffer_max_samples):
                total -= self._ringbuffer.popleft().shape[0]
        # Während aktiver Aufnahme: chunks befüllen + Watchdog gegen
        # klemmenden Hotkey. Watchdog-Trigger erfolgt aus separatem Thread,
        # weil PortAudio's stop()/close() nicht aus dem Audio-Callback
        # heraus aufgerufen werden darf.
        if self.state is State.RECORDING:
            self._chunks.append(chunk)
            self._chunks_total_samples += chunk.shape[0]
            if self._chunks_total_samples > MAX_RECORD_S * SAMPLE_RATE:
                self._set_error(
                    f"Diktat-Limit {int(MAX_RECORD_S)}s erreicht — "
                    f"automatisch beendet."
                )
                # Verhindern dass mehrere Audio-Frames jeweils einen
                # eigenen Finalize-Thread starten: chunks_total kurz
                # zurücksetzen, damit weitere Frames die Schwelle nicht
                # erneut überschreiten (state-Wechsel auf PROCESSING
                # passiert eh asynchron).
                self._chunks_total_samples = -1  # Sentinel
                threading.Thread(
                    target=self._finalize_recording, daemon=True
                ).start()

    def stop(self) -> None:
        with self._lock:
            if self.state is not State.RECORDING:
                print(f"[stop ignoriert — State={self.state.value}]")
                return
            postroll_ms = int(self.config.get("postroll_ms", 200))
            postroll_ms = max(0, min(POSTROLL_MS_MAX, postroll_ms))
        # Bei aktivem Post-Roll: state bleibt RECORDING, _on_audio schreibt
        # weitere postroll_ms in _chunks. Erst dann _finalize_recording().
        # Während dieses Fensters wird /start ignoriert (state=RECORDING) —
        # akzeptiert für die geringe Verzögerung.
        if postroll_ms > 0:
            timer = threading.Timer(postroll_ms / 1000.0, self._finalize_recording)
            timer.daemon = True
            self._postroll_timer = timer
            timer.start()
            print(f"⏸  Post-Roll {postroll_ms} ms läuft …")
        else:
            self._finalize_recording()

    def _finalize_recording(self) -> None:
        """Schließt die Aufnahme nach Post-Roll-Phase ab: state→PROCESSING,
        Stream im On-Demand-Modus zu, Worker startet.

        Try-wrappt den Stream-Close, damit ein Mikro-Abstecken o.ä. nicht
        den Recorder hängen lässt — State wird auf jeden Fall in
        PROCESSING/IDLE-Zyklus überführt."""
        with self._lock:
            self._postroll_timer = None
            if self.state is not State.RECORDING:
                # Bereits anders verarbeitet (z. B. shutdown) — überspringen
                return
            if not self._stream_always_on and self._stream is not None:
                try:
                    self._stream.stop()
                    self._stream.close()
                except Exception as e:  # noqa: BLE001
                    print(f"⚠  Stream-Close-Fehler in finalize: {e}",
                          file=sys.stderr)
                self._stream = None
            # Prebuffer-Modus: Stream bleibt offen, Ringpuffer rollt weiter
            self.state = State.PROCESSING
        # Verarbeitung in Worker-Thread, damit HTTP-Response sofort zurück geht
        threading.Thread(target=self._process, daemon=True).start()

    def _process(self) -> None:
        try:
            if not self._chunks:
                msg = "Keine Audiodaten aufgenommen (zu kurzer Klick?)"
                print(f"⚠  {msg}")
                self._set_error(msg)
                return

            audio = np.concatenate(self._chunks, axis=0)
            duration_s = len(audio) / SAMPLE_RATE

            # 3a — Kurz-Tipp-Schutz: still verwerfen, kein OpenAI-Call,
            # kein Error-Toast. Misst NUR die aktive Diktat-Dauer (ohne
            # Pre-Roll), damit der Schwellwert intuitiv bleibt.
            if duration_s < MIN_RECORD_S:
                print(f"⏭  Aufnahme {duration_s*1000:.0f} ms < "
                      f"{MIN_RECORD_S*1000:.0f} ms — verworfen (Kurz-Tipp).\n")
                return

            # 3b — Pre-Roll: bis zu preroll_ms (aus Config, max RINGBUFFER_S)
            # aus dem Ringpuffer vor das Diktat hängen.
            # Lock-Hinweis: Der Audio-Thread hält das Lock NICHT (würde im
            # Audio-Callback Latenz erzeugen). list(deque) während paralleler
            # popleft ist crash-sicher (CPython/GIL), kann aber Linke
            # Chunks verpassen. Toleriert, weil der Snapshot ohnehin auf
            # max_pre samples getrimmt wird — ein paar verlorene Frames an
            # der Linken sind innerhalb des Trim-Bereichs.
            preroll_ms = int(self.config.get("preroll_ms", 300))
            preroll_ms = max(0, min(PREROLL_MS_MAX, preroll_ms))
            if self._stream_always_on and preroll_ms > 0:
                pre_chunks = list(self._ringbuffer)
                if pre_chunks:
                    pre_audio = np.concatenate(pre_chunks, axis=0)
                    max_pre = int(preroll_ms / 1000.0 * SAMPLE_RATE)
                    if len(pre_audio) > max_pre:
                        pre_audio = pre_audio[-max_pre:]
                    audio = np.concatenate([pre_audio, audio], axis=0)
                    pre_ms = len(pre_audio) / SAMPLE_RATE * 1000
                    duration_s = len(audio) / SAMPLE_RATE
                    print(f"■  Aufnahme gestoppt ({duration_s:.1f}s, "
                          f"+{pre_ms:.0f} ms Pre-Roll) — transkribiere…")
                else:
                    print(f"■  Aufnahme gestoppt ({duration_s:.1f}s) — transkribiere…")
            else:
                print(f"■  Aufnahme gestoppt ({duration_s:.1f}s) — transkribiere…")

            wav_bytes = self._to_wav_bytes(audio)
            roh = self._transcribe(wav_bytes)
            if not roh.strip():
                msg = "Leere Transkription — nichts zu optimieren"
                print(f"⚠  {msg}")
                self._set_error(msg)
                return
            # Datenschutz: NIE den Volltext loggen — daemon.log liegt im
            # Hidden-Modus persistent auf Platte. Nur Länge ausgeben.
            print(f"📝  Roh:       <{len(roh)} Zeichen>")

            # Mode-Auflösung für diese Aufnahme:
            #   1. _session_mode (Modus-Hotkey hat /start mit mode-Body gefeuert)
            #   2. _active_mode  (Cycle-Hotkey hat ihn evtl. umgestellt)
            #   3. config["mode"] (Default-Fallback bei korruptem State)
            mode = (self._session_mode or self._active_mode
                    or self.config.get("mode", cfg_mod.DEFAULT_MODE))
            prompt = cfg_mod.get_mode_prompt(mode, self.config)
            if prompt is None:
                # Raw Draft: kein gpt-4o-mini-Call, Roh-Transkript direkt paste
                ausgabe = roh
                print(f"✂  Modus {mode}: Rohtranskript 1:1")
            else:
                ausgabe = self._optimize(roh, prompt)
                if not ausgabe:
                    print("⚠  Optimierung leer — nutze Roh-Transkript")
                    ausgabe = roh
                print(f"✨  {mode}: <{len(ausgabe)} Zeichen>")

            pyperclip.copy(ausgabe)
            status = self._paste(ausgabe)
            print(f"✔  {status}\n")
            # Onboarding-Marker für die Tray-App: ab jetzt hat der User
            # mindestens einmal erfolgreich diktiert. Schreiben ohne Lock —
            # einfacher float-Write, niemand liest darauf inkrementell.
            self.last_dictation_ts = time.time()
        except Exception as e:  # noqa: BLE001
            # Defensive: nur Exception-Typ + Kurz-Message — vermeidet, dass
            # OpenAI in Error-Strings möglicherweise Transkripts-Fragmente
            # echoed (z. B. content-policy-Verstöße). _set_error kürzt eh
            # auf 200 Zeichen.
            err = f"{type(e).__name__}: {e}"
            print(f"❌  Fehler in Verarbeitung: {type(e).__name__}",
                  file=sys.stderr)
            self._set_error(err)
        finally:
            with self._lock:
                self.state = State.IDLE
                # Session-Mode-Override gilt nur für die abgeschlossene Aufnahme.
                self._session_mode = None
                # RAM-Hygiene: aufgenommenes Audio nicht bis zum nächsten
                # Diktat im Speicher liegen lassen.
                self._chunks = []
                self._chunks_total_samples = 0

    @staticmethod
    def _to_wav_bytes(audio: np.ndarray) -> bytes:
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(np.dtype(DTYPE).itemsize)
            wf.setframerate(SAMPLE_RATE)
            wf.writeframes(audio.tobytes())
        return buf.getvalue()

    def _transcribe(self, wav_bytes: bytes) -> str:
        resp = self._client.audio.transcriptions.create(
            model=MODEL_TRANSCRIBE,
            file=("speech.wav", wav_bytes, "audio/wav"),
            language="de",
        )
        return resp.text

    def _optimize(self, roh: str, system_prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=MODEL_OPTIMIZE,
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": roh},
            ],
        )
        return (resp.choices[0].message.content or "").strip()

    def _paste(self, text: str) -> str:
        """Übergibt `text` ans aktive Fenster gemäß config['paste_mode'].

        - clipboard_ctrl_v: sendet Ctrl+V (Text liegt bereits im Clipboard).
        - clipboard_only:   nichts — User drückt selbst Ctrl+V / Rechtsklick.
        - send_input:       tippt den Text via Win32 SendInput (Unicode).
        Rückgabe: kurzer Status-String für die Log-Zeile.
        Unbekannter Wert fällt auf clipboard_ctrl_v zurück.
        """
        mode = self.config.get("paste_mode", "clipboard_ctrl_v")
        if mode == "clipboard_only":
            return "In Zwischenablage kopiert (manuell Ctrl+V)"
        if mode == "send_input":
            _type_text_unicode(text)
            return "Per SendInput ins aktive Fenster getippt"
        # clipboard_ctrl_v (Default + Fallback)
        # Lazy-Import: pyautogui macht beim Laden DISPLAY-Checks
        import pyautogui
        time.sleep(PASTE_DELAY_S)
        pyautogui.hotkey("ctrl", "v")
        return "In Zwischenablage kopiert und eingefügt"


# --- HTTP-Handler -----------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    recorder: Recorder  # wird vor serve_forever() gesetzt

    def _ok(self, body: str = "ok", content_type: str = "text/plain") -> None:
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json_body(self, max_bytes: int = 1024) -> dict | None:
        """Liest und parst JSON-Body. None wenn leer oder ungültig.
        max_bytes verhindert Riesen-Bodies (Push-to-Talk-Bodies sind winzig)."""
        try:
            cl = int(self.headers.get("Content-Length", "0") or 0)
        except ValueError:
            return None
        if cl <= 0 or cl > max_bytes:
            return None
        try:
            raw = self.rfile.read(cl).decode("utf-8")
            payload = json.loads(raw)
            return payload if isinstance(payload, dict) else None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None

    def do_POST(self):  # noqa: N802 — http.server API
        if self.path == "/start":
            payload = self._read_json_body()
            mode_override = None
            if payload is not None:
                m = payload.get("mode")
                if isinstance(m, str) and m in cfg_mod.MODES:
                    mode_override = m
            self.recorder.start(mode_override)
            self._ok()
        elif self.path == "/stop":
            self.recorder.stop()
            self._ok()
        elif self.path == "/pause-hotkeys":
            self.recorder.set_hotkeys_paused(True)
            self._ok("paused")
        elif self.path == "/resume-hotkeys":
            self.recorder.set_hotkeys_paused(False)
            self._ok("resumed")
        elif self.path == "/cycle":
            result = self.recorder.cycle_active_mode()
            if result is None:
                self.send_error(400, "cycle_loop empty")
                return
            mode_id, ui_name = result
            # Zeilenweise key=value für AHK (kein JSON-Parser nötig).
            body = f"active_mode={mode_id}\nui_name={ui_name}"
            self._ok(body)
        elif self.path == "/reload-config":
            try:
                status = self.recorder.reload_config()
                self._ok(status)
            except Exception as e:  # noqa: BLE001
                self.recorder._set_error(f"reload-config: {type(e).__name__}: {e}")
                self.send_error(500, f"reload failed: {e}")
        elif self.path == "/shutdown":
            self._ok("bye")
            # Hard-Exit statt server.shutdown(): sounddevice/PortAudio und
            # openai-SDK halten Non-Daemon-Threads am Leben, die einen
            # sauberen Python-Exit verhindern (pythonw.exe bleibt zombie).
            # os._exit(0) umgeht Python-Cleanup und killt alle Threads.
            # Wir haben nichts zu persistieren: Audio lebt nur im RAM,
            # Clipboard gehört dem OS, kein offener File-Handle außer Log.
            def hard_exit():
                time.sleep(0.15)  # Response-Bytes rauslassen
                handshake.clear_port_file()  # Discovery-Datei aufräumen vor Hard-Exit
                os._exit(0)
            threading.Thread(target=hard_exit, daemon=True).start()
        else:
            self.send_error(404)

    def do_GET(self):  # noqa: N802 — http.server API
        if self.path == "/health":
            # Reads bewusst lock-frei: Diagnose-Endpoint, polling 1×/s, ein
            # einzelner stale Snapshot ist hinnehmbar und besser als HTTP-
            # Polls hinter dem Recorder-Lock zu queueen.
            r = self.recorder
            active = r._active_mode or r.config.get("mode", cfg_mod.DEFAULT_MODE)
            active_ui = cfg_mod.get_mode_ui_name(active, r.config)
            cycle_size = len(r.config.get("cycle_loop") or [])
            audio_age = (time.time() - r._last_audio_ts) if r._stream_always_on else -1.0
            body = (
                f"state={r.state.value}\n"
                f"last_error={r.last_error}\n"
                f"last_error_ts={r.last_error_ts:.3f}\n"
                f"last_dictation_ts={r.last_dictation_ts:.3f}\n"
                f"mode={r.config.get('mode', cfg_mod.DEFAULT_MODE)}\n"
                f"active_mode={active}\n"
                f"active_mode_ui_name={active_ui}\n"
                f"cycle_loop_size={cycle_size}\n"
                f"hotkeys_revision={r._hotkeys_revision}\n"
                f"hotkeys_paused={'on' if r._hotkeys_paused else 'off'}\n"
                f"prebuffer={'on' if r._stream_always_on else 'off'}\n"
                f"audio_age={audio_age:.1f}\n"
                f"stream_recovering={'on' if r._stream_recovering else 'off'}"
            )
            self._ok(body)
        elif self.path == "/hotkeys":
            # Zeilenweise key=value für AHK. Modi werden indexiert
            # (mode.<i>.id / .spec / .ui_name), Anzahl in mode_count.
            hk = self.recorder.get_hotkeys()
            lines = [
                f"revision={hk['revision']}",
                f"main={hk['main'] or ''}",
                f"cycle={hk['cycle'] or ''}",
                f"mode_count={len(hk['modes'])}",
            ]
            for i, m in enumerate(hk["modes"]):
                lines.append(f"mode.{i}.id={m['mode_id']}")
                lines.append(f"mode.{i}.spec={m['hotkey']}")
                lines.append(f"mode.{i}.ui_name={m['ui_name']}")
            self._ok("\n".join(lines))
        else:
            self.send_error(404)

    def log_message(self, format, *args):  # noqa: A002 — http.server API
        # Standard-Access-Log unterdrücken (jeder Hotkey wäre eine Zeile)
        return


# --- Helpers ----------------------------------------------------------------

def _setup_hidden_logging() -> Path:
    """stdout/stderr auf %APPDATA%/Speech2Text/daemon.log umleiten.

    Wird nur im --hidden-Modus aufgerufen (Autostart ohne Console-Fenster).
    Einfache Rotation: wenn die Datei > LOG_MAX_BYTES ist, wird sie nach
    daemon.1.log verschoben (älteres daemon.1.log wird dabei überschrieben).
    """
    appdata = os.environ.get("APPDATA")
    log_dir = Path(appdata) / "Speech2Text" if appdata else Path.home() / ".speech2text"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "daemon.log"

    if log_file.exists() and log_file.stat().st_size > LOG_MAX_BYTES:
        backup = log_dir / "daemon.1.log"
        if backup.exists():
            backup.unlink()
        log_file.rename(backup)

    # line-buffered, damit jede Zeile sofort auf Platte landet (wichtig bei
    # crashes — Log ist die einzige Diagnose-Quelle im Hidden-Modus).
    # errors="replace": nie wegen eines exotischen Zeichens crashen.
    f = open(log_file, "a", encoding="utf-8", errors="replace", buffering=1)
    sys.stdout = f
    sys.stderr = f
    return log_file


# --- Entry-Point ------------------------------------------------------------

# Single-Instance pro Windows-Session über einen Named Mutex. Bei Port 0 (OS
# wählt freien Port, Multi-Session-Adressierung via handshake.py) ist der Bind
# kein Lock mehr. Der „Local\\"-Namespace ist je RDP-Session eigen → genau ein
# Daemon pro Session; das OS gibt den Mutex bei Prozess-Ende frei (auch bei
# os._exit) → kein Stale-Lock. Ersetzt den allow_reuse_address-Schutz (Session 19),
# der nur bei festem Port wirkte.
MUTEX_NAME = "Local\\Speech2Text-Daemon"

_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateMutexW.restype = wintypes.HANDLE
_k32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
_k32.CloseHandle.restype = wintypes.BOOL
_k32.CloseHandle.argtypes = [wintypes.HANDLE]
_ERROR_ALREADY_EXISTS = 183


def _acquire_single_instance_lock(name: str = MUTEX_NAME):
    """Erwirbt den Session-lokalen Single-Instance-Mutex. Returnt das Handle
    (für die Daemon-Lebensdauer offen halten) oder None, wenn in dieser Session
    bereits ein Daemon läuft."""
    handle = _k32.CreateMutexW(None, False, name)
    err = ctypes.get_last_error()
    if not handle:
        return None
    if err == _ERROR_ALREADY_EXISTS:
        _k32.CloseHandle(handle)
        return None
    return handle


def _release_single_instance_lock(handle) -> None:
    """Gibt den Mutex frei (Daemon beendet). None-sicher."""
    if handle:
        _k32.CloseHandle(handle)


class _SingleInstanceHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer für den Daemon (Bind auf Port 0).

    Der Single-Instance-Schutz läuft seit Multi-User (Ansatz B) NICHT mehr über
    den Port-Bind: Bei Port 0 wählt das OS je Start einen anderen freien Port,
    ein zweiter Bind gelingt also immer. Genau ein Daemon je Windows-Session
    garantiert stattdessen der Session-lokale Named Mutex in main()
    (_acquire_single_instance_lock). ThreadingHTTPServer: jede Request landet in
    einem eigenen Thread → /start und /stop warten nicht hinter /health-Polls.
    """


def main() -> int:
    # stdout/stderr robust auf UTF-8 stellen, sonst crashen print("▶ …") &
    # Co. auf cp1252-Consolen und wenn stdout durch eine Pipe läuft
    # (Scheduled Task, Bash-Shell, manche Autostart-Umgebungen).
    # errors="replace" statt Crash → im Worst-Case erscheint "?" statt Emoji.
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            try:
                _stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass

    # Hidden-Modus: explizit per --hidden, ODER automatisch im
    # PyInstaller-Bundle (--noconsole), wo es keinen stdout-Target gibt.
    # `sys.frozen` ist das Standard-Indikator für PyInstaller-Bundles.
    hidden = "--hidden" in sys.argv or getattr(sys, "frozen", False)
    if hidden:
        log_file = _setup_hidden_logging()
        print(f"=== Speech2Text Daemon gestartet (hidden) "
              f"— {time.strftime('%Y-%m-%d %H:%M:%S')} ===")
        print(f"    Log: {log_file}")

    # Config laden: primär %APPDATA%/Speech2Text/config.json, Fallback auf
    # .env (Entwicklungs-Modus). Settings-GUI schreibt später in die JSON.
    env_path = Path(__file__).resolve().parent.parent / ".env"
    load_dotenv(env_path)
    app_config = cfg_mod.load_config()
    api_key = cfg_mod.get_api_key(app_config) or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print(
            "❌  Kein OpenAI-API-Key gefunden.\n"
            f"    Erwartet entweder in {cfg_mod.config_path()}\n"
            f"    oder als OPENAI_API_KEY in {env_path}",
            file=sys.stderr,
        )
        return 2

    # Single-Instance-Gate: Session-lokaler Named Mutex ZUERST — BEVOR Recorder
    # und Mikrofon initialisiert werden. Bei Port 0 ist der Bind kein Lock mehr
    # (jeder Daemon bekommt einen anderen freien Port); der Mutex (Local\ = pro
    # RDP-Session) lässt genau einen Daemon je Session zu und wird vom OS bei
    # Prozess-Ende freigegeben (kein Stale). So bleibt Doppel-Daemon/Mic-
    # Contention (Session 18/19) verhindert, ohne je das Mikrofon zu belegen.
    instance_lock = _acquire_single_instance_lock()
    if instance_lock is None:
        print("❌  Es läuft schon ein Daemon in dieser Sitzung. "
              "Beende diese Instanz.", file=sys.stderr)
        return 3

    # Port 0 binden — das OS wählt einen freien, session-exklusiven Port.
    # ThreadingHTTPServer: jede Request in eigenem Thread → /start//stop warten
    # nicht hinter /health-Polls. Recorder-State ist mit self._lock thread-safe.
    try:
        server = _SingleInstanceHTTPServer((HOST, 0), Handler)
    except OSError as e:
        print(f"❌  Konnte keinen Port binden ({type(e).__name__}: {e}). "
              "Beende diese Instanz.", file=sys.stderr)
        _release_single_instance_lock(instance_lock)
        return 3
    actual_port = server.server_address[1]

    # Port in die per-User-Handshake-Datei schreiben, damit der Tray (gleiche
    # Session, gleiches %APPDATA%) den Daemon findet. handshake.py = Single Source.
    handshake.write_port(actual_port, os.getpid())

    # Erst NACH erfolgreichem Bind das Mikrofon + den Recorder öffnen.
    recorder = Recorder(app_config, api_key)
    Handler.recorder = recorder

    # Cold-Start vermeiden: TLS-Handshake + Auth gegen OpenAI im Hintergrund
    # vorab durchziehen, damit das ERSTE Diktat nicht 0,5–1 s extra wartet.
    # Fehler ignorieren: scheitert das (Offline, falscher Key), fängt's
    # spätestens der echte Diktat-Call ab.
    def _warmup() -> None:
        try:
            recorder._client.models.list()
        except Exception:  # noqa: BLE001
            pass
    threading.Thread(target=_warmup, daemon=True).start()

    print(f"Speech2Text Daemon läuft auf http://{HOST}:{actual_port} "
          f"(PID {os.getpid()} — Session-Port via handshake.py)")
    print(f"  Config:     {cfg_mod.config_path()}")
    print(f"  Modus:      {app_config.get('mode', cfg_mod.DEFAULT_MODE)}")
    print("  Endpoints:  POST /start · /stop · /cycle · /pause-hotkeys · /resume-hotkeys · /reload-config · /shutdown · GET /health · /hotkeys")
    print("  Hotkey:     src/tray_app.py (Push-to-Talk via Win32 Low-Level-Hook)")
    if hidden:
        print("  Logging:    hidden (stdout/stderr → Log-Datei)")
    else:
        print("  Beenden:    Strg+C")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBeende Daemon…")
        server.shutdown()
    finally:
        handshake.clear_port_file()
        _release_single_instance_lock(instance_lock)
    return 0


if __name__ == "__main__":
    sys.exit(main())
