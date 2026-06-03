"""Speech2Text Settings — tkinter-GUI mit Tabs (v1.3 Refresh).

Aufruf:
  python src/settings.py
  (oder via Tray-Menü „⚙️ Einstellungen…")

Schreibt %APPDATA%/Speech2Text/config.json (DPAPI-verschlüsselter API-Key)
und triggert POST /reload-config am Daemon, falls erreichbar.

Tab-Struktur (v1.3):
  - Allgemein: API-Key, Paste-Modus, Pre-Recording / Pre-Roll / Post-Roll
  - Modi:       Modus-Editor (Name, Prompt) + Modus-Hotkey + „Im Cycle"
  - Hotkeys:    Haupt + Cycle + Übersicht
  - Audio:      Eingabe-Gerät + Mikrofon-Test

Details: Projektplanung/05_Einstellungsmenue/SPEZIFIKATION.md §A1–A8.
"""
from __future__ import annotations

import _arch_fix  # noqa: F401  # ARM64-Windows: vor (lazy) sounddevice-Import

import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import config as cfg_mod
import daemon_client as dc
from settings_helpers import (
    AUDIO_DEFAULT_LABEL, DIRTY_FG, ERROR_FG_BY_THEME, FONT_GROUP, FONT_HINT,
    GROUP_FG_BY_THEME, HELP_API_KEY, HELP_AUDIO, HELP_MODE_NAME,
    HELP_MODE_PROMPT, HELP_PASTE_MODE, HELP_POSTROLL, HELP_PREBUFFER,
    HELP_PREROLL, HINT_FG_BY_THEME, LABELFRAME_INNER_PAD, MIC_TEST_DURATION_S,
    MODE_PROMPT_SOFT_MAX, PAD_X, PAD_Y, PAD_Y_GROUP, PASTE_MODES,
    POSTROLL_MS_MAX, PREROLL_MS_MAX, SAMPLE_RATE, TAB_PADDING, THEME_CHOICES,
    THEME_DEFAULT, THEME_FALLBACK, list_input_devices,
)
from settings_hotkey_section import HotkeySection


def trigger_reload() -> str:
    """POST /reload-config — Status-String. Fehler nicht-fatal."""
    return "reloaded" if dc.reload_config() else "(Daemon nicht erreichbar)"


# ============================================================================
# SettingsWindow — Tabs + Theme
# ============================================================================

class SettingsWindow:
    def __init__(self) -> None:
        self.cfg = cfg_mod.load_config()
        self.root = tk.Tk()
        self.root.title("Speech2Text — Einstellungen")
        initial_theme = self.cfg.get("theme", THEME_DEFAULT)
        if initial_theme not in THEME_CHOICES:
            initial_theme = THEME_DEFAULT
        self._current_theme = initial_theme
        self._apply_theme(initial_theme)

        # Init-Größe an Bildschirm klemmen — vergrößert auf 720x860, damit
        # die „Darstellung"-Gruppe im Allgemein-Tab direkt sichtbar ist
        # (nach Layout-Refactor v1.4 mit größerem LabelFrame-Spacing).
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(f"{min(720, sw - 40)}x{min(860, sh - 80)}")
        self.root.minsize(600, 480)

        # State für Mode-Editor (working copy aktueller Session)
        self._mode_edits: dict[str, dict] = {}
        self._current_mode_id = self.cfg.get("mode", cfg_mod.DEFAULT_MODE)

        # Dirty-Tracking — Indikator in Statusleiste
        self._dirty = False

        self.status_var = tk.StringVar(value="")
        self._hotkeys = HotkeySection(
            self.root, self.cfg,
            on_dirty=self._mark_dirty,
            set_status=lambda t: self.status_var.set(t),
        )
        self._build_ui()
        # Sub-Styles nach _build_ui nochmal applizieren — sonst greifen
        # Hint/Error/Dirty-Subklassen beim Initial-Render nicht sauber
        # (ttk-Quirk mit Sun Valley v2.6.x).
        self._apply_theme(initial_theme)

    # ------------------------------------------------------------ Theme

    def _apply_theme(self, theme: str) -> None:
        # Sun Valley via sv-ttk. Bei ImportError/TclError Fallback auf
        # ttk-Built-in clam, damit das Fenster IMMER öffnet.
        try:
            import sv_ttk
            sv_ttk.set_theme(theme)
        except Exception as exc:  # noqa: BLE001
            print(f"[settings] sv-ttk Theme-Fehler ({exc!r}) — "
                  f"Fallback {THEME_FALLBACK}", file=sys.stderr)
            try:
                ttk.Style(self.root).theme_use(THEME_FALLBACK)
            except tk.TclError:
                pass

        # Sub-Styles + LabelFrame-Header. Beim TLabelframe.Label MUSS der
        # foreground explizit gesetzt werden, sonst fällt ttk auf den
        # System-Default (schwarz) zurück und Dark-Mode wird unlesbar.
        style = ttk.Style(self.root)
        style.configure(
            "TLabelframe.Label",
            font=FONT_GROUP,
            foreground=GROUP_FG_BY_THEME[theme],
        )
        style.configure(
            "Hint.TLabel",
            foreground=HINT_FG_BY_THEME[theme],
            font=FONT_HINT,
        )
        style.configure("Dirty.TLabel", foreground=DIRTY_FG)
        style.configure("Error.TLabel", foreground=ERROR_FG_BY_THEME[theme])

        self._current_theme = theme
        self.root.update_idletasks()

    # ------------------------------------------------------------ UI-Top

    def _build_ui(self) -> None:
        # Footer mit fixer Position — auf kleinen Bildschirmen bleibt er sichtbar
        footer = ttk.Frame(self.root, padding=(PAD_X, PAD_Y, PAD_X, PAD_Y + 4))
        footer.pack(side="bottom", fill="x")
        ttk.Label(footer, textvariable=self.status_var, style="Hint.TLabel").pack(
            side="left",
        )
        ttk.Button(footer, text="Speichern & Schließen",
                   command=self._on_save_close).pack(side="right")
        ttk.Button(footer, text="Anwenden",
                   command=self._on_apply).pack(side="right", padx=(0, 6))
        ttk.Button(footer, text="Abbrechen",
                   command=self._on_cancel).pack(side="right", padx=(0, 6))

        # Notebook + Tabs
        self.nb = ttk.Notebook(self.root)
        self.nb.pack(side="top", fill="both", expand=True,
                     padx=PAD_X, pady=(PAD_Y + 2, 0))

        self._tab_allgemein = ttk.Frame(self.nb, padding=TAB_PADDING)
        self._tab_modi = ttk.Frame(self.nb, padding=TAB_PADDING)
        self._tab_hotkeys = ttk.Frame(self.nb, padding=TAB_PADDING)
        self._tab_audio = ttk.Frame(self.nb, padding=TAB_PADDING)
        self.nb.add(self._tab_allgemein, text="Allgemein")
        self.nb.add(self._tab_modi, text="Modi")
        self.nb.add(self._tab_hotkeys, text="Hotkeys")
        self.nb.add(self._tab_audio, text="Audio")

        self._build_allgemein_tab(self._tab_allgemein)
        self._build_modi_tab(self._tab_modi)
        self._hotkeys.build_hotkeys_tab(self._tab_hotkeys)
        self._build_audio_tab(self._tab_audio)

    # ------------------------------------------------------- Allgemein-Tab

    def _build_allgemein_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        # --- Gruppe „Zugang" ------------------------------------------
        grp = ttk.LabelFrame(parent, text="Zugang", padding=LABELFRAME_INNER_PAD)
        grp.grid(row=0, column=0, sticky="ew", pady=(0, PAD_Y_GROUP))
        grp.columnconfigure(1, weight=1)

        ttk.Label(grp, text="OpenAI API-Key").grid(row=0, column=0, sticky="w", pady=4)
        key_frame = ttk.Frame(grp)
        key_frame.grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 0))
        key_frame.columnconfigure(0, weight=1)
        self.api_key_var = tk.StringVar(value=cfg_mod.get_api_key(self.cfg))
        self.api_key_var.trace_add("write", lambda *_: self._mark_dirty())
        self.api_key_entry = ttk.Entry(
            key_frame, textvariable=self.api_key_var, show="*",
        )
        self.api_key_entry.grid(row=0, column=0, sticky="ew")
        self.show_key_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            key_frame, text="anzeigen", variable=self.show_key_var,
            command=self._toggle_key_visible,
        ).grid(row=0, column=1, padx=(8, 0))
        ttk.Label(grp, text=HELP_API_KEY, style="Hint.TLabel",
                  wraplength=480, justify="left").grid(
            row=1, column=1, sticky="w", pady=(0, 4), padx=(8, 0),
        )

        # --- Gruppe „Texteinfügung" -----------------------------------
        grp = ttk.LabelFrame(parent, text="Texteinfügung", padding=LABELFRAME_INNER_PAD)
        grp.grid(row=1, column=0, sticky="ew", pady=(0, PAD_Y_GROUP))
        grp.columnconfigure(1, weight=1)
        ttk.Label(grp, text="Paste-Modus").grid(row=0, column=0, sticky="w", pady=4)
        self.paste_keys = [k for k, _ in PASTE_MODES]
        self.paste_labels = [v for _, v in PASTE_MODES]
        cur_paste = self.cfg.get("paste_mode", "clipboard_ctrl_v")
        cur_paste_label = dict(PASTE_MODES).get(cur_paste, self.paste_labels[0])
        self.paste_var = tk.StringVar(value=cur_paste_label)
        self.paste_var.trace_add("write", lambda *_: self._mark_dirty())
        ttk.Combobox(grp, textvariable=self.paste_var, values=self.paste_labels,
                     state="readonly").grid(
            row=0, column=1, sticky="ew", pady=4, padx=(8, 0),
        )
        ttk.Label(grp, text=HELP_PASTE_MODE, style="Hint.TLabel",
                  wraplength=480, justify="left").grid(
            row=1, column=1, sticky="w", pady=(0, 4), padx=(8, 0),
        )

        # --- Gruppe „Aufnahme" ----------------------------------------
        grp = ttk.LabelFrame(parent, text="Aufnahme", padding=LABELFRAME_INNER_PAD)
        grp.grid(row=2, column=0, sticky="ew", pady=(0, PAD_Y_GROUP))
        grp.columnconfigure(1, weight=1)

        self.prebuffer_var = tk.BooleanVar(
            value=bool(self.cfg.get("prebuffer_enabled", True)),
        )
        self.prebuffer_var.trace_add("write", lambda *_: self._mark_dirty())
        ttk.Checkbutton(
            grp,
            text="Pre-Recording: Mikrofon permanent offen, fängt erstes Wort vorab ab",
            variable=self.prebuffer_var,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=4)
        ttk.Label(grp, text=HELP_PREBUFFER, style="Hint.TLabel",
                  wraplength=520, justify="left").grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 6),
        )

        ttk.Label(grp, text="Pre-Roll").grid(row=2, column=0, sticky="w", pady=4)
        pre_frame = ttk.Frame(grp)
        pre_frame.grid(row=2, column=1, sticky="w", pady=4, padx=(8, 0))
        cur_pre = max(0, min(PREROLL_MS_MAX,
                             int(self.cfg.get("preroll_ms", 300))))
        self.preroll_var = tk.IntVar(value=cur_pre)
        self.preroll_var.trace_add("write", lambda *_: self._mark_dirty())
        ttk.Spinbox(pre_frame, from_=0, to=PREROLL_MS_MAX, increment=50,
                    textvariable=self.preroll_var, width=6).grid(row=0, column=0)
        ttk.Label(pre_frame, text=f" ms (0–{PREROLL_MS_MAX})").grid(row=0, column=1)
        ttk.Label(grp, text=HELP_PREROLL, style="Hint.TLabel",
                  wraplength=480, justify="left").grid(
            row=3, column=1, sticky="w", pady=(0, 6), padx=(8, 0),
        )

        ttk.Label(grp, text="Post-Roll").grid(row=4, column=0, sticky="w", pady=4)
        post_frame = ttk.Frame(grp)
        post_frame.grid(row=4, column=1, sticky="w", pady=4, padx=(8, 0))
        cur_post = max(0, min(POSTROLL_MS_MAX,
                              int(self.cfg.get("postroll_ms", 200))))
        self.postroll_var = tk.IntVar(value=cur_post)
        self.postroll_var.trace_add("write", lambda *_: self._mark_dirty())
        ttk.Spinbox(post_frame, from_=0, to=POSTROLL_MS_MAX, increment=50,
                    textvariable=self.postroll_var, width=6).grid(row=0, column=0)
        ttk.Label(post_frame, text=f" ms (0–{POSTROLL_MS_MAX})").grid(row=0, column=1)
        ttk.Label(grp, text=HELP_POSTROLL, style="Hint.TLabel",
                  wraplength=480, justify="left").grid(
            row=5, column=1, sticky="w", pady=(0, 4), padx=(8, 0),
        )

        # --- Gruppe „Darstellung" -------------------------------------
        grp = ttk.LabelFrame(parent, text="Darstellung", padding=LABELFRAME_INNER_PAD)
        grp.grid(row=3, column=0, sticky="ew")
        grp.columnconfigure(1, weight=1)
        ttk.Label(grp, text="Erscheinungsbild").grid(
            row=0, column=0, sticky="w", pady=4,
        )
        self.theme_labels = {"dark": "Dark", "light": "Light"}
        self.theme_var = tk.StringVar(
            value=self.theme_labels.get(self._current_theme, "Dark"),
        )
        ttk.Combobox(
            grp, textvariable=self.theme_var,
            values=list(self.theme_labels.values()), state="readonly",
        ).grid(row=0, column=1, sticky="ew", pady=4, padx=(8, 0))
        self.theme_var.trace_add("write", self._on_theme_change)
        ttk.Label(
            grp,
            text="Sun-Valley-Theme (Windows-11-Fluent-Look). Live-Umschaltung "
                 "ohne Neustart — wirkt sofort.",
            style="Hint.TLabel", wraplength=480, justify="left",
        ).grid(row=1, column=1, sticky="w", pady=(0, 4), padx=(8, 0))

    def _on_theme_change(self, *_) -> None:
        label = self.theme_var.get()
        new_theme = next(
            (k for k, v in self.theme_labels.items() if v == label),
            "dark",
        )
        if new_theme == self._current_theme:
            return
        self._apply_theme(new_theme)
        self._mark_dirty()

    # ------------------------------------------------------------ Modi-Tab

    def _build_modi_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)
        row = 0

        # Modus-Auswahl + Beschreibung
        ttk.Label(parent, text="Modus").grid(row=row, column=0, sticky="w", pady=4)
        self.mode_keys = list(cfg_mod.MODES.keys())
        self.mode_labels = [cfg_mod.get_mode_ui_name(k, self.cfg)
                            for k in self.mode_keys]
        cur_label = cfg_mod.get_mode_ui_name(self._current_mode_id, self.cfg)
        self.mode_var = tk.StringVar(value=cur_label)
        ttk.Combobox(parent, textvariable=self.mode_var,
                     values=self.mode_labels, state="readonly").grid(
            row=row, column=1, sticky="ew", pady=4,
        )
        row += 1

        self.mode_desc_var = tk.StringVar()
        ttk.Label(parent, textvariable=self.mode_desc_var, style="Hint.TLabel",
                  wraplength=480, justify="left").grid(
            row=row, column=1, sticky="w", pady=(0, 8),
        )
        row += 1

        # Anzeigename + Reset
        ttk.Label(parent, text="Anzeigename").grid(row=row, column=0, sticky="w", pady=4)
        name_frame = ttk.Frame(parent)
        name_frame.grid(row=row, column=1, sticky="ew", pady=4)
        name_frame.columnconfigure(0, weight=1)
        self.mode_name_var = tk.StringVar()
        self.mode_name_var.trace_add("write", lambda *_: self._mark_dirty())
        ttk.Entry(name_frame, textvariable=self.mode_name_var).grid(
            row=0, column=0, sticky="ew",
        )
        ttk.Button(name_frame, text="↺ Standard",
                   command=self._reset_current_mode).grid(
            row=0, column=1, padx=(8, 0),
        )
        row += 1
        ttk.Label(parent, text=HELP_MODE_NAME, style="Hint.TLabel",
                  wraplength=480, justify="left").grid(
            row=row, column=1, sticky="w", pady=(0, 6),
        )
        row += 1

        # Prompt-Textbox
        ttk.Label(parent, text="Prompt").grid(row=row, column=0, sticky="nw", pady=4)
        prompt_frame = ttk.Frame(parent)
        prompt_frame.grid(row=row, column=1, sticky="nsew", pady=4)
        parent.rowconfigure(row, weight=1)
        prompt_frame.columnconfigure(0, weight=1)
        prompt_frame.rowconfigure(0, weight=1)
        self.mode_prompt_text = tk.Text(prompt_frame, height=8, wrap="word")
        self.mode_prompt_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(prompt_frame, orient="vertical",
                               command=self.mode_prompt_text.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        self.mode_prompt_text.configure(yscrollcommand=scroll.set)
        self.mode_count_var = tk.StringVar()
        self.mode_count_label = ttk.Label(
            prompt_frame, textvariable=self.mode_count_var, style="Hint.TLabel",
        )
        self.mode_count_label.grid(row=1, column=0, sticky="e", pady=(2, 0))
        self.mode_prompt_text.bind("<<Modified>>", self._on_prompt_changed)
        row += 1
        ttk.Label(parent, text=HELP_MODE_PROMPT, style="Hint.TLabel",
                  wraplength=480, justify="left").grid(
            row=row, column=1, sticky="w", pady=(0, 8),
        )
        row += 1

        # Modus-Hotkey + Im-Cycle (Coupling via HotkeySection)
        row = self._hotkeys.build_mode_widgets(parent, row)

        # Initial-Load + Trace
        self._load_mode_into_editor(self._current_mode_id)
        self.mode_var.trace_add("write", lambda *_: self._on_mode_change())

    # ----------------------------------------------------------- Audio-Tab

    def _build_audio_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)

        grp = ttk.LabelFrame(parent, text="Eingabe-Gerät", padding=LABELFRAME_INNER_PAD)
        grp.grid(row=0, column=0, sticky="ew", pady=(0, PAD_Y_GROUP))
        grp.columnconfigure(0, weight=1)

        self.audio_devices = list_input_devices()
        self.audio_labels = [lbl for _, lbl in self.audio_devices]
        cur_dev = self.cfg.get("audio_device")
        cur_dev_label = next(
            (lbl for idx, lbl in self.audio_devices if idx == cur_dev),
            AUDIO_DEFAULT_LABEL,
        )
        self.audio_var = tk.StringVar(value=cur_dev_label)
        self.audio_var.trace_add("write", lambda *_: self._mark_dirty())
        ttk.Combobox(grp, textvariable=self.audio_var, values=self.audio_labels,
                     state="readonly").grid(row=0, column=0, sticky="ew", pady=4)
        ttk.Label(grp, text=HELP_AUDIO, style="Hint.TLabel",
                  wraplength=520, justify="left").grid(
            row=1, column=0, sticky="w", pady=(0, 6),
        )

        grp = ttk.LabelFrame(parent, text="Mikrofon testen", padding=LABELFRAME_INNER_PAD)
        grp.grid(row=1, column=0, sticky="ew")
        grp.columnconfigure(0, weight=1)
        self.mic_test_btn = ttk.Button(
            grp, text=f"🎤 Aufnahme starten ({MIC_TEST_DURATION_S}s)",
            command=self._on_mic_test,
        )
        self.mic_test_btn.grid(row=0, column=0, sticky="ew", pady=4)
        self.mic_status_var = tk.StringVar(value="")
        ttk.Label(grp, textvariable=self.mic_status_var, style="Hint.TLabel",
                  wraplength=520, justify="left").grid(
            row=1, column=0, sticky="w", pady=(4, 0),
        )

    # ------------------------------------------------------- Mode-Editor

    def _toggle_key_visible(self) -> None:
        self.api_key_entry.configure(
            show="" if self.show_key_var.get() else "*",
        )

    def _update_prompt_count(self) -> None:
        text = self.mode_prompt_text.get("1.0", "end-1c")
        n = len(text)
        over = n > MODE_PROMPT_SOFT_MAX
        self.mode_count_var.set(f"{n} / {MODE_PROMPT_SOFT_MAX} Zeichen")
        self.mode_count_label.configure(
            foreground=ERROR_FG_BY_THEME[self._current_theme] if over
            else HINT_FG_BY_THEME[self._current_theme],
        )

    def _on_prompt_changed(self, _event) -> None:
        self._update_prompt_count()
        self.mode_prompt_text.edit_modified(False)
        self._mark_dirty()

    def _read_editor(self) -> dict:
        return {
            "ui_name": self.mode_name_var.get(),
            "prompt": self.mode_prompt_text.get("1.0", "end-1c"),
        }

    def _load_mode_into_editor(self, mode_id: str) -> None:
        default = cfg_mod.get_mode_default(mode_id)
        default_name = default.get("ui_name", mode_id)
        default_prompt = default.get("prompt") or ""

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
        self.mode_desc_var.set(default.get("description", ""))
        self._update_prompt_count()

        # HotkeySection synchronisieren
        self._hotkeys.update_for_mode(mode_id)

    def _save_current_mode_edits(self) -> None:
        self._mode_edits[self._current_mode_id] = self._read_editor()

    def _reset_current_mode(self) -> None:
        self._mode_edits.pop(self._current_mode_id, None)
        default = cfg_mod.get_mode_default(self._current_mode_id)
        self.mode_name_var.set(default.get("ui_name", self._current_mode_id))
        self.mode_prompt_text.delete("1.0", "end")
        self.mode_prompt_text.insert("1.0", default.get("prompt") or "")
        self.mode_prompt_text.edit_modified(False)
        self._update_prompt_count()
        self.status_var.set("Modus auf Standard zurückgesetzt")
        self._mark_dirty()

    def _on_mode_change(self) -> None:
        new_id = self._selected_mode_key()
        if new_id == self._current_mode_id:
            return
        self._save_current_mode_edits()
        self._current_mode_id = new_id
        self._load_mode_into_editor(new_id)

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

    # --------------------------------------------------------- Dirty-Track

    def _mark_dirty(self) -> None:
        if not self._dirty:
            self._dirty = True
            self.status_var.set("● ungespeicherte Änderungen")

    def _clear_dirty(self, msg: str = "") -> None:
        self._dirty = False
        self.status_var.set(msg)

    # ------------------------------------------------------------- Save

    def _save_and_reload(self) -> bool:
        plain_key = self.api_key_var.get().strip()
        try:
            preroll = max(0, min(PREROLL_MS_MAX, int(self.preroll_var.get())))
        except (tk.TclError, ValueError):
            preroll = 300
        try:
            postroll = max(0, min(POSTROLL_MS_MAX, int(self.postroll_var.get())))
        except (tk.TclError, ValueError):
            postroll = 200

        self._save_current_mode_edits()
        new_overrides: dict[str, dict] = {}
        for mode_id, edit in self._mode_edits.items():
            default = cfg_mod.get_mode_default(mode_id)
            d_name = default.get("ui_name", mode_id)
            d_prompt = default.get("prompt") or ""
            override: dict = {}
            ename = (edit.get("ui_name") or "").strip()
            if ename and ename != d_name:
                override["ui_name"] = ename
            eprompt = edit.get("prompt") or ""
            if eprompt.strip() != d_prompt.strip():
                override["prompt"] = eprompt
            if override:
                new_overrides[mode_id] = override

        new_cfg: dict = dict(cfg_mod.DEFAULT_CONFIG)
        new_cfg.update(self.cfg)
        new_cfg["mode"] = self._selected_mode_key()
        new_cfg["paste_mode"] = self._selected_paste_key()
        new_cfg["audio_device"] = self._selected_audio_device()
        new_cfg["prebuffer_enabled"] = bool(self.prebuffer_var.get())
        new_cfg["preroll_ms"] = preroll
        new_cfg["postroll_ms"] = postroll
        new_cfg["mode_overrides"] = new_overrides
        new_cfg["manual_prompt"] = ""
        new_cfg["theme"] = self._current_theme
        new_cfg.pop("hotkey", None)
        # Hotkeys + cycle_loop schreibt die HotkeySection direkt ins dict
        self._hotkeys.apply_to_config(new_cfg)

        # Konflikt-Check
        conflicts = cfg_mod.find_hotkey_conflicts(new_cfg)
        if conflicts:
            from hotkey_capture import format_hotkey_for_display
            lines = [
                f"  • {format_hotkey_for_display(s)}: {a} ↔ {b}"
                for a, b, s in conflicts
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
        self._clear_dirty(f"Gespeichert. Reload: {reload_status}")
        return True

    def _on_apply(self) -> None:
        self._save_and_reload()

    def _on_save_close(self) -> None:
        if self._save_and_reload():
            self.root.after(1200, self.root.destroy)

    def _on_cancel(self) -> None:
        if self._dirty:
            if not messagebox.askyesno(
                "Änderungen verwerfen?",
                "Es gibt ungespeicherte Änderungen.\nWirklich verwerfen?",
            ):
                return
        self.root.destroy()

    # ----------------------------------------------------- Mikrofon-Test

    def _on_mic_test(self) -> None:
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
            self._set_mic_status_safe(f"Wiedergabe … (Pegel max {peak_pct}%)")
            sd.play(audio, samplerate=SAMPLE_RATE, device=device)
            sd.wait()
            level_hint = (
                "leise — sprich näher ans Mikro" if peak_pct < 20
                else "OK" if peak_pct < 80
                else "sehr laut — Abstand vergrößern"
            )
            self._set_mic_status_safe(
                f"Test fertig. Pegel max {peak_pct}% — {level_hint}"
            )
        except Exception as e:  # noqa: BLE001
            self._set_mic_status_safe(f"Mikrofon-Test fehlgeschlagen: {e}")
        finally:
            self.root.after(
                0, lambda: self.mic_test_btn.configure(state="normal"),
            )

    def _set_mic_status_safe(self, text: str) -> None:
        self.root.after(0, lambda: self.mic_status_var.set(text))

    # ------------------------------------------------------------- Run

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    SettingsWindow().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
