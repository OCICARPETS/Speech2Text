"""Smoke-Tests für tray_app — Spec-Display + Pfad-Resolver + Stale-Port-Cleanup.

Vollständiger pystray-Run benötigt Tastatur+UI und ist nicht headless
testbar; das wird per Live-Test validiert.

Aufruf: `.venv/Scripts/python.exe -m unittest tests.test_tray_app -v`
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import tray_app as ta  # noqa: E402
import handshake  # noqa: E402


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
        p = ta._icon_path()
        self.assertIsNotNone(p)
        self.assertTrue(p.exists())
        self.assertEqual(p.name, "speech2text.ico")


class TestStalePortFileCleanup(unittest.TestCase):
    """Verwaiste daemon.port (PID tot = harter Crash) muss vor dem Daemon-Restart
    aufgeräumt werden, sonst pollt der Tray gegen den alten Port."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self._tmp.name

    def tearDown(self):
        if self._orig_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._orig_appdata
        self._tmp.cleanup()

    def test_keeps_port_file_when_pid_alive(self):
        handshake.write_port(50000, os.getpid())  # lebender PID
        self.assertFalse(ta._maybe_clear_stale_port_file())
        self.assertIsNotNone(handshake.read_port())

    def test_clears_port_file_when_pid_dead(self):
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        handshake.write_port(50000, p.pid)  # beendeter PID = stale
        self.assertTrue(ta._maybe_clear_stale_port_file())
        self.assertIsNone(handshake.read_port())

    def test_no_file_is_noop(self):
        self.assertFalse(ta._maybe_clear_stale_port_file())


if __name__ == "__main__":
    unittest.main(verbosity=2)
