#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
STACK_DIR="$REPO_DIR/docker/paddleocr-api"

IMAGE_NAME="${PADDLEOCR_DOCKER_IMAGE:-paperless-paddleocr-api:latest}"
CONTAINER_NAME="${PADDLEOCR_DOCKER_CONTAINER:-paperless-paddleocr-api}"
HOST_PORT="${PADDLEOCR_API_PORT:-8091}"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker ist nicht installiert oder nicht im PATH." >&2
  exit 1
fi

if [ ! -d "$STACK_DIR" ]; then
  echo "Stack-Verzeichnis nicht gefunden: $STACK_DIR" >&2
  exit 1
fi

echo "Baue PaddleOCR API Image $IMAGE_NAME ..."
docker build -t "$IMAGE_NAME" "$STACK_DIR"

if docker ps -a --format '{{.Names}}' | grep -Fxq "$CONTAINER_NAME"; then
  echo "Entferne vorhandenen Container $CONTAINER_NAME ..."
  docker rm -f "$CONTAINER_NAME" >/dev/null
fi

echo "Starte PaddleOCR API Container $CONTAINER_NAME auf Port $HOST_PORT ..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p "$HOST_PORT:8091" \
  -e PADDLEOCR_LANG="${PADDLEOCR_LANG:-german}" \
  -e PADDLEOCR_DEVICE="${PADDLEOCR_DEVICE:-cpu}" \
  -e PADDLEOCR_CPU_THREADS="${PADDLEOCR_CPU_THREADS:-4}" \
  -e PADDLEOCR_ENABLE_MKLDNN="${PADDLEOCR_ENABLE_MKLDNN:-true}" \
  -e PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="${PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK:-true}" \
  "$IMAGE_NAME" >/dev/null

echo
echo "PaddleOCR API ist gestartet:"
echo "  URL: http://127.0.0.1:${HOST_PORT}"
echo "  Health: curl -sS http://127.0.0.1:${HOST_PORT}/healthz"
echo "  OCR: curl -sS -F \"file=@/pfad/zur/seite.jpg\" http://127.0.0.1:${HOST_PORT}/ocr"
