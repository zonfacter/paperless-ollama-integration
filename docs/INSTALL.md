# Installation

## Goal

The easiest path is the guided installer:

```bash
sudo bash scripts/install-paperless-ai.sh
```

The installer:

- tells you up front which values you need
- detects whether you are more likely using:
  - a native VM / dedicated server setup
  - a Docker / Compose based Paperless setup
- asks for the required access data before changing files
- prepares the correct files for the chosen mode

## What You Need Before Starting

- a running `paperless-ngx` instance
- a reachable `Ollama` instance
- a Paperless API token
- the Paperless API URL
- the Ollama URL
- the primary model you want to use
- optionally a fallback model

For native installs you will usually also need:

- root access
- a local target user if you want to install the Paperless AI Console on port `3000`

For Docker installs you will usually also need:

- the path to your `docker-compose.yml` or `compose.yml`
- the Paperless webserver service name, usually `webserver`
- a host path where hook, prompt, and backfill files should be mounted

## Environment Types

### Native VM / Dedicated Server

Typical signs:

- `/opt/paperless/paperless.conf` exists
- `paperless-webserver.service` and related services exist in systemd
- Paperless is managed as local services on the VM or server

The installer can:

- copy hook, prompt, and backfill files into `/opt/paperless`
- update `paperless.conf`
- install the corrected scheduler unit
- optionally install the local Paperless AI Console on port `3000`

### Docker / Compose

Typical signs:

- you have `docker-compose.yml`, `docker-compose.yaml`, `compose.yml`, or `compose.yaml`
- Paperless runs inside containers

The installer can:

- create a dedicated integration directory with hook, prompt, and backfill files
- create a generated env file with the needed `PAPERLESS_*` variables
- create a `docker-compose.override.yml`
- optionally restart the selected Paperless webserver service via `docker compose up -d`

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

## Guided Installer

```bash
sudo bash scripts/install-paperless-ai.sh
```

Was der Installer abfragt:

- Installationsmodus `native` oder `docker`
- Paperless API URL
- Paperless API Token
- Ollama URL
- Primaermodell
- Fallback-Modell
- Timeout
- OCR-Kontext
- Mindest-Confidence

Zusatzfragen je nach Modus:

- `native`
  - Pfad zu `paperless.conf`
  - Zielverzeichnis fuer Hook und Prompt
  - optionaler Benutzer fuer die Port-`3000`-Weboberflaeche
- `docker`
  - Pfad zur Compose-Datei
  - Pfad fuer erzeugte `paperless-ai.env`
  - Host-Verzeichnis fuer Integration
  - Container-Pfad fuer den Mount
  - Service-Name des Paperless-Webservers

## Native Installation Manually

### Paperless konfigurieren

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

### Dienste

```bash
sudo cp systemd/paperless-scheduler.service /etc/systemd/system/paperless-scheduler.service
sudo systemctl daemon-reload
sudo systemctl restart paperless-webserver.service
sudo systemctl restart paperless-consumer.service
sudo systemctl restart paperless-task-queue.service
sudo systemctl restart paperless-scheduler.service
```

### Web-Steuerung fuer Paperless

Die Weboberflaeche auf Port `3000` kann Prompt und Modellkonfiguration ueber kleine Root-Helfer aendern.
Diese Dateien gehoeren auf dem Zielsystem typischerweise nach:

```bash
sudo install -m 755 scripts/paperless-ai-admin /usr/local/sbin/paperless-ai-admin
sudo install -m 755 scripts/paperless-set-ollama-model /usr/local/sbin/paperless-set-ollama-model
sudo cp systemd/paperless-ai-admin.sudoers.example /etc/sudoers.d/paperless-ai-admin
sudo cp systemd/paperless-model.sudoers.example /etc/sudoers.d/paperless-model
# replace PAPERLESS_UI_USER with your actual service user
```

### Ollama-Weboberflaeche

```bash
sudo mkdir -p /home/PAPERLESS_UI_USER/ollama-web
sudo cp web/server.py /home/PAPERLESS_UI_USER/ollama-web/server.py
sudo chown -R PAPERLESS_UI_USER:PAPERLESS_UI_USER /home/PAPERLESS_UI_USER/ollama-web
sudo cp systemd/ollama-web.service /etc/systemd/system/ollama-web.service
sudo systemctl daemon-reload
sudo systemctl enable --now ollama-web.service
```

## Docker / Compose Installation Manually

The guided installer is recommended. If you want to do it manually, the usual structure is:

1. create a host directory for the integration files
2. copy:
   - `hooks/ai_enrich.py`
   - `prompts/ai_enrich_prompt.txt`
   - `scripts/ai_backfill.py`
3. create a dedicated env file with the `PAPERLESS_*` values
4. create `docker-compose.override.yml`
5. mount the integration directory into the Paperless container
6. restart the Paperless webserver service with Docker Compose

Typical override structure:

```yaml
services:
  webserver:
    env_file:
      - ./paperless-ai.env
    volumes:
      - ./paperless-ai:/usr/src/paperless-ai:ro
```

Typical container-side values:

```dotenv
PAPERLESS_POST_CONSUME_SCRIPT=/usr/src/paperless-ai/ai_enrich.py
PAPERLESS_AI_PROMPT_FILE=/usr/src/paperless-ai/ai_enrich_prompt.txt
```
