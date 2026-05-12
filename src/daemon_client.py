"""Localhost-HTTP-Client zum Speech2Text-Daemon (recorder.py).

Ersetzt die WinHttp-COM-Calls aus dem AHK-Skript. Liefert sauber typisierte
Antworten und schluckt Netzwerk-Fehler (Daemon nicht erreichbar = häufiger
Normalfall, kein Crash-Grund). Daemon-Endpoints siehe `recorder.py.Handler`.

Body-Format der GET-Endpoints `/health` und `/hotkeys` ist `key=value` pro
Zeile — wir parsen das in dicts, weil AHK keinen JSON-Parser hatte und das
Format aus Kompatibilität bestehen bleibt.
"""
from __future__ import annotations

import json
import os
import time
from urllib import error as urlerr
from urllib import request as urlreq

# Default-URL — entspricht recorder.py PORT 17321 auf localhost.
DEFAULT_DAEMON_URL = "http://127.0.0.1:17321"

# Aktive URL — normalerweise = DEFAULT_DAEMON_URL. Override via ENV-Var
# S2T_DAEMON_URL für Test-Setups, um neben einer laufenden Produktiv-Instanz
# testen zu können. tray_app erkennt eine Custom-URL und unterdrückt den
# Auto-Daemon-Start in dem Fall.
DAEMON_URL = os.environ.get("S2T_DAEMON_URL", DEFAULT_DAEMON_URL)
DEFAULT_TIMEOUT_S = 0.5  # Health-Polls sollen schnell scheitern, wenn Daemon weg ist


def is_custom_url() -> bool:
    """True, wenn die aktive Daemon-URL per ENV-Var von der Default-URL
    abweicht. Verwendung: Auto-Daemon-Start nur bei Default-URL erlauben."""
    return DAEMON_URL != DEFAULT_DAEMON_URL


def _request(method: str, path: str,
             body: bytes | None = None,
             content_type: str | None = None,
             timeout: float = DEFAULT_TIMEOUT_S) -> tuple[int, str] | None:
    """Generischer HTTP-Call. Rückgabe (status, body_text) oder None bei
    Netzwerk-Fehler. Body als bytes; bei JSON-Bodies vom Aufrufer
    encodet + content_type='application/json; charset=utf-8'.
    """
    url = f"{DAEMON_URL}{path}"
    req = urlreq.Request(url, data=body, method=method)
    if content_type:
        req.add_header("Content-Type", content_type)
    try:
        with urlreq.urlopen(req, timeout=timeout) as r:
            text = r.read().decode("utf-8", errors="replace")
            return (r.status, text)
    except (urlerr.URLError, OSError, TimeoutError):
        return None


def _parse_key_value(text: str) -> dict[str, str]:
    """`/health`- und `/hotkeys`-Body parsen. Letzter Wert gewinnt bei
    Schlüssel-Duplikaten."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        eq = line.find("=")
        if eq <= 0:
            continue
        out[line[:eq].strip()] = line[eq + 1:].strip()
    return out


# --- Public API -------------------------------------------------------------

def health() -> dict[str, str] | None:
    """`GET /health`. None wenn Daemon nicht erreichbar oder kaputt antwortet."""
    r = _request("GET", "/health")
    if r is None or r[0] != 200:
        return None
    return _parse_key_value(r[1])


def hotkeys() -> dict | None:
    """`GET /hotkeys`. Rückgabe dict mit:
       revision: int
       main: str (oder leerer String)
       cycle: str (oder leerer String)
       modes: list[{"mode_id": str, "hotkey": str, "ui_name": str}]
    None bei Netzwerk-Fehler.
    """
    r = _request("GET", "/hotkeys")
    if r is None or r[0] != 200:
        return None
    kv = _parse_key_value(r[1])
    try:
        revision = int(kv.get("revision", "0") or "0")
        mode_count = int(kv.get("mode_count", "0") or "0")
    except ValueError:
        return None
    modes: list[dict[str, str]] = []
    for i in range(mode_count):
        mid = kv.get(f"mode.{i}.id", "")
        spec = kv.get(f"mode.{i}.spec", "")
        ui = kv.get(f"mode.{i}.ui_name", "")
        if mid and spec:
            modes.append({"mode_id": mid, "hotkey": spec, "ui_name": ui})
    return {
        "revision": revision,
        "main": kv.get("main", "") or "",
        "cycle": kv.get("cycle", "") or "",
        "modes": modes,
    }


def post(path: str, *, timeout: float = DEFAULT_TIMEOUT_S) -> bool:
    """POST ohne Body. True bei 2xx."""
    r = _request("POST", path, timeout=timeout)
    return r is not None and 200 <= r[0] < 300


def start_mode(mode_id: str | None) -> bool:
    """POST /start mit optionalem JSON-Body `{"mode": mode_id}`. mode_id=None
    bedeutet "aktiver Modus" (kein Body)."""
    if mode_id is None:
        return post("/start", timeout=1.0)
    body = json.dumps({"mode": mode_id}).encode("utf-8")
    r = _request("POST", "/start", body=body,
                 content_type="application/json; charset=utf-8", timeout=1.0)
    return r is not None and 200 <= r[0] < 300


def stop() -> bool:
    return post("/stop", timeout=1.0)


def cycle() -> tuple[str, str] | None:
    """POST /cycle. Rückgabe (mode_id, ui_name) oder None (z.B. cycle_loop leer)."""
    r = _request("POST", "/cycle", timeout=1.0)
    if r is None or r[0] != 200:
        return None
    kv = _parse_key_value(r[1])
    mid = kv.get("active_mode", "")
    ui = kv.get("ui_name", "")
    if not mid:
        return None
    return (mid, ui)


def pause_hotkeys() -> bool:
    return post("/pause-hotkeys")


def resume_hotkeys() -> bool:
    return post("/resume-hotkeys")


def reload_config() -> bool:
    return post("/reload-config", timeout=3.0)


def shutdown() -> bool:
    return post("/shutdown", timeout=2.0)


def wait_alive(timeout_s: float = 5.0, poll_interval_s: float = 0.2) -> bool:
    """Pollt /health bis Daemon antwortet oder Timeout. True wenn alive."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if health() is not None:
            return True
        time.sleep(poll_interval_s)
    return False
