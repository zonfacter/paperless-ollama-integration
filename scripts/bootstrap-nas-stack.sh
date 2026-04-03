#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DRY_RUN="false"
VALIDATE_ONLY="false"
EXIT_CODE=0

usage() {
  cat <<'EOF'
Usage: bootstrap-nas-stack.sh [--dry-run] [--validate] [--help]

Scaffold the repository for the current NAS/Docker Compose stack and validate
the local deployment state.

Options:
  --dry-run    Show the actions that would be taken without writing files.
  --validate   Only validate the current repository state, do not scaffold.
  -h, --help   Show this help.
EOF
}

for arg in "$@"; do
  case "${arg}" in
    --dry-run)
      DRY_RUN="true"
      ;;
    --validate)
      VALIDATE_ONLY="true"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n' "${arg}" >&2
      exit 1
      ;;
  esac
done

say() {
  printf '%s\n' "$*"
}

warn() {
  printf 'Warning: %s\n' "$*" >&2
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  EXIT_CODE=1
}

run_or_echo() {
  if [[ "${DRY_RUN}" == "true" ]]; then
    printf '[dry-run] '
    printf '%q ' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

copy_if_missing() {
  local src="$1"
  local dst="$2"
  if [[ -e "${dst}" ]]; then
    say "keep ${dst}"
    return 0
  fi
  if [[ "${DRY_RUN}" == "true" ]]; then
    say "[dry-run] copy ${src} -> ${dst}"
    return 0
  fi
  install -m 644 "${src}" "${dst}"
  say "created ${dst}"
}

env_get() {
  local key="$1"
  local file="$2"
  [[ -f "${file}" ]] || return 1
  awk -F= -v target="${key}" '
    $1 == target {
      value = substr($0, index($0, "=") + 1)
      print value
      found = 1
      exit
    }
    END {
      if (!found) exit 1
    }
  ' "${file}"
}

validate_placeholder() {
  local key="$1"
  local file="$2"
  local strict="${3:-true}"
  local value=""
  if ! value="$(env_get "${key}" "${file}" 2>/dev/null)"; then
    if [[ "${strict}" == "true" ]]; then
      fail "${file}: missing ${key}"
    else
      warn "${file}: missing ${key}"
    fi
    return
  fi
  if [[ "${value}" == *CHANGE_ME* || "${value}" == *REPLACE_WITH_TOKEN* ]]; then
    if [[ "${strict}" == "true" ]]; then
      fail "${file}: ${key} still contains a placeholder value"
    else
      warn "${file}: ${key} still contains a placeholder value"
    fi
  fi
}

check_path_exists() {
  local path="$1"
  local message="$2"
  if [[ ! -e "${path}" ]]; then
    fail "${message}: ${path}"
  fi
}

validate_compose_config() {
  local compose_cmd=()

  if ! command -v docker >/dev/null 2>&1; then
    if command -v docker-compose >/dev/null 2>&1; then
      compose_cmd=(docker-compose)
    else
      warn "docker not found, skipping compose validation"
      return 0
    fi
  else
    if docker compose version >/dev/null 2>&1; then
      compose_cmd=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
      compose_cmd=(docker-compose)
    else
      warn "docker compose not available, skipping compose validation"
      return 0
    fi
  fi

  if [[ ! -f "${REPO_DIR}/compose.yml" ]]; then
    fail "compose.yml is missing"
    return
  fi

  if [[ ! -f "${REPO_DIR}/.env" ]]; then
    warn ".env missing, skipping docker compose config validation"
    return 0
  fi

  if [[ "${DRY_RUN}" == "true" ]]; then
    say "[dry-run] (cd ${REPO_DIR} && ${compose_cmd[*]} config -q)"
    return 0
  fi

  if ! (cd "${REPO_DIR}" && "${compose_cmd[@]}" config -q); then
    fail "docker compose config validation failed"
  fi
}

validate_image_backend() {
  local env_file="$1"
  local enabled engine model base_url api_key

  enabled="$(env_get OPEN_WEBUI_ENABLE_IMAGE_GENERATION "${env_file}" 2>/dev/null || printf 'false')"
  engine="$(env_get OPEN_WEBUI_IMAGE_GENERATION_ENGINE "${env_file}" 2>/dev/null || printf 'openai')"
  model="$(env_get OPEN_WEBUI_IMAGE_GENERATION_MODEL "${env_file}" 2>/dev/null || printf '')"
  base_url="$(env_get OPEN_WEBUI_IMAGES_OPENAI_API_BASE_URL "${env_file}" 2>/dev/null || printf '')"
  api_key="$(env_get OPEN_WEBUI_IMAGES_OPENAI_API_KEY "${env_file}" 2>/dev/null || printf '')"

  if [[ "${enabled}" != "true" ]]; then
    return 0
  fi

  case "${engine}" in
    openai)
      if [[ -z "${base_url}" ]]; then
        fail "${env_file}: OPEN_WEBUI_ENABLE_IMAGE_GENERATION=true with engine=openai requires OPEN_WEBUI_IMAGES_OPENAI_API_BASE_URL"
      fi
      if [[ -z "${api_key}" ]]; then
        fail "${env_file}: OPEN_WEBUI_ENABLE_IMAGE_GENERATION=true with engine=openai requires OPEN_WEBUI_IMAGES_OPENAI_API_KEY"
      fi
      ;;
    comfyui)
      if [[ -z "${model}" ]]; then
        fail "${env_file}: engine=comfyui requires OPEN_WEBUI_IMAGE_GENERATION_MODEL"
      else
        check_path_exists \
          "${REPO_DIR}/data/comfyui/models/checkpoints/${model}" \
          "missing ComfyUI checkpoint for OPEN_WEBUI_IMAGE_GENERATION_MODEL"
      fi
      ;;
    automatic1111)
      local a1111_url
      a1111_url="$(env_get OPEN_WEBUI_AUTOMATIC1111_BASE_URL "${env_file}" 2>/dev/null || printf '')"
      if [[ -z "${a1111_url}" ]]; then
        fail "${env_file}: engine=automatic1111 requires OPEN_WEBUI_AUTOMATIC1111_BASE_URL"
      fi
      ;;
    *)
      warn "${env_file}: unknown OPEN_WEBUI_IMAGE_GENERATION_ENGINE=${engine}"
      ;;
  esac
}

validate_workspace_mount() {
  local env_file="$1"
  local workspace_path
  workspace_path="$(env_get OPEN_WEBUI_WORKSPACE_HOST_PATH "${env_file}" 2>/dev/null || printf '.')"
  if [[ "${workspace_path}" == "." ]]; then
    workspace_path="${REPO_DIR}"
  fi
  check_path_exists "${workspace_path}" "Open WebUI workspace host path does not exist"
}

scaffold_dirs() {
  local dirs=(
    "data/paperless/consume"
    "data/paperless/media"
    "data/paperless/export"
    "data/paperless/data"
    "data/redis"
    "data/db"
    "data/ollama"
    "data/paperless-ai-web"
    "data/open-webui"
    "data/comfyui/models/checkpoints"
    "data/comfyui/input"
    "data/comfyui/output"
    "data/comfyui/custom_nodes"
    "data/openvino-image-models"
    "data/paddleocr-cache"
    "config/tessdata-best"
  )

  local dir
  for dir in "${dirs[@]}"; do
    run_or_echo mkdir -p "${REPO_DIR}/${dir}"
  done
}

scaffold_files() {
  copy_if_missing "${REPO_DIR}/.env.example" "${REPO_DIR}/.env"
  copy_if_missing "${REPO_DIR}/compose.override.example.yml" "${REPO_DIR}/compose.override.yml"
  copy_if_missing "${REPO_DIR}/config/paperless.conf.example" "${REPO_DIR}/config/paperless-ai.env"
  copy_if_missing "${REPO_DIR}/config/preview_config.example.json" "${REPO_DIR}/config/preview_config.json"
  copy_if_missing "${REPO_DIR}/config/tag_allowlists.example.json" "${REPO_DIR}/config/tag_allowlists.json"
  copy_if_missing "${REPO_DIR}/config/tag_rules.example.json" "${REPO_DIR}/config/tag_rules.json"
  copy_if_missing "${REPO_DIR}/config/providers.example.json" "${REPO_DIR}/config/providers.json"
  copy_if_missing "${REPO_DIR}/config/models.example.json" "${REPO_DIR}/config/models.json"
  copy_if_missing "${REPO_DIR}/config/version.example.json" "${REPO_DIR}/config/version.json"
}

validate_repo_state() {
  local env_file="${REPO_DIR}/.env"
  local effective_env_file="${env_file}"
  local strict_env_validation="true"
  local config_files=(
    "config/paperless-ai.env"
    "config/preview_config.json"
    "config/tag_allowlists.json"
    "config/tag_rules.json"
    "config/providers.json"
    "config/models.json"
    "config/version.json"
  )

  say ""
  say "Validation"

  check_path_exists "${REPO_DIR}/compose.yml" "missing compose file"
  check_path_exists "${REPO_DIR}/docker/open-webui/Dockerfile" "missing repo-managed Open WebUI wrapper"
  check_path_exists "${REPO_DIR}/scripts/openwebui/install_model_profiles.py" "missing Open WebUI profile installer"
  check_path_exists "${REPO_DIR}/scripts/openwebui/install_workspace_agent_tools.py" "missing Open WebUI workspace tool installer"
  check_path_exists "${REPO_DIR}/scripts/nas/apply-amd-power-cap.sh" "missing AMD power-cap helper"
  check_path_exists "${REPO_DIR}/scripts/nas/mi50-power-cap.service" "missing AMD power-cap service"
  check_path_exists "${REPO_DIR}/docker/tika-ocr-proxy/Dockerfile" "missing tika-ocr-proxy Dockerfile"

  if [[ ! -f "${env_file}" ]]; then
    if [[ "${DRY_RUN}" == "true" && "${VALIDATE_ONLY}" != "true" ]]; then
      warn ".env is missing in the current tree; dry-run continues with .env.example as the projected target"
      effective_env_file="${REPO_DIR}/.env.example"
      strict_env_validation="false"
    else
      fail ".env is missing; run the bootstrap without --validate first"
      effective_env_file=""
    fi
  fi

  if [[ -n "${effective_env_file}" ]]; then
    validate_placeholder PAPERLESS_SECRET_KEY "${effective_env_file}" "${strict_env_validation}"
    validate_placeholder OPEN_WEBUI_SECRET_KEY "${effective_env_file}" "${strict_env_validation}"
    validate_placeholder PAPERLESS_ADMIN_PASSWORD "${effective_env_file}" "${strict_env_validation}"
    validate_placeholder POSTGRES_PASSWORD "${effective_env_file}" "${strict_env_validation}"
    validate_placeholder PAPERLESS_DBPASS "${effective_env_file}" "${strict_env_validation}"
    validate_workspace_mount "${effective_env_file}"
    validate_image_backend "${effective_env_file}"
  fi

  local rel_path
  for rel_path in "${config_files[@]}"; do
    if [[ -e "${REPO_DIR}/${rel_path}" ]]; then
      continue
    fi
    if [[ "${DRY_RUN}" == "true" && "${VALIDATE_ONLY}" != "true" ]]; then
      warn "${rel_path} is missing in the current tree; dry-run assumes the scaffold step will create it"
      continue
    fi
    fail "missing ${rel_path}"
  done

  validate_compose_config
}

print_next_steps() {
  local env_file="${REPO_DIR}/.env"
  local image_enabled="false"
  local image_engine="openai"

  if [[ -f "${env_file}" ]]; then
    image_enabled="$(env_get OPEN_WEBUI_ENABLE_IMAGE_GENERATION "${env_file}" 2>/dev/null || printf 'false')"
    image_engine="$(env_get OPEN_WEBUI_IMAGE_GENERATION_ENGINE "${env_file}" 2>/dev/null || printf 'openai')"
  fi

  say ""
  say "Next steps"
  say "1. Edit .env and replace all CHANGE_ME / REPLACE_WITH_TOKEN placeholders."
  say "2. Verify docker compose output:"
  say "   cd ${REPO_DIR} && docker compose config"
  say "3. Start the base stack:"
  say "   cd ${REPO_DIR} && docker compose up -d broker db gotenberg tika webserver ollama"
  say "4. Start optional services as needed:"
  say "   docker compose up -d consumer task-queue scheduler"
  say "   docker compose --profile ui up -d paperless-ai-web"
  say "   docker compose --profile chat-ui up -d --build open-webui"

  if [[ "${image_enabled}" == "true" ]]; then
    case "${image_engine}" in
      openai)
        say "5. Image generation is enabled via external OpenAI-compatible backend. Verify base URL and API key in .env."
        ;;
      comfyui)
        say "5. Image generation is enabled via experimental AMD ComfyUI. Ensure the checkpoint file exists and then run:"
        say "   docker compose --profile chat-ui --profile image-amd up -d --build comfyui-amd open-webui"
        ;;
      automatic1111)
        say "5. Image generation is enabled via AUTOMATIC1111. Verify the API endpoint and auth settings before testing."
        ;;
    esac
  else
    say "5. If you want image generation, enable it in .env and choose either an external OpenAI-compatible backend or an experimental local backend."
  fi
}

say "NAS stack bootstrap"
say "Repository: ${REPO_DIR}"
if [[ "${DRY_RUN}" == "true" ]]; then
  say "Dry-run mode is active."
fi
if [[ "${VALIDATE_ONLY}" == "true" ]]; then
  say "Validation-only mode is active."
fi

if [[ "${VALIDATE_ONLY}" != "true" ]]; then
  say ""
  say "Scaffolding directories and default files"
  scaffold_dirs
  scaffold_files
fi

validate_repo_state
print_next_steps

exit "${EXIT_CODE}"
