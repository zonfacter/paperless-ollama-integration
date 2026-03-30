#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

copy_if_missing() {
  local src="$1"
  local dst="$2"
  if [[ ! -e "$dst" ]]; then
    cp "$src" "$dst"
    printf 'created %s\n' "$dst"
  else
    printf 'kept existing %s\n' "$dst"
  fi
}

mkdir -p \
  data/paperless/consume \
  data/paperless/media \
  data/paperless/export \
  data/paperless/data \
  data/redis \
  data/db \
  data/ollama \
  data/paperless-ai-web \
  data/paddleocr-cache \
  config/tessdata-best

copy_if_missing .env.example .env
copy_if_missing compose.override.example.yml compose.override.yml
copy_if_missing config/paperless.conf.example config/paperless-ai.env
copy_if_missing config/preview_config.example.json config/preview_config.json
copy_if_missing config/tag_allowlists.example.json config/tag_allowlists.json
copy_if_missing config/tag_rules.example.json config/tag_rules.json
copy_if_missing config/providers.example.json config/providers.json
copy_if_missing config/models.example.json config/models.json
copy_if_missing config/version.example.json config/version.json

printf '\nNAS stack scaffold prepared in %s\n' "$ROOT_DIR"
printf 'Next steps:\n'
printf '  1. Edit .env and config/paperless-ai.env\n'
printf '  2. Start core services with: sudo docker compose up -d broker db gotenberg tika webserver ollama\n'
printf '  3. After webserver is healthy: sudo docker compose up -d consumer task-queue scheduler\n'
printf '  3. Add paperless-ai-web after Paperless is healthy\n'
