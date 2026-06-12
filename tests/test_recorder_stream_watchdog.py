"""Tests für den Audio-Stream-Watchdog (RDP-Reconnect-Fix).

Prüft die reine Reopen-Entscheidung `_should_reopen_stream()` ohne echtes
PortAudio/sounddevice-Gerät. Der eigentliche Reopen + Watchdog-Thread wird
per Live-Test (RDP-Disconnect/Reconnect auf dem Terminal-Server) validiert.

Aufruf: `.venv/Scripts/python.exe -m unittest tests.test_recorder_stream_watchdog -v`
"""
from __future__ import annotations

import contextlib
import io
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest import mock


@contextlib.contextmanager
def _silence():
    """stdout/stderr in einen Buffer umleiten — der Test-Runner-stdout ist hier
    cp1252, die Emoji-`print`s im Daemon (▶/⚠/🔁) würden sonst crashen. Im
    echten Daemon stellt main() stdout auf UTF-8 (errors=replace)."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        yield

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


def _bare_recorder():
    """Recorder-Instanz OHNE __init__ — kein Audio-Gerät, kein OpenAI-Client.
    Setzt nur die Attribute, die die getesteten Methoden anfassen."""
    rec = recorder.Recorder.__new__(recorder.Recorder)
    rec._lock = threading.Lock()
    rec.state = recorder.State.IDLE
    rec.config = {"prebuffer_enabled": True}
    rec._stream = None
    rec._stream_always_on = True
    rec._last_audio_ts = 0.0
    rec._stream_recovering = False
    rec._current_device = None
    rec._chunks = []
    rec._chunks_total_samples = 0
    rec._session_mode = None
    return rec


class TestReinitPortAudio(unittest.TestCase):
    """Fix(1)/(2): PortAudio muss neu initialisiert werden (Geräteliste wird
    beim Pa_Initialize gecached) — sonst bleibt Default-Input dauerhaft -1,
    wenn der Daemon ohne Aufnahmegerät startete (Autostart nach Reboot)."""

    def test_terminates_then_initializes(self):
        rec = _bare_recorder()
        with mock.patch.object(recorder, "sd") as msd:
            rec._reinit_portaudio(verbose=False)
        names = [c[0] for c in msd.mock_calls]
        self.assertEqual(names, ["_terminate", "_initialize"])

    def test_swallows_errors(self):
        # Reinit-Fehler darf die Recovery NICHT abbrechen.
        rec = _bare_recorder()
        with mock.patch.object(recorder, "sd") as msd:
            msd._terminate.side_effect = RuntimeError("PortAudio not initialized")
            rec._reinit_portaudio(verbose=False)  # darf nicht werfen


class TestWatchdogReinit(unittest.TestCase):
    def test_recovery_reinits_between_close_and_open(self):
        # Toter (staler) Dauerstream im IDLE → Recovery muss PortAudio NEU
        # initialisieren, nicht nur Stream close/open. Reihenfolge zählt.
        rec = _bare_recorder()
        rec._last_audio_ts = 0.0  # uralt → stale
        m = mock.Mock()
        rec._set_error = m.set_error
        rec._close_persistent_stream = m.close
        rec._reinit_portaudio = m.reinit
        rec._open_persistent_stream = m.open
        with _silence():
            rec._maybe_recover_stream()
        order = [c[0] for c in m.mock_calls if c[0] in ("close", "reinit", "open")]
        self.assertEqual(order, ["close", "reinit", "open"])
        m.reinit.assert_called_once()


class TestStartGuardImmediateRecovery(unittest.TestCase):
    """Fix(2): Druck auf totes Mikro → Sofort-Recovery statt nur abweisen."""

    def test_press_on_stale_stream_recovers_and_records(self):
        rec = _bare_recorder()
        rec._last_audio_ts = 0.0  # stale
        rec._set_error = mock.Mock()
        rec._close_persistent_stream = mock.Mock(
            side_effect=lambda *a, **k: setattr(rec, "_stream_always_on", False))
        rec._reinit_portaudio = mock.Mock()

        def _reopen_ok(*a, **k):
            rec._stream_always_on = True
            rec._last_audio_ts = time.time()
        rec._open_persistent_stream = mock.Mock(side_effect=_reopen_ok)

        with _silence():
            rec.start()
        rec._reinit_portaudio.assert_called_once()
        self.assertIs(rec.state, recorder.State.RECORDING)

    def test_press_on_stale_stream_aborts_when_reopen_fails(self):
        rec = _bare_recorder()
        rec._last_audio_ts = 0.0  # stale
        rec._set_error = mock.Mock()
        rec._close_persistent_stream = mock.Mock(
            side_effect=lambda *a, **k: setattr(rec, "_stream_always_on", False))
        rec._reinit_portaudio = mock.Mock()
        rec._open_persistent_stream = mock.Mock()  # lässt _stream_always_on=False

        with _silence():
            rec.start()
        rec._reinit_portaudio.assert_called_once()
        self.assertIs(rec.state, recorder.State.IDLE)
        rec._set_error.assert_called_once()


class TestOnDemandReinitRetry(unittest.TestCase):
    """Fix(2): On-Demand-Open (Prebuffer aus) bekommt bei Fehler einen
    PortAudio-Reinit + genau einen Retry."""

    def test_open_retries_after_reinit_on_failure(self):
        rec = _bare_recorder()
        rec._reinit_portaudio = mock.Mock()
        fake_stream = mock.Mock()
        with mock.patch.object(recorder, "sd") as msd:
            msd.InputStream.side_effect = [
                RuntimeError("Error querying device -1"), fake_stream]
            with _silence():
                ok = rec._open_ondemand_stream(None)
        self.assertTrue(ok)
        rec._reinit_portaudio.assert_called_once()
        fake_stream.start.assert_called_once()

    def test_open_fails_after_retry_sets_error(self):
        rec = _bare_recorder()
        rec._reinit_portaudio = mock.Mock()
        rec._set_error = mock.Mock()
        with mock.patch.object(recorder, "sd") as msd:
            msd.InputStream.side_effect = RuntimeError("Error querying device -1")
            with _silence():
                ok = rec._open_ondemand_stream(None)
        self.assertFalse(ok)
        rec._reinit_portaudio.assert_called_once()
        rec._set_error.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
