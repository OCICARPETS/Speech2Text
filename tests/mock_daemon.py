"""Mock-HTTP-Server, der recorder.py simuliert. Für E2E-Tests des Tray.

Aufruf: `.venv/Scripts/python.exe tests/mock_daemon.py [--port 17322]`
Endpoints:
  GET /health    — liefert frei-formatierten key=value-Body
  GET /hotkeys   — liefert frei-formatierten key=value-Body
  POST /start, /stop, /cycle, /pause-hotkeys, /resume-hotkeys, /reload-config,
       /shutdown — alle mit 200 OK
  POST /control/health — Mock-eigener Endpoint zum LIVE-Setzen des
       /health-Body (z.B. revision bumpen, state ändern)
  POST /control/hotkeys — analog für /hotkeys-Body

Gefakte Hotkeys: main=`+#F23` (Shift+Win+F23) — Kombination, die ein
echter Mensch nicht versehentlich drückt.
"""
from __future__ import annotations

import argparse
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_HEALTH_BODY = (
    "state=idle\n"
    "last_error=\n"
    "last_error_ts=0.000\n"
    "last_dictation_ts=0.000\n"
    "mode=polished_text\n"
    "active_mode=polished_text\n"
    "active_mode_ui_name=Polished Text\n"
    "cycle_loop_size=0\n"
    "hotkeys_revision=1\n"
    "hotkeys_paused=off\n"
    "prebuffer=on"
)

# Test-Hotkey: Shift+Win+F23 — unmöglich versehentlich gedrückt
_HOTKEYS_BODY = (
    "revision=1\n"
    "main=+#F23\n"
    "cycle=\n"
    "mode_count=0"
)


class _MockHandler(BaseHTTPRequestHandler):
    health_body = _HEALTH_BODY
    hotkeys_body = _HOTKEYS_BODY
    request_log: list[str] = []

    def log_message(self, format, *args):  # noqa: A002
        return  # Console-Spam unterdrücken

    def _ok(self, body: str):
        data = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):  # noqa: N802
        _MockHandler.request_log.append(f"GET {self.path}")
        if self.path == "/health":
            self._ok(_MockHandler.health_body)
        elif self.path == "/hotkeys":
            self._ok(_MockHandler.hotkeys_body)
        else:
            self.send_error(404)

    def do_POST(self):  # noqa: N802
        cl = int(self.headers.get("Content-Length", "0") or "0")
        body = self.rfile.read(cl) if cl > 0 else b""
        _MockHandler.request_log.append(
            f"POST {self.path}|{body.decode('utf-8', 'ignore')}"
        )
        if self.path == "/cycle":
            self._ok("active_mode=warm_friendly\nui_name=Warm")
        elif self.path == "/control/health":
            _MockHandler.health_body = body.decode("utf-8", "replace")
            self._ok("control-ok")
        elif self.path == "/control/hotkeys":
            _MockHandler.hotkeys_body = body.decode("utf-8", "replace")
            self._ok("control-ok")
        elif self.path in ("/start", "/stop", "/pause-hotkeys",
                           "/resume-hotkeys", "/reload-config", "/shutdown"):
            self._ok("ok")
        else:
            self.send_error(404)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=17322)
    args = p.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), _MockHandler)
    print(f"Mock-Daemon laeuft auf http://127.0.0.1:{args.port}", flush=True)
    print(f"  Stop: Strg+C oder /shutdown", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
