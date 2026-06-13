# CLAUDE.md — Speech2Text

Regeln, Patterns und Architektur-Entscheidungen für das Windows-Diktier-Tool mit Caps-Lock-Push-to-Talk und OpenAI-Transkription.

*Kategorie: Entwicklung · Erstellt: 2026-04-24*

---

## ⛔ Arbeitsregeln (höchste Priorität)

Diese Regeln gelten für **jede Session**, **jeden Tool-Call**. Sie überschreiben Gewohnheiten und „was sinnvoll wäre".

1. **Immer zuerst `tasks/current-task.md` lesen** — vor dem ersten Tool-Call, vor dem ersten Edit. Wenn die Datei fehlt: **sofort nachfragen**, welcher Scope gilt. Nicht „vorsichtshalber anfangen".

2. **Nur diesen Scope abarbeiten** — nichts, was nicht explizit in `current-task.md` steht. Auch kein „schnell noch X" während man gerade in der Datei ist.

3. **Nach `/clear` die Task-Datei erneut lesen** — komprimierter Kontext verliert Details. Erst Datei lesen, dann Scope in 1-2 Sätzen zurückspiegeln, dann weiterarbeiten.

4. **KEINE Änderungen an Dateien außerhalb des Tasks** — keine Typo-Fixes, keine Umstrukturierungen, keine Format-Anpassungen. Was nicht im Task steht, bleibt.

5. **KEINE eigenständigen Refactorings oder Zusatzrecherchen** — kein „while I'm here", kein „wäre konsequenter", keine Nebenarbeit ohne Freigabe.

6. **Verbesserungsideen: nur vorschlagen, NICHT umsetzen** — am Ende der Antwort als „💡 Vorschlag für später" erwähnen, dann stehenbleiben. Keine Umsetzung ohne explizite Freigabe.

7. **Bei Unsicherheit FRAGEN statt machen** — wenn Scope mehrdeutig ist, Annahmen nötig wären, mehrere Wege sinnvoll wären: **einmal zu viel fragen ist besser als einmal zu viel interpretieren**.

8. **Nach jedem Teilschritt Zwischenspeichern** — Dokument aktualisieren, ggf. Memory-Eintrag. Nicht in großen Rutschen erst am Ende. Insbesondere vor `/clear`.

9. **Scope-Wechsel nur durch User** — sagt der User „jetzt machen wir Y", muss `tasks/current-task.md` aktualisiert werden **bevor** die Y-Arbeit beginnt.

10. **Rückspiegelung:** Wenn Scope unklar oder groß, kurz in 1-2 Sätzen zurückspiegeln, was gleich getan wird, und auf Bestätigung warten.

### Wann diese Regeln brechen?

**Nie proaktiv.** Nur wenn der User explizit sagt „überschreib das" oder „ignorier current-task.md". Dann in der Antwort klar machen: „Ich verlasse den Scope auf deine Anweisung."

---

## ⛔ VERBOTE — Nicht tun

- **Keine Secrets im Code** — `OPENAI_API_KEY` ausschließlich in `.env` (gitignored). Nie committen, nie in Log-Ausgaben schreiben.
- **Keine eigenmächtigen Modellwechsel** — Transkription nutzt `gpt-4o-transcribe`, Optimierung nutzt `gpt-4o-mini`. Änderung nur auf ausdrücklichen Wunsch.
- **Keine Audio-Dateien auf Platte persistieren** — Audio läuft ausschließlich im Speicher (Datenschutz). Kein Cache, kein Log-Dump.
- **Kein Logging des transkribierten Textes in Dateien** — Konsolen-Ausgabe beim Debuggen ok, aber keine `history.log` oder ähnliches ohne explizite Freigabe.
- **Keine Änderungen am Caps-Lock-Verhalten ohne Rückfrage** — aktuell: dauerhaft deaktiviert als Großschreib-Toggle, nur Push-to-Talk-Trigger. Umstellung nur nach Bestätigung.
- **Kein `pip install` ohne Pin in `requirements.txt`** — reproduzierbare Umgebung. Neue Abhängigkeiten nur mit Versionsangabe.

---

## Projekt-Charakter

**Entwicklung**, Desktop-Tool für eine Person (GF). Kein Multi-User, kein Deployment, kein Server-Betrieb. Läuft lokal auf dem Windows-Arbeitsplatz.

**Unternehmen:** OCI Orient Carpet Import GmbH — Teppichgroßhändler, Coesfeld
**Firmendaten:** `../../../wissen/unternehmen/`
**IT-Infrastruktur:** `../../../wissen/infrastruktur/IT_UEBERSICHT.md`

**Zielnutzer:** Daniel Franken (GF). Windows-Arbeitsplatz, Produktivitätstool für E-Mails, Notizen, Berichte, beliebige Textfelder.
**Rolle dieses Projekts:** Persönliches Diktier-Tool zur Beschleunigung der Textarbeit. Pilot für den Umgang mit OpenAI-Audio-APIs — eventuell später als Modul in andere OCI-Anwendungen übernehmbar.

---

## Tech-Stack

| Schicht | Technologie | Zweck |
|---|---|---|
| **Hotkey** | AutoHotkey v2 | Caps-Lock Push-to-Talk, IPC zum Daemon via HTTP |
| **Daemon** | Python 3.11+ (`http.server` stdlib) | Localhost-HTTP-Server, hält Audio-Zustand und OpenAI-Client |
| **Audio** | `sounddevice` + `numpy` | Mikrofon-Input, 16 kHz, int16, Mono |
| **Transkription** | OpenAI `gpt-4o-transcribe` | Rohtext aus Audio |
| **Optimierung** | OpenAI `gpt-4o-mini` | Grammatik, Interpunktion, Füllwörter entfernt |
| **Clipboard** | `pyperclip` | Text in Windows-Zwischenablage |
| **Auto-Paste** | `pyautogui` (Ctrl+V) | Einfügen ins zuletzt aktive Fenster |
| **Konfiguration** | `python-dotenv` | `.env` → `OPENAI_API_KEY` |

**Architekturprinzip:** Python läuft als **persistenter Daemon** (kein Start pro Tastendruck). Der Tray feuert nur leichtgewichtige HTTP-Pings an `localhost:<Session-Port>/start` und `/stop`. Grund: Python-Import-Zeit ist zu hoch für Push-to-Talk; außerdem bleibt der OpenAI-Client + sounddevice-Stream warm.

**Multi-Session (Ansatz B, 2026-06):** Kein fester Port mehr. Der Daemon bindet **Port 0** (OS wählt einen freien Port) und hinterlegt ihn in der per-User-Datei `%APPDATA%\Speech2Text\daemon.port` (`src/handshake.py`); Tray/Client lesen ihn via `daemon_client.daemon_url()`. Single-Instance **pro Windows-Session** über den Named Mutex `Local\Speech2Text-Daemon` (nicht mehr über den Port-Bind). So bekommt jede gleichzeitig angemeldete RDP-Sitzung ihren eigenen Daemon — kein maschinenweiter Port, kein Cross-Session-Leak. Details: `Projektplanung/08_Multi-User-Terminal-Server/`.

---

## Konventionen

- **Sprache:** Deutsch (UI-Ausgaben, Doku, Kommentare). Variablennamen Englisch/Deutsch-Mix.
- **Kommunikation:** Viele Rückfragen, Schritte einzeln besprechen, ins Detail gehen.
- **Dokumentgröße:** 200–400 Zeilen pro `.md` (Soft-Limit), max 600 (Hard-Limit).
- **Feature-Ordner-Schema:** `Projektplanung/NN_Feature/SPEZIFIKATION.md` — nummeriert, ein Ordner pro Feature.
- **Code-Stil Python:** PEP 8, Type-Hints wo es hilft, Docstrings nur bei Modulen und öffentlichen Klassen.
- **Code-Stil AHK:** v2-Syntax (nicht v1!). `#Requires AutoHotkey v2.0` als erste Zeile.

---

## Positionierung / Strategische Anker

- **Produktivitäts-Multiplikator** für textlastige Arbeit — E-Mails, CRM-Notizen, Angebotstexte.
- **Kein ERP-Touch** — rein lokales Tool, keine C3SQL-Verbindung, kein Azure-Deploy.
- **Pilot für OpenAI-Audio** — Erkenntnisse fließen später in AussendienstAPP (Sprachnotizen zu Besuchsberichten).
- **Minimale Reibung** — eine Taste (Caps Lock), kein Fenster-Switch, kein Mausklick.

---

## Doku-Wegweiser

| Was | Wo |
|---|---|
| **Regeln & Pattern** (diese Datei) | `CLAUDE.md` |
| **Projekt-Vision / Roadmap / Entscheidungen** | `PLANUNG.md` |
| **Tagesstand / laufende Arbeit** | `tasks/current-task.md` |
| **Arbeits-Workflow / Session-Rituale** | `Projektplanung/WORKFLOW.md` |
| **Feature-Übersicht (Wunschliste)** | `Projektplanung/FEATURE_UEBERSICHT.md` |
| **Feature-Details (pro Feature)** | `Projektplanung/NN_Feature/SPEZIFIKATION.md` |
| **Briefing / User-Antworten** | `BRIEFING.md` |
| **Quick-Start / Installation** | `README.md` |
| **Python-Daemon-Code** | `src/recorder.py` |
| **AutoHotkey-Hotkey** | `src/shortcut.ahk` |
| **Dependencies** | `requirements.txt` |
| **Secret-Template** | `.env.example` |

### Dokumentations-Konventionen

- **`.md` Datei-Größe:** 200–400 Zeilen Soft-Limit, max. 600 Hard-Limit.
- **Feature-Ordner:** `Projektplanung/NN_Feature/SPEZIFIKATION.md` — nummeriert, ein Ordner pro Feature.
- **SPEZIFIKATION-Sektionen:** Vision & Scope · Anforderungen · Zielumgebung · Abgrenzung · Technische Skizze · Umsetzungsplan · Deployment · Offene Punkte · Historie.
- **Sync-Pflicht:** Neue Entscheidungen zeitnah in `PLANUNG.md` + relevanter `SPEZIFIKATION.md`. Memory ist Ergänzung, nicht Ersatz.

---

## Abhängigkeiten

- **AussendienstAPP:** potenzieller späterer Konsument (Sprachnotizen), aktuell keine harte Kopplung.
- **Wissen/Infrastruktur:** keine — Tool läuft lokal ohne Server-Touch.
