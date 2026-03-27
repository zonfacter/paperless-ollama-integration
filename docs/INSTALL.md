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
ollama pull qwen3.5:9b
ollama pull qwen3.5:4b
ollama pull qwen2.5:7b-instruct
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
PAPERLESS_AI_OLLAMA_MODEL=qwen3.5:9b
PAPERLESS_AI_FALLBACK_ENABLED=true
PAPERLESS_AI_FALLBACK_MODEL=qwen3.5:4b
PAPERLESS_AI_FALLBACK_ON_TIMEOUT_ONLY=true
PAPERLESS_AI_HTTP_TIMEOUT_SECONDS=300
PAPERLESS_AI_FALLBACK_HTTP_TIMEOUT_SECONDS=300
PAPERLESS_AI_PROMPT_FILE=/opt/paperless/ai_enrich_prompt.txt
PAPERLESS_AI_CONTENT_CHARS=5000
PAPERLESS_AI_MIN_CONFIDENCE=0.35
PAPERLESS_AI_DEFAULT_TAG_COLOR=#4f6bed
PAPERLESS_AI_QWEN35_THINK=false
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

## Web-Steuerung fuer Paperless

Die Weboberflaeche auf Port `3000` kann Prompt und Modellkonfiguration ueber kleine Root-Helfer aendern.
Diese Dateien gehoeren auf dem Zielsystem typischerweise nach:

```bash
sudo install -m 755 scripts/paperless-ai-admin /usr/local/sbin/paperless-ai-admin
sudo install -m 755 scripts/paperless-set-ollama-model /usr/local/sbin/paperless-set-ollama-model
sudo cp systemd/paperless-ai-admin.sudoers.example /etc/sudoers.d/paperless-ai-admin
sudo cp systemd/paperless-model.sudoers.example /etc/sudoers.d/paperless-model
# replace PAPERLESS_UI_USER with your actual service user
```

## Ollama-Weboberflaeche

```bash
sudo mkdir -p /home/PAPERLESS_UI_USER/ollama-web
sudo cp web/server.py /home/PAPERLESS_UI_USER/ollama-web/server.py
sudo chown -R PAPERLESS_UI_USER:PAPERLESS_UI_USER /home/PAPERLESS_UI_USER/ollama-web
sudo cp systemd/ollama-web.service /etc/systemd/system/ollama-web.service
sudo systemctl daemon-reload
sudo systemctl enable --now ollama-web.service
```
