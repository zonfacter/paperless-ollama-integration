# Installation

## Goal

This repository currently has two supported installation paths:

- `scripts/install-paperless-ai.sh`
  - for native installs and simple Docker/Compose setups where you mainly want to add the Hook, Prompt, Backfill script, and basic Paperless integration
- `scripts/bootstrap-nas-stack.sh`
  - for the full repo-managed NAS/Compose stack with `paperless-ai-web`, optional `open-webui`, repo-managed wrapper images, telemetry, and optional image/OCR sidecars

If you only need the Hook integration, the guided installer is the easiest path:

```bash
curl -fsSL https://raw.githubusercontent.com/zonfacter/paperless-ollama-integration/main/scripts/install-paperless-ai.sh -o /tmp/install-paperless-ai.sh
sudo bash /tmp/install-paperless-ai.sh
```

First check without writing anything:

```bash
curl -fsSL https://raw.githubusercontent.com/zonfacter/paperless-ollama-integration/main/scripts/install-paperless-ai.sh -o /tmp/install-paperless-ai.sh
sudo bash /tmp/install-paperless-ai.sh --dry-run
```

The installer:

- tells you up front which values you need
- detects whether you are more likely using:
  - a native VM / dedicated server setup
  - a Docker / Compose based Paperless setup
- asks for the required access data before changing files
- prepares the correct files for the chosen mode

If you prefer reviewing the repository first:

```bash
git clone https://github.com/zonfacter/paperless-ollama-integration.git
cd paperless-ollama-integration
sudo bash scripts/install-paperless-ai.sh --dry-run
```

For the full NAS/Compose stack, use the bootstrap script instead:

```bash
git clone https://github.com/zonfacter/paperless-ollama-integration.git
cd paperless-ollama-integration
./scripts/bootstrap-nas-stack.sh --dry-run
./scripts/bootstrap-nas-stack.sh
```

And to validate an already scaffolded checkout:

```bash
./scripts/bootstrap-nas-stack.sh --validate
```

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

## Full NAS / Compose Stack

`bootstrap-nas-stack.sh` is the reference entry point for the current repo-managed NAS stack.

It currently handles:

- data directories for `paperless-ngx`, `ollama`, `paperless-ai-web`, `open-webui`, `ComfyUI`, `OpenVINO`, and optional OCR sidecars
- missing default files such as `.env`, `compose.override.yml`, and the JSON/ENV config files under `config/`
- validation of required secrets and placeholder values
- workspace-path checks for `Open WebUI`
- image backend checks for:
  - external OpenAI-compatible image endpoints
  - experimental local `ComfyUI` checkpoints
- `docker compose config -q` validation when Docker and `.env` are available

Important scope note:

- `install-paperless-ai.sh` does not try to install or manage the entire expanded NAS stack
- `bootstrap-nas-stack.sh` does not replace the guided Hook installer for native VM setups
- the two scripts intentionally cover different deployment scopes

## Optional: PaddleOCR API Container

If you want to test or expose `PaddleOCR` as a separate HTTP service, this repository also includes an optional API container:

```text
docker/paddleocr-api/
```

Typical use case:

- keep `paperless-ngx` OCR unchanged
- run `PaddleOCR` beside it as a comparison or future enhancement service
- call it from scripts or a later review step

## Optional: OpenCode Container (separater Workspace)

Das Repo enthaelt einen optionalen `opencode`-Service mit eigenem Workspace-Unterordner.

Voraussetzung in `.env`:

```dotenv
OPENCODE_WORKSPACE_HOST_PATH=/volume4/AI-TEST/workspace/opencode
OPENCODE_CONFIG_HOST_PATH=./data/opencode
OPENCODE_OPENAI_BASE_URL=http://llama-cpp:8080/v1
OPENCODE_OLLAMA_HOST=http://ollama:11434
OPENCODE_DEFAULT_MODEL=orfree/gpt-oss-20b-free
OPENCODE_DEFAULT_AGENT=build
OPENCODE_HOSTNAME=0.0.0.0
OPENCODE_PORT=4096
OPENCODE_SERVER_USERNAME=opencode
OPENCODE_SERVER_PASSWORD=bitte-ein-starkes-passwort-setzen
OPENROUTER_API_KEY=sk-or-v1-...
```

Start:

```bash
cd /volume1/docker/paperless-ai/paperless-ollama-integration
mkdir -p /volume4/AI-TEST/workspace/opencode
sudo docker compose --profile opencode up -d opencode
```

Interaktiv nutzen:

```bash
sudo docker exec -it paperless-opencode bash
opencode
```

Der Container arbeitet dann nur im gemounteten Ordner `OPENCODE_WORKSPACE_HOST_PATH`.

Empfohlener Start mit Repo-Defaults (Modell + Agent):

```bash
sudo docker exec -it paperless-opencode opencode-default
```

Schneller Funktionstest:

```bash
sudo docker exec paperless-opencode opencode-selftest
```

Web-Zugriff im Browser:

```text
http://<NAS-IP>:4096
```

Hinweis:
- `opencode` laeuft im Compose-Setup als Server (`opencode serve`).
- Fuer LAN-Zugriff sollte `OPENCODE_SERVER_PASSWORD` gesetzt sein.

Custom Provider (empfohlen, nachhaltig):

```bash
cp config/opencode.example.json data/opencode/opencode.json
sudo docker compose --profile opencode restart opencode
```

Damit nutzt `opencode` explizit lokale Provider (`ollama_local`, `llamacpp_local`) statt impliziter Defaults.
Die Modell-Defaults kannst du dann in `data/opencode/opencode.json` zentral pflegen.
Aktuell empfohlen fuer lokale Tool-Calls in `opencode`: `ollama_local/qwen3.5:9b`.
Wenn Tool-Calls haengen: zuerst `small_model` ebenfalls auf `ollama_local/qwen3.5:9b` setzen und danach `opencode` neu starten.
Fuer stabile Agent-Tool-Calls im Alltag: `orfree/gpt-oss-20b-free` als Build-Modell.

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
ollama pull kwmcglon/gemma-4-E4B-it

Hinweis: Die Gemma-4-Modelle funktionieren nur mit Ollama 0.20.2 oder neuer. Wenn Docker-Stacks weiterhin `ollama/ollama:latest` (0.18.x) nutzen, muss der Container auf `ollama/ollama:0.20.2` aktualisiert werden, bevor `kwmcglon/gemma-4-E4B-it` geladen werden kann.

Fuer Docker-Stacks:

```bash
cd /volume1/docker/paperless-ai/paperless-ollama-integration
sudo docker compose pull ollama
sudo docker compose up -d --force-recreate ollama
sudo docker exec paperless-ollama ollama --version
sudo docker exec paperless-ollama ollama pull kwmcglon/gemma-4-E4B-it
```
```

## Hook installieren

```bash
sudo cp hooks/ai_enrich.py /opt/paperless/ai_enrich.py
sudo cp prompts/ai_enrich_prompt.txt /opt/paperless/ai_enrich_prompt.txt
sudo chown paperless:paperless /opt/paperless/ai_enrich.py /opt/paperless/ai_enrich_prompt.txt
sudo chmod 755 /opt/paperless/ai_enrich.py
sudo chmod 644 /opt/paperless/ai_enrich_prompt.txt
```

## Guided Hook Installer

```bash
curl -fsSL https://raw.githubusercontent.com/zonfacter/paperless-ollama-integration/main/scripts/install-paperless-ai.sh -o /tmp/install-paperless-ai.sh
sudo bash /tmp/install-paperless-ai.sh
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

Optional:

- `--dry-run`
  - sammelt alle Eingaben
  - zeigt die geplanten Dateien und Befehle
  - schreibt nichts auf das System

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
