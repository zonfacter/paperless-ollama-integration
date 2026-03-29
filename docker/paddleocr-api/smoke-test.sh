#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8091}"
IMAGE_PATH="${2:-}"

echo "Health:"
curl -sS "${BASE_URL}/healthz"
echo

if [[ -n "${IMAGE_PATH}" ]]; then
  echo "OCR:"
  curl -sS -F "file=@${IMAGE_PATH}" "${BASE_URL}/ocr"
  echo
else
  echo "No image path supplied, skipping /ocr smoke test."
fi
