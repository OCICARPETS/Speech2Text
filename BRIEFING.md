# BRIEFING — Speech2Text

*Erstellt: 2026-04-24 · Kategorie: Entwicklung*
*Abgeleitet aus: `vorlagen/briefing/entwicklung.md`*

> Das Briefing ist in einer kurzen, intensiven Abstimmung entstanden — keine vollständige Frage-Runde, weil der Scope vom User sehr präzise vorformuliert wurde. Die offengebliebenen Fragen sind in `PLANUNG.md` Abschnitt 5 dokumentiert.

---

## Allgemein

### A1. Was genau soll entwickelt werden?
Ein **Windows-Desktop-Tool** aus zwei Komponenten:
- **Python-Daemon** (`recorder.py`) — hält einen HTTP-Server auf `localhost:17321`, nimmt Audio auf, ruft OpenAI auf, schreibt in Zwischenablage, löst Auto-Paste aus.
- **AutoHotkey-Skript** (`shortcut.ahk`) — deaktiviert Caps-Lock-Standardfunktion, sendet bei Caps-Down ein `POST /start`, bei Caps-Up ein `POST /stop`.

### A2. Wer sind die Endnutzer?
**Eine Person:** Daniel Franken (GF OCI Carpets). Windows-Arbeitsplatz im Büro. Kein Multi-User-Betrieb vorgesehen.

### A3. Was ist das Kernproblem, das gelöst werden soll?
**Texteingabe kostet Zeit.** E-Mails, CRM-Notizen, Angebotstexte, Whatsapp-Antworten — alles wird getippt, obwohl Sprechen schneller wäre. Bestehende Diktat-Tools (Windows-Spracherkennung, Google Docs Voice Typing) sind entweder unzuverlässig oder brauchen Fenster-Wechsel.

---

## Technologie

### T1. Gibt es bereits eine Technologie-Vorgabe?
**Ja — vom User vorgegeben:**
- **Python** für Audio + OpenAI-Calls (`sounddevice`, `openai`, `pyperclip`, `python-dotenv`).
- **AutoHotkey** für den Hotkey (weil Windows-nativ, keine Admin-Rechte nötig, deaktiviert Caps-Lock sauber).

### T2. Braucht das Projekt eine Datenbank?
**Nein.** Keine Persistenz. Audio lebt nur im RAM. Optimierter Text landet in Zwischenablage und ist „weg", sobald der nächste Clipboard-Vorgang läuft.

### T3. Wo soll die Anwendung laufen?
**Ausschließlich lokal** auf Daniels Arbeitsplatz. Kein Server-Deploy, kein Azure, kein Docker.

### T4. Muss die Anwendung mit bestehenden Systemen integriert werden?
**Nein** (in dieser Phase). Später ggf. Übernahme der Transcribe-Pipeline in AussendienstAPP für Sprachnotizen — aber als eigenes Projekt.

---

## Oberfläche & Design

### D1. Mobile-First oder Desktop-First?
**Desktop-only** (Windows). Keine UI im klassischen Sinn — das Tool hat **kein Fenster**. Einzige sichtbare Komponenten:
- Console-Fenster des Python-Daemons (zeigt Status, Fehler).
- AHK-Skript als Tray-Icon (Standard-AHK-Icon; Custom Tray ist Priorität-2-Feature).

### D2. Soll das gleiche Design-System wie die AussendienstAPP verwendet werden?
**Nein** — keine Weboberfläche, kein Design-System.

### D3. Gibt es Branding-Vorgaben?
**Nein** — rein funktionales Tool für eine Person.

---

## Zugriff & Sicherheit

### S1. Wer darf die Anwendung nutzen?
**Nur der lokale Windows-User** (Daniel). HTTP-Daemon bindet an `127.0.0.1` — nicht von außen erreichbar.

### S2. Wie wird authentifiziert?
**Keine App-Authentifizierung.** Die einzige Auth-Grenze ist der OpenAI-API-Key (`.env`, gitignored). Wer Zugriff auf den Windows-Desktop hat, kann diktieren — aber das ist genau wie bei Windows-Diktat.

### S3. Gibt es sensible Daten die besonders geschützt werden müssen?
**Audio enthält potenziell sensible Inhalte** (Kunden-Infos, Preise, Personal-Themen). Maßnahmen:
- **Kein Disk-Write** von Audio — nur RAM.
- **Kein Log** des transkribierten Textes in Dateien.
- **OpenAI-DPA**: API-Daten werden nicht für Modelltraining verwendet (Stand 04/2026). Für hochsensible Inhalte (Personalakten, Verträge) trotzdem **nicht diktieren** — stattdessen tippen.

---

## Entwicklungsprozess

### E1. Soll ein Git-Repository auf GitHub angelegt werden?
**Noch nicht entschieden.** MVP zuerst lokal validieren, dann ggf. privates Repo unter `OCICARPETS`.

### E2. Gibt es ein bestehendes Repo das erweitert wird?
**Nein** — komplett neues Projekt.

### E3. Wie soll deployed werden?
**Kein klassisches Deployment.** „Deploy" = Dateien im Projekt-Ordner + `pip install -r requirements.txt` + AHK starten. Autostart bei Windows-Login ist ein Priorität-2-Feature.

---

## Scope & Priorisierung

### P1. Was ist der MVP (Minimum Viable Product)?
**4 Kern-Features** (alle ✅ im MVP):
1. **Hotkey-Trigger** — Caps Lock Push-to-Talk
2. **Audio-Daemon** — Aufnahme im Speicher
3. **KI-Pipeline** — `gpt-4o-transcribe` + `gpt-4o-mini`
4. **Text-Ausgabe** — Clipboard + Auto-Paste

Wenn Daniel Caps-Lock hält, spricht, loslässt → optimierter Text erscheint im aktiven Fenster. Fertig.

### P2. Welche Features sind Nice-to-have?
- Autostart bei Windows-Login
- Tray-Icon mit Status-Ampel
- Fehler-Toast bei Daemon-Ausfall
- Kontext-bewusste Optimierung (pro aktivem Fenster anderer Prompt)
- Diktat-Historie (opt-in)

### P3. Gibt es einen Zeitrahmen oder Deadline?
**Keine harte Deadline.** Persönliches Produktivitätstool — wird genutzt, sobald MVP läuft. Priorität-2-Features nach Bedarf.

---

## Erkenntnisse & Optimierungen

> Dieser Abschnitt wird nach Projektabschluss aktualisiert und fließt zurück in `vorlagen/briefing/entwicklung.md`.

| Datum | Erkenntnis |
|-------|-----------|
| 2026-04-24 | Bei klar vorformuliertem Scope reicht Kurz-Briefing (3 Rückfragen statt voller Fragen-Runde). Briefing-Vorlage könnte eine „Express-Option" bekommen, wenn der User bereits eine präzise Beschreibung mitliefert. |
