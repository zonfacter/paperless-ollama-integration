# Paperless Ollama Integration

Lokale Integration von `paperless-ngx` mit `Ollama` fuer KI-gestuetzte Nachbearbeitung von Dokumenten.

Der aktuelle Stand dieses Projekts bildet eine funktionierende Installation mit folgenden Bausteinen ab:

- `paperless-ngx` als native Systemd-Installation
- `Ollama` lokal auf `127.0.0.1:11434`
- `qwen2.5:3b-instruct` als lokales Modell
- Hook nach erfolgreichem Dokumentimport
- automatische Vergabe von:
  - Titel
  - Korrespondenz
  - Dokumenttyp
  - Tags
- minimale Browser-Oberflaeche fuer `Ollama`

## Projektinhalt

- `hooks/ai_enrich.py`
  - produktiver Hook fuer Paperless
- `prompts/ai_enrich_prompt.txt`
  - externer Prompt, getrennt vom Python-Code
- `web/server.py`
  - leichte Weboberflaeche fuer den lokalen `Ollama`-Server
- `systemd/paperless-scheduler.service`
  - korrigierte Scheduler-Unit auf `celery beat`
- `systemd/ollama-web.service`
  - Systemd-Unit fuer die lokale Weboberflaeche
- `scripts/configure-paperless-ai-ollama.sh`
  - Konfigurationshilfe fuer `paperless.conf`
- `docs/`
  - Installations-, Betriebs- und Sicherheitsdokumentation

## Architektur

1. `paperless-ngx` importiert ein Dokument.
2. OCR/Textinhalt und Metadaten stehen in der Paperless-API bereit.
3. `PAPERLESS_POST_CONSUME_SCRIPT` startet `hooks/ai_enrich.py`.
4. Der Hook liest das Dokument per API.
5. `Ollama` erzeugt eine strukturierte JSON-Antwort.
6. Der Hook schreibt Titel, Korrespondenz, Dokumenttyp und Tags zurueck.

## Wichtige Pfade im produktiven Aufbau

- Hook: `/opt/paperless/ai_enrich.py`
- Prompt: `/opt/paperless/ai_enrich_prompt.txt`
- Paperless-Konfiguration: `/opt/paperless/paperless.conf`
- Ollama-API: `http://127.0.0.1:11434`
- lokale Weboberflaeche: `http://<host>:3000`

## Hinweise

- Dieses Repository enthaelt keine Tokens oder geheimen Schluessel.
- Host-spezifische Benutzer, Ports und Pfade koennen je nach System angepasst werden.
- Der Prompt ist bewusst als Textdatei ausgelagert, damit er ohne Codeaenderung angepasst werden kann.
