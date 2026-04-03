#!/usr/bin/env bash
set -eu

if [ -n "${OPEN_WEBUI_COMFYUI_WORKFLOW_FILE:-}" ] && [ -f "${OPEN_WEBUI_COMFYUI_WORKFLOW_FILE}" ] && [ -z "${COMFYUI_WORKFLOW:-}" ]; then
  export COMFYUI_WORKFLOW="$(python /opt/paperless-open-webui/load_json_env.py "${OPEN_WEBUI_COMFYUI_WORKFLOW_FILE}")"
fi

if [ -n "${OPEN_WEBUI_COMFYUI_WORKFLOW_NODES_FILE:-}" ] && [ -f "${OPEN_WEBUI_COMFYUI_WORKFLOW_NODES_FILE}" ] && [ -z "${COMFYUI_WORKFLOW_NODES:-}" ]; then
  export COMFYUI_WORKFLOW_NODES="$(python /opt/paperless-open-webui/load_json_env.py "${OPEN_WEBUI_COMFYUI_WORKFLOW_NODES_FILE}")"
fi

python /opt/paperless-open-webui/apply_openwebui_patches.py
python /opt/paperless-open-webui/bootstrap_openwebui.py &

exec bash start.sh
