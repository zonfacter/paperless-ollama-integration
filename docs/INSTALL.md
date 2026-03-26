# Installation

## Voraussetzungen

- laufendes `paperless-ngx`
- lokales `Ollama`
- erreichbare Paperless-API
- API-Token fuer einen Paperless-Benutzer

## Ollama

Beispiel:

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen2.5:3b-instruct
```

## Hook installieren

```bash
sudo cp hooks/ai_enrich.py /opt/paperless/ai_enrich.py
sudo cp prompts/ai_enrich_prompt.txt /opt/paperless/ai_enrich_prompt.txt
sudo chown paperless:paperless /opt/paperless/ai_enrich.py /opt/paperless/ai_enrich_prompt.txt
sudo chmod 755 /opt/paperless/ai_enrich.py
sudo chmod 644 /opt/paperless/ai_enrich_prompt.txt
```

## Paperless konfigurieren

In `/opt/paperless/paperless.conf`:

```dotenv
PAPERLESS_POST_CONSUME_SCRIPT=/opt/paperless/ai_enrich.py
PAPERLESS_API_URL=http://127.0.0.1:8000
PAPERLESS_API_TOKEN=REPLACE_WITH_TOKEN
PAPERLESS_AI_PROVIDER=ollama
PAPERLESS_AI_OLLAMA_URL=http://127.0.0.1:11434
PAPERLESS_AI_OLLAMA_MODEL=qwen2.5:3b-instruct
PAPERLESS_AI_PROMPT_FILE=/opt/paperless/ai_enrich_prompt.txt
PAPERLESS_AI_CONTENT_CHARS=12000
PAPERLESS_AI_MIN_CONFIDENCE=0.35
PAPERLESS_AI_DEFAULT_TAG_COLOR=#4f6bed
```

## Dienste

```bash
sudo cp systemd/paperless-scheduler.service /etc/systemd/system/paperless-scheduler.service
sudo systemctl daemon-reload
sudo systemctl restart paperless-webserver.service
sudo systemctl restart paperless-consumer.service
sudo systemctl restart paperless-task-queue.service
sudo systemctl restart paperless-scheduler.service
```

## Ollama-Weboberflaeche

```bash
sudo mkdir -p /home/thomas/ollama-web
sudo cp web/server.py /home/thomas/ollama-web/server.py
sudo chown -R thomas:thomas /home/thomas/ollama-web
sudo cp systemd/ollama-web.service /etc/systemd/system/ollama-web.service
sudo systemctl daemon-reload
sudo systemctl enable --now ollama-web.service
```
