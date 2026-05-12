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


if __name__ == "__main__":
    unittest.main(verbosity=2)
