"""Smoke-Tests für tray_app — Spec-Display + Pfad-Resolver.

Vollständiger pystray-Run benötigt Tastatur+UI und ist nicht headless
testbar; das wird per Live-Test in Phase 10 validiert.

Aufruf: `.venv/Scripts/python.exe -m unittest tests.test_tray_app -v`
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import tray_app as ta  # noqa: E402


class TestSpecDisplay(unittest.TestCase):
    def test_capslock(self):
        self.assertEqual(ta._spec_to_display("CapsLock"), "Caps Lock")

    def test_f9(self):
        self.assertEqual(ta._spec_to_display("F9"), "F9")

    def test_ctrl_alt_r(self):
        self.assertEqual(ta._spec_to_display("^!r"), "Ctrl + Alt + R")

    def test_shift_win_f12(self):
        self.assertEqual(ta._spec_to_display("+#F12"), "Shift + Win + F12")

    def test_scrolllock(self):
        self.assertEqual(ta._spec_to_display("ScrollLock"), "Scroll Lock")

    def test_pause(self):
        self.assertEqual(ta._spec_to_display("Pause"), "Pause")

    def test_empty(self):
        self.assertEqual(ta._spec_to_display(""), "")


class TestPathResolvers(unittest.TestCase):
    def test_icon_path_found_in_dev_layout(self):
        # In Dev-Layout muss assets/speech2text.ico unter <projekt>/assets/ liegen
        p = ta._icon_path()
        self.assertIsNotNone(p)
        self.assertTrue(p.exists())
        self.assertEqual(p.name, "speech2text.ico")


if __name__ == "__main__":
    unittest.main(verbosity=2)
