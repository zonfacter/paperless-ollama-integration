# Config Examples

## Zweck

Diese Datei beschreibt die mitgelieferte Beispielkonfiguration fuer den produktiven Paperless-Ollama-Betrieb, ohne private Daten oder Tokens zu enthalten.

## Beispiel-Datei

- `config/paperless.conf.example`

Die Datei ist absichtlich bereinigt:

- kein echter API-Token
- keine privaten Dokumentdaten
- keine host-spezifischen Geheimnisse

## Was die Vorlage abbildet

Die Beispielkonfiguration folgt dem produktiven Muster dieses Projekts:

- lokales `Ollama`
- lokaler Paperless-API-Zugriff
- aktiver Post-Consume-Hook
- `Qwen 3.5` als Primaermodell
- Fallback-Modell optional aktiviert
- `think=false` fuer `Qwen 3.5`

## Wichtige Felder

### Pflicht

- `PAPERLESS_POST_CONSUME_SCRIPT`
- `PAPERLESS_API_URL`
- `PAPERLESS_API_TOKEN`
- `PAPERLESS_AI_PROVIDER`
- `PAPERLESS_AI_OLLAMA_URL`
- `PAPERLESS_AI_OLLAMA_MODEL`
- `PAPERLESS_AI_PROMPT_FILE`

### Qualitaet und Laufzeit

- `PAPERLESS_AI_CONTENT_CHARS`
- `PAPERLESS_AI_MIN_CONFIDENCE`
- `PAPERLESS_AI_HTTP_TIMEOUT_SECONDS`

### Optionaler Fallback

- `PAPERLESS_AI_FALLBACK_ENABLED`
- `PAPERLESS_AI_FALLBACK_MODEL`
- `PAPERLESS_AI_FALLBACK_ON_TIMEOUT_ONLY`
- `PAPERLESS_AI_FALLBACK_HTTP_TIMEOUT_SECONDS`

### Modellverhalten

- `PAPERLESS_AI_QWEN35_THINK=false`

## Uebernahme

Die Beispiel-Datei ist keine komplette `paperless.conf`, sondern nur der relevante KI-Abschnitt.

Typischer Ablauf:

1. Datei ansehen
2. Platzhalter anpassen
3. relevante Werte nach `/opt/paperless/paperless.conf` uebernehmen
4. Worker neu starten
