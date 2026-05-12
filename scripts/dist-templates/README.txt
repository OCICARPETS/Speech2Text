Speech2Text - Push-to-Talk-Diktiertool
========================================

Was es macht:
-------------
Caps Lock gedrueckt halten und sprechen, beim Loslassen wird die
Aufnahme an OpenAI gesendet, transkribiert, optional optimiert und
direkt ins aktive Fenster eingefuegt (Outlook, Word, CRM, Browser, ...).


Installation:
-------------
1. install.bat doppelklicken
2. Eventuell UAC-Dialog bestaetigen (nur bei Autostart-Eintrag)
3. Frage "Bei Windows-Anmeldung automatisch starten?" beantworten
4. Nach Abschluss: Doppelklick auf "Speech2Text" auf dem Desktop


Wichtig - SmartScreen-Hinweis beim ersten Start:
------------------------------------------------
Beim ersten Aufruf der Speech2Text-Exe meldet Windows ggf.:

    "Ihr PC wurde durch Windows geschuetzt"
    (SmartScreen-Warnung)

Das ist normal - Speech2Text ist nicht code-signiert (ein
EV-Zertifikat kostet 200-400 EUR pro Jahr, was fuer ein
internes Tool unverhaeltnismaessig ist).

So freigeben:
1. Auf "Weitere Informationen" klicken
2. Dann auf "Trotzdem ausfuehren"

Windows merkt sich die Freigabe pro Datei. Wenn ein Update kommt
und die Exe ersetzt wird, muss die Bestaetigung einmal erneut
erfolgen.


Erster Start - Konfiguration:
------------------------------
Ab v1.3: Beim allerersten Start oeffnet sich das Einstellungs-
Fenster AUTOMATISCH, damit der API-Key sofort eingerichtet wird.

1. Mikrofon-Symbol erscheint rechts unten im Systemtray
   (Tooltip: "API-Key fehlt - Einstellungen oeffnen")
2. Einstellungs-Fenster ist bereits offen
3. OpenAI API-Key eintragen (sk-...) - wird mit Windows-DPAPI
   verschluesselt gespeichert (nur dieser Windows-Account kann ihn
   wieder entschluesseln)
4. Optional: Optimierungs-Modus waehlen, Audio-Geraet, Pre-Roll usw.
5. "Speichern und Schliessen"
6. Der Daemon startet automatisch, der Tooltip wechselt zu "bereit"

Falls das Settings-Fenster nicht von selbst aufgeht: Rechtsklick
aufs Tray-Icon - "Einstellungen..."


Bedienung:
----------
- Caps Lock halten   = Aufnahme laeuft
- Caps Lock loslassen = Transkription + Optimierung + Text einfuegen
- Tray-Tooltip zeigt Status: bereit / Aufnahme / verarbeite

Hinweis: Caps Lock ist als Grossschreib-Toggle deaktiviert, solange
das Tool laeuft. Die Taste dient nur als Push-to-Talk.


Optimierungs-Modi:
------------------
Voreingestellte Modi (alle editierbar in den Einstellungen):
- Raw Draft        - Roh-Transkript ohne Optimierung
- Clean Dictation  - nur Fuellwoerter raus
- Polished Text    - Grammatik + Interpunktion
- Smart Flow       - geglaettete Satzuebergaenge
- Mirror Tone      - behaelt Sprachstil bei
- Warm and Friendly - freundlich umgeschrieben
- Executive        - Fuehrungssprache
- Unleashed        - intensive Tonalitaet
- Claude Code Prompt - fuer CLI-Coding-Agents
- Manuell          - eigener System-Prompt

Anzeigename und Prompt jedes Modus sind im Einstellungsmenue
ueber den Reset-Button auf den Standard zurueckstellbar.


Datenschutz und Daten:
----------------------
- Audio wird AUSSCHLIESSLICH im Speicher verarbeitet, nie auf Platte
- Konfiguration:    %APPDATA%\Speech2Text\config.json
- Logfile:          %APPDATA%\Speech2Text\daemon.log
                    (nur Status-Meldungen + Fehler, KEINE Transkripte)
- API-Key:          per Windows-DPAPI verschluesselt im config.json


Pre-Recording (Mikrofon permanent offen):
-----------------------------------------
Optional. Faengt das erste Wort vorab ab, falls man schon spricht
bevor man die Caps-Lock-Taste vollstaendig durchgedrueckt hat.
Trade-off: Windows zeigt dann durchgehend den Mikrofon-Indikator
im Systemtray (Datenschutz-Wahrnehmung).
Toggle im Einstellungsmenue.


Deinstallation:
---------------
- uninstall.bat im Installationsverzeichnis doppelklicken
  (%LocalAppData%\Programs\Speech2Text)
- Oder im Original-Setup-Verzeichnis
- Konfiguration unter %APPDATA%\Speech2Text bleibt erhalten -
  bei Bedarf manuell loeschen.


System-Voraussetzungen:
-----------------------
- Windows 10 oder 11 (64-bit, x64 oder ARM64 via x64-Emulation)
- Mikrofon
- OpenAI API-Key (https://platform.openai.com/api-keys)
- Internetverbindung fuer OpenAI-API-Calls
- KEIN Python, KEIN AutoHotkey separat noetig (alles im Bundle)


Verwendete Open-Source-Komponenten:
-----------------------------------
Speech2Text-Hotkey.exe nutzt pystray (LGPL-3.0) fuer das Tray-Icon
und Pillow (HPND/MIT-kompatibel) fuer die Icon-Verarbeitung. Details
und vollstaendige Liste: siehe LIZENZEN.txt im Installations-Ordner.


Fehlersuche:
------------
- "Daemon offline" im Tray? - Daemon laeuft nicht. Hotkey-Exe neu
  starten (kuemmert sich um Auto-Daemon-Start).
- "Aufnahme zu schnell hintereinander"? - Post-Roll-Fenster (Default
  200 ms) noch aktiv. Kurz warten.
- Logfile inspizieren: Tray - "Log oeffnen"


Versionshinweise / Updates:
---------------------------
Neuere Version: install.bat erneut ausfuehren - ueberschreibt
das Programm-Verzeichnis. Konfiguration bleibt erhalten.
