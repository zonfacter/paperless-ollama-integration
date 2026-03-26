# Betrieb

## Relevante Dienste

- `paperless-webserver.service`
- `paperless-consumer.service`
- `paperless-task-queue.service`
- `paperless-scheduler.service`
- `ollama.service`
- `ollama-web.service`

## Pruefen

```bash
systemctl status paperless-webserver.service paperless-consumer.service paperless-task-queue.service paperless-scheduler.service ollama.service ollama-web.service --no-pager
```

## Paperless-Test

Dokument in den Consume-Ordner legen und dann pruefen:

```bash
curl -H "Authorization: Token <TOKEN>" http://127.0.0.1:8000/api/documents/?page_size=5\&ordering=-id
```

## Prompt aendern

Der aktive Prompt liegt in:

```text
/opt/paperless/ai_enrich_prompt.txt
```

Nach Aenderungen ist normalerweise kein Dienstneustart noetig. Neue Hook-Laeufe verwenden den geaenderten Prompt.

## Modell testen

```bash
curl -sS http://127.0.0.1:11434/api/generate -d '{"model":"qwen2.5:3b-instruct","prompt":"Antworte nur mit OK.","stream":false}'
```
