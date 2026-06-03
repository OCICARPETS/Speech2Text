"""Hotkey-Capture-Dialog für die Settings-GUI.

Modal-Dialog: User drückt eine Tasten-Kombi, wir bauen daraus eine AHK-v2-Spec
(`^!r` = Ctrl+Alt+R), validieren gegen `config.validate_hotkey()` und einen
Excludes-Set (Doppelbelegungen) und geben die Spec zurück.

Tracking der Modifier erfolgt manuell über keysym-Sets (KeyPress/KeyRelease) —
Windows-tkinter meldet `event.state` für Alt/Win unzuverlässig.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import config as cfg_mod

# keysym-Token, die als Modifier behandelt werden (Tasten dieser Sorte
# starten KEINE Hotkey-Erfassung; sie aktivieren nur die Modifier-Bits).
_MOD_KEYSYMS = {
    "Control_L", "Control_R",
    "Alt_L", "Alt_R", "Meta_L", "Meta_R",
    "Shift_L", "Shift_R",
    "Super_L", "Super_R", "Win_L", "Win_R",
}

# Modifier-keysym → AHK-Modifier-Char.
_MOD_KEYSYM_TO_AHK = {
    "Control_L": "^", "Control_R": "^",
    "Alt_L": "!", "Alt_R": "!", "Meta_L": "!", "Meta_R": "!",
    "Shift_L": "+", "Shift_R": "+",
    "Super_L": "#", "Super_R": "#", "Win_L": "#", "Win_R": "#",
}

# Spezial-Tasten-keysym → AHK-Token. Buchstaben (a-z) und Ziffern (0-9) und
# F-Tasten werden separat behandelt — siehe `_keysym_to_ahk_token`.
_SPECIAL_KEYSYM_TO_AHK = {
    "Caps_Lock": "CapsLock",
    "Pause": "Pause",
    "Insert": "Insert",
    "Scroll_Lock": "ScrollLock",
    "Num_Lock": "NumLock",
}


def _keysym_to_ahk_token(keysym: str) -> str | None:
    """Übersetzt einen tkinter-keysym in ein AHK-v2-Tasten-Token.
    Rückgabe: Token-String oder None bei nicht zugelassener Taste."""
    if keysym in _SPECIAL_KEYSYM_TO_AHK:
        return _SPECIAL_KEYSYM_TO_AHK[keysym]
    # F-Tasten: keysym = "F1".."F24"
    if (len(keysym) >= 2 and keysym[0] == "F"
            and keysym[1:].isdigit()):
        return keysym
    # Buchstaben: keysym = "a".."z" oder "A".."Z" (je nach Shift) — wir nutzen lowercase
    if len(keysym) == 1 and keysym.isalpha():
        return keysym.lower()
    # Ziffern
    if len(keysym) == 1 and keysym.isdigit():
        return keysym
    return None


def format_hotkey_for_display(spec: str | None) -> str:
    """AHK-v2-Spec → menschenlesbare Anzeige.

    `^!r` → `Ctrl + Alt + R`
    `F9`  → `F9`
    leer/None → `—`
    """
    if not spec:
        return "—"
    mods, key = cfg_mod._split_hotkey_spec(spec)
    parts: list[str] = []
    if "^" in mods:
        parts.append("Ctrl")
    if "!" in mods:
        parts.append("Alt")
    if "+" in mods:
        parts.append("Shift")
    if "#" in mods:
        parts.append("Win")
    if not key:
        return " + ".join(parts) if parts else "—"
    parts.append(key.upper() if len(key) == 1 else key)
    return " + ".join(parts)


def _build_spec(active_mods: set[str], key_token: str) -> str:
    """Baut eine AHK-v2-Spec in normalisierter Modifier-Reihenfolge."""
    chars = {_MOD_KEYSYM_TO_AHK[k] for k in active_mods if k in _MOD_KEYSYM_TO_AHK}
    ordered = "".join(m for m in cfg_mod.HOTKEY_MODIFIER_ORDER if m in chars)
    return ordered + key_token


class HotkeyCaptureDialog:
    """Modal-Dialog zur Hotkey-Erfassung.

    Public API:
        result = HotkeyCaptureDialog(parent, exclude=...).show()

    `result` ist die AHK-v2-Spec bei OK, None bei Abbruch.
    `exclude` ist ein Set normalisierter Hotkey-Strings, die als
    Doppelbelegung zurückgewiesen werden.
    """

    def __init__(
        self,
        parent: tk.Misc,
        *,
        title: str = "Hotkey erfassen",
        exclude: set[str] | None = None,
        slot_label: str = "",
    ) -> None:
        self._parent = parent
        self._exclude = set(exclude or ())
        self._active_mods: set[str] = set()
        self._candidate_spec: str | None = None
        self.result: str | None = None

        self._win = tk.Toplevel(parent)
        self._win.title(title)
        self._win.geometry("420x220")
        self._win.resizable(False, False)
        self._win.transient(parent)
        self._win.grab_set()

        outer = ttk.Frame(self._win, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)

        if slot_label:
            ttk.Label(
                outer, text=f"Slot: {slot_label}", style="Hint.TLabel",
            ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        ttk.Label(
            outer,
            text=("Drücke jetzt die gewünschte Taste oder Tasten-"
                  "Kombination. Esc bricht ab."),
            wraplength=380, justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(0, 10))

        self._preview_var = tk.StringVar(value="(noch keine Eingabe)")
        ttk.Label(
            outer, textvariable=self._preview_var,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=2, column=0, sticky="w", pady=(0, 6))

        self._error_var = tk.StringVar(value="")
        ttk.Label(
            outer, textvariable=self._error_var, style="Error.TLabel",
            wraplength=380, justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(0, 10))

        btn_frame = ttk.Frame(outer)
        btn_frame.grid(row=4, column=0, sticky="ew")
        btn_frame.columnconfigure(0, weight=1)
        ttk.Button(btn_frame, text="Abbrechen", command=self._on_cancel).grid(
            row=0, column=1, padx=(0, 6),
        )
        self._ok_btn = ttk.Button(btn_frame, text="OK", command=self._on_ok,
                                  state="disabled")
        self._ok_btn.grid(row=0, column=2)

        self._win.bind("<KeyPress>", self._on_key_press)
        self._win.bind("<KeyRelease>", self._on_key_release)
        # Esc fängt _on_key_press über das normale KeyPress-Handling ab —
        # zusätzlich expliziter Bind, falls Fokus woanders ist.
        self._win.bind("<Escape>", lambda _e: self._on_cancel())

        # Damit KeyPress/KeyRelease ankommen
        self._win.focus_set()

    # --- Event-Handling ---------------------------------------------------

    def _on_key_press(self, event: tk.Event) -> str | None:
        ks = event.keysym
        if ks == "Escape":
            self._on_cancel()
            return "break"
        if ks in _MOD_KEYSYMS:
            self._active_mods.add(ks)
            self._update_live_preview()
            return "break"
        # Non-Modifier-Taste → Kandidat bauen
        token = _keysym_to_ahk_token(ks)
        if token is None:
            self._error_var.set(f"Taste '{ks}' ist nicht zugelassen.")
            self._candidate_spec = None
            self._ok_btn.configure(state="disabled")
            return "break"
        spec = _build_spec(self._active_mods, token)
        ok, reason = cfg_mod.validate_hotkey(spec)
        if not ok:
            self._preview_var.set(format_hotkey_for_display(spec))
            self._error_var.set(reason)
            self._candidate_spec = None
            self._ok_btn.configure(state="disabled")
            return "break"
        norm = cfg_mod.normalize_hotkey(spec)
        if norm in self._exclude:
            self._preview_var.set(format_hotkey_for_display(spec))
            self._error_var.set("Diese Kombi ist schon einem anderen Slot zugewiesen.")
            self._candidate_spec = None
            self._ok_btn.configure(state="disabled")
            return "break"
        # Erfolg: Vorschau + OK aktiv
        self._preview_var.set(format_hotkey_for_display(spec))
        self._error_var.set("")
        self._candidate_spec = spec
        self._ok_btn.configure(state="normal")
        return "break"

    def _on_key_release(self, event: tk.Event) -> str | None:
        ks = event.keysym
        if ks in _MOD_KEYSYMS:
            self._active_mods.discard(ks)
            # Live-Preview nur, wenn noch kein Kandidat steht — sonst
            # bleibt die fertige Spec sichtbar bis OK/Abbrechen.
            if self._candidate_spec is None:
                self._update_live_preview()
        return None

    def _update_live_preview(self) -> None:
        if not self._active_mods:
            self._preview_var.set("(noch keine Eingabe)")
            return
        chars = {_MOD_KEYSYM_TO_AHK[k] for k in self._active_mods
                 if k in _MOD_KEYSYM_TO_AHK}
        ordered = "".join(m for m in cfg_mod.HOTKEY_MODIFIER_ORDER if m in chars)
        # Display ohne Tasten-Token: "Ctrl + Alt + …"
        self._preview_var.set(format_hotkey_for_display(ordered) + " + …")

    def _on_ok(self) -> None:
        if self._candidate_spec:
            self.result = self._candidate_spec
            self._win.destroy()

    def _on_cancel(self) -> None:
        self.result = None
        self._win.destroy()

    def show(self) -> str | None:
        self._win.wait_window()
        return self.result
