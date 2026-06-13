"""Test der zentralen Versions-Konstante (Single Source of Truth).

src/version.py liefert die Programm-Version. settings.py zeigt sie im Fenster an,
build-distribution.py nutzt sie fuer den ZIP-Namen — beide importieren version.VERSION,
damit es nur EINE Stelle gibt, an der die Versionsnummer steht.

Aufruf: .venv/Scripts/python.exe -m unittest tests.test_version -v
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import version  # noqa: E402


class TestVersion(unittest.TestCase):
    def test_version_exists_and_format(self):
        self.assertTrue(hasattr(version, "VERSION"))
        self.assertRegex(version.VERSION, r"^\d+\.\d+\.\d+$")

    def test_build_distribution_has_no_hardcoded_version(self):
        """build-distribution.py muss version.VERSION nutzen, nicht hartkodieren."""
        bd = (ROOT / "scripts" / "build-distribution.py").read_text(encoding="utf-8")
        self.assertNotRegex(
            bd, r'VERSION\s*=\s*["\']\d',
            "build-distribution.py hat noch eine hartkodierte VERSION — "
            "stattdessen version.VERSION importieren (Single Source).")
        self.assertIn("version", bd, "build-distribution.py referenziert das version-Modul nicht")

    def test_settings_displays_version(self):
        """settings.py muss die Versionskonstante referenzieren (Anzeige im Fenster)."""
        st = (SRC / "settings.py").read_text(encoding="utf-8")
        self.assertIn("VERSION", st,
                      "settings.py zeigt die Version nicht an (VERSION nicht referenziert)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
