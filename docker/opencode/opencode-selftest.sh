#!/usr/bin/env bash
set -euo pipefail

MODEL="${OPENCODE_DEFAULT_MODEL:-orfree/gpt-oss-20b-free}"
PROMPT="${1:-Antworte nur mit: OPENCODE_OK}"

exec opencode run --model "${MODEL}" --format default "${PROMPT}"
