"""Tests für die Single-Instance-Absicherung des Daemons (Session 19).

Hintergrund: `http.server.HTTPServer` setzt allow_reuse_address=1. Auf Windows
erlaubt SO_REUSEADDR ZWEI erfolgreiche Binds auf denselben Port → ein im
Startup-Race doppelt gespawnter Daemon stirbt nicht, sondern läuft weiter und
greift parallel das Mikrofon ab (WASAPI-Contention → Stream-Staleness →
Audio-Verlust). `_SingleInstanceHTTPServer` setzt allow_reuse_address=False,
sodass der zweite Bind sauber scheitert.

Aufruf: `.venv/Scripts/python.exe -m unittest tests.test_recorder_single_instance -v`
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


class TestSingleInstanceServer(unittest.TestCase):
    def test_allow_reuse_address_is_false(self):
        # Klassen-Attribut: ohne das erlaubt Windows den Doppel-Bind.
        self.assertFalse(recorder._SingleInstanceHTTPServer.allow_reuse_address)

    def test_second_bind_on_same_port_raises(self):
        """Zweiter Daemon auf demselben Port muss am Bind scheitern (OSError)."""
        s1 = recorder._SingleInstanceHTTPServer(
            (recorder.HOST, 0), BaseHTTPRequestHandler)
        port = s1.server_address[1]
        try:
            with self.assertRaises(OSError):
                s2 = recorder._SingleInstanceHTTPServer(
                    (recorder.HOST, port), BaseHTTPRequestHandler)
                s2.server_close()  # falls wider Erwarten doch gebunden
        finally:
            s1.server_close()

    def test_first_bind_succeeds_and_releases(self):
        """Erster Bind klappt; nach server_close ist der Port wieder frei."""
        s1 = recorder._SingleInstanceHTTPServer(
            (recorder.HOST, 0), BaseHTTPRequestHandler)
        port = s1.server_address[1]
        s1.server_close()
        # Jetzt muss derselbe Port erneut bindbar sein.
        s2 = recorder._SingleInstanceHTTPServer(
            (recorder.HOST, port), BaseHTTPRequestHandler)
        s2.server_close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
