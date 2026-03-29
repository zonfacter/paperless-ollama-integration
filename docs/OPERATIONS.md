# Betrieb

## Relevante Dienste

- `paperless-webserver.service`
- `paperless-consumer.service`
- `paperless-task-queue.service`
- `paperless-scheduler.service`
- `ollama.service`
- `ollama-web.service`
- optional: `paddleocr-api` as Docker container

## Pruefen

```bash
systemctl status paperless-webserver.service paperless-consumer.service paperless-task-queue.service paperless-scheduler.service ollama.service ollama-web.service --no-pager
```

## Typischer Tagesbetrieb

### Neue Dokumente

- neue Uploads laufen automatisch durch den Post-Consume-Hook
- Titel, Korrespondenz, Dokumenttyp und Tags werden direkt nach dem Import gesetzt
- kein manueller Schritt noetig, solange das Ergebnis passt

### Bestehende Dokumente

- Port `3000` fuer manuelle Review und Backfill verwenden
- `Review Workspace` fuer ein einzelnes Dokument
- `Backfill` fuer groessere Mengen oder Korrekturdurchlaeufe

## Paperless-Test

Dokument in den Consume-Ordner legen und dann pruefen:

```bash
curl -H "Authorization: Token <TOKEN>" http://127.0.0.1:8000/api/documents/?page_size=5\&ordering=-id
```

## Dienste neu starten

```bash
sudo systemctl restart paperless-consumer.service
sudo systemctl restart paperless-task-queue.service
sudo systemctl restart paperless-scheduler.service
sudo systemctl restart ollama.service
sudo systemctl restart ollama-web.service
```

## Prompt aendern

Der aktive Prompt liegt in:

```text
/opt/paperless/ai_enrich_prompt.txt
```

Nach Aenderungen ist normalerweise kein Dienstneustart noetig. Neue Hook-Laeufe verwenden den geaenderten Prompt.

## Modell und Hook testen

```bash
curl -sS http://127.0.0.1:11434/api/generate -d '{"model":"qwen3.5:4b","prompt":"Antworte nur mit OK.","stream":false}'
```

## Optionalen PaddleOCR-Dienst testen

Wenn der optionale Docker-Dienst laeuft:

```bash
curl -sS http://127.0.0.1:8091/healthz
curl -sS -F "file=@/path/to/page.jpg" http://127.0.0.1:8091/ocr
```

## Wichtige Konfiguration in `paperless.conf`

Typische Felder:

```dotenv
PAPERLESS_POST_CONSUME_SCRIPT=/opt/paperless/ai_enrich.py
PAPERLESS_AI_PROVIDER=ollama
PAPERLESS_AI_OLLAMA_URL=http://127.0.0.1:11434
PAPERLESS_AI_OLLAMA_MODEL=qwen3.5:9b
PAPERLESS_AI_FALLBACK_ENABLED=true
PAPERLESS_AI_FALLBACK_MODEL=qwen3.5:4b
PAPERLESS_AI_FALLBACK_ON_TIMEOUT_ONLY=true
PAPERLESS_AI_HTTP_TIMEOUT_SECONDS=300
PAPERLESS_AI_FALLBACK_HTTP_TIMEOUT_SECONDS=300
PAPERLESS_AI_CONTENT_CHARS=5000
PAPERLESS_AI_MIN_CONFIDENCE=0.35
PAPERLESS_AI_DEFAULT_TAG_COLOR=#4f6bed
PAPERLESS_AI_PROMPT_FILE=/opt/paperless/ai_enrich_prompt.txt
PAPERLESS_AI_QWEN35_THINK=false
```

## Verhalten bei `Qwen 3.5`

- `Qwen 3.5` neigt ohne Zusatzparameter zu Thinking
- fuer Paperless-JSON-Extraktion ist das in der Regel unerwuenscht
- der Hook setzt deshalb fuer `qwen3.5:*` standardmaessig `think=false`
- nur wenn `PAPERLESS_AI_QWEN35_THINK=true` gesetzt wird, bleibt Thinking aktiv

## Backfill ohne Weboberflaeche

```bash
sudo -u paperless /bin/bash -lc '
export PAPERLESS_API_URL=http://127.0.0.1:8000
export PAPERLESS_API_TOKEN=<TOKEN>
export PAPERLESS_AI_PROVIDER=ollama
export PAPERLESS_AI_OLLAMA_URL=http://127.0.0.1:11434
export PAPERLESS_AI_OLLAMA_MODEL=qwen3.5:9b
export PAPERLESS_AI_PROMPT_FILE=/opt/paperless/ai_enrich_prompt.txt
python3 /opt/paperless/ai_backfill.py --only-missing-metadata --limit 20
'
```
