# Speech2Text — Anleitung für Pilot-Nutzer

*Diktier-Tool für den Terminal-Server · Stand: v1.5.1 (2026-06-13)*

Mit Speech2Text diktierst du Text per Tastendruck: **Caps Lock gedrückt halten, sprechen, loslassen** — der gesprochene Text wird automatisch sauber formatiert und ins aktive Fenster eingefügt (E-Mail, Word, CRM, Browser …). Jeder Nutzer arbeitet komplett für sich (eigenes Mikrofon, eigene Einstellungen) — andere Sitzungen bekommen davon nichts mit.

---

## 1. Einrichtung (einmalig, ohne Admin-Rechte)

Das Programm ist bereits zentral auf dem Server installiert. Du musst es nur für dein Benutzerkonto aktivieren:

1. Öffne den Ordner **`C:\Program Files\Speech2Text`**.
2. Doppelklick auf **`install-user.bat`**.
3. Das Fenster meldet „Einrichtung abgeschlossen" und startet Speech2Text. Rechts unten erscheint ein **Mikrofon-Symbol** (Systray, ggf. unter dem `^`-Pfeil).

> Ab jetzt startet Speech2Text bei jeder Anmeldung automatisch.

---

## 2. Beim allerersten Start

- Es öffnet sich automatisch das **Einstellungs-Fenster** (Tooltip am Symbol: „API-Key fehlt").
- Falls eine **SmartScreen-Warnung** kommt („Ihr PC wurde durch Windows geschützt"): auf **„Weitere Informationen" → „Trotzdem ausführen"** klicken. Das ist normal (internes Tool ohne kostenpflichtiges Zertifikat) und nur einmal nötig.

---

## 3. API-Key eintragen (einmalig)

Speech2Text nutzt OpenAI für die Spracherkennung. Dafür brauchst du deinen **persönlichen API-Key**:

1. Den Key bekommst du von **Daniel Franken / der IT** (beginnt mit `sk-…`).
2. Im Einstellungs-Fenster im Feld **OpenAI-API-Key** einfügen.
3. **„Speichern & Schließen"**.

> Der Key wird mit Windows verschlüsselt gespeichert und ist **nur für dein Konto** lesbar — kein anderer Nutzer und kein Administrator kann ihn sehen.

Das Mikrofon-Symbol zeigt danach den Tooltip **„bereit"**.

---

## 4. Diktieren

- **Caps Lock gedrückt halten** → sprechen → **loslassen**.
- Der Text wird transkribiert, optimiert und automatisch ins zuletzt aktive Fenster eingefügt.
- Der Tooltip am Symbol zeigt den Status: *bereit / Aufnahme / verarbeite*.

> Solange das Tool läuft, ist Caps Lock **nur** die Diktier-Taste (kein Großschreib-Umschalter mehr).

---

## 5. Modi (Schreibstil)

Über das Tray-Menü oder die Einstellungen wählbar — die wichtigsten:

| Modus | Wirkung |
|---|---|
| **Clean Dictation** | nur Füllwörter raus, sonst wortgetreu (Standard) |
| **Polished Text** | Grammatik + Interpunktion geglättet |
| **Raw Draft** | reines Roh-Transkript ohne Optimierung |
| **Executive** | Führungssprache, knapp |

Alle Modi und ihre Texte lassen sich in den Einstellungen anpassen.

---

## 6. Tipps & häufige Fragen

- **„Daemon offline" am Symbol?** Kurz warten — das Tool startet den Hintergrunddienst selbst neu. Sonst: Rechtsklick aufs Symbol → „Beenden", dann das Desktop-Icon „Speech2Text" erneut starten.
- **Erstes Wort fehlt manchmal?** In den Einstellungen unter *Audio* das **Pre-Recording** aktivieren (Mikrofon bleibt dann bereit).
- **Versehentliches kurzes Antippen** von Caps Lock wird ignoriert (kein leeres Diktat).
- **Welche Version?** Steht im Einstellungs-Fenster (Titel + unten links).

---

## 7. Datenschutz

- Die Audioaufnahme bleibt **nur im Arbeitsspeicher** — sie wird nie auf der Platte gespeichert.
- Zur Spracherkennung wird das Audio an **OpenAI** gesendet (kein Training mit den Daten laut Vertrag).
- Protokolle enthalten **keine** Diktat-Inhalte, nur Status-Meldungen.

---

## 8. Support

Bei Problemen oder Wünschen: **Daniel Franken** ansprechen. Hilfreich für die Fehlersuche: Rechtsklick aufs Tray-Symbol → **„Log öffnen"**.

*Pilot-Phase: Rückmeldungen zu Erkennungsqualität, Bedienung und Wünschen sind ausdrücklich erwünscht.*
