# SPEZIFIKATION: KI-Pipeline (OpenAI Transcribe + Mini-Optimierung)

*Status: ✅ MVP umgesetzt · Priorität: 1 · Erstellt: 2026-04-24*

---

## 1. Vision & Scope

Die **KI-Pipeline** verwandelt rohes Audio in polierten Text — in zwei klar getrennten Schritten. Schritt 1 extrahiert den wörtlichen Inhalt (`gpt-4o-transcribe`). Schritt 2 entfernt Sprech-Ungenauigkeiten und macht den Text lesbar (`gpt-4o-mini` mit festem System-Prompt). Die Trennung ist bewusst: wäre beides in einem `gpt-4o-audio-preview`-Call, würden wir die Kontrolle über den Optimierungs-Prompt verlieren und hätten keinen Debug-Hook, um das Roh-Transkript anzuschauen.

## 2. Enthaltene Anforderungen / Use Cases

- **A1:** `gpt-4o-transcribe` erhält WAV-Bytes und gibt deutsches Roh-Transkript zurück.
- **A2:** `language="de"` explizit gesetzt — verhindert Fehlerkennung bei gemischtem Audio.
- **A3:** Roh-Transkript wird an `gpt-4o-mini` gegeben mit festem System-Prompt:
  > „Korrigiere Grammatik und Interpunktion. Entferne Füllwörter und Ähms. Behalte den Sinn bei, aber mache den Text professionell und flüssig. Antworte ausschließlich mit dem optimierten Text, ohne Einleitung oder Kommentar."
- **A4:** `temperature=0.2` — konservative Optimierung, minimiert kreative Abweichungen.
- **A5:** Leeres oder nur-Whitespace-Roh-Transkript → Pipeline bricht ab (keine API-Kosten für leere Optimierung).
- **A6:** Fehler in der Pipeline (Netzwerk, Rate-Limit, 401) werden auf Console geloggt (ohne API-Key!) und nicht an AHK weitergereicht — Daemon kehrt in `IDLE` zurück, nächster Tastendruck funktioniert wieder.

## 3. Zielgruppe / Zielumgebung

- **Input:** WAV-Bytes aus `02_Audio-Daemon` (16 kHz, Mono, int16).
- **Output:** Python-String (optimierter Text) → wird an `04_Text-Ausgabe` übergeben.
- **Abhängigkeit:** `openai`-SDK (>= 1.54), `.env` mit `OPENAI_API_KEY`.

## 4. Abgrenzung

**Bewusst nicht im Scope:**
- **Keine lokalen Modelle** — Whisper lokal, Llama lokal etc. sind explizit ausgeschlossen (MVP-Scope: OpenAI-API).
- **Kein Streaming** — `gpt-4o-transcribe` kann streamen, aber für Push-to-Talk wartet der Nutzer ohnehin auf das Ende. Komplexität lohnt nicht.
- **Kein Modus-Schalter** (E-Mail / Notiz / Stichpunkt) im MVP — Optimierungs-Prompt ist fest. Modi kommen ggf. als Priorität-3-Feature.
- **Keine Fenster-Kontext-Injection** — aktueller Fenstertitel wird nicht an den Optimizer übergeben. Priorität-3.

## 5. Technische Skizze / Architektur

### Zwei-Call-Pipeline

```
WAV-Bytes (16 kHz mono)
       │
       ▼
┌──────────────────────────────────────┐
│  client.audio.transcriptions.create( │
│      model="gpt-4o-transcribe",      │
│      file=(name, bytes, "audio/wav"),│
│      language="de",                  │
│  )                                   │
└──────────────────────────────────────┘
       │
       ▼ resp.text
Roh-Transkript (string)
       │
       ▼
┌──────────────────────────────────────────────┐
│  client.chat.completions.create(             │
│      model="gpt-4o-mini",                    │
│      temperature=0.2,                        │
│      messages=[                              │
│          {"role":"system","content":PROMPT}, │
│          {"role":"user","content":roh},      │
│      ],                                      │
│  )                                           │
└──────────────────────────────────────────────┘
       │
       ▼ resp.choices[0].message.content
Optimierter Text (string) → 04_Text-Ausgabe
```

### Kosten-Abschätzung (Stand 2026-04, zur Orientierung)

- `gpt-4o-transcribe`: ~$0.006/min Audio → 30 s Diktat = $0.003
- `gpt-4o-mini`: typisches Diktat ~200 Tokens In + 200 Out = ~$0.0001
- **Pro Diktat also < $0.005** — bei 50 Diktaten/Tag < $0.25. Vernachlässigbar.

### Fehler-Handling

- `openai.AuthenticationError` → Daemon loggt „Invalid API key" und bleibt aktiv (ggf. korrigiert der User den Key in `.env` und startet neu).
- `openai.RateLimitError` → Log + IDLE. Nächster Versuch geht.
- `openai.APITimeoutError` → Log + IDLE. Nächster Versuch geht.
- **Kein Retry im MVP** — Push-to-Talk-UX: lieber sofort aufgeben und der User diktiert nochmal.

## 6. Umsetzungsplan

- [x] `_transcribe(wav_bytes) -> str` mit `gpt-4o-transcribe`
- [x] `_optimize(roh) -> str` mit `gpt-4o-mini` + fester System-Prompt
- [x] `temperature=0.2`
- [x] Leer-Check vor Optimierung
- [x] Fehler-Logging auf stderr
- [ ] Manueller Test: bekanntes deutsches Sample → Transkript inhaltlich korrekt
- [ ] Manueller Test: Füllwort-Test („äh, also, ich mein, ich wollte sagen…") → saubere Version
- [ ] Manueller Test: API-Key falsch → klare Fehlermeldung

## 7. Deployment

- Kein separates Deployment — Teil von `src/recorder.py`.
- Voraussetzung: `.env` mit `OPENAI_API_KEY` existiert und ist gültig.
- Bei Modell-Deprecation: Änderung nur mit User-Freigabe (siehe `CLAUDE.md` Verbote).

## 8. Offene Punkte und Entscheidungen

- [ ] **Sprache `de` fest oder Auto-Detect?** Aktuell fest. Bei gelegentlichem Englisch-Einwurf („ich schick dir das Abstract") könnte Auto-Detect besser sein — aber auch fehleranfälliger.
- [ ] **Prompt-Anpassung?** Aktueller System-Prompt ist generisch-professionell. Soll es Varianten geben (locker vs. formell vs. sachlich)?
- [ ] **Timeout?** OpenAI-SDK hat Default-Timeouts. Für Push-to-Talk sollte der Daemon nach z.B. 20 s aufgeben und IDLE werden.
- [ ] **Token-Kosten-Logging?** Opt-In, kumulierte Kosten pro Session. Priorität 3.
- [ ] **Streaming?** Priorität 3 — wäre UX-Verbesserung (Text erscheint während Sprechen), aber komplex.

## 9. Gotchas

- **Dateiname in API-Call:** Die `file`-Parameter-Tupel-Signatur ist `(name, bytes, content_type)`. Ohne `content_type="audio/wav"` gab's in älteren SDK-Versionen 400er.
- **`resp.text` vs. `resp.text()`:** Bei `transcriptions.create` ist es `resp.text` (Property, kein Call). ✅ Umgesetzt.
- **`message.content` kann `None` sein:** Falls der Optimizer aus irgendeinem Grund leer antwortet. Fallback auf `""` + `strip()`. ✅ Umgesetzt.
- **API-Key-Leakage:** Niemals `print(os.environ)` oder `print(client)` — OpenAI-Client hält den Key als Attribut. `.env`-Datei gitignore!
- **`gpt-4o-mini` paraphrasiert „hilfreich" (Session 19):** Bei knapp formulierten „Bereinigungs"-Prompts schreibt das Modell den Text um/fasst zusammen, statt nur Füllwörter zu löschen — A/B-belegt −15 bis −26 % Zeichen für `clean_dictation`. Gegenmittel: expliziter Anti-Paraphrase-Prompt („Wort für Wort", Verbotsliste umformulieren/zusammenfassen/kürzen, Zahlen/Eigennamen schützen). Senkt die Kürzung auf reine Füllwort-Entfernung (−11 bis −17 %, Inhaltswörter bleiben). Prompt-Texte leben in `src/config.py` → `MODES`, nicht im Daemon-Code.

## 10. Historie & Verweise

- **Entstehung:** Briefing 2026-04-24. Modell-Frage (`gpt-4o-audio-preview` vs. `gpt-4o-transcribe + mini`) explizit abgestimmt.
- **Session 19 (2026-06-12):** `clean_dictation`-System-Prompt anti-paraphrase gehärtet (s. Gotcha §9 + `tests/test_config_clean_dictation.py`). Kein Modellwechsel.
- **Zugehörige Dateien:** `src/recorder.py` (Methoden `_transcribe`, `_optimize`), `src/config.py` (`MODES`-Prompts).
- **Referenzen:**
  - OpenAI Speech-to-Text Guide: https://platform.openai.com/docs/guides/speech-to-text (Stand 2026-04-24)
  - OpenAI API Reference Transcriptions: https://platform.openai.com/docs/api-reference/audio/createTranscription
  - OpenAI Python SDK: https://github.com/openai/openai-python
  - OpenAI Pricing: https://openai.com/pricing (Stand 2026-04-24)
