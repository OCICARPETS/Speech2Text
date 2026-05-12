"""Win32 Low-Level Keyboard Hook + Hotkey-Manager.

Ersetzt die AHK-Hotkey-Schicht aus `shortcut.ahk` (v1.2). Nutzt
`SetWindowsHookExW(WH_KEYBOARD_LL)` — denselben Mechanismus, den AHK
intern verwendet (`$`-Prefix). Damit funktioniert die Hotkey-Erkennung
auch in RDP-Sessions, wo `RegisterHotKey` stumm bleibt.

Architektur:
  - Modul-Konstanten + `parse_spec()` (Pure-Python, ohne Win32 importierbar)
  - `HotkeyManager`-Klasse — startet einen Hook-Thread mit Win32-Message-
    Loop und ruft Callbacks pro gebundenem Hotkey.

`parse_spec()` ist bewusst Win32-frei (kein ctypes-Import) — Tests
können das Modul ohne Windows laden.

Lizenz: eigener Code. Keine LGPL/GPL-Last.
"""
from __future__ import annotations

import sys
import threading
from typing import Callable

# --- Modifier-Bitmaske + Virtual-Key-Mapping --------------------------------

MOD_CTRL  = 1 << 0
MOD_ALT   = 1 << 1
MOD_SHIFT = 1 << 2
MOD_WIN   = 1 << 3

_MOD_CHARS: dict[str, int] = {
    "^": MOD_CTRL, "!": MOD_ALT, "+": MOD_SHIFT, "#": MOD_WIN,
}

# Win32 Virtual-Key-Codes (USER32 USER.h)
VK_CAPITAL  = 0x14
VK_PAUSE    = 0x13
VK_INSERT   = 0x2D
VK_SCROLL   = 0x91
VK_NUMLOCK  = 0x90

# Modifier-VKs (für GetAsyncKeyState im Hook-Callback)
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU    = 0xA4  # left Alt
VK_RMENU    = 0xA5  # right Alt
VK_LSHIFT   = 0xA0
VK_RSHIFT   = 0xA1
VK_LWIN     = 0x5B
VK_RWIN     = 0x5C


def _build_key_map() -> dict[str, int]:
    m: dict[str, int] = {
        "CapsLock":   VK_CAPITAL,
        "Pause":      VK_PAUSE,
        "Insert":     VK_INSERT,
        "ScrollLock": VK_SCROLL,
        "NumLock":    VK_NUMLOCK,
    }
    for i in range(1, 25):
        m[f"F{i}"] = 0x6F + i  # VK_F1 = 0x70
    for c in range(ord("A"), ord("Z") + 1):
        m[chr(c)] = c
        m[chr(c).lower()] = c
    for d in range(10):
        m[str(d)] = 0x30 + d
    return m


_KEY_MAP: dict[str, int] = _build_key_map()


def parse_spec(spec: str) -> tuple[int, int] | None:
    """AHK-v2-Spec → ``(modifier_bitmask, vk_code)``.

    Beispiele:
      ``CapsLock`` → ``(0, 0x14)``
      ``^!r``      → ``(MOD_CTRL|MOD_ALT, 0x52)``
      ``+#F12``    → ``(MOD_SHIFT|MOD_WIN, 0x7B)``

    Rückgabe ``None`` bei leerer oder ungültiger Spec.
    """
    if not spec:
        return None
    mods = 0
    i = 0
    while i < len(spec) and spec[i] in _MOD_CHARS:
        mods |= _MOD_CHARS[spec[i]]
        i += 1
    key = spec[i:]
    if not key:
        return None  # Modifier-only — nicht erlaubt
    vk = _KEY_MAP.get(key)
    if vk is None:
        return None
    return (mods, vk)


# --- Win32-Hook (Import nur unter Windows) ---------------------------------
# Wir trennen Spec-Parser (oben) und Hook-Layer (unten) sauber, damit Tests
# das Modul auf Nicht-Windows laden können.

_IS_WINDOWS = sys.platform == "win32"

if _IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    WH_KEYBOARD_LL = 13
    WM_KEYDOWN     = 0x0100
    WM_KEYUP       = 0x0101
    WM_SYSKEYDOWN  = 0x0104
    WM_SYSKEYUP    = 0x0105

    HC_ACTION = 0

    class _KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode",      wintypes.DWORD),
            ("scanCode",    wintypes.DWORD),
            ("flags",       wintypes.DWORD),
            ("time",        wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_void_p),
        ]

    LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
        ctypes.c_long,
        ctypes.c_int,
        wintypes.WPARAM,
        ctypes.POINTER(_KBDLLHOOKSTRUCT),
    )

    _user32.SetWindowsHookExW.argtypes = (
        ctypes.c_int, LowLevelKeyboardProc, wintypes.HINSTANCE, wintypes.DWORD,
    )
    _user32.SetWindowsHookExW.restype = wintypes.HHOOK
    _user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
    _user32.UnhookWindowsHookEx.restype = wintypes.BOOL
    _user32.CallNextHookEx.argtypes = (
        wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM,
    )
    _user32.CallNextHookEx.restype = wintypes.LPARAM
    _user32.GetMessageW.argtypes = (
        ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT,
    )
    _user32.GetMessageW.restype = wintypes.BOOL
    _user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
    _user32.GetAsyncKeyState.restype = ctypes.c_short
    _user32.PostThreadMessageW.argtypes = (
        wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    )
    _user32.PostThreadMessageW.restype = wintypes.BOOL
    _kernel32.GetCurrentThreadId.restype = wintypes.DWORD

    WM_QUIT = 0x0012


def _modifier_state() -> int:
    """Bitmaske der aktuell gedrückten Modifier (Ctrl/Alt/Shift/Win),
    egal ob links oder rechts. Nur unter Windows aufrufbar."""
    if not _IS_WINDOWS:
        return 0
    state = 0
    # high-bit von GetAsyncKeyState bedeutet "currently pressed"
    HIGH = 0x8000

    def down(vk: int) -> bool:
        return bool(_user32.GetAsyncKeyState(vk) & HIGH)

    if down(VK_LCONTROL) or down(VK_RCONTROL):
        state |= MOD_CTRL
    if down(VK_LMENU) or down(VK_RMENU):
        state |= MOD_ALT
    if down(VK_LSHIFT) or down(VK_RSHIFT):
        state |= MOD_SHIFT
    if down(VK_LWIN) or down(VK_RWIN):
        state |= MOD_WIN
    return state


# Modifier-VKs, die nicht als "Haupttaste" zählen — wir ignorieren sie als
# Hotkey-Trigger, damit z.B. ein gehaltenes Ctrl nicht versehentlich einen
# Modifier-less Hotkey deckt.
_MODIFIER_VKS = frozenset({
    VK_LCONTROL, VK_RCONTROL, VK_LMENU, VK_RMENU,
    VK_LSHIFT, VK_RSHIFT, VK_LWIN, VK_RWIN,
})


# --- HotkeyManager ----------------------------------------------------------

class HotkeyManager:
    """Verwaltet globale Hotkeys via Win32 Low-Level Keyboard Hook.

    Thread-Modell:
      - Eigener Hook-Thread mit Win32-Message-Loop (GetMessageW)
      - `bind()`, `unbind_all()`, `pause()`, `resume()` sind thread-safe
      - Callbacks (`on_press`, `on_release`) laufen im Hook-Thread —
        Konsument MUSS schnell zurückkehren (HTTP-POST ist ok, kein UI).

    Suppression:
      - Gebundene Hotkeys werden NICHT an Windows weitergereicht (Return 1
        statt CallNextHookEx). Damit triggert CapsLock keinen Großschrift-
        Toggle, F-Tasten keine App-Aktionen, Ctrl+R kein Browser-Refresh.
      - Ungebundene Tasten gehen normal weiter.

    Pause-Modus:
      - `pause()` setzt ein Flag; im Hook-Callback werden gebundene
        Hotkeys ignoriert (an Windows weitergereicht). Wird von der
        Settings-GUI während des Capture-Dialogs genutzt.
    """

    def __init__(self) -> None:
        # Map (mods, vk) → (on_press_cb, on_release_cb). on_release_cb darf
        # None sein (für reine Tap-Hotkeys wie Cycle).
        self._bindings: dict[tuple[int, int], tuple[Callable[[], None],
                                                    Callable[[], None] | None]] = {}
        # Set der vk-Codes, die aktuell als "down" verfolgt werden (Auto-
        # Repeat-Filter: KeyDown nur einmal feuern, bis ein KeyUp kommt).
        self._down: set[int] = set()
        self._lock = threading.Lock()
        self._paused = False
        self._hook = None  # HHOOK
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        # Hook-Proc als Member-Attribut halten — sonst sammelt GC den
        # Callback ein und Windows ruft eine freed function pointer auf.
        self._hook_proc = None

    # -- Public API --------------------------------------------------------

    def bind(self, spec: str,
             on_press: Callable[[], None],
             on_release: Callable[[], None] | None = None) -> bool:
        """Bindet einen AHK-v2-Spec. Doppel-Binding überschreibt stillschweigend.
        Return False bei ungültigem Spec."""
        parsed = parse_spec(spec)
        if parsed is None:
            return False
        with self._lock:
            self._bindings[parsed] = (on_press, on_release)
        return True

    def unbind_all(self) -> None:
        with self._lock:
            self._bindings.clear()
            self._down.clear()

    def pause(self) -> None:
        with self._lock:
            self._paused = True

    def resume(self) -> None:
        with self._lock:
            self._paused = False

    def start(self) -> None:
        """Startet den Hook-Thread. Idempotent."""
        if self._thread is not None and self._thread.is_alive():
            return
        if not _IS_WINDOWS:
            raise RuntimeError("HotkeyManager.start() benötigt Windows")
        ready = threading.Event()
        self._thread = threading.Thread(
            target=self._hook_thread, args=(ready,), daemon=True,
            name="HotkeyHook"
        )
        self._thread.start()
        # Auf Hook-Setup warten, damit bind() vor erster Tastenerfassung wirkt.
        ready.wait(timeout=2.0)

    def stop(self) -> None:
        """Hook abbauen + Message-Loop beenden. Idempotent."""
        if not _IS_WINDOWS or self._thread is None:
            return
        tid = self._thread_id
        if tid is not None:
            _user32.PostThreadMessageW(tid, WM_QUIT, 0, 0)
        self._thread.join(timeout=2.0)
        self._thread = None
        self._thread_id = None
        self._hook = None
        self._hook_proc = None

    # -- Internal ----------------------------------------------------------

    def _hook_thread(self, ready: threading.Event) -> None:
        self._thread_id = _kernel32.GetCurrentThreadId()
        # Hook-Proc MUSS auf self gehalten werden (siehe __init__-Kommentar)
        self._hook_proc = LowLevelKeyboardProc(self._low_level_proc)
        self._hook = _user32.SetWindowsHookExW(
            WH_KEYBOARD_LL, self._hook_proc, None, 0,
        )
        if not self._hook:
            err = ctypes.get_last_error()
            print(f"[HotkeyHook] SetWindowsHookExW fehlgeschlagen (err={err})",
                  file=sys.stderr)
            ready.set()
            return
        ready.set()
        # Message-Loop — WH_KEYBOARD_LL braucht eine laufende Pump im Thread,
        # der den Hook installiert hat. GetMessageW blockiert bis WM_QUIT
        # oder ein anderes Message.
        msg = wintypes.MSG()
        while True:
            rv = _user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if rv == 0 or rv == -1:
                break
            # TranslateMessage/DispatchMessage hier nicht nötig — wir haben
            # kein Fenster, nur Hook-Callbacks.
        try:
            if self._hook:
                _user32.UnhookWindowsHookEx(self._hook)
        finally:
            self._hook = None

    def _low_level_proc(self, nCode: int, wParam: int, lParam):
        # nCode < 0 → laut Doku einfach durchreichen, nicht inspizieren
        if nCode != HC_ACTION:
            return _user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
        try:
            ks = lParam.contents
            vk = ks.vkCode
            is_down = wParam in (WM_KEYDOWN, WM_SYSKEYDOWN)
            is_up   = wParam in (WM_KEYUP,   WM_SYSKEYUP)

            if vk in _MODIFIER_VKS:
                # Modifier selbst nie als Haupttaste — durchreichen.
                return _user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

            with self._lock:
                paused = self._paused
                bindings_snapshot = dict(self._bindings)

            if paused:
                return _user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

            mods = _modifier_state()

            # Match: erst exakter Modifier-Match (mods,vk), sonst Fallback
            # (0,vk) für modifier-lose Bindings (z.B. CapsLock alleine).
            # Beide Pfade lookup, um Auto-Repeat sauber zu tracken.
            entry = bindings_snapshot.get((mods, vk))
            if entry is None and mods != 0:
                # Modifier sind gedrückt, aber wir haben keinen passenden
                # Hotkey — durchreichen, kein Suppress.
                return _user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
            if entry is None:
                # Kein Hotkey für diese Taste — durchreichen.
                return _user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

            on_press, on_release = entry
            if is_down:
                if vk in self._down:
                    # Auto-Repeat: kein erneuter Trigger, aber Event suppressen
                    return 1
                self._down.add(vk)
                try:
                    on_press()
                except Exception as e:  # noqa: BLE001
                    print(f"[HotkeyHook] on_press error: "
                          f"{type(e).__name__}: {e}", file=sys.stderr)
                return 1  # suppress
            elif is_up:
                if vk not in self._down:
                    # KeyUp ohne vorheriges KeyDown (z.B. nach pause/resume)
                    return 1
                self._down.discard(vk)
                if on_release is not None:
                    try:
                        on_release()
                    except Exception as e:  # noqa: BLE001
                        print(f"[HotkeyHook] on_release error: "
                              f"{type(e).__name__}: {e}", file=sys.stderr)
                return 1  # suppress
        except Exception as e:  # noqa: BLE001
            # Defensiv: ein Crash im Hook-Callback würde den Hook abreißen.
            print(f"[HotkeyHook] proc error: {type(e).__name__}: {e}",
                  file=sys.stderr)
        return _user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
