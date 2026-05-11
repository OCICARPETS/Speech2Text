---
description: Bugfix abschließen — SPEZIFIKATION ergänzen, current-task aktualisieren, committen, pushen. (Voraussetzung Git-Repo.)
---

# Bugfix-Done

Ein Bugfix ist durchgelaufen (1-3 geänderte Dateien). Schließe ihn sauber ab.

**Argument:** `$ARGUMENTS` = Feature-/Modul-Bereich des Fixes (z.B. „Artikel-Modul", „ErpAuftragDetail").
Falls leer: aus dem Diff/Commit-Kontext herleiten oder beim User nachfragen.

**Voraussetzung:** Projekt muss ein Git-Repo sein. Wenn kein `.git` existiert: **abbrechen** mit Meldung „Dieser Command setzt ein Git-Repo voraus — bitte manuell die SPEZIFIKATION + current-task aktualisieren."

## Ablauf

1. **Diff prüfen:** `git diff` + `git status -s` — was wurde geändert? Welches Feature ist betroffen?
2. **Passende SPEZIFIKATION finden:** `Projektplanung/NN_<Feature>/SPEZIFIKATION.md` zum Bereich.
3. **SPEZIFIKATION ergänzen:** Eintrag unter „Bekannte Fallen" (wenn der Fix einen Gotcha behebt) ODER unter „Offene Punkte" als erledigt markieren. Knapp halten — 1-2 Sätze plus Datei-Referenz.
4. **`tasks/current-task.md` aktualisieren:** Fix unter „Was wurde gemacht" eintragen, ggf. aus „Offene Punkte" entfernen.
5. **Commit erstellen:** Format `<Bereich>: <was kurz>`. Eine Commit-Message, atomar.
6. **Push:** `git push origin <default-branch>` direkt nach dem Commit.
7. **Bestätigung:** Kurze Meldung an User: „Fix committed (`<sha>`), gepusht, SPEZIFIKATION ergänzt."

## Regeln

- **Kein Scope-Creep** — nur die Dateien des Fixes, keine „while-I'm-here"-Verbesserungen.
- **Keine eigenständige SPEZIFIKATION-Komplettüberarbeitung** — nur der eine Eintrag.
- **Wenn der Fix CLAUDE.md-Regeln berührt** (neue Falle, neues Verbot): CLAUDE.md ergänzen und im Commit erwähnen.
- **Wenn unklar welche SPEZIFIKATION gemeint ist:** beim User nachfragen, nicht raten.
