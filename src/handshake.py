"""Port-Handshake-Datei pro Windows-User — Multi-Session-Adressierung (Ansatz B).

Der Daemon bindet einen freien Port (bind auf Port 0, OS wählt) und schreibt den
tatsächlich vergebenen Port in eine per-User-Datei %APPDATA%/Speech2Text/daemon.port.
Der Tray/Client liest den Port dort. Weil %APPDATA% pro Windows-User getrennt ist,
findet jede gleichzeitig angemeldete RDP-Session automatisch nur ihren eigenen
Daemon — kein maschinenweiter Fix-Port 17321, kein Cross-Session-Leak.

Single Source of Truth für den Ablageort ist config.config_dir() (dasselbe
%APPDATA%/Speech2Text wie config.json + daemon.log). stdlib-only.
"""
from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from pathlib import Path

import config as cfg_mod

PORT_FILENAME = "daemon.port"

# Default-/Fallback-Port (Abwärtskompatibilität zu v1.4.2 während des Rollouts).
DEFAULT_PORT = 17321


def port_file_path() -> Path:
    return cfg_mod.config_dir() / PORT_FILENAME


def write_port(port: int, pid: int) -> None:
    """Schreibt Port + PID atomar in die per-User-Handshake-Datei.

    Format identisch zu /health (key=value pro Zeile). Atomar via tmp + os.replace,
    damit ein gleichzeitig lesender Client nie eine halb geschriebene Datei sieht.
    """
    path = port_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(f"port={port}\npid={pid}\n", encoding="utf-8")
    os.replace(tmp, path)  # atomar auf demselben Volume (NTFS)


def read_port() -> tuple[int, int] | None:
    """Liest (port, pid) aus der Handshake-Datei. None, wenn fehlt oder kaputt."""
    try:
        text = port_file_path().read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, val = line.partition("=")
            values[key.strip()] = val.strip()
    try:
        return int(values["port"]), int(values["pid"])
    except (KeyError, ValueError):
        return None


def clear_port_file() -> None:
    """Entfernt die Handshake-Datei (idempotent — kein Fehler, wenn sie fehlt)."""
    try:
        port_file_path().unlink()
    except (FileNotFoundError, OSError):
        pass


def resolve_daemon_url(default_port: int = DEFAULT_PORT) -> str:
    """Daemon-URL aus der Handshake-Datei; Fallback auf default_port, wenn keine
    Datei da ist (Abwärtskompatibilität / Start-Race während des Daemon-Hochlaufs)."""
    entry = read_port()
    port = entry[0] if entry else default_port
    return f"http://127.0.0.1:{port}"


# --- Prozess-Liveness (Stale-Erkennung) -------------------------------------

_kernel32 = ctypes.windll.kernel32
# restype/argtypes EXPLIZIT — sonst schneidet ctypes das 64-bit-Handle auf int32
# ab (klassische Falle → CloseHandle scheitert / Heap-Korruption).
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.WaitForSingleObject.restype = wintypes.DWORD
_kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_SYNCHRONIZE = 0x00100000
_WAIT_OBJECT_0 = 0x00000000


def is_pid_alive(pid: int) -> bool:
    """True, wenn ein Prozess mit dieser PID läuft (nicht nur existiert).

    Wichtig gegen die Stale-/PID-Reuse-Falle: Ein beendeter, aber noch nicht
    „gereapter" Prozess (offenes Handle anderswo) existiert als Objekt weiter —
    OpenProcess gelingt dann, obwohl der Prozess tot ist. Deshalb zusätzlich
    WaitForSingleObject(0): ist das Prozess-Objekt signalisiert → beendet → tot.
    """
    if pid <= 0:
        return False
    handle = _kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION | _SYNCHRONIZE, False, pid)
    if not handle:
        # Kein Handle: PID existiert nicht (oder kein Zugriff). Als tot behandeln —
        # ein verwaister Daemon-Eintrag soll den Neustart nicht blockieren.
        return False
    try:
        # 0-ms-Timeout: signalisiert (WAIT_OBJECT_0) = beendet; sonst läuft noch.
        return _kernel32.WaitForSingleObject(handle, 0) != _WAIT_OBJECT_0
    finally:
        _kernel32.CloseHandle(handle)
