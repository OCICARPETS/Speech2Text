"""Tests für den Audio-Stream-Watchdog (RDP-Reconnect-Fix).

Prüft die reine Reopen-Entscheidung `_should_reopen_stream()` ohne echtes
PortAudio/sounddevice-Gerät. Der eigentliche Reopen + Watchdog-Thread wird
per Live-Test (RDP-Disconnect/Reconnect auf dem Terminal-Server) validiert.

Aufruf: `.venv/Scripts/python.exe -m unittest tests.test_recorder_stream_watchdog -v`
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import recorder  # noqa: E402

S = recorder.STREAM_STALE_S


class TestShouldReopenStream(unittest.TestCase):
    def test_not_idle_never_reopens(self):
        # Während Recording/Processing den Stream NICHT anfassen — auch wenn er
        # (scheinbar) stale ist. Reopen nur im IDLE-Zustand.
        self.assertFalse(recorder._should_reopen_stream(
            now=1000.0, last_audio_ts=0.0, stale_s=S,
            want_prebuffer=True, stream_always_on=True, state_is_idle=False))

    def test_prebuffer_off_never_reopens(self):
        # On-Demand-Modus (kein Dauerstream) → Watchdog ist nicht zuständig.
        self.assertFalse(recorder._should_reopen_stream(
            now=1000.0, last_audio_ts=0.0, stale_s=S,
            want_prebuffer=False, stream_always_on=False, state_is_idle=True))

    def test_wanted_but_not_open_reopens(self):
        # Prebuffer gewünscht, aber kein Stream offen (z.B. Open-Fail beim
        # Daemon-Start, Gerät war noch nicht da) → (re)open versuchen.
        self.assertTrue(recorder._should_reopen_stream(
            now=1000.0, last_audio_ts=1000.0, stale_s=S,
            want_prebuffer=True, stream_always_on=False, state_is_idle=True))

    def test_open_and_fresh_does_not_reopen(self):
        # Stream offen + frischer Callback (jünger als stale_s) → alles gut.
        self.assertFalse(recorder._should_reopen_stream(
            now=1000.0, last_audio_ts=1000.0 - (S / 2), stale_s=S,
            want_prebuffer=True, stream_always_on=True, state_is_idle=True))

    def test_open_but_stale_reopens(self):
        # Stream offen, aber seit > stale_s kein Callback mehr → tot → reopen.
        self.assertTrue(recorder._should_reopen_stream(
            now=1000.0, last_audio_ts=1000.0 - (S + 1.0), stale_s=S,
            want_prebuffer=True, stream_always_on=True, state_is_idle=True))

    def test_exactly_at_threshold_not_yet_stale(self):
        # Genau auf der Schwelle (== stale_s) gilt noch als frisch (strikt >).
        self.assertFalse(recorder._should_reopen_stream(
            now=1000.0, last_audio_ts=1000.0 - S, stale_s=S,
            want_prebuffer=True, stream_always_on=True, state_is_idle=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
