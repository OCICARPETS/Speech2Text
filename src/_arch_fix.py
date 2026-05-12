"""ARM64-Windows-Workaround fuer sounddevice / PortAudio.

sounddevice 0.5.x waehlt die zu ladende PortAudio-DLL anhand von
`platform.machine()`. Auf Windows 11 ARM64 meldet Python die System-
Architektur (ARM64), auch wenn der Prozess unter x64-Emulation laeuft.
sounddevice sucht dann `libportaudioarm64.dll` und scheitert im x64-
Prozess (Error 0xC1 / 0x7E je nach Wheel-Inhalt).

Loesung: VOR `import sounddevice` `platform.machine()` so patchen, dass
in einem x64-Prozess immer `AMD64` zurueckkommt. Dadurch laedt
sounddevice die ohnehin im Bundle/Wheel vorhandene x64-DLL.

Side-Effect-on-Import: erste Zeile (vor `import sounddevice`)
    import _arch_fix  # noqa: F401

Der Patch ist eng begrenzt:
  * nur Windows
  * nur wenn der Prozess als x64 laeuft (PROCESSOR_ARCHITECTURE=AMD64)
  * nur wenn das OS sich als ARM64 meldet

Native ARM64-Python-Builds bleiben unberuehrt.
"""
from __future__ import annotations

import os
import platform
import sys


def _apply() -> None:
    if sys.platform != "win32":
        return
    process_arch = os.environ.get("PROCESSOR_ARCHITECTURE", "").upper()
    if process_arch != "AMD64":
        return  # nativer ARM64- oder 32-bit-Prozess → kein Patch
    if platform.machine().upper() != "ARM64":
        return  # echtes x64-Windows → kein Patch
    original = platform.machine

    def _patched(*args, **kwargs):  # type: ignore[no-untyped-def]
        value = original(*args, **kwargs)
        if isinstance(value, str) and value.upper() == "ARM64":
            return "AMD64"
        return value

    platform.machine = _patched  # type: ignore[assignment]


_apply()
