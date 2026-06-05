"""Unit-Tests für `src/keyboard_hook.py`. Pure-Python, kein Win32 nötig.

Aufruf: `.venv/Scripts/python.exe -m unittest tests.test_keyboard_hook -v`
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# src/ in den Path nehmen — Module liegen flach.
SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import keyboard_hook as kh  # noqa: E402


class TestParseSpec(unittest.TestCase):
    def test_capslock_no_modifier(self):
        self.assertEqual(kh.parse_spec("CapsLock"), (0, 0x14))

    def test_f9_no_modifier(self):
        self.assertEqual(kh.parse_spec("F9"), (0, 0x78))

    def test_f24(self):
        self.assertEqual(kh.parse_spec("F24"), (0, 0x87))

    def test_ctrl_alt_r(self):
        expected = (kh.MOD_CTRL | kh.MOD_ALT, 0x52)  # R = 0x52
        self.assertEqual(kh.parse_spec("^!r"), expected)

    def test_uppercase_letter_matches(self):
        # Buchstaben sind case-insensitive im Mapping
        self.assertEqual(kh.parse_spec("^!R"), (kh.MOD_CTRL | kh.MOD_ALT, 0x52))

    def test_shift_win_f12(self):
        expected = (kh.MOD_SHIFT | kh.MOD_WIN, 0x7B)  # F12 = 0x7B
        self.assertEqual(kh.parse_spec("+#F12"), expected)

    def test_all_modifiers_with_digit(self):
        expected = (kh.MOD_CTRL | kh.MOD_ALT | kh.MOD_SHIFT | kh.MOD_WIN, 0x33)
        self.assertEqual(kh.parse_spec("^!+#3"), expected)

    def test_modifier_order_irrelevant(self):
        # AHK-Modifier-Reihenfolge ist beliebig im Input
        self.assertEqual(kh.parse_spec("!^r"), (kh.MOD_CTRL | kh.MOD_ALT, 0x52))

    def test_pause_special(self):
        self.assertEqual(kh.parse_spec("Pause"), (0, 0x13))

    def test_insert_special(self):
        self.assertEqual(kh.parse_spec("Insert"), (0, 0x2D))

    def test_scrolllock_special(self):
        self.assertEqual(kh.parse_spec("ScrollLock"), (0, 0x91))

    def test_numlock_special(self):
        self.assertEqual(kh.parse_spec("NumLock"), (0, 0x90))

    def test_digit_zero(self):
        self.assertEqual(kh.parse_spec("0"), (0, 0x30))

    def test_digit_nine(self):
        self.assertEqual(kh.parse_spec("9"), (0, 0x39))

    # --- Negative Tests --------------------------------------------------

    def test_empty_returns_none(self):
        self.assertIsNone(kh.parse_spec(""))

    def test_none_returns_none(self):
        self.assertIsNone(kh.parse_spec(None))

    def test_modifier_only_returns_none(self):
        self.assertIsNone(kh.parse_spec("^!"))

    def test_unknown_key_returns_none(self):
        self.assertIsNone(kh.parse_spec("BogusKey"))

    def test_two_chars_unknown_returns_none(self):
        # `xy` ist nicht in unserer Whitelist
        self.assertIsNone(kh.parse_spec("xy"))

    def test_f25_out_of_range(self):
        self.assertIsNone(kh.parse_spec("F25"))


class TestWin32Signatures(unittest.TestCase):
    """Regressionstests für den Hook-Crash aus Session 11.
    LowLevelKeyboardProc-lParam MUSS LPARAM (int) sein, nicht POINTER,
    sonst wirft CallNextHookEx in jedem Tastendruck ArgumentError."""

    def test_llkhf_injected_constants(self):
        # Win32-Bit-Werte stehen seit Win2k fest — wenn die sich ändern,
        # bricht wesentlich mehr als nur dieser Test.
        if not kh._IS_WINDOWS:
            self.skipTest("Win32-Konstanten nur unter Windows verfügbar")
        self.assertEqual(kh.LLKHF_INJECTED, 0x10)
        self.assertEqual(kh.LLKHF_LOWER_IL_INJECTED, 0x02)

    def test_lowlevel_proc_lparam_is_integer_type(self):
        # Die Proc-Signatur MUSS LPARAM (=int) als lParam haben. Sonst
        # crasht CallNextHookEx(lParam) mit ArgumentError 'LP_struct
        # cannot be interpreted as an integer'.
        if not kh._IS_WINDOWS:
            self.skipTest("ctypes-WINFUNCTYPE nur unter Windows verfügbar")
        from ctypes import wintypes
        argtypes = kh.LowLevelKeyboardProc._argtypes_
        # Position 3 = lParam (nach nCode, wParam)
        self.assertEqual(argtypes[2], wintypes.LPARAM,
                         msg="lParam muss LPARAM (integer) sein, "
                             "sonst crasht CallNextHookEx")


class TestHotkeyManagerBind(unittest.TestCase):
    """HotkeyManager-Logik ohne Hook-Thread (start() nicht aufrufen).
    Wir testen nur Bind/Unbind/Pause-State, weil die echte Hook-Schicht
    nur in einem interaktiven Live-Test mit Tastendruck validierbar ist.
    """

    def test_bind_valid_spec(self):
        mgr = kh.HotkeyManager()
        called = []
        ok = mgr.bind("F9", lambda: called.append("press"))
        self.assertTrue(ok)
        self.assertIn((0, 0x78), mgr._bindings)

    def test_bind_invalid_spec_returns_false(self):
        mgr = kh.HotkeyManager()
        self.assertFalse(mgr.bind("BogusKey", lambda: None))
        self.assertFalse(mgr.bind("", lambda: None))

    def test_unbind_all_clears(self):
        mgr = kh.HotkeyManager()
        mgr.bind("F9", lambda: None)
        mgr.bind("CapsLock", lambda: None)
        self.assertEqual(len(mgr._bindings), 2)
        mgr.unbind_all()
        self.assertEqual(len(mgr._bindings), 0)

    def test_bind_overwrites_same_spec(self):
        mgr = kh.HotkeyManager()
        mgr.bind("F9", lambda: None)
        mgr.bind("F9", lambda: None)  # zweites Mal überschreibt
        self.assertEqual(len(mgr._bindings), 1)

    def test_pause_resume_toggle(self):
        mgr = kh.HotkeyManager()
        self.assertFalse(mgr._paused)
        mgr.pause()
        self.assertTrue(mgr._paused)
        mgr.resume()
        self.assertFalse(mgr._paused)


class TestHandleEventMacroKeyboard(unittest.TestCase):
    """Regressionstests fuer den Makro-Tastatur-Bug (siehe tray.log-Analyse
    2026-05-18): Modifier werden vor der Haupttaste released, dadurch fand
    der KeyUp die Bindung nicht mehr → Aufnahme blieb haengen + Cycle ueber
    dieselbe vk wurde durch den vk-only Auto-Repeat-Filter blockiert.

    Wir testen `_handle_event` direkt — pure Python, kein Win32 noetig.
    `_dispatch` wird durch synchrones Tracking ersetzt.
    """

    def setUp(self) -> None:
        self.mgr = kh.HotkeyManager()
        self.calls: list[str] = []
        # _dispatch synchron + tracking, damit wir die Callbacks zaehlen
        # koennen ohne echten Worker-Thread.
        self.mgr._dispatch = lambda cb: cb()
        # Per-Test wird ein on_press/on_release-Pair pro logischem Hotkey
        # registriert. Die Lambdas haengen Strings an self.calls.
        self.vk_f1 = 0x70

    def _press(self, vk: int, mods: int) -> int:
        snap = dict(self.mgr._bindings)
        return self.mgr._handle_event(vk, is_down=True, is_up=False,
                                       mods=mods, bindings_snapshot=snap)

    def _release(self, vk: int, mods: int) -> int:
        snap = dict(self.mgr._bindings)
        return self.mgr._handle_event(vk, is_down=False, is_up=True,
                                       mods=mods, bindings_snapshot=snap)

    def test_macro_release_first_modifier_triggers_on_release(self) -> None:
        """Beim KeyUp sind alle Modifier schon weg (mods=0). on_release
        muss trotzdem feuern und _down muss sauber sein."""
        self.mgr.bind("^#F1",
                      on_press=lambda: self.calls.append("press"),
                      on_release=lambda: self.calls.append("release"))
        # Press mit echten Modifiern
        rv_down = self._press(self.vk_f1, kh.MOD_CTRL | kh.MOD_WIN)
        # Up mit mods=0 (Makro hat Modifier zuerst released)
        rv_up = self._release(self.vk_f1, 0)
        self.assertEqual(rv_down, kh.HotkeyManager._SUPPRESS)
        self.assertEqual(rv_up, kh.HotkeyManager._SUPPRESS)
        self.assertEqual(self.calls, ["press", "release"])
        self.assertEqual(self.mgr._down, {},
                         "vk darf nach Release nicht in _down haengen")

    def test_cross_talk_main_and_cycle_same_vk(self) -> None:
        """Main ^#F1 und Cycle ^+F1 teilen sich vk=F1. Nach Main-Press
        + sauberem Release muss Cycle anschliessend wieder triggern —
        also DARF _down nach Release nicht F1 enthalten."""
        self.mgr.bind("^#F1",
                      on_press=lambda: self.calls.append("main_press"),
                      on_release=lambda: self.calls.append("main_release"))
        self.mgr.bind("^+F1",
                      on_press=lambda: self.calls.append("cycle"))
        # Main-Sequenz (Makro-Pattern: Up mit mods=0)
        self._press(self.vk_f1, kh.MOD_CTRL | kh.MOD_WIN)
        self._release(self.vk_f1, 0)
        # Cycle-Druck danach — muss triggern
        self._press(self.vk_f1, kh.MOD_CTRL | kh.MOD_SHIFT)
        self.assertEqual(self.calls,
                         ["main_press", "main_release", "cycle"],
                         "Cycle muss nach Main-Release triggern, kein stuck-vk")

    def test_auto_repeat_blocks_second_press_until_release(self) -> None:
        """Solange ein Press nicht released wurde, blockt Auto-Repeat
        Folge-Presses derselben Bindung (Win32-Auto-Repeat-Verhalten)."""
        self.mgr.bind("^#F1",
                      on_press=lambda: self.calls.append("press"),
                      on_release=lambda: self.calls.append("release"))
        self._press(self.vk_f1, kh.MOD_CTRL | kh.MOD_WIN)
        # Zweiter Down ohne dazwischenliegenden Up → suppress, kein 2. press
        rv = self._press(self.vk_f1, kh.MOD_CTRL | kh.MOD_WIN)
        self.assertEqual(rv, kh.HotkeyManager._SUPPRESS)
        self.assertEqual(self.calls, ["press"])

    def test_release_without_prior_press_passes_through(self) -> None:
        """Ein KeyUp ohne tracked Press (z.B. nach pause/resume oder beim
        ersten Start mitten in einer gehaltenen Taste) wird durchgereicht,
        kein on_release feuert."""
        self.mgr.bind("^#F1",
                      on_press=lambda: self.calls.append("press"),
                      on_release=lambda: self.calls.append("release"))
        rv = self._release(self.vk_f1, 0)
        self.assertEqual(rv, kh.HotkeyManager._PASS)
        self.assertEqual(self.calls, [])

    def test_resume_clears_down_state(self) -> None:
        """resume() muss _down clearen, damit pausen-bedingte stuck-keys
        nicht den naechsten Press blockieren."""
        self.mgr.bind("^#F1",
                      on_press=lambda: self.calls.append("press"),
                      on_release=lambda: self.calls.append("release"))
        self._press(self.vk_f1, kh.MOD_CTRL | kh.MOD_WIN)
        self.assertIn(self.vk_f1, self.mgr._down)
        self.mgr.pause()
        self.mgr.resume()
        self.assertEqual(self.mgr._down, {},
                         "resume() muss _down clearen")
        # Folge-Press nach resume funktioniert wieder
        self._press(self.vk_f1, kh.MOD_CTRL | kh.MOD_WIN)
        self.assertEqual(self.calls, ["press", "press"])

    def test_unmatched_press_with_modifiers_passes_through(self) -> None:
        """Bindung ist ^#F1; Druck Ctrl+Shift+F1 (CS) trifft sie nicht und
        muss durchgereicht werden (kein Suppress, sonst frisst der Hook
        normale Tastenkombis)."""
        self.mgr.bind("^#F1",
                      on_press=lambda: self.calls.append("press"))
        rv = self._press(self.vk_f1, kh.MOD_CTRL | kh.MOD_SHIFT)
        self.assertEqual(rv, kh.HotkeyManager._PASS)
        self.assertEqual(self.calls, [])

    def test_no_release_callback_still_clears_down(self) -> None:
        """Tap-only Hotkey (Cycle) hat on_release=None. Trotzdem muss
        _down auf KeyUp aufgeraeumt werden, damit der naechste Tap geht."""
        self.mgr.bind("^+F1",
                      on_press=lambda: self.calls.append("cycle"))
        self._press(self.vk_f1, kh.MOD_CTRL | kh.MOD_SHIFT)
        self._release(self.vk_f1, 0)  # Makro: mods bereits weg
        self.assertEqual(self.mgr._down, {})
        # Zweiter Tap funktioniert
        self._press(self.vk_f1, kh.MOD_CTRL | kh.MOD_SHIFT)
        self.assertEqual(self.calls, ["cycle", "cycle"])


class TestHandleEventLockKey(unittest.TestCase):
    """CapsLock-Stuck-Fix: Lock-Tasten (CapsLock/NumLock/ScrollLock) modifier-
    los gebunden werden IMMER abgefangen — auch mit echtem oder (nach RDP-
    Reconnect) stalem Modifier. Sonst schlüpft z.B. Ctrl+CapsLock durch und
    toggelt den Lock-State, der sich danach nicht mehr ausschalten lässt.
    NUR Lock-Tasten — normale Tasten behalten den Modifier-Mismatch-Pass-Through.
    """

    def setUp(self) -> None:
        self.mgr = kh.HotkeyManager()
        self.calls: list[str] = []
        self.mgr._dispatch = lambda cb: cb()  # synchron, kein Worker-Thread
        self.vk_caps = kh.VK_CAPITAL  # 0x14
        self.vk_num = kh.VK_NUMLOCK   # 0x90
        self.vk_f9 = 0x78

    def _press(self, vk: int, mods: int) -> int:
        return self.mgr._handle_event(vk, True, False, mods,
                                      dict(self.mgr._bindings))

    def _release(self, vk: int, mods: int) -> int:
        return self.mgr._handle_event(vk, False, True, mods,
                                      dict(self.mgr._bindings))

    def test_capslock_with_stray_ctrl_is_suppressed_not_passed(self) -> None:
        self.mgr.bind("CapsLock",
                      on_press=lambda: self.calls.append("press"),
                      on_release=lambda: self.calls.append("release"))
        rv = self._press(self.vk_caps, kh.MOD_CTRL)  # Ctrl haengt (stray)
        self.assertEqual(rv, kh.HotkeyManager._SUPPRESS,
                         "CapsLock muss auch mit Modifier abgefangen werden")
        self.assertEqual(self.calls, ["press"])
        # Gemerkte Bindung ist die modifier-lose (0, vk) — wichtig fuer KeyUp.
        self.assertEqual(self.mgr._down.get(self.vk_caps), (0, self.vk_caps))

    def test_capslock_release_finds_binding_despite_modifier(self) -> None:
        self.mgr.bind("CapsLock",
                      on_press=lambda: self.calls.append("press"),
                      on_release=lambda: self.calls.append("release"))
        self._press(self.vk_caps, kh.MOD_CTRL)
        rv = self._release(self.vk_caps, kh.MOD_CTRL)  # Up noch mit Ctrl
        self.assertEqual(rv, kh.HotkeyManager._SUPPRESS)
        self.assertEqual(self.calls, ["press", "release"])
        self.assertEqual(self.mgr._down, {})

    def test_capslock_normal_press_still_works(self) -> None:
        self.mgr.bind("CapsLock", on_press=lambda: self.calls.append("press"))
        rv = self._press(self.vk_caps, 0)
        self.assertEqual(rv, kh.HotkeyManager._SUPPRESS)
        self.assertEqual(self.calls, ["press"])

    def test_unbound_capslock_passes_through(self) -> None:
        # CapsLock NICHT gebunden → normal durchreichen (kein Suppress).
        self.assertEqual(self._press(self.vk_caps, kh.MOD_CTRL),
                         kh.HotkeyManager._PASS)
        self.assertEqual(self._press(self.vk_caps, 0),
                         kh.HotkeyManager._PASS)

    def test_numlock_also_covered(self) -> None:
        self.mgr.bind("NumLock", on_press=lambda: self.calls.append("num"))
        rv = self._press(self.vk_num, kh.MOD_SHIFT)
        self.assertEqual(rv, kh.HotkeyManager._SUPPRESS)
        self.assertEqual(self.calls, ["num"])

    def test_non_lock_key_keeps_modifier_passthrough(self) -> None:
        # F9 modifier-los gebunden; Ctrl+F9 trifft NICHT → muss durchgereicht
        # werden. Der Lock-Sonderfall gilt ausschliesslich fuer Lock-Tasten.
        self.mgr.bind("F9", on_press=lambda: self.calls.append("f9"))
        rv = self._press(self.vk_f9, kh.MOD_CTRL)
        self.assertEqual(rv, kh.HotkeyManager._PASS)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
