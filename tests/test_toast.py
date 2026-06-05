"""Headless-Tests für den Custom-Toast (v1.4 Punkt 1).

Der eigentliche Tk-Mainloop braucht ein Display und wird per Live-Test
validiert. Hier wird die thread-sichere Grenze (show() = nur put_nowait), die
Coalesce-Logik und der Lazy-tkinter-Import geprüft — alles ohne echtes Tk.

Aufruf: `.venv/Scripts/python.exe -m unittest tests.test_toast -v`
"""
from __future__ import annotations

import queue
import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import toast  # noqa: E402


class TestCoalesce(unittest.TestCase):
    def test_empty(self):
        self.assertIsNone(toast._coalesce([]))

    def test_single(self):
        self.assertEqual(toast._coalesce([("A", 1500)]), ("A", 1500))

    def test_keeps_last(self):
        items = [("A", 1500), ("B", 1500), ("C", 1500)]
        self.assertEqual(toast._coalesce(items), ("C", 1500))


class TestShowMarshaling(unittest.TestCase):
    def test_show_without_start_is_noop(self):
        ctrl = toast.ToastController()
        # Darf nicht werfen und nichts einreihen, solange nicht gestartet.
        ctrl.show("Modus: X", 1500)
        with self.assertRaises(queue.Empty):
            ctrl._queue.get_nowait()

    def test_show_only_enqueues_no_tk(self):
        ctrl = toast.ToastController()
        ctrl._started = True  # Start simulieren ohne Tk-Thread
        ctrl.show("Modus: Clean Dictation", toast.TOAST_DURATION_MODE_MS)
        self.assertEqual(
            ctrl._queue.get_nowait(),
            ("Modus: Clean Dictation", toast.TOAST_DURATION_MODE_MS),
        )

    def test_stop_without_start_is_noop(self):
        toast.ToastController().stop()  # darf nicht werfen


class TestThemeColors(unittest.TestCase):
    def test_valid_theme(self):
        ctrl = toast.ToastController(get_theme=lambda: "light")
        self.assertEqual(ctrl._theme_colors(), toast._THEME_COLORS["light"])

    def test_invalid_theme_falls_back_to_dark(self):
        ctrl = toast.ToastController(get_theme=lambda: "neon")
        self.assertEqual(ctrl._theme_colors(), toast._THEME_COLORS["dark"])

    def test_get_theme_exception_falls_back(self):
        def boom():
            raise RuntimeError("config kaputt")
        ctrl = toast.ToastController(get_theme=boom)
        self.assertEqual(ctrl._theme_colors(), toast._THEME_COLORS["dark"])


class TestLazyTkinterImport(unittest.TestCase):
    def test_module_has_no_toplevel_tkinter_binding(self):
        # tkinter wird erst in _run_ui importiert (lokaler Name `tk`),
        # daher darf das Modul keinen tkinter-/tk-Modulattribut tragen.
        self.assertFalse(hasattr(toast, "tkinter"))
        self.assertFalse(hasattr(toast, "tk"))


class TestConstants(unittest.TestCase):
    def test_durations(self):
        self.assertEqual(toast.TOAST_DURATION_MODE_MS, 1500)
        self.assertGreater(toast.TOAST_DURATION_INFO_MS,
                           toast.TOAST_DURATION_MODE_MS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
