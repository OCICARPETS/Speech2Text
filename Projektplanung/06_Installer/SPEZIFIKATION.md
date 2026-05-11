# SPEZIFIKATION: Installer / Portable Distribution

*Status: 🔜 Geplant · Priorität: 2 · Erstellt: 2026-04-24*

---

## 1. Vision & Scope

Speech2Text soll auf jedem OCI-Windows-PC in **zwei Klicks** lauffähig sein — ohne Python-Installation, ohne AutoHotkey-Installation, ohne `pip`-Befehle, ohne Verzeichnis-Editing. Ein klassischer Windows-Installer (`Speech2Text-Setup.exe`) legt alles am richtigen Ort ab, richtet Autostart ein und öffnet das Einstellungsfenster (siehe `05_Einstellungsmenue`) für die erste API-Key-Eingabe.

## 2. Enthaltene Anforderungen / Use Cases

- **A1:** Ein einziges `.exe` reicht dem Endanwender — keine Python-/AHK-Vorinstallation nötig.
- **A2:** Standard-Installationspfad `C:\Program Files\Speech2Text\` (Adminrechte für Install, nicht für Betrieb).
- **A3:** Autostart-Eintrag wahlweise bei Install (Checkbox im Installer) oder später per Einstellungsmenü.
- **A4:** Start-Menü-Einträge: „Speech2Text starten", „Speech2Text Einstellungen", „Speech2Text deinstallieren".
- **A5:** Nach Install öffnet sich automatisch das Einstellungsmenü zur API-Key-Eingabe (Daemon startet nicht, solange kein Key hinterlegt ist).
- **A6:** Sauberer Uninstall: Alle Dateien unter `C:\Program Files\Speech2Text\` weg, Autostart-Eintrag weg, `%APPDATA%\Speech2Text\` **bleibt** (damit bei Neuinstallation Config erhalten ist — Opt-out per Checkbox).
- **A7:** Versioniert: Installer trägt Versionsnummer, Updates ersetzen alte Version in-place.
- **A8:** Offline-Installationsfähig — keine Internetverbindung beim Install nötig (OpenAI-Key kommt danach).

## 3. Zielgruppe / Zielumgebung

- **Installer-Nutzer:** IT-affine Endanwender bei OCI. Kein Dev-Hintergrund.
- **Plattform:** Windows 10/11 (64-bit).
- **Rechte:** Install benötigt Admin (für `Program Files`), Betrieb nicht.

## 4. Abgrenzung

- **Kein MSI** — Inno Setup produziert `.exe`, das reicht für interne Verteilung. MSI wäre nötig bei Ausrollung via SCCM/Intune.
- **Kein Auto-Update-Mechanismus** im MVP — Updates kommen als neuer Installer per Mail/Netzlaufwerk. Auto-Update ist Priorität 3.
- **Keine Code-Signierung** im ersten Wurf (OCI-internes Tool → SmartScreen-Warnung akzeptabel). Bei externer Distribution später mit Code-Signing-Zertifikat.

## 5. Technische Skizze / Architektur

### Drei Bausteine

```
┌─────────────────────┐     ┌──────────────────────┐     ┌───────────────────────┐
│  PyInstaller        │     │  Ahk2Exe             │     │  Inno Setup           │
│                     │     │                      │     │                       │
│  recorder.py        │     │  shortcut.ahk        │     │  bündelt alle EXEs,   │
│  settings.py        │──▶──│                      │──▶──│  legt Autostart-Link, │
│  config.py          │     │  → hotkey.exe        │     │  Start-Menü, Uninst.  │
│                     │     │  (AutoHotkey self-   │     │                       │
│  → daemon.exe       │     │   contained)         │     │  → Speech2Text-Setup  │
│  → settings.exe     │     │                      │     │    .exe               │
└─────────────────────┘     └──────────────────────┘     └───────────────────────┘
```

### PyInstaller-Konfiguration (Entwurf)

```
pyinstaller src/recorder.py \
  --name speech2text-daemon \
  --onefile \
  --windowed \
  --icon assets/speech2text.ico \
  --add-data "assets;assets"
```

`--windowed` statt Console-App → kein CMD-Fenster im Hintergrund. Logs gehen dann in Datei (siehe Open Points).

### Inno Setup `.iss` (Skizze)

- Installation: `{pf}\Speech2Text\`
- Dateien: `speech2text-daemon.exe`, `speech2text-settings.exe`, `speech2text-hotkey.exe`, README, License.
- Autostart: optional, schreibt Shortcuts in `{commonstartup}` oder Registry-Key `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
- Nach Install: `[Run]`-Sektion startet `speech2text-settings.exe` für API-Key-Eingabe.

### Versionierung

- Version in `version.py` des Python-Codes (`__version__ = "0.1.0"`).
- Inno-Setup liest via Pre-Build-Script aus `version.py`.
- Installer-Dateiname: `Speech2Text-Setup-0.1.0.exe`.

## 6. Umsetzungsplan

### Phase 1 — PyInstaller-Bundle für Daemon
- [ ] `speech2text.spec` schreiben (mit hidden imports, data files).
- [ ] Erster Build: `pyinstaller speech2text.spec` → `dist/speech2text-daemon.exe` testen.
- [ ] Fallstricke: `sounddevice` braucht `_sounddevice_data/portaudio.dll` — mit `--collect-binaries sounddevice` einschließen.

### Phase 2 — Settings-App paketieren
- [ ] `speech2text-settings.exe` Build parallel (eigene Spec).
- [ ] tkinter ist Stdlib, kein Extra-Handling nötig.

### Phase 3 — AHK kompilieren
- [ ] `Ahk2Exe.exe shortcut.ahk → speech2text-hotkey.exe`.
- [ ] Flag `/bin` auf Unicode-64-Version.

### Phase 4 — Inno Setup
- [ ] `installer.iss` mit Version-Injection.
- [ ] Test-Install auf sauberem Windows (VM).
- [ ] Test-Uninstall.
- [ ] Test-Update (alte Version → neue Version, Config bleibt).

### Phase 5 — Distribution
- [ ] Installer ins OCI-Netzlaufwerk (oder internen SharePoint) legen.
- [ ] Installations-Anleitung für Endanwender (eine Seite, Screenshots).

## 7. Deployment

- **Build-Host:** Lokaler Entwicklungsrechner mit Python 3.13 (Kompatibilität zu PyInstaller 6.x am besten) — evtl. Umstieg von 3.14 auf 3.13 für Build notwendig. Check beim Phase-1-Build.
- **Target:** OCI-Windows-Clients, per Netzlaufwerk/Mail verteilt.

## 8. Offene Punkte und Entscheidungen

- [ ] **Python 3.13 oder 3.14 für Build?** 3.14 ist brandneu, PyInstaller-Support könnte noch nicht komplett sein. Beim ersten Build-Versuch klären; ggf. paralleles 3.13-venv.
- [ ] **`--windowed` vs Console-App?** Ohne Console kein Live-Log-Fenster — dafür File-Logging in `%APPDATA%\Speech2Text\log.txt` (letzte 100 Zeilen). Ohne Transkript-Inhalte!
- [ ] **PortAudio DLL:** Manche Windows-Installationen haben Konflikte. Bundle-Strategie testen.
- [ ] **SmartScreen-Warnung:** Ohne Code-Signing meldet Windows den Installer als „Unbekannter Herausgeber". Für OCI-intern: User-Akzeptanz via kurze Doku. Für extern: EV-Cert kaufen.
- [ ] **Update-Strategie:** Manuell pro neuem Installer reicht initial. Später evtl. „Auf Updates prüfen"-Knopf im Einstellungsmenü, der eine Versions-Datei auf dem Netzlaufwerk liest.
- [ ] **AHK-Autostart via Dateizuordnung?** Alternative: keinen kompilierten `hotkey.exe`, sondern AHK v2 Runtime mitliefern und `.ahk`-Datei starten. Trade-off: Runtime ~3 MB extra, dafür User kann `shortcut.ahk` editieren.

## 9. Abhängigkeiten / Querverweise

- **Voraussetzung:** Config-Layer (`05_Einstellungsmenue` Phase 1) — Installer darf keine `.env`-Datei vom User erwarten.
- **Kein Breaking Change** am Daemon nötig, wenn Config-Layer da ist — gleiche `recorder.py`, nur als `.exe` verpackt.

## 10. Historie & Verweise

- **Entstehung:** User-Wunsch 2026-04-24 — Tool soll auf anderen lokalen Clients installierbar sein.
- **Zugehörige Features:** `05_Einstellungsmenue` (API-Key + Präferenzen), alle vier MVP-Features (werden gebündelt).
- **Referenzen:**
  - PyInstaller Docs: https://pyinstaller.org/en/stable/
  - Inno Setup: https://jrsoftware.org/isinfo.php
  - Ahk2Exe: https://www.autohotkey.com/docs/v2/Scripts.htm#ahk2exe
