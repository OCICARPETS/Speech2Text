"""Tests für den Clean-Dictation-Prompt (Session 19).

Der Modus soll AUSSCHLIESSLICH Füllwörter/Versprecher entfernen, nichts
paraphrasieren oder kürzen. Mit der alten Kurzfassung kürzte gpt-4o-mini den
Text um −15 bis −26 % (A/B-belegt). Der überarbeitete Prompt enthält explizite
Anti-Paraphrase-Anweisungen; dieser Test fixiert sie, damit eine spätere
Änderung den Modus nicht versehentlich wieder „aggressiv" macht.

Aufruf: `.venv/Scripts/python.exe -m unittest tests.test_config_clean_dictation -v`
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import config as cfg_mod  # noqa: E402


class TestCleanDictationPrompt(unittest.TestCase):
    def setUp(self):
        self.prompt = cfg_mod.get_mode_prompt("clean_dictation")

    def test_prompt_exists(self):
        self.assertIsNotNone(self.prompt)
        self.assertIsInstance(self.prompt, str)

    def test_prompt_is_anti_paraphrase(self):
        # Kernmarker des konservativen Prompts.
        for marker in ("Wort für Wort", "VERBOTEN", "umformulieren",
                       "zusammenfassen", "kürzen"):
            self.assertIn(marker, self.prompt,
                          f"Anti-Paraphrase-Marker fehlt: {marker!r}")

    def test_prompt_still_targets_fillers(self):
        self.assertIn("Füllwörter", self.prompt)

    def test_prompt_protects_numbers_and_names(self):
        # Zahlen + Eigennamen (Kundennamen) müssen explizit geschützt sein.
        self.assertIn("Zahl", self.prompt)
        self.assertIn("Eigenname", self.prompt)

    def test_prompt_output_only_no_preamble(self):
        self.assertIn("ohne", self.prompt)
        self.assertIn("Einleitung", self.prompt)


if __name__ == "__main__":
    unittest.main(verbosity=2)
