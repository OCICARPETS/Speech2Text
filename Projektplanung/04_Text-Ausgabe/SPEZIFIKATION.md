# SPEZIFIKATION: Text-Ausgabe (Clipboard + Auto-Paste)

*Status: ✅ MVP umgesetzt · Priorität: 1 · Erstellt: 2026-04-24*

---

## 1. Vision & Scope

Die **Text-Ausgabe** ist das sichtbare Ergebnis des Tools. Nachdem `gpt-4o-mini` den polierten Text geliefert hat, soll dieser ohne weitere Nutzeraktion im aktiven Fenster landen — dort, wo Daniel vor dem Diktat den Cursor hatte. Das Feature ist absichtlich redundant gestaltet: der Text wird **sowohl** in die Zwischenablage gelegt (Fallback für den Fall, dass Auto-Paste fehlschlägt) **als auch** per simuliertem `Ctrl+V` eingefügt.

## 2. Enthaltene Anforderungen / Use Cases

- **A1:** `pyperclip.copy(optimierter_text)` — Text landet in Windows-Zwischenablage.
- **A2:** Kurze Pause (~50 ms) zwischen Clipboard-Set und SendInput, damit das System-Clipboard den Text wirklich registriert hat.
- **A3:** `pyautogui.hotkey("ctrl", "v")` — sendet Ctrl+V ins aktive Fenster. Kein Fenster-Switch nötig, weil der Daemon keinen Fokus stiehlt (Console-Fenster bleibt inaktiv, User war in Texteditor/Outlook/etc.).
- **A4:** Paste geht in das Fenster, das beim Aufnehmen aktiv war — Daemon stiehlt nie den Fokus.
- **A5:** Bei Exception im Paste-Schritt: Text ist dennoch in Zwischenablage, User kann manuell Ctrl+V drücken.

## 3. Zielgruppe / Zielumgebung

- **Input:** String (optimierter Text) aus `03_KI-Pipeline`.
- **Zielumgebungen:** Alle Windows-Textfelder, die auf Standard-`Ctrl+V` reagieren — Outlook, Word, Edge, Chrome, VS Code, Notepad, Teams, WhatsApp Web, Slack-Desktop, CRM-Web-UI usw.

## 4. Abgrenzung

**Bewusst nicht im Scope:**
- **Keine Rich-Text-Formatierung** — reiner Plain-Text. Fettung/Kursiv gehen verloren.
- **Keine Clipboard-Historie** / Restore des vorigen Clipboard-Inhalts. Priorität-3 (opt-in).
- **Kein SendInput mit Unicode-Trick** — `pyautogui.hotkey` sendet echten `Ctrl+V`, also System-Clipboard wird genutzt. Alternative („type each character") ist langsam und bricht bei Umlauten in manchen Apps.
- **Kein Fallback auf Fenster-Aktivierung** — wenn Paste fehlschlägt (z.B. weil User zwischendurch das Fenster gewechselt hat), wird **nicht** versucht, das ursprüngliche Fenster wieder zu aktivieren.

## 5. Technische Skizze / Architektur

```python
def _paste() -> None:
    import pyautogui
    import time
    time.sleep(0.05)
    pyautogui.hotkey("ctrl", "v")
```

Aufruf-Reihenfolge in `_process()`:
```
optimiert = self._optimize(roh)       # Text bereit
pyperclip.copy(optimiert)             # Schritt 1: Clipboard
self._paste()                         # Schritt 2: Ctrl+V
```

### Warum aus Python, nicht aus AHK
Alternative wäre: AHK wartet auf Response vom Daemon und macht `Send ^v`. Aber:
- Der AHK-POST ist **async** (siehe `01_Hotkey-Trigger`) — keine Response zum Warten.
- Einen synchronen Callback-Kanal aufzubauen (AHK als Server, Python als Client) verdoppelt die IPC-Komplexität.
- `pyautogui.hotkey` braucht kein Admin und tut exakt dasselbe.

### Warum 50 ms Sleep
Windows-Clipboard ist asynchron. Unmittelbar nach `pyperclip.copy()` ist der Text technisch gesetzt, aber einige Zielapps (insbesondere Electron-basierte) pollen den Clipboard-Inhalt und können bei sehr schnellem `Ctrl+V` den alten Inhalt einfügen. 50 ms ist empirisch stabil und für den User unmerklich.

### Was bei Paste-Fehler passiert

- `pyautogui.hotkey` schlägt auf Windows praktisch nie fehl (es schickt die Keys einfach in die Input-Queue).
- Sollte doch eine Exception auftreten: sie fliegt aus `_paste()` raus, wird in `_process()` von `try/except` gefangen → Fehlerausgabe auf stderr, State zurück auf IDLE. Der Text ist trotzdem in der Zwischenablage.

## 6. Umsetzungsplan

- [x] `pyperclip.copy()` nach Optimierung
- [x] 50 ms Sleep vor Paste
- [x] `pyautogui.hotkey("ctrl", "v")`
- [x] Lazy-Import von `pyautogui` im Worker-Thread (nicht beim Modul-Load)
- [x] try/except in `_process()` fängt alle Pipeline-Fehler ab
- [ ] Manueller Test: Diktat in Outlook → Text erscheint im Editor-Fenster
- [ ] Manueller Test: Diktat in VS Code → Text erscheint an Cursor-Position
- [ ] Manueller Test: Diktat mit Umlauten (ÄÖÜß) → korrekt eingefügt
- [ ] Manueller Test: Fenster-Wechsel während Verarbeitung → Paste landet im neuen Fenster (Edge-Case akzeptabel)

## 7. Deployment

- Kein separates Deployment — Teil von `src/recorder.py`.
- `pyautogui` aus `requirements.txt`.

## 8. Offene Punkte und Entscheidungen

- [ ] **Auto-Paste abschaltbar?** Manche Zielumgebungen (z.B. Terminal-Apps) reagieren ungewöhnlich auf SendInput-Ctrl+V. Env-Variable `S2T_AUTO_PASTE=0` für nur-Clipboard-Modus?
- [ ] **Clipboard-Restore?** Opt-In: vorher vorhandenen Clipboard-Inhalt nach Paste wiederherstellen. Aufwand vs. Nutzen unklar — viele Clipboard-Tools (z.B. Windows+V Historie) lösen das systemweit.
- [ ] **Tray-Toast bei Erfolg?** Priorität 2 — „✔ Text eingefügt" als TrayTip. Aktuell nur Console-Log.
- [ ] **Umgang mit sehr langem Text?** 10-Minuten-Diktat = mehrere Absätze. Manche Editor-Apps (Outlook Mobile Web) setzen Ctrl+V nicht komplett auf einmal. Nicht im MVP-Scope.

## 9. Gotchas

- **`pyautogui` FAIL_SAFE:** Standardmäßig bricht `pyautogui` ab, wenn die Maus in die linke obere Ecke fährt. Für Hotkey-Betätigung irrelevant — wir bewegen keine Maus. Falls doch stört: `pyautogui.FAILSAFE = False`.
- **Tastatur-Layout:** `pyautogui.hotkey("ctrl","v")` sendet Virtual-Key-Codes, keine Zeichen — layout-unabhängig. ✅ Gut für deutsche Tastatur.
- **Clipboard während `pyperclip.copy()`:** Auf Windows nutzt `pyperclip` die Clipboard-API per `ctypes`. Bei Race-Conditions mit anderen Clipboard-Managern (ClipboardFusion, Ditto) kann es haken. Bisher nicht beobachtet.
- **Remote-Sessions / RDP:** Clipboard-Routing in RDP kann tricky sein. Für MVP nicht relevant (Daniel arbeitet lokal).

## 10. Historie & Verweise

- **Entstehung:** Briefing 2026-04-24. Output-Frage („nur Clipboard" vs. „Clipboard + SendInput") → User wählt **beides**.
- **Zugehörige Dateien:** `src/recorder.py` (Methoden `_process`, `_paste`).
- **Referenzen:**
  - `pyperclip` Docs: https://pyperclip.readthedocs.io/ (Stand 2026-04-24)
  - `pyautogui` Keyboard Control: https://pyautogui.readthedocs.io/en/latest/keyboard.html
