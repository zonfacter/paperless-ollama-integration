#!/usr/bin/env bash
set -euo pipefail

PROFILE="${1:-}"
ENV_FILE="${2:-.env}"

if [[ -z "${PROFILE}" ]]; then
  echo "Usage: $0 <rocm-stable|rocm-next> [path-to-.env]"
  exit 1
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Env file not found: ${ENV_FILE}"
  exit 1
fi

set_kv() {
  local key="$1"
  local value="$2"
  if grep -qE "^${key}=" "${ENV_FILE}"; then
    sed -i -E "s|^${key}=.*$|${key}=${value}|" "${ENV_FILE}"
  else
    printf "%s=%s\n" "${key}" "${value}" >> "${ENV_FILE}"
  fi
}

case "${PROFILE}" in
  rocm-stable)
    set_kv "OLLAMA_IMAGE_TAG" "0.12.3-rocm"
    set_kv "OLLAMA_VULKAN" "0"
    set_kv "OLLAMA_KEEP_ALIVE" "2m"
    set_kv "OLLAMA_MAX_LOADED_MODELS" "1"
    set_kv "OLLAMA_NUM_PARALLEL" "1"
    ;;
  rocm-next)
    set_kv "OLLAMA_IMAGE_TAG" "0.20.2"
    set_kv "OLLAMA_VULKAN" "0"
    set_kv "OLLAMA_KEEP_ALIVE" "10m"
    set_kv "OLLAMA_MAX_LOADED_MODELS" "2"
    set_kv "OLLAMA_NUM_PARALLEL" "2"
    ;;
  *)
    echo "Unknown profile: ${PROFILE}"
    echo "Allowed: rocm-stable, rocm-next"
    exit 1
    ;;
esac

echo "Applied ${PROFILE} to ${ENV_FILE}"
grep -E "^(OLLAMA_IMAGE_TAG|OLLAMA_VULKAN|OLLAMA_KEEP_ALIVE|OLLAMA_MAX_LOADED_MODELS|OLLAMA_NUM_PARALLEL)=" "${ENV_FILE}" || true

