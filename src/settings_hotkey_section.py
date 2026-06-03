"""Hotkey-Section für die Settings-GUI (v1.3 Auslagerung aus settings.py).

Hält alle Widgets und Working-Sets rund um die drei Hotkey-Slots
(Haupt-Hotkey, Cycle-Hotkey, Modus-Hotkey pro Modus) plus die Cycle-Loop-
Checkbox und die Hotkey-Übersicht. Zwei Build-Methoden, weil die Widgets
sich logisch auf zwei Tabs verteilen:

  - `build_hotkeys_tab(parent)`  — Haupt + Cycle + Treeview-Übersicht
  - `build_mode_widgets(parent)` — Modus-Hotkey-Slot + „Im Cycle"-Checkbox

Beide Tabs greifen auf dieselben Working-Sets zu. Beim Wechsel des
aktiven Modus im Modi-Tab muss `update_for_mode(mode_id)` aufgerufen
werden.
"""
from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk
from typing import Callable

import config as cfg_mod
import daemon_client as dc
from hotkey_capture import HotkeyCaptureDialog, format_hotkey_for_display
from settings_helpers import LABELFRAME_INNER_PAD, PAD_Y_GROUP


class HotkeySection:
    """State + Widgets für alle Hotkey-Slots der Settings-GUI."""

    def __init__(self,
                 root: tk.Misc,
                 cfg: dict,
                 on_dirty: Callable[[], None],
                 set_status: Callable[[str], None]) -> None:
        self.root = root
        self.cfg = cfg
        self.on_dirty = on_dirty
        self.set_status = set_status

        # Working-Sets — werden in apply_to_config zurück ins cfg-dict gemergt
        hk_block = (cfg.get("hotkeys") or {})
        self._main_hotkey: str = hk_block.get("main") or "CapsLock"
        self._cycle_hotkey: str | None = hk_block.get("cycle") or None
        self._per_mode_hotkeys: dict[str, str] = {
            mid: spec for mid, spec in (hk_block.get("per_mode") or {}).items()
            if spec
        }
        self._cycle_loop_set: set[str] = set(cfg.get("cycle_loop") or [])

        # tk.Variables — werden erst nach build() befüllt
        self._main_hotkey_var: tk.StringVar | None = None
        self._cycle_hotkey_var: tk.StringVar | None = None
        self._mode_hotkey_var: tk.StringVar | None = None
        self._mode_in_cycle_var: tk.BooleanVar | None = None
        self._overview: ttk.Treeview | None = None

        # Aktueller Modus im Modi-Tab — wird von update_for_mode() gesetzt
        self._current_mode_id: str = cfg.get("mode", cfg_mod.DEFAULT_MODE)

    # ---------------------------------------------------------------- Build

    def build_hotkeys_tab(self, parent: ttk.Frame) -> None:
        """Baut Main-Slot, Cycle-Slot und Übersicht — jeweils in eigener
        LabelFrame-Gruppe (v1.4 Layout-Refactor)."""
        parent.columnconfigure(0, weight=1)

        # --- Gruppe „Haupt-Hotkey" -------------------------------------
        grp_main = ttk.LabelFrame(
            parent, text="Haupt-Hotkey", padding=LABELFRAME_INNER_PAD,
        )
        grp_main.grid(row=0, column=0, sticky="ew", pady=(0, PAD_Y_GROUP))
        grp_main.columnconfigure(0, weight=1)
        main_row = ttk.Frame(grp_main)
        main_row.grid(row=0, column=0, sticky="ew")
        main_row.columnconfigure(0, weight=1)
        self._main_hotkey_var = tk.StringVar(
            value=format_hotkey_for_display(self._main_hotkey),
        )
        ttk.Label(
            main_row, textvariable=self._main_hotkey_var,
            relief="groove", padding=4, font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            main_row, text="🎯 Erfassen…",
            command=self._capture_main,
        ).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(
            grp_main,
            text="Push-to-Talk-Taste: halten zum Aufnehmen, loslassen zum "
                 "Beenden + Transkribieren.",
            style="Hint.TLabel", wraplength=520, justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        # --- Gruppe „Cycle-Hotkey" -------------------------------------
        grp_cycle = ttk.LabelFrame(
            parent, text="Cycle-Hotkey", padding=LABELFRAME_INNER_PAD,
        )
        grp_cycle.grid(row=1, column=0, sticky="ew", pady=(0, PAD_Y_GROUP))
        grp_cycle.columnconfigure(0, weight=1)
        cycle_row = ttk.Frame(grp_cycle)
        cycle_row.grid(row=0, column=0, sticky="ew")
        cycle_row.columnconfigure(0, weight=1)
        self._cycle_hotkey_var = tk.StringVar(
            value=format_hotkey_for_display(self._cycle_hotkey),
        )
        ttk.Label(
            cycle_row, textvariable=self._cycle_hotkey_var,
            relief="groove", padding=4, font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            cycle_row, text="🎯 Erfassen…",
            command=self._capture_cycle,
        ).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(
            cycle_row, text="✕ Löschen",
            command=self._clear_cycle,
        ).grid(row=0, column=2, padx=(6, 0))
        ttk.Label(
            grp_cycle,
            text="Tipp-Hotkey, der den aktiven Modus durch die Cycle-Modi "
                 "(siehe Modi-Tab) durchschaltet. Leer = nicht benutzt.",
            style="Hint.TLabel", wraplength=520, justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(8, 0))

        # --- Gruppe „Hotkey-Übersicht" ---------------------------------
        grp_overview = ttk.LabelFrame(
            parent, text="Hotkey-Übersicht", padding=LABELFRAME_INNER_PAD,
        )
        grp_overview.grid(row=2, column=0, sticky="nsew")
        grp_overview.columnconfigure(0, weight=1)
        grp_overview.rowconfigure(0, weight=1)
        parent.rowconfigure(2, weight=1)
        self._overview = ttk.Treeview(
            grp_overview, columns=("hotkey", "funktion"),
            show="headings", height=6,
        )
        self._overview.heading("hotkey", text="Hotkey")
        self._overview.heading("funktion", text="Funktion")
        self._overview.column("hotkey", width=200, anchor="w")
        self._overview.column("funktion", width=420, anchor="w")
        self._overview.grid(row=0, column=0, sticky="nsew")
        self.refresh_overview()

    def build_mode_widgets(self, parent: ttk.Frame, row: int) -> int:
        """Modus-Hotkey-Slot + Cycle-Loop-Checkbox in den Modi-Tab.
        Wird mit dem aktuellen Modus aus update_for_mode() bestückt.
        Returns next row."""
        ttk.Label(parent, text="Modus-Hotkey").grid(
            row=row, column=0, sticky="w", pady=4,
        )
        mh_frame = ttk.Frame(parent)
        mh_frame.grid(row=row, column=1, sticky="ew", pady=4)
        mh_frame.columnconfigure(0, weight=1)
        self._mode_hotkey_var = tk.StringVar(value=format_hotkey_for_display(None))
        ttk.Label(
            mh_frame, textvariable=self._mode_hotkey_var,
            relief="groove", padding=4, font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(
            mh_frame, text="🎯 Erfassen…",
            command=self._capture_mode,
        ).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(
            mh_frame, text="✕ Löschen",
            command=self._clear_mode,
        ).grid(row=0, column=2, padx=(6, 0))
        row += 1
        ttk.Label(
            parent,
            text="Optional: eigene Push-to-Talk-Taste für genau diesen Modus.",
            foreground="#666", wraplength=460, justify="left",
        ).grid(row=row, column=1, sticky="w", pady=(0, 8))
        row += 1

        ttk.Label(parent, text="Im Cycle-Loop").grid(
            row=row, column=0, sticky="w", pady=4,
        )
        self._mode_in_cycle_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            parent,
            text="Diesen Modus per Cycle-Hotkey durchschalten",
            variable=self._mode_in_cycle_var,
            command=self._on_mode_in_cycle_toggle,
        ).grid(row=row, column=1, sticky="w", pady=4)
        row += 1
        return row

    # ----------------------------------------------------- Public Updates

    def update_for_mode(self, mode_id: str) -> None:
        """Bei Modus-Wechsel im Modi-Tab: Slot + Checkbox umladen."""
        self._current_mode_id = mode_id
        if self._mode_hotkey_var is not None:
            self._mode_hotkey_var.set(
                format_hotkey_for_display(self._per_mode_hotkeys.get(mode_id)),
            )
        if self._mode_in_cycle_var is not None:
            self._mode_in_cycle_var.set(mode_id in self._cycle_loop_set)

    def refresh_overview(self) -> None:
        """Treeview-Übersicht neu befüllen."""
        if self._overview is None:
            return
        for iid in self._overview.get_children():
            self._overview.delete(iid)
        if self._main_hotkey:
            self._overview.insert("", "end", values=(
                format_hotkey_for_display(self._main_hotkey),
                "Haupt-Push-to-Talk",
            ))
        if self._cycle_hotkey:
            n = len(self._cycle_loop_set)
            self._overview.insert("", "end", values=(
                format_hotkey_for_display(self._cycle_hotkey),
                f"Cycle-Modus durchschalten ({n} im Loop)",
            ))
        for mode_id in cfg_mod.MODES:
            spec = self._per_mode_hotkeys.get(mode_id)
            if not spec:
                continue
            ui = cfg_mod.get_mode_ui_name(mode_id, self.cfg)
            tag = " · im Cycle" if mode_id in self._cycle_loop_set else ""
            self._overview.insert("", "end", values=(
                format_hotkey_for_display(spec),
                f'Modus „{ui}"{tag}',
            ))

    def apply_to_config(self, cfg: dict) -> None:
        """Schreibt die Working-Sets in das übergebene cfg-Dict zurück."""
        per_mode_clean = {
            mid: spec for mid, spec in self._per_mode_hotkeys.items() if spec
        }
        cfg["hotkeys"] = {
            "main": self._main_hotkey or "CapsLock",
            "cycle": self._cycle_hotkey or None,
            "per_mode": per_mode_clean,
        }
        # Cycle-Loop in MODES-Reihenfolge, gefiltert auf gecheckte Modi
        cfg["cycle_loop"] = [m for m in cfg_mod.MODES if m in self._cycle_loop_set]

    # --------------------------------------------------------- Capture-IO

    def _excludes_without(self, slot_label: str) -> set[str]:
        """Belegte Hotkeys ohne den gerade editierten Slot — fürs Capture-
        exclude-Set, damit der gerade Slot seinen eigenen Wert nicht als
        Konflikt sieht. Slot-Labels: 'main', 'cycle', 'mode:<mode_id>'."""
        out: set[str] = set()
        if slot_label != "main" and self._main_hotkey:
            out.add(cfg_mod.normalize_hotkey(self._main_hotkey))
        if slot_label != "cycle" and self._cycle_hotkey:
            out.add(cfg_mod.normalize_hotkey(self._cycle_hotkey))
        for mid, spec in self._per_mode_hotkeys.items():
            if not spec or slot_label == f"mode:{mid}":
                continue
            out.add(cfg_mod.normalize_hotkey(spec))
        out.discard("")
        return out

    def _open_capture(self, slot_label: str,
                      friendly_name: str) -> str | None:
        """Öffnet HotkeyCaptureDialog. Pausiert globale Tray-Hotkeys während
        Capture (sonst frisst der LL-Hook bereits belegte Tasten, bevor
        tkinter sie sieht). Pause/Resume gehen über den Daemon."""
        excludes = self._excludes_without(slot_label)
        paused = dc.pause_hotkeys()
        if paused:
            # Tray pollt /health alle 300 ms — kurzer Buffer, damit der
            # Hook nachweislich abgeschaltet ist, bevor wir capturen.
            time.sleep(0.4)
        try:
            dlg = HotkeyCaptureDialog(
                self.root, exclude=excludes, slot_label=friendly_name,
            )
            return dlg.show()
        finally:
            if paused:
                dc.resume_hotkeys()

    def _capture_main(self) -> None:
        spec = self._open_capture("main", "Haupt-Hotkey")
        if spec:
            self._main_hotkey = spec
            self._main_hotkey_var.set(format_hotkey_for_display(spec))
            self.refresh_overview()
            self.on_dirty()
            self.set_status(
                f"Haupt-Hotkey gesetzt: {format_hotkey_for_display(spec)}"
            )

    def _capture_cycle(self) -> None:
        spec = self._open_capture("cycle", "Cycle-Hotkey")
        if spec:
            self._cycle_hotkey = spec
            self._cycle_hotkey_var.set(format_hotkey_for_display(spec))
            self.refresh_overview()
            self.on_dirty()
            self.set_status(
                f"Cycle-Hotkey gesetzt: {format_hotkey_for_display(spec)}"
            )

    def _clear_cycle(self) -> None:
        self._cycle_hotkey = None
        self._cycle_hotkey_var.set(format_hotkey_for_display(None))
        self.refresh_overview()
        self.on_dirty()
        self.set_status("Cycle-Hotkey gelöscht")

    def _capture_mode(self) -> None:
        mode_id = self._current_mode_id
        ui = cfg_mod.get_mode_ui_name(mode_id, self.cfg)
        spec = self._open_capture(f"mode:{mode_id}", f'Modus „{ui}"')
        if spec:
            self._per_mode_hotkeys[mode_id] = spec
            self._mode_hotkey_var.set(format_hotkey_for_display(spec))
            self.refresh_overview()
            self.on_dirty()
            self.set_status(
                f'Modus-Hotkey für „{ui}" gesetzt: '
                f"{format_hotkey_for_display(spec)}"
            )

    def _clear_mode(self) -> None:
        mode_id = self._current_mode_id
        self._per_mode_hotkeys.pop(mode_id, None)
        self._mode_hotkey_var.set(format_hotkey_for_display(None))
        self.refresh_overview()
        self.on_dirty()
        self.set_status("Modus-Hotkey gelöscht")

    def _on_mode_in_cycle_toggle(self) -> None:
        mode_id = self._current_mode_id
        if bool(self._mode_in_cycle_var.get()):
            self._cycle_loop_set.add(mode_id)
        else:
            self._cycle_loop_set.discard(mode_id)
        self.refresh_overview()
        self.on_dirty()
