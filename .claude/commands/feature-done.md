---
description: Feature abschließen — SPEZIFIKATION überarbeiten, FEATURE_UEBERSICHT prüfen, committen, pushen. (Voraussetzung Git-Repo.)
---

# Feature-Done

Ein größeres Feature ist umgesetzt. Schließe es sauber ab und stelle sicher, dass die Doku den neuen Stand widerspiegelt.

**Argument:** `$ARGUMENTS` = Feature-Name (z.B. „Artikel-Modul", „Kernsortiment").
Falls leer: aus dem Diff/Commits herleiten oder beim User nachfragen.

**Voraussetzung:** Projekt muss ein Git-Repo sein. Wenn kein `.git` existiert: **abbrechen** mit Meldung „Dieser Command setzt ein Git-Repo voraus — bitte manuell die SPEZIFIKATION + FEATURE_UEBERSICHT + current-task aktualisieren."

## Ablauf

1. **Diff & Commits prüfen:** `git status -s`, `git log --oneline -10`, `git diff` — welche Dateien gehören zum Feature, welche Commits wurden im Verlauf erstellt?

2. **Feature-Ordner finden:** `Projektplanung/NN_<Feature>/SPEZIFIKATION.md`. Falls nicht existent: User fragen ob neu anlegen — dann aus dem Sektionen-Template aus `CLAUDE.md` → Doku-Wegweiser anlegen.

3. **SPEZIFIKATION überarbeiten — alle Sektionen durchgehen:**
   - **Vision & Scope:** falls geändert
   - **Aktueller Stand:** auf den neuen Zustand updaten („✅ Fertig (YYYY-MM)")
   - **Code-Referenzen:** neue Dateien/Methoden eintragen, gelöschte raus
   - **DB-Objekte:** neue Tables/Views/SPs ergänzen
   - **Was bei Änderungen beachten:** neue Architektur-Entscheidungen
   - **Bekannte Fallen:** neue Gotchas die im Verlauf aufgetaucht sind
   - **Offene Punkte:** umgesetzte Punkte raus, neue offene rein
   - **Historie & Pläne:** Verweis auf den `docs/superpowers/plans/`-Eintrag (falls vorhanden)

4. **`Projektplanung/FEATURE_UEBERSICHT.md` prüfen:** „Aktueller Stand"-Block des Features anpassen (z.B. „✅ Fertig (YYYY-MM)").

5. **`tasks/current-task.md` aktualisieren:** Feature aus „Offene Punkte" raus, kurzer Eintrag unter „Was wurde gemacht".

6. **`CLAUDE.md` prüfen:** Berührt das Feature die CLAUDE.md-Regeln? Neue Verbote, neue Patterns, neue Konventionen? Wenn ja: ergänzen.

7. **Commit-Strategie:**
   - Wenn das Feature als Branch entwickelt wurde: `superpowers:finishing-a-development-branch` Skill nutzen (Squash-Merge auf Default-Branch).
   - Wenn direkt auf master/main mit Zwischen-Commits: 1-2 abschließende Commits (Code-Abschluss, dann Doku-Update).
   - Commit-Message-Format: `<Feature>: <was umgesetzt>`.

8. **Push:** `git push origin <default-branch>` direkt nach dem letzten Commit.

9. **Bestätigung:** Übersicht ausgeben — was gemacht, welche SPEZIFIKATION aktualisiert, welche Commits, ahead-Count nach Push (sollte 0 sein).

## Regeln

- **SPEZIFIKATION ist Pflicht** — kein Feature ohne aktualisierte Spec. Wenn die Spec fehlt, neu anlegen.
- **Nicht über den Scope hinaus refaktorieren** — auch nicht „weil die Spec sowieso angefasst wird".
- **`docs/superpowers/plans/` synchronisieren** — Plan-Datei bleibt als Historie, aber der finale Stand muss in der SPEZIFIKATION stehen.
- **Bei Unsicherheit zum Scope** (z.B. „war Punkt X Teil dieses Features oder nicht?"): beim User nachfragen.
