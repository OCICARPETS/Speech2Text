# Arbeits-Workflow mit Claude — Speech2Text

> Leitfaden für Session-Rituale. Muster übernommen aus `aussendienst-app`, adaptiert für Python+AHK-Desktop-Tool.
>
> **Prinzip:** Claude hat begrenzten Kontext. Die Dateien in dieser Struktur sind
> die **externe Erinnerung** — damit nach `/clear` oder in einer neuen Session
> sofort klar ist, wo wir stehen.

---

## 🚀 Schnellbefehle (Slash-Commands)

### Universal — gelten in jedem Projekt

| Command | Wofür |
|---|---|
| `/checkpoint` | Stand prüfen, Scope-Verletzungen aufzeigen |
| `/session-ende` | Tag abschließen, current-task aktualisieren, Memory-Sync |

### Code-Standard — bei diesem Entwicklungsprojekt

| Command | Wofür |
|---|---|
| `/bugfix-done <Bereich>` | Kleinen Fix abschließen — SPEZ ergänzen, Commit, Push |
| `/feature-done <Name>` | Größeres Feature abschließen — SPEZ überarbeiten, FEATURE_UEBERSICHT, Commits, Push |

```
/checkpoint
/bugfix-done Audio-Daemon
/feature-done KI-Pipeline
/session-ende
```

> ⚠️ **Speech2Text ist aktuell noch ohne Git-Repo.** Die Code-Commands brechen ab,
> bis ein Repo eingerichtet ist (`git init` + GitHub-Remote). Solange greift
> nur der Universal-Set. Sobald Git da ist: ohne weitere Änderung nutzbar.

---

## 🟢 Session-Start

### Standard-Einstieg (immer am Anfang)

```
/checkpoint
```

Claude liest `tasks/current-task.md`, prüft Scope und meldet sich mit kurzer
Zusammenfassung. Kein sofortiges Losarbeiten.

Alternative (Langform):

```
Bitte lies zuerst tasks/current-task.md und CLAUDE.md.
Gib mir dann einen Einzeiler, wo wir stehen und was du vorschlägst als nächsten Schritt.
```

### Wenn ein bestimmtes Feature im Fokus ist

```
Heute arbeiten wir an {01_Hotkey-Trigger | 02_Audio-Daemon | 03_KI-Pipeline | 04_Text-Ausgabe}.
Lies tasks/current-task.md + Projektplanung/NN_.../SPEZIFIKATION.md.
```

### Nach längerer Pause (Tage/Wochen)

```
Ich war weg. Gib mir einen Überblick: PLANUNG.md Abschnitt „Aktueller Stand",
tasks/current-task.md, und welche Priorität-2-Features offen sind.
```

---

## 🔵 Während einer Session

### Wenn ich eine Entscheidung treffe

Entscheidungen landen in **zwei** Dateien:
1. In `PLANUNG.md` unter „Zentrale Entscheidungen" (mit Datum + Begründung)
2. Falls feature-spezifisch: in der `SPEZIFIKATION.md` des betroffenen Features

### Wenn neue Erkenntnisse aus Tests kommen

Erkenntnisse aus manuellen Tests (z.B. „OpenAI-Transcribe bricht bei > 10 s ab", „sounddevice wählt bei Dock-Wechsel falsches Mikro") **direkt in die passende SPEZIFIKATION.md** als Abschnitt „Gotchas" oder „Offene Punkte". Nicht nur im Chatfenster — sonst verloren nach `/clear`.

### Wenn der Scope unklar wird

```
Prüf nochmal gegen tasks/current-task.md — sind wir noch im Scope?
```

---

## 🟡 Nach einem Arbeitsschritt

### Teilschritt fertig

```
Update bitte tasks/current-task.md mit dem neuen Stand.
Memory-Eintrag falls etwas Dauerhaftes dabei ist (z.B. Modell-Wechsel, API-Versionsproblem).
```

### Feature-Deep-Dive weitergebracht

```
Ergänze das in Projektplanung/NN_.../SPEZIFIKATION.md. Prüfe ob
FEATURE_UEBERSICHT.md auch einen Hinweis braucht. Dann tasks/current-task.md aktualisieren.
```

### Code-Änderung gemacht

```
Aktualisiere tasks/current-task.md (was geändert, warum).
Wenn PLANUNG.md-relevant: auch dort „Zentrale Entscheidungen" ergänzen.
Kein Commit ohne explizite Freigabe.
```

---

## 🔴 Session-Ende

### Standard-Abschluss

```
/session-ende
```

Claude aktualisiert `tasks/current-task.md`, prüft SPEZIFIKATIONen, schreibt
Memory-Updates und gibt eine 3-Stichworte-Übersicht für morgen. Sobald Git da
ist: zusätzlich Commit/Push.

Alternative (Langform):

```
Wir hören hier auf. Bitte:
- tasks/current-task.md aktualisieren
- Memory-Update falls nötig
- Kurz sagen, was als nächstes ansteht
```

### Wenn viel passiert ist und Kontext voll

```
Mach einen Session-Abschluss. Ich werde dann /clear machen.
Stelle sicher, dass alle wichtigen Erkenntnisse in den richtigen .md-Dateien
stehen und nicht nur im Kontextfenster.
```

---

## ⚪ Welche Datei wofür

| Du willst… | → Datei |
|---|---|
| heute anfangen / Überblick | `tasks/current-task.md` |
| Regeln / Verbote nachschlagen | `CLAUDE.md` |
| Feature-Details verstehen | `Projektplanung/NN_.../SPEZIFIKATION.md` |
| Feature-Übersicht / Wunschliste | `Projektplanung/FEATURE_UEBERSICHT.md` |
| Installations-Schritte | `README.md` |
| Strategische Entscheidungen | `PLANUNG.md` Abschnitt „Entscheidungen" |
| OpenAI-Key / Umgebungsvariablen | `.env` (nicht committen!) + `.env.example` |

---

## 📏 Schreibregeln für `.md`-Dateien

- **200–400 Zeilen** pro Datei (Soft-Limit), max. **600** (Hard-Limit)
- Darüber: **splitten** oder entschlacken
- Neue Feature-Ordner: `Projektplanung/NN_Name/SPEZIFIKATION.md`
- **Sync-Pflicht:** Erkenntnisse aus Tests/Debugging **zeitnah** in die richtige Datei

---

## 🎯 Kurzphrasen für den Alltag

| Phrase | Was Claude tun soll |
|---|---|
| „Session-Start" | `tasks/current-task.md` + `CLAUDE.md` lesen, Status zurückspiegeln |
| „Stand checken" | Zusammenfassung aus PLANUNG.md + current-task.md |
| „{Feature X} vertiefen" | `SPEZIFIKATION.md` laden + mit mir durchgehen |
| „Scope prüfen" | Aktuelle Arbeit gegen `current-task.md` prüfen |
| „Daemon-Log anschauen" | User pasted Console-Output, Claude interpretiert |

---

## Pro-Tipp: Wann `/clear`?

**Ja, wenn:**
- Session läuft lang und viele Edits gemacht wurden
- Thema wechselt (z.B. KI-Pipeline → Autostart-Setup)
- Claude erfindet Kontext oder macht Fehler

**Nein, wenn:**
- Du mitten in einem Debugging bist (Kontext über Fehler-Chain verloren = schlecht)
- Session < 1 h alt

**Vor jedem `/clear`:** `/session-ende` ausführen — sichert alles in den
`.md`-Dateien (tasks/current-task, SPEZIFIKATION, Memory).

Nach `/clear`: `/checkpoint` — Claude steigt sofort wieder ein.
