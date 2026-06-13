"""Tests für handshake.py — Port-Handshake-Datei pro Windows-User (Ansatz B, Multi-User).

Der Daemon bindet einen freien Port (0) und hinterlegt ihn in einer per-User-
Datei %APPDATA%/Speech2Text/daemon.port; der Tray liest ihn dort. Dadurch findet
jede gleichzeitig angemeldete RDP-Session automatisch nur ihren eigenen Daemon.

Aufruf: .venv/Scripts/python.exe -m unittest tests.test_handshake -v
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

import handshake  # noqa: E402


class _TmpAppData(unittest.TestCase):
    """Basis: lenkt %APPDATA% auf ein temporäres Verzeichnis um, damit Tests
    NICHT die produktive daemon.port des laufenden Daemons anfassen."""

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


class TestPortFile(_TmpAppData):
    def test_port_file_path_under_config_dir(self):
        p = handshake.port_file_path()
        self.assertEqual(p.name, "daemon.port")
        self.assertEqual(p.parent.name, "Speech2Text")

    def test_write_then_read_roundtrip(self):
        handshake.write_port(54321, 4242)
        self.assertEqual(handshake.read_port(), (54321, 4242))

    def test_read_returns_none_when_missing(self):
        self.assertIsNone(handshake.read_port())

    def test_write_creates_dir_if_missing(self):
        self.assertFalse(handshake.port_file_path().parent.exists())
        handshake.write_port(17777, 1)
        self.assertTrue(handshake.port_file_path().exists())

    def test_write_is_atomic_no_tmp_leftover(self):
        handshake.write_port(17777, 1)
        leftovers = list(handshake.port_file_path().parent.glob("*.tmp"))
        self.assertEqual(leftovers, [])

    def test_write_overwrites_previous(self):
        handshake.write_port(11111, 1)
        handshake.write_port(22222, 2)
        self.assertEqual(handshake.read_port(), (22222, 2))

    def test_clear_removes_file(self):
        handshake.write_port(17777, 1)
        handshake.clear_port_file()
        self.assertIsNone(handshake.read_port())

    def test_clear_is_idempotent_when_missing(self):
        handshake.clear_port_file()  # darf nicht werfen

    def test_read_returns_none_on_corrupt_file(self):
        p = handshake.port_file_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("garbage-not-key-value", encoding="utf-8")
        self.assertIsNone(handshake.read_port())


class TestResolveDaemonUrl(_TmpAppData):
    def test_url_from_port_file(self):
        handshake.write_port(50505, 99)
        self.assertEqual(handshake.resolve_daemon_url(), "http://127.0.0.1:50505")

    def test_fallback_to_default_port_when_no_file(self):
        self.assertEqual(handshake.resolve_daemon_url(17321),
                         "http://127.0.0.1:17321")


class TestPidAlive(unittest.TestCase):
    def test_own_pid_is_alive(self):
        self.assertTrue(handshake.is_pid_alive(os.getpid()))

    def test_exited_process_is_not_alive(self):
        # Popen hält ein Handle offen → die PID wird NICHT recycelt, der Kernel
        # behält das (beendete) Prozess-Objekt. is_pid_alive muss trotzdem False
        # liefern (WaitForSingleObject signalisiert „beendet"), nicht bloß auf
        # OpenProcess-Erfolg vertrauen. Das deckt die PID-Reuse-/Stale-Falle ab.
        p = subprocess.Popen([sys.executable, "-c", "pass"])
        p.wait()
        self.assertFalse(handshake.is_pid_alive(p.pid))


if __name__ == "__main__":
    unittest.main(verbosity=2)
