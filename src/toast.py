"""Speech2Text Custom-Toast (v1.4 Punkt 1) — Ersatz für pystray.Icon.notify().

Leichtgewichtiges Popup mit kurzer Standzeit und Coalesce, statt des trägen
Windows-System-Toasts (~5 s, keine Queue).

Architektur (Plan: plans/silly-hatching-stardust.md, Multi-Agent-Judge 8.5/10):
  - `pystray.Icon.run()` bleibt UNVERÄNDERT auf dem Main-Thread des Tray-Prozesses.
  - Ein dedizierter Daemon-Thread `ToastUI` erzeugt EINE versteckte `tk.Tk()`-Root
    und fährt `root.mainloop()`. ALLE Tk-Objekte gehören ausschließlich diesem
    Thread.
  - Von beliebigen Threads (z.B. dem `HkDispatch`-Worker in `_cycle_action`) ist
    nur `show()` aufrufbar — das macht ausschließlich `queue.Queue.put_nowait`,
    also keinen einzigen Tk-Zugriff (Cross-Thread-Tk wäre nicht thread-safe).
  - Der `ToastUI`-Thread pollt die Queue per `root.after`, coalesct auf den
    zuletzt eingereihten Eintrag und setzt EINEN Hide-Timer, der bei jedem neuen
    `show()` via `after_cancel` zurückgesetzt wird (Verlängern/Aktualisieren statt
    Stapeln).

`tkinter` wird LAZY erst in `_run_ui` importiert, damit der Modulkopf nichts
vorzeitig in den PyInstaller-Bundle zieht und die `_arch_fix`-Importreihenfolge
im Tray nicht stört.

Datenschutz: der Toast-Text wird NICHT geloggt (kein print des Texts).
"""
from __future__ import annotations

import queue
import threading
from typing import Callable

# --- Standzeiten (ms) — als Konstanten anpassbar ---------------------------
TOAST_DURATION_MODE_MS = 1500   # Mode-Switch: häufig, flüchtig
TOAST_DURATION_INFO_MS = 4000   # Fehler/System: länger, mehrzeilig

# --- Layout ----------------------------------------------------------------
TOAST_MARGIN_PX = 14            # Abstand zur Bildschirmkante
TASKBAR_RESERVE_PX = 48         # grobe Taskleisten-Höhe (v1, keine Win32-Workarea)
TOAST_POLL_MS = 50              # Queue-Drain-Intervall im ToastUI-Thread
TOAST_MAX_WIDTH_PX = 360        # wraplength für mehrzeilige Texte
_TOAST_FONT = ("Segoe UI", 11)

# Theme-Farben bewusst LOKAL gehalten (nicht aus settings_helpers importiert —
# das würde tkinter/sounddevice-Last in den Tray-Bundle ziehen). Werte an
# settings_helpers.GROUP_FG_BY_THEME angelehnt, identisch zum HTML-Mockup.
_THEME_COLORS = {
    "dark":  {"bg": "#2b2b2b", "fg": "#ffffff", "border": "#4a4a4a"},
    "light": {"bg": "#f4f4f4", "fg": "#1f1f1f", "border": "#cfcfcf"},
}
_FALLBACK_THEME = "dark"


def _coalesce(items):
    """Aus einer Liste gequeueter ``(text, duration)``-Einträge den anzuzeigenden
    wählen: den zuletzt eingereihten. Pure Funktion → ohne Tk testbar."""
    return items[-1] if items else None


class ToastController:
    """Verwaltet einen einzelnen, wiederverwendeten Toast in einem eigenen
    Tk-Mainloop-Thread. Thread-sicher von außen nur über ``start``/``show``/``stop``.
    """

    def __init__(self, get_theme: Callable[[], str] | None = None) -> None:
        self._get_theme = get_theme
        self._queue: queue.Queue = queue.Queue()
        self._ready = threading.Event()
        self._stop_evt = threading.Event()
        self._thread: threading.Thread | None = None
        self._started = False

        # Folgende Felder NUR im ToastUI-Thread berühren:
        self._root = None
        self._win = None
        self._label = None
        self._hide_after = None

    # -- Public (thread-safe) ------------------------------------------------

    def start(self) -> None:
        """Startet den ToastUI-Thread (idempotent)."""
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(
            target=self._run_ui, name="ToastUI", daemon=True,
        )
        self._thread.start()
        # Auf Tk-Init warten (Muster wie HotkeyManager.start()). Die Queue
        # puffert ohnehin, daher ist der Timeout unkritisch.
        self._ready.wait(timeout=2.0)

    def show(self, text: str, duration_ms: int = TOAST_DURATION_INFO_MS) -> None:
        """Toast anzeigen/aktualisieren. Thread-sicher: NUR ``put_nowait``,
        kein Tk-Zugriff, kein Logging des Texts."""
        if not self._started:
            return
        try:
            self._queue.put_nowait((text, int(duration_ms)))
        except queue.Full:  # Queue ist unbounded → praktisch nie
            pass

    def stop(self) -> None:
        """Beendet den ToastUI-Thread sauber (idempotent, von jedem Thread).

        WICHTIG: Macht KEINEN Tk-Aufruf vom aufrufenden Thread. Es wird nur ein
        Event gesetzt; der ToastUI-Thread bemerkt das in seinem nächsten
        ``_drain``-Tick und räumt Tk selbst ab. Sonst würde der Tcl-Interpreter
        am Prozessende vom falschen Thread freigegeben
        (``Tcl_AsyncDelete: async handler deleted by the wrong thread``)."""
        if not self._started:
            return
        self._stop_evt.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._started = False

    # -- Intern --------------------------------------------------------------

    def _theme_colors(self) -> dict:
        name = _FALLBACK_THEME
        if self._get_theme is not None:
            try:
                cand = self._get_theme()
                if cand in _THEME_COLORS:
                    name = cand
            except Exception:  # noqa: BLE001
                pass
        return _THEME_COLORS[name]

    # -- ToastUI-Thread only -------------------------------------------------

    def _run_ui(self) -> None:
        try:
            import tkinter as tk  # LAZY — nur in diesem Thread
        except Exception as exc:  # noqa: BLE001
            # Ohne Tk kein Toast — still scheitern, der Tray läuft weiter.
            print(f"[Toast] tkinter nicht verfügbar: "
                  f"{type(exc).__name__}: {exc}", flush=True)
            self._ready.set()
            return

        try:
            root = tk.Tk()
            root.withdraw()
            win = tk.Toplevel(root)
            win.withdraw()
            win.overrideredirect(True)
            for attr, val in (("-topmost", True), ("-alpha", 0.95),
                              ("-toolwindow", True)):
                try:
                    win.attributes(attr, val)
                except tk.TclError:
                    pass
            label = tk.Label(
                win, text="", font=_TOAST_FONT, justify="left",
                wraplength=TOAST_MAX_WIDTH_PX, padx=16, pady=10,
            )
            label.pack(padx=1, pady=1)  # 1px zeigt die Toplevel-bg = Rahmen
            self._root, self._win, self._label = root, win, label
        except Exception as exc:  # noqa: BLE001
            print(f"[Toast] Init-Fehler: {type(exc).__name__}: {exc}", flush=True)
            self._ready.set()
            return

        self._ready.set()
        root.after(TOAST_POLL_MS, self._drain)
        try:
            root.mainloop()
        except Exception as exc:  # noqa: BLE001
            print(f"[Toast] Mainloop-Fehler: {type(exc).__name__}: {exc}",
                  flush=True)
        finally:
            try:
                root.destroy()
            except Exception:  # noqa: BLE001
                pass
            # Alle Tk-Referenzen HIER (im ToastUI-Thread) freigeben, damit der
            # Tcl-Interpreter in genau diesem Thread dealloc't wird und nicht
            # erst beim Interpreter-Shutdown auf dem Main-Thread.
            self._root = self._win = self._label = None
            root = win = label = None  # noqa: F841

    def _drain(self) -> None:
        # Stop-Signal? Mainloop im EIGENEN Thread beenden (kein Re-Schedule).
        if self._stop_evt.is_set():
            self._teardown_ui()
            return
        items = []
        try:
            while True:
                items.append(self._queue.get_nowait())
        except queue.Empty:
            pass
        latest = _coalesce(items)
        if latest is not None:
            try:
                self._render(*latest)
            except Exception as exc:  # noqa: BLE001
                print(f"[Toast] Render-Fehler: {type(exc).__name__}: {exc}",
                      flush=True)
        if self._root is not None:
            self._root.after(TOAST_POLL_MS, self._drain)

    def _teardown_ui(self) -> None:
        """Beendet die Mainloop — läuft im ToastUI-Thread (via _drain)."""
        root = self._root
        if root is None:
            return
        if self._hide_after is not None:
            try:
                root.after_cancel(self._hide_after)
            except Exception:  # noqa: BLE001
                pass
            self._hide_after = None
        try:
            root.quit()
        except Exception:  # noqa: BLE001
            pass

    def _render(self, text: str, duration_ms: int) -> None:
        win, label, root = self._win, self._label, self._root
        if win is None or label is None or root is None:
            return
        colors = self._theme_colors()
        win.configure(bg=colors["border"])
        label.configure(text=text, bg=colors["bg"], fg=colors["fg"])
        win.update_idletasks()
        w = win.winfo_reqwidth()
        h = win.winfo_reqheight()
        x = win.winfo_screenwidth() - w - TOAST_MARGIN_PX
        y = win.winfo_screenheight() - h - TOAST_MARGIN_PX - TASKBAR_RESERVE_PX
        win.geometry(f"+{max(0, x)}+{max(0, y)}")
        win.deiconify()
        win.lift()
        if self._hide_after is not None:
            try:
                root.after_cancel(self._hide_after)
            except Exception:  # noqa: BLE001
                pass
        self._hide_after = root.after(int(duration_ms), self._hide)

    def _hide(self) -> None:
        self._hide_after = None
        if self._win is not None:
            try:
                self._win.withdraw()
            except Exception:  # noqa: BLE001
                pass


# --- Manueller Dev-Smoke ----------------------------------------------------
if __name__ == "__main__":
    import time

    ctrl = ToastController(get_theme=lambda: "dark")
    ctrl.start()
    # Schnelles Mehrfach-Cyclen → EIN Toast, Text-Update + Timer-Reset:
    ctrl.show("Modus: Clean Dictation", TOAST_DURATION_MODE_MS)
    time.sleep(0.2)
    ctrl.show("Modus: Smart Flow", TOAST_DURATION_MODE_MS)
    time.sleep(0.2)
    ctrl.show("Modus: Polished Text", TOAST_DURATION_MODE_MS)
    time.sleep(2.5)
    # Mehrzeiliger Info/Fehler-Toast (längere Standzeit):
    ctrl.show("Daemon nicht erreichbar\nWird automatisch neu gestartet …",
              TOAST_DURATION_INFO_MS)
    time.sleep(5.0)
    ctrl.stop()
