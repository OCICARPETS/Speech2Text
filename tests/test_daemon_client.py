"""Tests für daemon_client gegen einen Mock-HTTP-Server.

Seit Multi-User (Ansatz B) hat daemon_client KEINE feste DAEMON_URL-Konstante
mehr: die Daemon-URL wird pro Request aufgelöst (daemon_url()) — ENV-Override
S2T_DAEMON_URL zuerst, sonst aus der per-User-Handshake-Datei. Die Tests lenken
den Client deshalb über den ENV-Override auf den Mock-Port.

Aufruf: .venv/Scripts/python.exe -m unittest tests.test_daemon_client -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import daemon_client as dc  # noqa: E402
import handshake  # noqa: E402


# --- Mock-Server -----------------------------------------------------------

class _MockHandler(BaseHTTPRequestHandler):
    # Klassen-State, damit Test-Setup pro Test reagieren kann
    health_body: str = "state=idle\nlast_error=\nlast_error_ts=0.000\nmode=polished_text\nactive_mode=polished_text\nactive_mode_ui_name=Polished Text\ncycle_loop_size=0\nhotkeys_revision=0\nhotkeys_paused=off\nprebuffer=on"
    hotkeys_body: str = "revision=0\nmain=CapsLock\ncycle=\nmode_count=0"
    cycle_body: str = "active_mode=polished_text\nui_name=Polished Text"
    post_log: list[str] = []
    fail_with_500: bool = False

    def log_message(self, format, *args):  # noqa: A002
        return

    def _ok(self, body: str):
        if _MockHandler.fail_with_500:
            self.send_error(500, "mock failure")
            return
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self._ok(_MockHandler.health_body)
        elif self.path == "/hotkeys":
            self._ok(_MockHandler.hotkeys_body)
        else:
            self.send_error(404)

    def do_POST(self):  # noqa: N802
        cl = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(cl) if cl > 0 else b""
        _MockHandler.post_log.append(f"{self.path}|{body.decode('utf-8', 'ignore')}")
        if self.path == "/cycle":
            self._ok(_MockHandler.cycle_body)
        elif self.path in ("/start", "/stop", "/pause-hotkeys",
                           "/resume-hotkeys", "/reload-config", "/shutdown"):
            self._ok("ok")
        else:
            self.send_error(404)


class MockDaemon:
    """Startet/stoppt einen Mock-HTTP-Server und lenkt den Client per
    S2T_DAEMON_URL-Override darauf."""

    def __init__(self, port: int = 17321):
        self.port = port
        self.server: HTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self):
        os.environ["S2T_DAEMON_URL"] = f"http://127.0.0.1:{self.port}"
        _MockHandler.post_log.clear()
        _MockHandler.fail_with_500 = False
        self.server = HTTPServer(("127.0.0.1", self.port), _MockHandler)
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       daemon=True)
        self.thread.start()
        time.sleep(0.05)  # Warm-up — Server-Socket muss listen() drauf sein
        return self

    def __exit__(self, *exc):
        os.environ.pop("S2T_DAEMON_URL", None)
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=1.0)


# --- Tests -----------------------------------------------------------------

class TestDaemonClient(unittest.TestCase):
    # Mock auf Port 17322 — Konflikt-frei zur produktiv laufenden Instanz
    PORT = 17322

    def setUp(self):
        _MockHandler.health_body = "state=idle\nlast_error=\nlast_error_ts=0.000\nmode=polished_text\nactive_mode=polished_text\nactive_mode_ui_name=Polished Text\ncycle_loop_size=0\nhotkeys_revision=0\nhotkeys_paused=off\nprebuffer=on"
        _MockHandler.hotkeys_body = "revision=5\nmain=CapsLock\ncycle=F10\nmode_count=2\nmode.0.id=executive\nmode.0.spec=F11\nmode.0.ui_name=Executive\nmode.1.id=warm_friendly\nmode.1.spec=F12\nmode.1.ui_name=Warm"

    def tearDown(self):
        os.environ.pop("S2T_DAEMON_URL", None)

    def test_health_returns_dict(self):
        with MockDaemon(self.PORT):
            h = dc.health()
            self.assertIsNotNone(h)
            self.assertEqual(h["state"], "idle")
            self.assertEqual(h["active_mode"], "polished_text")
            self.assertEqual(h["prebuffer"], "on")

    def test_health_none_when_unreachable(self):
        os.environ["S2T_DAEMON_URL"] = "http://127.0.0.1:1"  # nichts dahinter
        self.assertIsNone(dc.health())

    def test_hotkeys_parsed(self):
        with MockDaemon(self.PORT):
            hk = dc.hotkeys()
            self.assertIsNotNone(hk)
            self.assertEqual(hk["revision"], 5)
            self.assertEqual(hk["main"], "CapsLock")
            self.assertEqual(hk["cycle"], "F10")
            self.assertEqual(len(hk["modes"]), 2)
            self.assertEqual(hk["modes"][0],
                             {"mode_id": "executive", "hotkey": "F11",
                              "ui_name": "Executive"})

    def test_start_mode_includes_json_body(self):
        with MockDaemon(self.PORT):
            self.assertTrue(dc.start_mode("executive"))
            last = _MockHandler.post_log[-1]
            self.assertTrue(last.startswith("/start|"))
            self.assertIn('"mode": "executive"', last)

    def test_start_no_mode_sends_empty_body(self):
        with MockDaemon(self.PORT):
            self.assertTrue(dc.start_mode(None))
            last = _MockHandler.post_log[-1]
            self.assertTrue(last.startswith("/start|"))
            self.assertEqual(last.split("|", 1)[1], "")

    def test_stop_pause_resume(self):
        with MockDaemon(self.PORT):
            self.assertTrue(dc.stop())
            self.assertTrue(dc.pause_hotkeys())
            self.assertTrue(dc.resume_hotkeys())
            paths = [p.split("|", 1)[0] for p in _MockHandler.post_log]
            self.assertIn("/stop", paths)
            self.assertIn("/pause-hotkeys", paths)
            self.assertIn("/resume-hotkeys", paths)

    def test_cycle_returns_tuple(self):
        with MockDaemon(self.PORT):
            _MockHandler.cycle_body = "active_mode=executive\nui_name=Executive"
            r = dc.cycle()
            self.assertEqual(r, ("executive", "Executive"))

    def test_health_returns_none_on_500(self):
        with MockDaemon(self.PORT):
            _MockHandler.fail_with_500 = True
            self.assertIsNone(dc.health())

    def test_wait_alive_returns_true_when_up(self):
        with MockDaemon(self.PORT):
            self.assertTrue(dc.wait_alive(timeout_s=1.0))

    def test_wait_alive_returns_false_on_timeout(self):
        os.environ["S2T_DAEMON_URL"] = "http://127.0.0.1:1"
        self.assertFalse(dc.wait_alive(timeout_s=0.3, poll_interval_s=0.1))


class TestDaemonUrlResolution(unittest.TestCase):
    """Auflösung der Daemon-URL: ENV-Override vor Handshake-Datei."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_appdata = os.environ.get("APPDATA")
        os.environ["APPDATA"] = self._tmp.name
        os.environ.pop("S2T_DAEMON_URL", None)

    def tearDown(self):
        os.environ.pop("S2T_DAEMON_URL", None)
        if self._orig_appdata is None:
            os.environ.pop("APPDATA", None)
        else:
            os.environ["APPDATA"] = self._orig_appdata
        self._tmp.cleanup()

    def test_env_override_takes_precedence(self):
        os.environ["S2T_DAEMON_URL"] = "http://127.0.0.1:9999"
        self.assertEqual(dc.daemon_url(), "http://127.0.0.1:9999")
        self.assertTrue(dc.is_custom_url())

    def test_url_from_handshake_file_when_no_override(self):
        handshake.write_port(40404, 7)
        self.assertEqual(dc.daemon_url(), "http://127.0.0.1:40404")
        self.assertFalse(dc.is_custom_url())

    def test_is_custom_url_false_without_override(self):
        self.assertFalse(dc.is_custom_url())


if __name__ == "__main__":
    unittest.main(verbosity=2)
