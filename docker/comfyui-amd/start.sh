#!/usr/bin/env bash
set -eu

cd /opt/ComfyUI

mkdir -p /opt/ComfyUI/models /opt/ComfyUI/input /opt/ComfyUI/output /opt/ComfyUI/custom_nodes

exec python main.py \
  --listen "${COMFYUI_LISTEN:-0.0.0.0}" \
  --port "${COMFYUI_PORT:-8188}" \
  ${COMFYUI_EXTRA_ARGS:-}
