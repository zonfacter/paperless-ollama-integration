#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$SCRIPT_DIR"

docker compose -f docker-compose.example.yml up --build -d

echo "PaddleOCR API started on http://127.0.0.1:8091"
