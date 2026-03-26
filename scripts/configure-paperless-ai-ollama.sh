#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <paperless_api_token>" >&2
  exit 1
fi

PAPERLESS_TOKEN="$1"
CONF="/opt/paperless/paperless.conf"

cp -a "$CONF" "${CONF}.bak.$(date +%Y%m%d%H%M%S)"

python3 - "$CONF" "$PAPERLESS_TOKEN" <<'PY'
import pathlib
import sys

conf_path = pathlib.Path(sys.argv[1])
paperless_token = sys.argv[2]

updates = {
    "PAPERLESS_POST_CONSUME_SCRIPT": "/opt/paperless/ai_enrich.py",
    "PAPERLESS_API_URL": "http://127.0.0.1:8000",
    "PAPERLESS_API_TOKEN": paperless_token,
    "PAPERLESS_AI_PROVIDER": "ollama",
    "PAPERLESS_AI_OLLAMA_URL": "http://127.0.0.1:11434",
    "PAPERLESS_AI_OLLAMA_MODEL": "qwen2.5:3b-instruct",
    "PAPERLESS_AI_PROMPT_FILE": "/opt/paperless/ai_enrich_prompt.txt",
    "PAPERLESS_AI_CONTENT_CHARS": "12000",
    "PAPERLESS_AI_MIN_CONFIDENCE": "0.35",
    "PAPERLESS_AI_DEFAULT_TAG_COLOR": "#4f6bed",
}

text = conf_path.read_text()
lines = text.splitlines()
handled = set()
new_lines = []

for line in lines:
    replaced = False
    for key, value in updates.items():
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            handled.add(key)
            replaced = True
            break
    if not replaced:
        new_lines.append(line)

if handled != set(updates):
    new_lines.append("")
    new_lines.append("# Paperless AI enrichment")
    for key, value in updates.items():
        if key not in handled:
            new_lines.append(f"{key}={value}")

conf_path.write_text("\n".join(new_lines) + "\n")
PY

systemctl restart paperless-webserver.service
systemctl restart paperless-consumer.service
systemctl restart paperless-task-queue.service
systemctl restart paperless-scheduler.service || true

echo "Paperless AI with Ollama configured."
