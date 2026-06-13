"""Tests für die Single-Instance-Absicherung des Daemons.

Seit Multi-User (Ansatz B) bindet der Daemon Port 0 (OS wählt einen freien Port,
Adressierung über handshake.write_port) — der Bind ist dann KEIN Single-Instance-
Schloss mehr. Der Schutz läuft über einen Session-lokalen Named Mutex (`Local\\…`):
atomar genau ein Daemon je Windows-Session, vom OS bei Prozess-Ende freigegeben
(auch bei os._exit → kein Stale-Lock). Das ersetzt den alten allow_reuse_address=
False-Schutz (Session 19), der nur bei festem Port wirkte.

Aufruf: .venv/Scripts/python.exe -m unittest tests.test_recorder_single_instance -v
"""
from __future__ import annotations

import sys
import unittest
from http.server import BaseHTTPRequestHandler
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import recorder  # noqa: E402

# Eigener Mutex-Name für die Tests — kollidiert NICHT mit dem produktiven Daemon.
_TEST_MUTEX = "Local\\Speech2Text-Daemon-UNITTEST"


class TestSingleInstanceMutex(unittest.TestCase):
    def test_acquire_returns_handle(self):
        h = recorder._acquire_single_instance_lock(_TEST_MUTEX)
        self.assertIsNotNone(h)
        recorder._release_single_instance_lock(h)

    def test_second_acquire_fails_while_first_held(self):
        """Zweiter Daemon-Lock in derselben Session muss abgewiesen werden."""
        h1 = recorder._acquire_single_instance_lock(_TEST_MUTEX)
        self.assertIsNotNone(h1)
        try:
            h2 = recorder._acquire_single_instance_lock(_TEST_MUTEX)
            self.assertIsNone(h2)
        finally:
            recorder._release_single_instance_lock(h1)

    def test_reacquirable_after_release(self):
        """Nach Freigabe (Daemon beendet) ist der Lock wieder erwerbbar."""
        h1 = recorder._acquire_single_instance_lock(_TEST_MUTEX)
        recorder._release_single_instance_lock(h1)
        h2 = recorder._acquire_single_instance_lock(_TEST_MUTEX)
        self.assertIsNotNone(h2)
        recorder._release_single_instance_lock(h2)

    def test_release_none_is_safe(self):
        recorder._release_single_instance_lock(None)  # darf nicht werfen


class TestPortZeroBind(unittest.TestCase):
    def test_bind_port_zero_yields_free_port(self):
        """Bind auf Port 0 → OS vergibt einen freien Port (> 0)."""
        s = recorder._SingleInstanceHTTPServer((recorder.HOST, 0),
                                               BaseHTTPRequestHandler)
        try:
            self.assertGreater(s.server_address[1], 0)
        finally:
            s.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
