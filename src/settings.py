"""Speech2Text Settings — tkinter-GUI für per-User-Konfiguration.

Aufruf:
  python src/settings.py
  (oder via Tray-Menü „⚙️ Einstellungen…", sobald in shortcut.ahk aktiviert)

Schreibt %APPDATA%/Speech2Text/config.json (DPAPI-verschlüsselter API-Key)
und triggert POST /reload-config am Daemon, falls erreichbar.

Details: Projektplanung/05_Einstellungsmenue/SPEZIFIKATION.md §A1–A8.
"""
from __future__ import annotations

import _arch_fix  # noqa: F401  # ARM64-Windows: patcht platform.machine() vor (lazy) sounddevice-Import

import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import config as cfg_mod
import daemon_client as dc
from hotkey_capture import HotkeyCaptureDialog, format_hotkey_for_display
from settings_helpers import (
    AUDIO_DEFAULT_LABEL, HELP_API_KEY, HELP_AUDIO, HELP_CYCLE_HOTKEY,
    HELP_HOTKEY, HELP_MODE_HOTKEY, HELP_MODE_IN_CYCLE, HELP_MODE_NAME,
    HELP_MODE_PROMPT, HELP_PASTE_MODE, HELP_POSTROLL, HELP_PREBUFFER,
    HELP_PREROLL, MIC_TEST_DURATION_S, MODE_PROMPT_SOFT_MAX,
    PASTE_MODES, POSTROLL_MS_MAX, PREROLL_MS_MAX, SAMPLE_RATE,
    list_input_devices,
)


def trigger_reload() -> str:
    """POST /reload-config — Status-String zurück. Fehler nicht-fatal."""
    ok = dc.reload_config()
    return "reloaded" if ok else "(Daemon nicht erreichbar)"


def _post(path: str) -> bool:
    """POST ohne Body. Thin Wrapper auf daemon_client.post — wir behalten
    den lokalen Namen, weil Bestandscode ihn auf vielen Stellen aufruft."""
    return dc.post(path)


class SettingsWindow:
    def __init__(self) -> None:
        self.cfg = cfg_mod.load_config()
        self.root = tk.Tk()
        self.root.title("Speech2Text — Einstellungen")
        # Init-Groesse an den Bildschirm klemmen (kleine Aufloesungen / ARM-Tablets).
        # Inhalt liegt in einem scrollbaren Canvas, Buttons in einem fixen Footer —
        # selbst bei minsize-Hoehe sind die Aktions-Buttons immer sichtbar.
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        init_w = min(680, max(560, screen_w - 40))
        init_h = min(900, max(420, screen_h - 80))
        self.root.geometry(f"{init_w}x{init_h}")
        self.root.minsize(560, 420)
        # Pro Feldname: Liste von Widgets, die per Help-Toggle ein-/ausblenden.
        self._help_widgets: list[tk.Widget] = []
        # Working-Copy der Modus-Edits während der Session.
        # {mode_id: {"ui_name": str, "prompt": str}} — wird beim Save gegen
        # MODES-Defaults verglichen, nur Diffs landen in mode_overrides.
        self._mode_edits: dict[str, dict] = {}
        # Hotkey-Layer (Schritt 6): Working-Copies — werden beim Save in das
        # finale "hotkeys"-dict + "cycle_loop"-list aggregiert.
        hk_block = (self.cfg.get("hotkeys") or {})
        self._main_hotkey: str = hk_block.get("main") or "CapsLock"
        self._cycle_hotkey: str | None = hk_block.get("cycle") or None
        self._per_mode_hotkeys: dict[str, str] = {
            mid: spec for mid, spec in (hk_block.get("per_mode") or {}).items()
            if spec
        }
        self._cycle_loop_set: set[str] = set(self.cfg.get("cycle_loop") or [])
        # Aktuell im Editor sichtbarer Modus (für Switch-Logic).
        self._current_mode_id = self.cfg.get("mode", cfg_mod.DEFAULT_MODE)
        self._build_ui()
        self._resize_to_content()

    # --- UI ---------------------------------------------------------------

    def _help_row(self, parent: ttk.Frame, row: int, text: str) -> int:
        """Fügt eine kleine graue Erklärungs-Zeile unter ein Feld ein.
        Wird per Help-Toggle gemeinsam ein-/ausgeblendet. Gibt nächste Row."""
        lbl = ttk.Label(
            parent, text=text, foreground="#666",
            wraplength=420, justify="left",
        )
        lbl.grid(row=row, column=1, sticky="w", pady=(0, 6))
        lbl.grid_remove()  # Standard: versteckt
        self._help_widgets.append(lbl)
        return row + 1

    # --- Hotkey-Slot-Helpers ---------------------------------------------

    def _current_hotkey_excludes(self, exclude_slot: str) -> set[str]:
        """Sammelt alle aktuell belegten Hotkeys (normalisiert) außer dem
        angegebenen Slot — fürs Capture-Dialog-`exclude`-Set, damit der
        gerade editierte Slot seinen eigenen Wert nicht als Konflikt sieht.
        Slot-Labels: 'main', 'cycle', 'mode:<mode_id>'."""
        out: set[str] = set()
        if exclude_slot != "main" and self._main_hotkey:
            out.add(cfg_mod.normalize_hotkey(self._main_hotkey))
        if exclude_slot != "cycle" and self._cycle_hotkey:
            out.add(cfg_mod.normalize_hotkey(self._cycle_hotkey))
        for mid, spec in self._per_mode_hotkeys.items():
            if not spec:
                continue
            if exclude_slot == f"mode:{mid}":
                continue
            out.add(cfg_mod.normalize_hotkey(spec))
        out.discard("")
        return out

    def _open_capture(self, slot_label: str, friendly_name: str) -> str | None:
        """Öffnet HotkeyCaptureDialog. Rückgabe: AHK-Spec oder None.
        Pausiert globale AHK-Hotkeys während Capture, sonst frisst der
        Hook bereits belegte Tasten, bevor tkinter sie sieht."""
        excludes = self._current_hotkey_excludes(slot_label)
        paused = _post("/pause-hotkeys")
        if paused:
            # AHK-Polling-Intervall ist 300 ms — kurzer Buffer, damit AHK
            # garantiert reagiert hat, bevor Capture die Eingabe entgegennimmt.
            import time as _t
            _t.sleep(0.4)
        try:
            dlg = HotkeyCaptureDialog(
                self.root, exclude=excludes, slot_label=friendly_name,
            )
            return dlg.show()
        finally:
            if paused:
                _post("/resume-hotkeys")

    def _capture_main_hotkey(self) -> None:
        spec = self._open_capture("main", "Haupt-Hotkey")
        if spec:
            self._main_hotkey = spec
            self._main_hotkey_var.set(format_hotkey_for_display(spec))
            self._refresh_overview()
            self.status_var.set(f"Haupt-Hotkey gesetzt: {format_hotkey_for_display(spec)}")

    def _capture_cycle_hotkey(self) -> None:
        spec = self._open_capture("cycle", "Cycle-Hotkey")
        if spec:
            self._cycle_hotkey = spec
            self._cycle_hotkey_var.set(format_hotkey_for_display(spec))
            self._refresh_overview()
            self.status_var.set(f"Cycle-Hotkey gesetzt: {format_hotkey_for_display(spec)}")

    def _clear_cycle_hotkey(self) -> None:
        self._cycle_hotkey = None
        self._cycle_hotkey_var.set(format_hotkey_for_display(None))
        self._refresh_overview()
        self.status_var.set("Cycle-Hotkey gelöscht")

    def _capture_mode_hotkey(self) -> None:
        mode_id = self._current_mode_id
        ui = cfg_mod.get_mode_ui_name(mode_id, self.cfg)
        spec = self._open_capture(f"mode:{mode_id}", f"Modus „{ui}“")
        if spec:
            self._per_mode_hotkeys[mode_id] = spec
            self._mode_hotkey_var.set(format_hotkey_for_display(spec))
            self._refresh_overview()
            self.status_var.set(f"Modus-Hotkey für „{ui}“ gesetzt: "
                                 f"{format_hotkey_for_display(spec)}")

    def _clear_mode_hotkey(self) -> None:
        mode_id = self._current_mode_id
        self._per_mode_hotkeys.pop(mode_id, None)
        self._mode_hotkey_var.set(format_hotkey_for_display(None))
        self._refresh_overview()
        self.status_var.set("Modus-Hotkey gelöscht")

    def _on_mode_in_cycle_toggle(self) -> None:
        mode_id = self._current_mode_id
        if bool(self._mode_in_cycle_var.get()):
            self._cycle_loop_set.add(mode_id)
        else:
            self._cycle_loop_set.discard(mode_id)
        self._refresh_overview()

    def _refresh_overview(self) -> None:
        """Hotkey-Übersicht (Treeview) neu befüllen aus den Working-Sets.
        Sortierung: Haupt → Cycle → Modus-Hotkeys (in MODES-Reihenfolge)."""
        # Vor dem Initial-Build kann _refresh_overview von Capture-Methoden
        # aufgerufen werden (theoretisch), bevor _overview existiert.
        if not getattr(self, "_overview", None):
            return
        for iid in self._overview.get_children():
            self._overview.delete(iid)
        if self._main_hotkey:
            self._overview.insert("", "end", values=(
                format_hotkey_for_display(self._main_hotkey),
                "Haupt-Push-to-Talk",
            ))
        if self._cycle_hotkey:
            cycle_size = len(self._cycle_loop_set)
            self._overview.insert("", "end", values=(
                format_hotkey_for_display(self._cycle_hotkey),
                f"Cycle-Modus durchschalten ({cycle_size} im Loop)",
            ))
        for mode_id in cfg_mod.MODES:
            spec = self._per_mode_hotkeys.get(mode_id)
            if not spec:
                continue
            ui = cfg_mod.get_mode_ui_name(mode_id, self.cfg)
            in_cycle = " · im Cycle" if mode_id in self._cycle_loop_set else ""
            self._overview.insert("", "end", values=(
                format_hotkey_for_display(spec),
                f"Modus „{ui}“{in_cycle}",
            ))

    def _build_ui(self) -> None:
        # --- Footer (Buttons) zuerst, damit sie auf kleinen Screens
        # garantiert sichtbar sind — pack(side="bottom") reserviert den
        # Platz, der Scroll-Bereich darueber bekommt den Rest. ---
        footer = ttk.Frame(self.root, padding=(14, 8, 14, 14))
        footer.pack(side="bottom", fill="x")
        footer.columnconfigure(0, weight=1)
        ttk.Button(footer, text="Abbrechen", command=self.root.destroy).grid(
            row=0, column=1, padx=(0, 6),
        )
        ttk.Button(footer, text="Anwenden", command=self._on_apply).grid(
            row=0, column=2, padx=(0, 6),
        )
        ttk.Button(
            footer, text="Speichern & Schließen", command=self._on_save_close,
        ).grid(row=0, column=3)

        # --- Scrollbarer Mittelbereich (alles ausser Footer) ---
        canvas_holder = ttk.Frame(self.root)
        canvas_holder.pack(side="top", fill="both", expand=True)
        canvas = tk.Canvas(canvas_holder, highlightthickness=0)
        vsb = ttk.Scrollbar(
            canvas_holder, orient="vertical", command=canvas.yview,
        )
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        outer = ttk.Frame(canvas, padding=14)
        outer_window = canvas.create_window((0, 0), window=outer, anchor="nw")

        def _on_canvas_configure(event: tk.Event) -> None:
            # Inner-Frame-Breite an die Canvas-Breite koppeln, damit
            # die Felder horizontal ueber die volle Breite layouten.
            canvas.itemconfig(outer_window, width=event.width)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_outer_configure(_event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))
        outer.bind("<Configure>", _on_outer_configure)

        def _on_mousewheel(event: tk.Event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        # Wheel nur binden, solange die Maus ueber dem Canvas ist —
        # sonst kollidiert es mit Treeview/Text-Eigenscroll.
        canvas.bind("<Enter>", lambda _e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda _e: canvas.unbind_all("<MouseWheel>"))

        outer.columnconfigure(1, weight=1)

        row = 0

        # Hilfe-Toggle ganz oben
        self.help_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            outer, text="ℹ Hilfetexte zu allen Feldern anzeigen",
            variable=self.help_var, command=self._toggle_help,
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
        row += 1

        # API-Key
        ttk.Label(outer, text="OpenAI API-Key").grid(row=row, column=0, sticky="w", pady=4)
        key_frame = ttk.Frame(outer)
        key_frame.grid(row=row, column=1, sticky="ew", pady=4)
        key_frame.columnconfigure(0, weight=1)
        self.api_key_var = tk.StringVar(value=cfg_mod.get_api_key(self.cfg))
        self.api_key_entry = ttk.Entry(key_frame, textvariable=self.api_key_var, show="*")
        self.api_key_entry.grid(row=0, column=0, sticky="ew")
        self.show_key_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            key_frame, text="anzeigen", variable=self.show_key_var,
            command=self._toggle_key_visible,
        ).grid(row=0, column=1, padx=(8, 0))
        row += 1
        row = self._help_row(outer, row, HELP_API_KEY)

        # Modus + Editor (Anzeigename, Prompt). Labels im Dropdown reflektieren
        # User-Overrides (falls gesetzt) — Snapshot beim Init, kein Live-Update
        # während Session, weil Dropdown-Reverse-Lookup sonst kompliziert wird.
        ttk.Label(outer, text="Modus (Optimierung)").grid(row=row, column=0, sticky="w", pady=4)
        self.mode_keys = list(cfg_mod.MODES.keys())
        self.mode_labels = [cfg_mod.get_mode_ui_name(k, self.cfg) for k in self.mode_keys]
        cur_mode = self._current_mode_id
        cur_label = cfg_mod.get_mode_ui_name(cur_mode, self.cfg)
        self.mode_var = tk.StringVar(value=cur_label)
        ttk.Combobox(
            outer, textvariable=self.mode_var, values=self.mode_labels,
            state="readonly",
        ).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1

        # Modus-Beschreibung (statisch aus MODES, kein Override hier)
        self.mode_desc_var = tk.StringVar()
        ttk.Label(
            outer, textvariable=self.mode_desc_var, foreground="#444",
            wraplength=440, justify="left",
        ).grid(row=row, column=1, sticky="w", pady=(0, 6))
        row += 1

        # Anzeigename — editierbar (Entry) + Reset-Button
        ttk.Label(outer, text="Anzeigename").grid(row=row, column=0, sticky="w", pady=4)
        name_frame = ttk.Frame(outer)
        name_frame.grid(row=row, column=1, sticky="ew", pady=4)
        name_frame.columnconfigure(0, weight=1)
        self.mode_name_var = tk.StringVar()
        ttk.Entry(name_frame, textvariable=self.mode_name_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(name_frame, text="↺ Standard",
                   command=self._reset_current_mode).grid(row=0, column=1, padx=(8, 0))
        row += 1
        row = self._help_row(outer, row, HELP_MODE_NAME)

        # Prompt-Textbox — editierbar für jeden Modus
        ttk.Label(outer, text="Prompt").grid(row=row, column=0, sticky="nw", pady=4)
        prompt_frame = ttk.Frame(outer)
        prompt_frame.grid(row=row, column=1, sticky="ew", pady=4)
        prompt_frame.columnconfigure(0, weight=1)
        self.mode_prompt_text = tk.Text(prompt_frame, height=6, wrap="word")
        self.mode_prompt_text.grid(row=0, column=0, sticky="ew")
        prompt_scroll = ttk.Scrollbar(prompt_frame, orient="vertical",
                                       command=self.mode_prompt_text.yview)
        prompt_scroll.grid(row=0, column=1, sticky="ns")
        self.mode_prompt_text.configure(yscrollcommand=prompt_scroll.set)
        # Char-Counter unter Textbox
        self.mode_count_var = tk.StringVar()
        self.mode_count_label = ttk.Label(
            prompt_frame, textvariable=self.mode_count_var, foreground="#666",
        )
        self.mode_count_label.grid(row=1, column=0, sticky="e", pady=(2, 0))
        self.mode_prompt_text.bind("<<Modified>>", self._on_prompt_changed)
        row += 1
        row = self._help_row(outer, row, HELP_MODE_PROMPT)

        # Modus-Hotkey + Cycle-Loop-Toggle für den AKTUELL editierten Modus.
        # Werte werden beim Modus-Wechsel ausgetauscht (siehe _load_mode_into_editor).
        ttk.Label(outer, text="Modus-Hotkey").grid(row=row, column=0, sticky="w", pady=4)
        mode_hk_frame = ttk.Frame(outer)
        mode_hk_frame.grid(row=row, column=1, sticky="ew", pady=4)
        mode_hk_frame.columnconfigure(0, weight=1)
        self._mode_hotkey_var = tk.StringVar(value=format_hotkey_for_display(None))
        ttk.Label(
            mode_hk_frame, textvariable=self._mode_hotkey_var,
            relief="groove", padding=4, font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(mode_hk_frame, text="🎯 Erfassen…",
                   command=self._capture_mode_hotkey).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(mode_hk_frame, text="✕ Löschen",
                   command=self._clear_mode_hotkey).grid(row=0, column=2, padx=(6, 0))
        row += 1
        row = self._help_row(outer, row, HELP_MODE_HOTKEY)

        ttk.Label(outer, text="Im Cycle-Loop").grid(row=row, column=0, sticky="w", pady=4)
        self._mode_in_cycle_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            outer, text="Diesen Modus per Cycle-Hotkey durchschalten",
            variable=self._mode_in_cycle_var,
            command=self._on_mode_in_cycle_toggle,
        ).grid(row=row, column=1, sticky="w", pady=4)
        row += 1
        row = self._help_row(outer, row, HELP_MODE_IN_CYCLE)

        # Initial-Load: Editor-Felder mit aktuellem Modus füllen + trace setzen.
        # trace_add NACH dem initialen Load, damit der Init-Schreibvorgang auf
        # mode_var nicht selbst _on_mode_change triggert.
        self._load_mode_into_editor(self._current_mode_id)
        self.mode_var.trace_add("write", lambda *_: self._on_mode_change())

        # Paste-Modus
        ttk.Label(outer, text="Paste-Modus").grid(row=row, column=0, sticky="w", pady=4)
        self.paste_keys = [k for k, _ in PASTE_MODES]
        self.paste_labels = [v for _, v in PASTE_MODES]
        cur_paste = self.cfg.get("paste_mode", "clipboard_ctrl_v")
        cur_paste_label = dict(PASTE_MODES).get(cur_paste, self.paste_labels[0])
        self.paste_var = tk.StringVar(value=cur_paste_label)
        ttk.Combobox(
            outer, textvariable=self.paste_var, values=self.paste_labels,
            state="readonly",
        ).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1
        row = self._help_row(outer, row, HELP_PASTE_MODE)

        # Audio-Device
        ttk.Label(outer, text="Audio-Eingabe").grid(row=row, column=0, sticky="w", pady=4)
        self.audio_devices = list_input_devices()
        self.audio_labels = [lbl for _, lbl in self.audio_devices]
        cur_dev = self.cfg.get("audio_device")
        cur_dev_label = next(
            (lbl for idx, lbl in self.audio_devices if idx == cur_dev),
            AUDIO_DEFAULT_LABEL,
        )
        self.audio_var = tk.StringVar(value=cur_dev_label)
        ttk.Combobox(
            outer, textvariable=self.audio_var, values=self.audio_labels,
            state="readonly",
        ).grid(row=row, column=1, sticky="ew", pady=4)
        row += 1
        row = self._help_row(outer, row, HELP_AUDIO)

        # Haupt-Hotkey (Capture-Widget statt Dropdown)
        ttk.Label(outer, text="Haupt-Hotkey").grid(row=row, column=0, sticky="w", pady=4)
        main_hk_frame = ttk.Frame(outer)
        main_hk_frame.grid(row=row, column=1, sticky="ew", pady=4)
        main_hk_frame.columnconfigure(0, weight=1)
        self._main_hotkey_var = tk.StringVar(
            value=format_hotkey_for_display(self._main_hotkey),
        )
        ttk.Label(
            main_hk_frame, textvariable=self._main_hotkey_var,
            relief="groove", padding=4, font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(main_hk_frame, text="🎯 Erfassen…",
                   command=self._capture_main_hotkey).grid(row=0, column=1, padx=(8, 0))
        row += 1
        row = self._help_row(outer, row, HELP_HOTKEY)

        # Cycle-Hotkey (optional)
        ttk.Label(outer, text="Cycle-Hotkey").grid(row=row, column=0, sticky="w", pady=4)
        cycle_hk_frame = ttk.Frame(outer)
        cycle_hk_frame.grid(row=row, column=1, sticky="ew", pady=4)
        cycle_hk_frame.columnconfigure(0, weight=1)
        self._cycle_hotkey_var = tk.StringVar(
            value=format_hotkey_for_display(self._cycle_hotkey),
        )
        ttk.Label(
            cycle_hk_frame, textvariable=self._cycle_hotkey_var,
            relief="groove", padding=4, font=("Segoe UI", 10, "bold"),
        ).grid(row=0, column=0, sticky="ew")
        ttk.Button(cycle_hk_frame, text="🎯 Erfassen…",
                   command=self._capture_cycle_hotkey).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(cycle_hk_frame, text="✕ Löschen",
                   command=self._clear_cycle_hotkey).grid(row=0, column=2, padx=(6, 0))
        row += 1
        row = self._help_row(outer, row, HELP_CYCLE_HOTKEY)

        # Pre-Recording-Ringpuffer
        ttk.Label(outer, text="Pre-Recording").grid(row=row, column=0, sticky="w", pady=4)
        self.prebuffer_var = tk.BooleanVar(
            value=bool(self.cfg.get("prebuffer_enabled", True)),
        )
        ttk.Checkbutton(
            outer,
            text="Erstes Wort nicht verschlucken (Mikro permanent offen)",
            variable=self.prebuffer_var,
        ).grid(row=row, column=1, sticky="w", pady=4)
        row += 1
        row = self._help_row(outer, row, HELP_PREBUFFER)

        # Pre-Roll (Spinbox in Millisekunden)
        ttk.Label(outer, text="Pre-Roll-Länge").grid(row=row, column=0, sticky="w", pady=4)
        preroll_frame = ttk.Frame(outer)
        preroll_frame.grid(row=row, column=1, sticky="w", pady=4)
        cur_preroll = int(self.cfg.get("preroll_ms", 300))
        cur_preroll = max(0, min(PREROLL_MS_MAX, cur_preroll))
        self.preroll_var = tk.IntVar(value=cur_preroll)
        ttk.Spinbox(
            preroll_frame, from_=0, to=PREROLL_MS_MAX, increment=50,
            textvariable=self.preroll_var, width=6,
        ).grid(row=0, column=0)
        ttk.Label(preroll_frame, text=f" ms (0–{PREROLL_MS_MAX})").grid(row=0, column=1)
        row += 1
        row = self._help_row(outer, row, HELP_PREROLL)

        # Post-Roll (Spinbox in Millisekunden)
        ttk.Label(outer, text="Post-Roll-Länge").grid(row=row, column=0, sticky="w", pady=4)
        postroll_frame = ttk.Frame(outer)
        postroll_frame.grid(row=row, column=1, sticky="w", pady=4)
        cur_postroll = int(self.cfg.get("postroll_ms", 200))
        cur_postroll = max(0, min(POSTROLL_MS_MAX, cur_postroll))
        self.postroll_var = tk.IntVar(value=cur_postroll)
        ttk.Spinbox(
            postroll_frame, from_=0, to=POSTROLL_MS_MAX, increment=50,
            textvariable=self.postroll_var, width=6,
        ).grid(row=0, column=0)
        ttk.Label(postroll_frame, text=f" ms (0–{POSTROLL_MS_MAX})").grid(row=0, column=1)
        row += 1
        row = self._help_row(outer, row, HELP_POSTROLL)

        # Trenner
        ttk.Separator(outer, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(12, 8),
        )
        row += 1

        # Hotkey-Übersicht — alle aktuell belegten Slots auf einen Blick.
        # Wird automatisch nach jedem Capture/Reset/Toggle aktualisiert.
        ttk.Label(outer, text="Hotkey-Übersicht",
                  font=("Segoe UI", 9, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(4, 4),
        )
        row += 1
        self._overview = ttk.Treeview(
            outer, columns=("hotkey", "funktion"), show="headings", height=6,
        )
        self._overview.heading("hotkey", text="Hotkey")
        self._overview.heading("funktion", text="Funktion")
        self._overview.column("hotkey", width=200, anchor="w")
        self._overview.column("funktion", width=380, anchor="w")
        self._overview.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        row += 1
        self._refresh_overview()

        # Trenner #2
        ttk.Separator(outer, orient="horizontal").grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(8, 8),
        )
        row += 1

        # Mikrofon-Test
        self.mic_test_btn = ttk.Button(
            outer, text=f"🎤 Mikrofon testen ({MIC_TEST_DURATION_S}s)",
            command=self._on_mic_test,
        )
        self.mic_test_btn.grid(row=row, column=0, columnspan=2, sticky="ew", pady=4)
        row += 1

        self.mic_status_var = tk.StringVar(value="")
        ttk.Label(outer, textvariable=self.mic_status_var, foreground="#555").grid(
            row=row, column=0, columnspan=2, sticky="w",
        )
        row += 1

        # Status-Zeile (für Save-Feedback)
        self.status_var = tk.StringVar(value="")
        ttk.Label(outer, textvariable=self.status_var, foreground="#2563EB").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(8, 0),
        )
        row += 1

        # Buttons liegen jetzt im fixen Footer (siehe Anfang von _build_ui) —
        # kein Spacer + Button-Frame mehr im Scroll-Bereich.

    # --- Aktionen ---------------------------------------------------------

    def _toggle_key_visible(self) -> None:
        self.api_key_entry.configure(show="" if self.show_key_var.get() else "*")

    def _toggle_help(self) -> None:
        show = bool(self.help_var.get())
        for w in self._help_widgets:
            if show:
                w.grid()
            else:
                w.grid_remove()
        self._resize_to_content()

    def _update_prompt_count(self) -> None:
        """Aktualisiert den Char-Counter unter dem Prompt-Feld."""
        text = self.mode_prompt_text.get("1.0", "end-1c")
        n = len(text)
        over = n > MODE_PROMPT_SOFT_MAX
        self.mode_count_var.set(f"{n} / {MODE_PROMPT_SOFT_MAX} Zeichen")
        self.mode_count_label.configure(foreground="#c00" if over else "#666")

    def _on_prompt_changed(self, _event: tk.Event) -> None:
        self._update_prompt_count()
        # <<Modified>>-Flag muss zurückgesetzt werden, sonst feuert das
        # Event nicht erneut bei der nächsten Änderung.
        self.mode_prompt_text.edit_modified(False)

    def _read_editor(self) -> dict:
        """Liest aktuellen Editor-Inhalt (Name + Prompt) als dict."""
        return {
            "ui_name": self.mode_name_var.get(),
            # tk.Text liefert immer ein trailing "\n" — beim Speichern
            # entscheidet erst der Vergleich zu Default, ob's matched.
            "prompt": self.mode_prompt_text.get("1.0", "end-1c"),
        }

    def _load_mode_into_editor(self, mode_id: str) -> None:
        """Füllt Name- und Prompt-Felder mit dem aktuellen Wert für mode_id.
        Reihenfolge: Working-Copy `_mode_edits` (User-Edits dieser Session)
        > persistierter Override aus `self.cfg` > MODES-Default.

        Lädt zusätzlich den Modus-Hotkey und den Cycle-Loop-Toggle aus den
        live-Working-Sets `_per_mode_hotkeys` / `_cycle_loop_set`."""
        default = cfg_mod.get_mode_default(mode_id)
        default_name = default.get("ui_name", mode_id)
        default_prompt = default.get("prompt") or ""

        # Working-Copy hat Vorrang (User editiert in dieser Session)
        if mode_id in self._mode_edits:
            edit = self._mode_edits[mode_id]
            name = edit.get("ui_name", default_name)
            prompt = edit.get("prompt", default_prompt)
        else:
            persisted = cfg_mod.get_mode_override(self.cfg, mode_id)
            name = persisted.get("ui_name", default_name)
            prompt = persisted.get("prompt", default_prompt)

        self.mode_name_var.set(name)
        self.mode_prompt_text.delete("1.0", "end")
        self.mode_prompt_text.insert("1.0", prompt)
        self.mode_prompt_text.edit_modified(False)

        # Beschreibung (immer aus MODES, nicht override-bar)
        self.mode_desc_var.set(default.get("description", ""))
        self._update_prompt_count()

        # Hotkey + Cycle-Loop für diesen Modus
        self._mode_hotkey_var.set(
            format_hotkey_for_display(self._per_mode_hotkeys.get(mode_id))
        )
        self._mode_in_cycle_var.set(mode_id in self._cycle_loop_set)

    def _save_current_mode_edits(self) -> None:
        """Schreibt aktuellen Editor-Inhalt für `_current_mode_id` in die
        Working-Copy `_mode_edits`. Aufgerufen vor jedem Modus-Wechsel."""
        self._mode_edits[self._current_mode_id] = self._read_editor()

    def _reset_current_mode(self) -> None:
        """Setzt den aktuellen Modus auf MODES-Default zurück: Editor-Felder
        mit Default-Werten füllen, Working-Copy-Eintrag entfernen, sodass
        beim Save kein Override gespeichert wird."""
        if self._current_mode_id in self._mode_edits:
            del self._mode_edits[self._current_mode_id]
        default = cfg_mod.get_mode_default(self._current_mode_id)
        self.mode_name_var.set(default.get("ui_name", self._current_mode_id))
        self.mode_prompt_text.delete("1.0", "end")
        self.mode_prompt_text.insert("1.0", default.get("prompt") or "")
        self.mode_prompt_text.edit_modified(False)
        self._update_prompt_count()
        self.status_var.set("Modus auf Standard zurückgesetzt (noch nicht gespeichert)")

    def _on_mode_change(self) -> None:
        """Wird beim Dropdown-Wechsel aufgerufen. Sichert die aktuellen
        Editor-Werte für den alten Modus, lädt den neuen."""
        new_id = self._selected_mode_key()
        if new_id == self._current_mode_id:
            return
        self._save_current_mode_edits()
        self._current_mode_id = new_id
        self._load_mode_into_editor(new_id)
        self._resize_to_content()

    def _resize_to_content(self) -> None:
        """Wachsendes Resize: vergrößert das Fenster, falls der aktuelle
        Inhalt mehr Platz braucht. Schrumpft NICHT — manuelle User-Größe
        bleibt erhalten. Wird verzögert via after(0, …) aufgerufen, damit
        tkinter zuvor die Layout-Änderung verarbeitet hat.

        Wachstum wird auf den verfuegbaren Bildschirm geclippt — sonst
        landet das Fenster auf kleinen Aufloesungen mit dem Footer
        unsichtbar unter dem Taskbar."""
        def apply_resize() -> None:
            self.root.update_idletasks()
            needed_h = self.root.winfo_reqheight()
            needed_w = self.root.winfo_reqwidth()
            cur_h = self.root.winfo_height()
            cur_w = self.root.winfo_width()
            max_h = self.root.winfo_screenheight() - 80
            max_w = self.root.winfo_screenwidth() - 40
            new_h = min(max_h, max(cur_h, needed_h))
            new_w = min(max_w, max(cur_w, needed_w))
            if new_h != cur_h or new_w != cur_w:
                self.root.geometry(f"{new_w}x{new_h}")
        self.root.after(0, apply_resize)

    def _selected_mode_key(self) -> str:
        label = self.mode_var.get()
        for k, l in zip(self.mode_keys, self.mode_labels):
            if l == label:
                return k
        return cfg_mod.DEFAULT_MODE

    def _selected_paste_key(self) -> str:
        label = self.paste_var.get()
        for k, l in zip(self.paste_keys, self.paste_labels):
            if l == label:
                return k
        return self.paste_keys[0]

    def _selected_audio_device(self) -> int | None:
        label = self.audio_var.get()
        for idx, lbl in self.audio_devices:
            if lbl == label:
                return idx
        return None

    def _save_and_reload(self) -> bool:
        """Persistiert Config + triggert /reload-config am Daemon. Updated
        Status-Zeile. Rückgabe True bei Erfolg (auch wenn Daemon offline).
        Bei Hotkey-Konflikten: Modal mit Liste, Save abgebrochen."""
        plain_key = self.api_key_var.get().strip()
        try:
            preroll_ms = int(self.preroll_var.get())
        except (tk.TclError, ValueError):
            preroll_ms = 300
        preroll_ms = max(0, min(PREROLL_MS_MAX, preroll_ms))
        try:
            postroll_ms = int(self.postroll_var.get())
        except (tk.TclError, ValueError):
            postroll_ms = 200
        postroll_ms = max(0, min(POSTROLL_MS_MAX, postroll_ms))

        # Aktuellen Editor-Stand für den gerade gewählten Modus ins Working-
        # Set übernehmen, dann gegen Defaults vergleichen → mode_overrides.
        self._save_current_mode_edits()
        new_overrides: dict[str, dict] = {}
        for mode_id, edit in self._mode_edits.items():
            default = cfg_mod.get_mode_default(mode_id)
            default_name = default.get("ui_name", mode_id)
            default_prompt = default.get("prompt") or ""
            override: dict = {}
            edited_name = (edit.get("ui_name") or "").strip()
            if edited_name and edited_name != default_name:
                override["ui_name"] = edited_name
            edited_prompt = edit.get("prompt") or ""
            # Prompt-Override speichern, wenn der editierte Wert (gestrippt)
            # vom Default (gestrippt) abweicht. Leerer Prompt = Sentinel für
            # „kein Optimize-Call"; nur dann speichern, wenn der Default das
            # nicht eh schon ist.
            if edited_prompt.strip() != default_prompt.strip():
                override["prompt"] = edited_prompt
            if override:
                new_overrides[mode_id] = override

        # Hotkeys aggregieren — leere Slots werden nicht persistiert.
        per_mode_clean = {
            mid: spec for mid, spec in self._per_mode_hotkeys.items() if spec
        }
        hotkeys_block = {
            "main": self._main_hotkey or "CapsLock",
            "cycle": self._cycle_hotkey or None,
            "per_mode": per_mode_clean,
        }
        # Cycle-Loop: in MODES-Reihenfolge gefiltert auf gecheckte Modi.
        cycle_loop = [mid for mid in cfg_mod.MODES if mid in self._cycle_loop_set]

        new_cfg: dict = dict(cfg_mod.DEFAULT_CONFIG)
        new_cfg.update(self.cfg)  # unbekannte Felder beibehalten
        new_cfg["mode"] = self._selected_mode_key()
        new_cfg["paste_mode"] = self._selected_paste_key()
        new_cfg["audio_device"] = self._selected_audio_device()
        new_cfg["hotkeys"] = hotkeys_block
        new_cfg["cycle_loop"] = cycle_loop
        new_cfg["prebuffer_enabled"] = bool(self.prebuffer_var.get())
        new_cfg["preroll_ms"] = preroll_ms
        new_cfg["postroll_ms"] = postroll_ms
        new_cfg["mode_overrides"] = new_overrides
        # Legacy-Felder leeren — werden via mode_overrides bzw. hotkeys verwaltet
        new_cfg["manual_prompt"] = ""
        new_cfg.pop("hotkey", None)

        # Konflikt-Check VOR dem Schreiben: Doppelbelegung würde AHK irritieren
        # (zweite Hotkey()-Bindung überschreibt die erste, der Slot wäre tot).
        conflicts = cfg_mod.find_hotkey_conflicts(new_cfg)
        if conflicts:
            lines = [
                f"  • {format_hotkey_for_display(spec)}: "
                f"{a} ↔ {b}"
                for a, b, spec in conflicts
            ]
            messagebox.showerror(
                "Hotkey-Konflikt",
                "Folgende Hotkeys sind doppelt belegt — bitte zuerst auflösen:\n\n"
                + "\n".join(lines),
            )
            return False

        try:
            cfg_mod.set_api_key(new_cfg, plain_key)
            cfg_mod.save_config(new_cfg)
        except OSError as e:
            messagebox.showerror("Speichern fehlgeschlagen", str(e))
            return False

        self.cfg = new_cfg
        reload_status = trigger_reload()
        self.status_var.set(f"Gespeichert. Reload: {reload_status}")
        return True

    def _on_apply(self) -> None:
        """Anwenden: speichert + reload, Fenster bleibt offen."""
        self._save_and_reload()

    def _on_save_close(self) -> None:
        """Speichern & Schließen: speichert + reload + schließt nach
        kurzer Status-Anzeige."""
        if self._save_and_reload():
            self.root.after(1500, self.root.destroy)

    # --- Mikrofon-Test ----------------------------------------------------

    def _on_mic_test(self) -> None:
        # Im Hintergrund-Thread, damit die UI nicht einfriert
        self.mic_test_btn.configure(state="disabled")
        self.mic_status_var.set("Aufnahme läuft … bitte sprechen")
        threading.Thread(target=self._mic_test_worker, daemon=True).start()

    def _mic_test_worker(self) -> None:
        try:
            import numpy as np
            import sounddevice as sd
            device = self._selected_audio_device()
            audio = sd.rec(
                int(MIC_TEST_DURATION_S * SAMPLE_RATE),
                samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                device=device,
            )
            sd.wait()
            peak = int(np.max(np.abs(audio)))
            peak_pct = round(peak / 32767 * 100)
            self._set_status_safe(f"Wiedergabe … (Pegel max {peak_pct}%)")
            sd.play(audio, samplerate=SAMPLE_RATE, device=device)
            sd.wait()
            level_hint = (
                "leise — sprich näher ans Mikro" if peak_pct < 20
                else "OK" if peak_pct < 80
                else "sehr laut — Abstand vergrößern"
            )
            self._set_status_safe(f"Test fertig. Pegel max {peak_pct}% — {level_hint}")
        except Exception as e:  # noqa: BLE001
            self._set_status_safe(f"Mikrofon-Test fehlgeschlagen: {e}")
        finally:
            self.root.after(0, lambda: self.mic_test_btn.configure(state="normal"))

    def _set_status_safe(self, text: str) -> None:
        self.root.after(0, lambda: self.mic_status_var.set(text))

    # --- Run --------------------------------------------------------------

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    SettingsWindow().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
