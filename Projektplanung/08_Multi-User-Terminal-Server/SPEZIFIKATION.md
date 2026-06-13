# SPEZIFIKATION — 08 Multi-User / Terminal-Server-Tauglichkeit

*Feature-Ordner: `Projektplanung/08_Multi-User-Terminal-Server/` · Erstellt: 2026-06-13 (Session 20) · Status: **✅ Implementiert (Ansatz B) + live bewiesen (2026-06-13)**. Offen: v1.5.0-Release; Folge-Themen Deployment + API-Key.*

Grundlage: Code-Analyse + 2-Session-Verifikation (Session 20) + Design-Panel (3 Architektur-Ansätze, Judge-Bewertung). Verwandte Memory: [[project_multiuser_port_kollision]], [[feedback_localhost_daemon_single_instance]].

---

## 1. Vision & Scope

Speech2Text soll weiteren OCI-Mitarbeitern auf dem **Windows-Terminal-Server** zur Verfügung stehen — mehrere Nutzer **gleichzeitig** per RDP angemeldet, jeder mit eigenem Diktat, eigenem Mikrofon, eigener Konfiguration. Heute ist das **nicht möglich und ein Datenschutz-Leak** (siehe §2).

**In-Scope (diese Spec):** Der **Architektur-Fix** der Laufzeit-Trennung — jede Windows-Session bekommt ihren eigenen, isolierten Daemon. Das ist der harte Blocker vor jedem Rollout.

**Folge-Themen (eigene Entscheidungen, hier nur skizziert):** Deployment-Mechanik für viele User (§8) und API-Key-/Kosten-Strategie (§9). Beide hängen vom Architektur-Fix ab, sind aber separat umsetzbar.

---

## 2. Problem (belegt, Session 20)

Der Daemon bindet `127.0.0.1:17321` (`recorder.py:42-43`) — **maschinenweit**, ohne Session-Ableitung, ohne Authentifizierung (`recorder.py` `do_POST`/`do_GET` routen nur nach `self.path`).

**Real verifiziert am 2026-06-13:**
1. **Nur ein Daemon maschinenweit:** Zweit-Daemon-Start → **Exit 3** (`WinError 10048`), Mikro nie angefasst (Bind-Gate vor Mikro). `allow_reuse_address=False` (Fix A, Session 19) macht das zur harten Sperre.
2. **Sitzungsübergreifend erreichbar:** Aus der `administrator`-Sitzung (anderes Konto, **keine** eigene Installation) lieferte `Invoke-RestMethod http://127.0.0.1:17321/health` **df's Daemon** (`mode=clean_dictation`, `prebuffer=on`).

**Folge bei Mehrbenutzerbetrieb:** Der zuerst gestartete Daemon „gewinnt" den Port für den ganzen Server. Jeder weitere Daemon stirbt am Bind → der Tray des Zweit-Users adoptiert via `/health` den **fremden** Daemon → Hotkey-Druck nimmt **fremdes Mikro** auf, Text landet in **fremder Zwischenablage/Fenster** (`recorder.py:289-295, 767, 841`). **Cross-Session-Leak in beide Richtungen.** Ironie: Genau der Single-Instance-Fix (Fix A) verschärft das, weil er den Zweit-User-Daemon zuverlässig killt.

**Was bereits sauber ist:** Config/Hotkeys/Modes/API-Key liegen pro User in `%APPDATA%\Speech2Text\` (`config.py:220`), API-Key DPAPI-user-gebunden (kein Fremd-Zugriff). Nur die **Laufzeit-Adressierung** bricht die Trennung.

---

## 3. Anforderungen

**Funktional:**
- **F1** — Jede gleichzeitig angemeldete Windows-Session bekommt ihren **eigenen** funktionierenden Daemon (kein „nur einer gewinnt").
- **F2** — Ein Tray spricht **ausschließlich** den Daemon **seiner** Session an; Fremd-Daemon-Adoption ist unmöglich.
- **F3** — Mikrofon, Transkription, Zwischenablage und Auto-Paste bleiben in der **auslösenden** Session (kein Cross-Session-Leak).
- **F4** — Der Single-Instance-Schutz **pro Session** bleibt erhalten: genau ein Daemon je Session hält das Mikro (Session-19-Garantie gegen Doppel-Daemon/Mic-Contention darf NICHT regredieren).
- **F5** — Der Test-Override `S2T_DAEMON_URL` behält Vorrang.

**Nicht-funktional:**
- **NF1** — Reconnect-stabil über RDP-Disconnect/Reconnect und Neulogin.
- **NF2** — Minimaler Eingriff, **keine** neue externe Dependency (nur stdlib: `os`, `ctypes`, `msvcrt`).
- **NF3** — Kein `config.json`-Schema-Bruch, DPAPI-Key unberührt.
- **NF4** — Diagnostizierbar (Session/Port im Log).

---

## 4. Zielumgebung

- Windows Server 2019, RDP-Mehrbenutzer (~10 aktive Sessions real beobachtet, Ziel bis ~30 Mitarbeiter).
- `%APPDATA%` muss **lokal** sein (kein umgeleitetes Roaming-Profil auf UNC — vgl. [[feedback_path_resolve_unc_falle]]). **Vor Umsetzung verifizieren.**
- Loopback `127.0.0.1` ist maschinenweit (nicht session-isoliert) — bestätigt in Session 20.

---

## 5. Architektur-Entscheidung

Drei Ausprägungen von „Trennung pro Session" wurden unabhängig entworfen und von einem Judge bewertet (Gewichtung: Robustheit + Wartbarkeit + Aufwand hoch, Sicherheit mittel — interne, vertrauenswürdige Nutzer):

| Ansatz | Mechanik | Gesamt | Kernschwäche |
|---|---|---|---|
| **A** SessionId-Port | `PORT = 17321 + SessionId` | 5.9 | SessionIds auf Terminal-Server nicht klein/dicht → Deckelung bricht Trennung; Port-Kollision = stilles Versagen |
| **B** Handshake-Datei ⭐ | Daemon bindet Port **0** (OS wählt frei), schreibt Port in `%APPDATA%\Speech2Text\daemon.port`; Tray liest ihn dort | **7.3** | Single-Instance muss von `allow_reuse_address` auf **Lockdatei + PID-Liveness** umgebaut werden |
| **C** B + Token | Wie B + Zufalls-Token in der Datei (ACL-geschützt), jeder Request braucht es | 6.3 | Für interne Nutzer ungenutzter Aufwand; schützt nicht gegen lokalen Admin/SYSTEM |

**Empfehlung (Judge + meine):** **Ansatz B jetzt umsetzen.** Er löst das eigentliche Problem (versehentlicher Cross-Session-Leak) **strukturell** — Port 0 + die ohnehin pro-User-getrennte `%APPDATA%`-Datei machen jede Session automatisch eigenständig, ohne Session-Arithmetik, ohne Kollisionsfenster. **Ansatz A** scheitert genau im Terminal-Server-Fall, für den er gedacht ist. **Ansatz C** (Token gegen *absichtlichen* Fremdzugriff) ist für eine vertrauenswürdige interne Belegschaft mit je eigenem Konto unnötig — und da B und C **dieselbe** Handshake-Datei nutzen, kostet die Token-Ergänzung später fast nichts. → **C bleibt als optionale spätere Härtung reserviert** (`token=`-Feld + 403-Guard), falls geteilte Maschinen mit gegenseitigem Misstrauen je real werden.

---

## 6. Technische Skizze (Ansatz B)

> **✅ UMGESETZT (2026-06-13, TDD, Suite 111/111 grün, live bewiesen).** Realisierte Code-Stellen:
> - **`src/handshake.py`** (NEU): `port_file_path`/`write_port`/`read_port`/`clear_port_file` (atomar via `os.replace`), `resolve_daemon_url`, `is_pid_alive` (OpenProcess + WaitForSingleObject — crash-/PID-reuse-sicher). Tests: `tests/test_handshake.py` (13).
> - **`recorder.py`**: Bind auf `(HOST, 0)` + `handshake.write_port(actual_port, getpid())` direkt nach Bind. Single-Instance über **Named Mutex `Local\Speech2Text-Daemon`** (`_acquire_/_release_single_instance_lock`) — **statt** der unten skizzierten Lockdatei (User-Wahl): atomar, session-isoliert (`Local\` = je RDP-Session), **crash-sicher** (OS gibt den Mutex bei Prozess-Ende frei, auch bei `os._exit`) → eliminiert R2 für den Lock. `clear_port_file` in `/shutdown` (vor `os._exit`) + `finally`. Tests: `tests/test_recorder_single_instance.py` (5).
> - **`daemon_client.py`**: `DAEMON_URL`-Konstante → `daemon_url()` (ENV-Override `S2T_DAEMON_URL` zuerst, sonst `handshake.resolve_daemon_url`); `_request` löst pro Call auf; `is_custom_url` auf ENV-Check. Tests: `tests/test_daemon_client.py` (13).
> - **`tray_app.py`**: `dc.daemon_url()`; neue `_maybe_clear_stale_port_file()` im Poll-Loop vor Daemon-Restart. Tests: `tests/test_tray_app.py` (11).
> - **Live bewiesen:** harter Cut deployt, Daemon auf zufälligem Port (z. B. 7993), Diktat funktioniert, `administrator`-Sitzung erreicht `127.0.0.1:17321` NICHT mehr (vorher = Leak). Mutex verhindert Doppel-Daemon trotz Kaltstart-Timeout.

*Die folgende Skizze ist der ursprüngliche Entwurf (Lockdatei-Variante); für den Single-Instance-Lock wurde stattdessen der Named Mutex gewählt (siehe oben).*

**Neues Modul `src/handshake.py`** (stdlib-only, Single Source für die Port-Datei; von `recorder.py` + `daemon_client.py` importiert):
- `port_file_path() -> Path` = `cfg_mod.config_dir() / "daemon.port"` (nutzt den vorhandenen per-User-Anker, kein zweiter `%APPDATA%`-Resolver).
- `write_port(port, pid)` — atomar: in `daemon.port.tmp` schreiben (`port=…\npid=…`, gleiches `key=value`-Format wie `/health`), dann `os.replace()`.
- `read_port() -> tuple[int,int] | None`; `is_pid_alive(pid) -> bool` (Win32 `OpenProcess`); `clear_port_file()`.
- `resolve_daemon_url(default_port=17321) -> str` — Datei → `http://127.0.0.1:<port>`; fehlt sie → Fallback auf Default-Port (Abwärtskompatibilität während Rollout, §7).

**`src/recorder.py`:**
- Bind auf `(HOST, 0)` statt `(HOST, PORT)` (`main()` ~Z.1069); `actual_port = server.server_address[1]`.
- **Direkt nach erfolgreichem Bind, vor Recorder/Mikro-Init** (Reihenfolge wie heute): `handshake.write_port(actual_port, os.getpid())`.
- **Single-Instance-Umbau (kritisch, F4):** `allow_reuse_address=False` trägt auf Port 0 nicht mehr (jeder Bind gelingt auf anderem Port). **Ersatz:** per-User-Lockdatei `daemon.lock` via `os.open(O_CREAT|O_EXCL)` bzw. `msvcrt.locking()` **vor** dem Bind. Schlägt sie fehl → in `daemon.port` hinterlegte PID prüfen: lebt sie → `return 3` (Daemon läuft schon); ist sie tot (Stale) → Lock übernehmen, alte Datei überschreiben. Im `finally`/Shutdown: `clear_port_file()` + Lock freigeben.
- Startup-Log um `Session <id> → Port <port>` ergänzen (NF4).

**`src/daemon_client.py`:**
- `DAEMON_URL`-Modul-**Konstante** → **Funktion** `daemon_url()`: ENV-Override `S2T_DAEMON_URL` zuerst, sonst `handshake.resolve_daemon_url()`. `_request()` löst die URL **pro Call** auf → folgt automatisch einem Port-Wechsel nach Daemon-Neustart. `is_custom_url()` auf ENV-Check umstellen. Betrifft 3 Tray-Call-Sites (`tray_app.py` ~:249/:380/:396).

**`src/tray_app.py`:**
- `dc.DAEMON_URL` → `dc.daemon_url()`. Health-Poll/Debounce/Re-Check bleiben. **Stale-Cleanup** im Poll-Loop: wenn `/health` fehlschlägt UND `daemon.port` auf toten PID zeigt → `clear_port_file()` vor Restart.

**`src/config.py`:** optional `PORT_FILENAME`/`LOCK_FILENAME`-Konstanten neben `CONFIG_FILENAME`. `config_dir()` unverändert wiederverwendet.

**Build:** `handshake.py` wird via Import automatisch gebündelt (`--paths .\src`); bei onefile Hidden-Import-Check. Keine neue PyPI-Dependency.

---

## 7. Umsetzungsplan (TDD, nach Freigabe)

1. **`handshake.py` + Unit-Tests** — write/read/clear-Roundtrip, `is_pid_alive` (lebt/tot), `resolve_daemon_url`-Fallback + ENV-Vorrang.
2. **Single-Instance-Umbau in `recorder.py`** (Lockdatei + PID-Liveness) — **höchstes Risiko (F4)**. Tests gegen das Startup-Race (Tray-Debounce 2 s < Daemon-Kaltstart ~6 s): zweiter Start bei lebendem PID → `return 3`; bei totem PID → übernimmt. Bind auf Port 0 + `write_port`.
3. **`daemon_client.py`** URL-Konstante → Funktion + `_request`-Auflösung pro Call + `is_custom_url`.
4. **`tray_app.py`** Call-Sites + Stale-Cleanup.
5. **Volle Suite grün** + `py_compile`. Build Daemon- **und** Tray-Exe (beide bündeln `handshake.py`).
6. **Manuelle 2-Session-Verifikation** auf dem Server: zwei gleichzeitige Konten, jeder diktiert → Text bleibt je in eigener Session, kein Leak (Gegenprobe zu Session-20-Stufe-A).

---

## 8. Deployment (Folge-Thema)

> **✅ UMGESETZT (2026-06-13, Option 2 zentral, → v1.5.1).** User-Wahl: Pilot (2-5 MA), zentrale Installation. Neue `scripts/dist-templates/install-admin.bat` (Programm → `%ProgramFiles%\Speech2Text`, Admin-Check via `net session`, KEIN maschinenweiter `taskkill`) + `install-user.bat` (Desktop-/Autostart-LNK auf die zentrale Exe, killt nur die eigene Sitzung, startet App). `uninstall.bat` deckt beide Install-Orte ab (zentral nur mit Admin). `README.txt` mit Wegen A (Einzelplatz) / B (Terminal-Server). `build-distribution.py` packt die neuen Skripte (verifiziert: im v1.5.1-ZIP enthalten). `install.bat` (per-User, Einzel-PC) bleibt abwärtskompatibel. **Offen: Test der zentralen Installation durch Admin (User) + ggf. GitHub-Release v1.5.1.**

Heute: per-User-`install.bat` → `%LocalAppData%`. Bei ~30 Usern liegt die App 30× (je ~90 MB).
**Empfohlen — Option 2:** Programm **einmal zentral** nach `%ProgramFiles%\Speech2Text` (read-only, einmalig Admin), pro User nur Autostart-LNK + Config in `%APPDATA%`. Updates an einer Stelle, Daten pro User getrennt. `install.bat` in Admin-Teil (Programm) + admin-freien User-Teil (LNK/Config) splitten; die maschinenweite `taskkill`-Logik entschärfen (darf keine Fremd-Session killen). Option 3 (GPO/Login-Script) nur bei Wunsch nach vollautomatischem, policy-gesteuertem Rollout.

---

## 9. API-Key / Kosten (Folge-Thema, Empfehlung)

Jeder Mitarbeiter braucht OpenAI-Zugang.
- **Kurzfristig — Option A (Status quo):** jeder eigener Key, DPAPI-pro-User. Beste Key-Isolation, exaktes Kosten-Tracking pro Mitarbeiter, schon implementiert. Nachteil: 30 Keys verwalten.
- **Abraten — gemeinsamer Klartext-Key:** verletzt die Secret-Regel, kein Kosten-Tracking, ein Leak trifft das ganze OCI-Konto.
- **Mittelfristig — Option C (OCI-Proxy/Gateway):** echter Key nur serverseitig, Kosten/Limits pro User zentral, an einer Stelle rotierbar. Passt zur Pilot-Rolle (später AussendienstAPP-Sprachnotizen). Höherer Bau-/Betriebsaufwand — sinnvoll ab dauerhaft >5–10 aktiven Nutzern.

---

## 10. Risiken & Test-Anforderungen

- **R1 (höchstes) — Single-Instance-Regression:** Der Lockdatei-Ersatz muss F4 exakt garantieren, sonst kehrt der Session-19-Doppel-Daemon/Mic-Contention-Bug zurück. Zwingend gegen das Startup-Race testen.
- **R2 — Stale-Datei + PID-Reuse:** `/shutdown` nutzt `os._exit(0)` ohne Cleanup (`recorder.py` ~:919) → Datei bleibt nach hartem Stop liegen; nach Reboot kann eine fremde PID die alte wiederverwenden. Mitigation: `pid`+Startzeit/`ts` mitschreiben **oder** Tray verwirft die Datei nach `/health`-Timeout trotz vermeintlich lebendem PID.
- **R3 — Start-Race / 17321-Fallback:** Zwischen `Popen` und `write_port` pollt der Tray gegen den 17321-Fallback — der ist maschinenweit und könnte während der Migration eine fremde Alt-Instanz treffen. Fallback **nur** während der Rollout-Phase aktiv lassen, im Folge-Release entfernen.
- **R4 — Migration:** Alte v1.4.2-Instanz (fester 17321) und neue (Port 0) kollidieren nicht am Port, könnten aber beide das Mikro öffnen (Contention). **Harter Cut:** alte Trays+Daemons beenden, dann neue Version starten (Trays vor Daemons, [[feedback_localhost_daemon_single_instance]]). VERSION-Bump Minor (z. B. 1.5.0, Protokoll-/Discovery-Änderung).
- **R5 — `%APPDATA%` auf UNC/Roaming:** würde pro-Request-Datei-Read verlangsamen — vorab prüfen (§4).

---

## 11. Offene Punkte — Entscheidungen für den User

1. ✅ **Architektur-Variante: ENTSCHIEDEN + UMGESETZT — Ansatz B** (User-Wahl 2026-06-13), Single-Instance über Named Mutex `Local\…`. Token (C) bleibt optionale spätere Härtung.
2. **Deployment:** Option 2 (zentral, empfohlen) vs. Status-quo (per-User) vs. GPO — *entscheidbar nach dem Architektur-Fix.*
3. **API-Key:** Option A jetzt (empfohlen), C später — *entscheidbar nach dem Architektur-Fix.*
4. **`%APPDATA%`-Lokalität** auf dem Server verifizieren (§4/R5).

---

## 12. Historie

- **2026-06-13 (Session 20) — Analyse & Design:** Code-Analyse (8-Agenten-Workflow, 3× adversarial bestätigt), 2-Session-Real-Test (Zweit-Daemon → Exit 3; `administrator`-Sitzung erreicht df's Daemon = Leak belegt), Design-Panel (3 Ansätze + Judge → Empfehlung B). Spec erstellt, User gibt Ansatz B frei.
- **2026-06-13 (Session 20) — Implementierung & Live-Beweis:** TDD-Umsetzung (4 Module, +~32 Tests, Suite **111/111**). Single-Instance auf Named Mutex `Local\…` umgestellt (User-Wahl statt Lockdatei — crash-sicher). Alle 3 Exes neu gebaut (Settings wegen `daemon_client`-Import mitgebaut), Frozen-Exe-Smoke perfekt (Port 0 → 64149, `daemon.port`, Mutex-Doppelstart → Exit 3). **Harter Cut deployt + Live-Test grün:** Diktat funktioniert, `administrator`-Sitzung erreicht 17321 nicht mehr (Cross-Session-Leak geschlossen). Offen: v1.5.0-Release, Folge-Themen Deployment + API-Key.
