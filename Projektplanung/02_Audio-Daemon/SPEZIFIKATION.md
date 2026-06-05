# SPEZIFIKATION: Audio-Daemon (Python HTTP-Server + sounddevice)

*Status: ✅ produktiv · Priorität: 1 · Erstellt: 2026-04-24 · Erweitert: 2026-04-24 (Hidden-Modus, /shutdown, /health mit Fehler-Feldern) · 2026-06-05 (Stream-Health-Watchdog gegen RDP-Reconnect — §9)*

---

## 1. Vision & Scope

Der **Audio-Daemon** ist das Herzstück des Tools. Er läuft **persistent** (während der gesamten Arbeitssitzung), lauscht auf lokale HTTP-Signale vom AHK-Skript und verwaltet einen Audio-Aufnahme-Zustand. Er hält den OpenAI-Client und den sounddevice-Stream „warm", damit die Reaktion auf einen Tastendruck unter 50 ms bleibt. Ohne Daemon: bei jedem Tastendruck würde Python neu starten (Import `openai` + `sounddevice` dauert 1–2 s — unbrauchbar für Push-to-Talk).

## 2. Enthaltene Anforderungen / Use Cases

- **A1:** HTTP-Server auf `127.0.0.1:17321` — **nur** Localhost-Binding (nicht von außen erreichbar).
- **A2:** Endpoints:
  - `POST /start` → Audio-Aufnahme starten (ignoriert, wenn State ≠ IDLE)
  - `POST /stop` → Aufnahme stoppen und Verarbeitung in Worker-Thread anstoßen
  - `POST /shutdown` → Prozess beenden (Hard-Exit via `os._exit(0)` — s. Gotchas)
  - `GET /health` → Multi-Line-Response: `state=…`, `last_error=…`, `last_error_ts=…`
- **A3:** State-Machine: `IDLE → RECORDING → PROCESSING → IDLE`. Thread-safe per `threading.Lock`.
- **A4:** Audio-Parameter fest: **16 kHz Mono int16**. Ausreichend für Sprache, minimiert Upload-Volumen.
- **A5:** Audio **ausschließlich im Speicher** — keine Disk-Persistenz (Datenschutz, siehe `CLAUDE.md` Verbote).
- **A6:** Verarbeitung (OpenAI-Calls + Paste) läuft in **Worker-Thread**, damit `/stop` sofort mit 200 OK antwortet und AHK nicht blockiert.
- **A7:** Beim Start: `.env` laden, `OPENAI_API_KEY` prüfen. Fehlt der Key → klare Fehlermeldung und Exit-Code 2.
- **A8:** `Ctrl+C` sauber behandeln — Daemon räumt Stream auf und beendet.

## 3. Zielgruppe / Zielumgebung

- **Nutzer:** Python-Prozess als Hintergrund-Daemon (Console-Fenster offen während der Arbeit).
- **Plattform:** Windows 10/11 mit Python 3.11+ und funktionierendem Standard-Mikrofon.
- **Abhängigkeiten:** `sounddevice`, `numpy`, `openai`, `pyperclip`, `pyautogui`, `python-dotenv` (siehe `requirements.txt`).

## 4. Abgrenzung

**Bewusst nicht im Scope:**
- **Keine Audio-Persistenz** — kein Cache, kein Log-Dump. Audio lebt max. bis zum nächsten `IDLE`-Zustand.
- **Kein Audio-Pre-Processing** (Noise Reduction, Gain, AGC) — `gpt-4o-transcribe` ist robust genug.
- **Kein Multi-User / Multi-Session** — State ist global im Prozess. Bei zweiter Instanz würde Port-Binding fehlschlagen.
- **Kein HTTPS / Auth** — Binding auf `127.0.0.1` reicht; wer lokal Zugriff hat, darf triggern.

## 5. Technische Skizze / Architektur

### Komponenten

```
┌──────────────────────────────────────────────────────────┐
│  recorder.py (Single-Process)                            │
│                                                          │
│  ┌─────────────────┐     ┌───────────────────────────┐   │
│  │  HTTPServer     │────▶│  Recorder                 │   │
│  │  127.0.0.1:17321│     │  - state: IDLE/REC/PROC   │   │
│  │                 │     │  - stream: sounddevice    │   │
│  │  /start /stop   │     │  - chunks: list[np.array] │   │
│  │  /health        │     │  - client: OpenAI()       │   │
│  └─────────────────┘     └───────────────────────────┘   │
│                                     │                    │
│                                     ▼                    │
│                          ┌─────────────────────┐         │
│                          │  Worker-Thread      │         │
│                          │  _process()         │         │
│                          │  - WAV encode       │         │
│                          │  - transcribe       │         │
│                          │  - optimize         │         │
│                          │  - clipboard+paste  │         │
│                          └─────────────────────┘         │
└──────────────────────────────────────────────────────────┘
```

### State-Machine

```
 IDLE ──POST /start──▶ RECORDING ──POST /stop──▶ PROCESSING ──(Worker fertig)──▶ IDLE
   │                    │                           │
   │                    └─(erneutes /stop ignoriert)│
   └─(erneutes /start ignoriert)                   (erneutes /start ignoriert)
```

Grund für „ignorieren" statt „Fehler": Bei Taste runter+hoch+runter+hoch in Millisekunden-Folge (schnelle Eingabefehler) soll der Daemon nicht crashen.

### Audio-Pipeline

1. `sounddevice.InputStream(samplerate=16000, channels=1, dtype="int16", callback=...)`
2. Callback puffert jedes Chunk in `self._chunks: list[np.ndarray]`.
3. Bei `/stop`: Stream stoppen, `np.concatenate(chunks)` → finales Audio.
4. `wave`-Modul packt das Array in WAV-Bytes im Speicher (`io.BytesIO`).
5. WAV-Bytes gehen an OpenAI.

### Thread-Sicherheit

- `self._lock: threading.Lock` schützt State-Transitions.
- `self._chunks` wird nur vom sounddevice-Callback (schreibend) und vom Worker-Thread (lesend, nach `stream.stop()`) angefasst — keine Race durch Stop-Barrier.
- HTTP-Handler-Threads (`HTTPServer` ist per Default single-threaded — jede Anfrage sequenziell) lesen/schreiben nur via `recorder.start()` / `recorder.stop()` mit Lock.

## 6. Umsetzungsplan

- [x] HTTP-Server + Handler in `recorder.py`
- [x] Recorder-Klasse mit State + Lock
- [x] sounddevice-Callback sammelt Chunks
- [x] Worker-Thread ruft `_transcribe()` + `_optimize()` + `_paste()`
- [x] `.env`-Loading + Key-Check beim Start
- [x] Ctrl+C-Handler
- [ ] Manueller Test: Daemon starten, `curl -X POST http://127.0.0.1:17321/start` + `/stop` per curl
- [ ] Manueller Test: Aufnahme + Transkription laufen durch
- [ ] Manueller Test: 60-s-Aufnahme (OpenAI hat Limits — prüfen)

## 7. Deployment

- Manueller Start: `scripts\start-daemon.bat` (aktiviert ggf. venv, ruft `python src/recorder.py`).
- Port-Konflikt bei zweitem Start — klare Fehlermeldung erwünscht.
- Priorität-2: Autostart per Startup-Ordner (Shortcut auf `.bat`).

## 8. Offene Punkte und Entscheidungen

- [ ] **Audio-Gerät konfigurierbar?** Aktuell `sounddevice` nutzt Default-Input. Bei Dock-Wechsel (Headset vs. Webcam-Mikro) ggf. falsches Gerät. Lösung: Teil des Einstellungsmenüs (`05_Einstellungsmenue` A4), Default bleibt „Windows-Standard dynamisch".
- [ ] **Pre-Recording-Ringpuffer gegen Wort-Verschlucken** *(identifiziert 2026-04-24)*: Das erste Wort eines Diktats wird häufig abgeschnitten. Ursache: sounddevice-Stream-Startup-Latenz (~50–200 ms) + AHK→HTTP→Daemon-Latenz + User spricht zu früh nach Tastendruck. **Lösung:** Daemon hält den `InputStream` dauerhaft offen und einen Rolling-Ringpuffer (z. B. 500 ms) im Speicher. Bei `/start` werden die letzten 300–500 ms aus dem Puffer vor die eigentliche Aufnahme gehängt. Aufwand: mittel, berührt `Recorder.start()`/`_callback()`. Datenschutz beachten — Ringpuffer bleibt im RAM, wird bei `/shutdown` automatisch verworfen.
- [ ] **300-ms-Schwellwert als Kurz-Tipp-Schutz** *(2026-04-24)*: Im Worker-Thread nach `/stop` die Gesamtdauer der Aufnahme prüfen (`len(audio) / sample_rate`). Unter 300 ms → stiller Abort (kein OpenAI-Call, kein Fehler-Toast, State zurück auf IDLE). Spart API-Calls bei versehentlichem Caps-Lock-Antippen. Orthogonal zum Ringpuffer — prüft die *fertige* Aufnahme, verzögert nichts am Start.
- [ ] **Max-Dauer-Limit?** 60 s Hard-Limit im Daemon (automatischer Stop) gegen versehentliches Dauer-Diktat?
- [ ] **VU-Meter / Pegel-Anzeige?** Niceties für Priorität 2.
- [ ] **Daemon-Logging:** Aktuell `print()`. Bei Priorität 2 evtl. rotierendes Log — aber **ohne Transkript-Inhalte**.
- [ ] **OpenAI-Fehlerpfade:** Timeouts, Rate-Limits, Network-Outage — wie klar signalisieren? Aktuell: Console-Fehler, sonst still.

## 9. Gotchas

- **`sounddevice`-Buffer ist recycled:** Im Callback muss `indata.copy()` aufgerufen werden, sonst sieht man später Müll. ✅ Umgesetzt.
- **`np.concatenate` bei leerer Liste crasht:** Guard gegen leere `_chunks` vor Verarbeitung. ✅ Umgesetzt.
- **`HTTPServer` auf Windows:** Standard-Implementierung akzeptiert `Ctrl+C` manchmal erst nach nächstem Request. Für MVP akzeptabel.
- **Ports unter 1024 auf Windows:** Keine Admin-Rechte für `< 1024`. **17321** gewählt (unregistriert, unwahrscheinlich kollidiert).
- **`pyautogui` beim Import:** Macht DISPLAY-Checks. Lazy-Import im Worker-Thread verhindert Probleme, falls Daemon headless gestartet wird. ✅ Umgesetzt.
- **`server.shutdown()` beendet Python NICHT sauber** (entdeckt während Variante B): sounddevice/PortAudio und openai-SDK hinterlassen Non-Daemon-Threads (PortAudio-Worker, HTTP-Keep-Alive-Pool). Diese halten den Prozess am Leben, `pythonw.exe` bleibt als Zombie im Task-Manager, obwohl AHK schon beendet ist. **Fix:** Im `/shutdown`-Handler `os._exit(0)` in einem Delay-Thread (150 ms Grace-Time für Response-Bytes). Umgeht Python-Cleanup und killt alle Threads hart — unkritisch, weil wir nichts persistieren müssen.
- **Persistenter Prebuffer-Stream stirbt bei Geräte-Störung (RDP-Reconnect):** Auf Terminal-Servern ist das Mikro session-redirected; beim RDP-Disconnect verschwindet es, PortAudio meldet `[audio status] input overflow` und ruft `_on_audio` nicht mehr auf → der Daemon nimmt weiter „auf", bekommt aber leere `_chunks` („Keine Audiodaten"), bis man das Programm komplett neu startet (Daemon-Restart allein heilt nicht zuverlässig). **Fix (2026-06-05):** Stream-Health-Watchdog in `recorder.py` — `_last_audio_ts` (Lebenszeichen je Callback) + Thread `_stream_watchdog_loop`/`_maybe_recover_stream` öffnet den Stream bei Stillstand (> `STREAM_STALE_S=2 s` ohne Callback) automatisch neu, mit Retry bis wieder Frames kommen. `start()`-Guard weist Aufnahmen bei totem Stream **sichtbar** ab („Mikrofon wird neu verbunden — gleich nochmal") statt leer aufzunehmen. Pure-Logik `_should_reopen_stream()` (Tests `tests/test_recorder_stream_watchdog.py`), neue `/health`-Felder `audio_age`/`stream_recovering`. Live per RDP-Reconnect validiert.

## 9a. Hidden-Modus + File-Log (Scope-Erweiterung 2026-04-24)

Für Autostart (Variante B) darf kein CMD-Fenster aufpoppen. Daemon kann mit `--hidden` gestartet werden:

- Aufruf: `.venv\Scripts\pythonw.exe src\recorder.py --hidden` (s. `scripts\start-daemon-hidden.bat`)
- `pythonw.exe` (statt `python.exe`) erzeugt keine Console. Ohne Umleitung würden `print()`-Aufrufe crashen.
- `_setup_hidden_logging()` leitet `sys.stdout` + `sys.stderr` auf `%APPDATA%\Speech2Text\daemon.log` um (line-buffered, damit bei Crash die letzte Zeile auf Platte ist).
- Primitive Rotation: wenn `daemon.log` > 1 MB, wird sie zu `daemon.1.log` umbenannt (eine Generation, vorhandenes `.1.log` wird überschrieben).
- Sichtbare Variante (`start-daemon.bat` ohne `--hidden`) bleibt für Debugging erhalten.

## 9b. Endpoint-Erweiterungen (Scope-Erweiterung 2026-04-24)

### `/health` mit Fehler-Feldern

Ursprünglich lieferte `/health` nur `state=...`. Für den Fehler-Toast (siehe `03_KI-Pipeline` und `01_Hotkey-Trigger`) wurde das Response-Format auf Multi-Line erweitert:

```
state=idle
last_error=AuthenticationError: Incorrect API key
last_error_ts=1714000000.123
```

- Plain-Text (kein JSON) — AHK-Parsing ohne Library möglich per RegEx.
- `last_error` wird auf 200 Zeichen begrenzt und auf Newline/CR gestrippt, damit die Zeilen-Struktur nicht bricht.
- `last_error_ts` ist `time.time()` zur Fehlerzeit (0.0 wenn noch nie passiert).
- AHK merkt sich den zuletzt gesehenen TS und feuert `TrayTip` nur bei steigendem Wert.

### `/shutdown` (siehe auch Gotcha oben)

```python
elif self.path == "/shutdown":
    self._ok("bye")
    def hard_exit():
        time.sleep(0.15)
        os._exit(0)
    threading.Thread(target=hard_exit, daemon=True).start()
```

Hard-Exit nach 150 ms ist essenziell — sonst `pythonw.exe`-Zombie.

## 10. Historie & Verweise

- **Entstehung:** Briefing 2026-04-24. IPC-Mechanismus: Datei-Flag vs. Socket vs. HTTP → HTTP gewählt wegen AHK-Freundlichkeit.
- **Zugehörige Dateien:** `src/recorder.py`, `scripts/start-daemon.bat`
- **Referenzen:**
  - `sounddevice` Docs: https://python-sounddevice.readthedocs.io/ (Stand 2026-04-24)
  - `http.server` Stdlib: https://docs.python.org/3/library/http.server.html
  - IANA Port-Liste (17321 ist „unassigned"): https://www.iana.org/assignments/service-names-port-numbers/
