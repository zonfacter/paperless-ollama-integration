#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

DEFAULT_PRIMARY_MODEL="qwen3.5:9b"
DEFAULT_FALLBACK_MODEL="qwen3.5:4b"
DEFAULT_TIMEOUT="300"
DEFAULT_CONTENT_CHARS="5000"
DEFAULT_CONFIDENCE="0.35"
DEFAULT_TAG_COLOR="#4f6bed"
DEFAULT_PAPERLESS_API_URL="http://127.0.0.1:8000"
DEFAULT_OLLAMA_URL="http://127.0.0.1:11434"
DRY_RUN="false"

for arg in "$@"; do
  case "${arg}" in
    --dry-run)
      DRY_RUN="true"
      ;;
    -h|--help)
      cat <<'EOF'
Usage: install-paperless-ai.sh [--dry-run]

Options:
  --dry-run   Collect inputs and print what would be changed without writing files.
  -h, --help  Show this help.
EOF
      exit 0
      ;;
    *)
      echo "Unknown option: ${arg}" >&2
      exit 1
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root."
  exit 1
fi

say() {
  printf '%s\n' "$*"
}

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
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

ask() {
  local prompt="$1"
  local default="${2-}"
  local reply
  if [[ -n "${default}" ]]; then
    read -r -p "${prompt} [${default}]: " reply
    printf '%s' "${reply:-$default}"
  else
    read -r -p "${prompt}: " reply
    printf '%s' "${reply}"
  fi
}

ask_required() {
  local prompt="$1"
  local value=""
  while [[ -z "${value}" ]]; do
    value="$(ask "${prompt}")"
  done
  printf '%s' "${value}"
}

ask_yes_no() {
  local prompt="$1"
  local default="${2:-y}"
  local reply
  local suffix="y/N"
  if [[ "${default}" == "y" ]]; then
    suffix="Y/n"
  fi
  while true; do
    read -r -p "${prompt} [${suffix}]: " reply
    reply="${reply:-$default}"
    case "${reply}" in
      y|Y|yes|YES) return 0 ;;
      n|N|no|NO) return 1 ;;
    esac
  done
}

find_compose_file() {
  local candidate
  for candidate in \
    "${PWD}/compose.yml" \
    "${PWD}/compose.yaml" \
    "${PWD}/docker-compose.yml" \
    "${PWD}/docker-compose.yaml" \
    "/opt/paperless/docker-compose.yml" \
    "/opt/paperless/compose.yml" \
    "/srv/paperless/docker-compose.yml"; do
    if [[ -f "${candidate}" ]]; then
      printf '%s' "${candidate}"
      return 0
    fi
  done
  return 1
}

update_key_value_file() {
  local file="$1"
  local temp_file
  shift
  if [[ "${DRY_RUN}" == "true" ]]; then
    say "[dry-run] would update ${file} with:"
    local pair
    for pair in "$@"; do
      say "  - ${pair}"
    done
    return 0
  fi
  temp_file="$(mktemp)"
  python3 - "$file" "$temp_file" "$@" <<'PY'
import pathlib
import sys

src = pathlib.Path(sys.argv[1])
dst = pathlib.Path(sys.argv[2])
pairs = [arg.split("=", 1) for arg in sys.argv[3:]]
updates = {key: value for key, value in pairs}

if src.exists():
    lines = src.read_text().splitlines()
else:
    lines = []

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

missing = [key for key in updates if key not in handled]
if missing:
    if new_lines and new_lines[-1] != "":
        new_lines.append("")
    for key in missing:
        new_lines.append(f"{key}={updates[key]}")

dst.write_text("\n".join(new_lines).rstrip() + "\n")
PY
  install -m 600 "${temp_file}" "${file}"
  rm -f "${temp_file}"
}

install_native() {
  local conf_file="$1"
  local install_dir="$2"
  local paperless_api_url="$3"
  local paperless_api_token="$4"
  local ollama_url="$5"
  local primary_model="$6"
  local fallback_enabled="$7"
  local fallback_model="$8"
  local timeout_seconds="$9"
  local content_chars="${10}"
  local confidence="${11}"
  local tag_color="${12}"

  run_or_echo mkdir -p "${install_dir}"
  run_or_echo install -m 755 "${REPO_DIR}/hooks/ai_enrich.py" "${install_dir}/ai_enrich.py"
  run_or_echo install -m 644 "${REPO_DIR}/prompts/ai_enrich_prompt.txt" "${install_dir}/ai_enrich_prompt.txt"
  run_or_echo install -m 644 "${REPO_DIR}/scripts/ai_backfill.py" "${install_dir}/ai_backfill.py"

  run_or_echo cp -a "${conf_file}" "${conf_file}.bak.$(date +%Y%m%d%H%M%S)"
  update_key_value_file "${conf_file}" \
    "PAPERLESS_POST_CONSUME_SCRIPT=${install_dir}/ai_enrich.py" \
    "PAPERLESS_API_URL=${paperless_api_url}" \
    "PAPERLESS_API_TOKEN=${paperless_api_token}" \
    "PAPERLESS_AI_PROVIDER=ollama" \
    "PAPERLESS_AI_OLLAMA_URL=${ollama_url}" \
    "PAPERLESS_AI_OLLAMA_MODEL=${primary_model}" \
    "PAPERLESS_AI_FALLBACK_ENABLED=${fallback_enabled}" \
    "PAPERLESS_AI_FALLBACK_MODEL=${fallback_model}" \
    "PAPERLESS_AI_FALLBACK_ON_TIMEOUT_ONLY=true" \
    "PAPERLESS_AI_HTTP_TIMEOUT_SECONDS=${timeout_seconds}" \
    "PAPERLESS_AI_FALLBACK_HTTP_TIMEOUT_SECONDS=${timeout_seconds}" \
    "PAPERLESS_AI_PROMPT_FILE=${install_dir}/ai_enrich_prompt.txt" \
    "PAPERLESS_AI_CONTENT_CHARS=${content_chars}" \
    "PAPERLESS_AI_MIN_CONFIDENCE=${confidence}" \
    "PAPERLESS_AI_DEFAULT_TAG_COLOR=${tag_color}" \
    "PAPERLESS_AI_QWEN35_THINK=false"

  run_or_echo install -m 644 "${REPO_DIR}/systemd/paperless-scheduler.service" /etc/systemd/system/paperless-scheduler.service
  run_or_echo systemctl daemon-reload
  if ask_yes_no "Restart native Paperless services now" "y"; then
    run_or_echo systemctl restart paperless-webserver.service
    run_or_echo systemctl restart paperless-consumer.service
    run_or_echo systemctl restart paperless-task-queue.service
    if [[ "${DRY_RUN}" == "true" ]]; then
      say "[dry-run] systemctl restart paperless-scheduler.service"
    else
      systemctl restart paperless-scheduler.service || true
    fi
  fi

  if ask_yes_no "Install the local Paperless AI Console on port 3000" "y"; then
    local ui_user
    ui_user="$(ask_required "Local user that should run the web UI")"
    local ui_home
    ui_home="$(eval echo "~${ui_user}")"
    if [[ "${DRY_RUN}" != "true" ]]; then
      [[ -d "${ui_home}" ]] || fail "Home directory not found for ${ui_user}"
    fi
    run_or_echo mkdir -p "${ui_home}/ollama-web"
    run_or_echo install -m 755 "${REPO_DIR}/web/server.py" "${ui_home}/ollama-web/server.py"
    run_or_echo chown -R "${ui_user}:${ui_user}" "${ui_home}/ollama-web"

    run_or_echo install -m 755 "${REPO_DIR}/scripts/paperless-ai-admin" /usr/local/sbin/paperless-ai-admin
    run_or_echo install -m 755 "${REPO_DIR}/scripts/paperless-set-ollama-model" /usr/local/sbin/paperless-set-ollama-model

    if [[ "${DRY_RUN}" == "true" ]]; then
      say "[dry-run] would render /etc/sudoers.d/paperless-ai-admin for user ${ui_user}"
      say "[dry-run] would render /etc/sudoers.d/paperless-model for user ${ui_user}"
      say "[dry-run] would render /etc/systemd/system/ollama-web.service for user ${ui_user}"
      say "[dry-run] systemctl daemon-reload"
      say "[dry-run] systemctl enable --now ollama-web.service"
    else
      sed "s/PAPERLESS_UI_USER/${ui_user}/g" "${REPO_DIR}/systemd/paperless-ai-admin.sudoers.example" > /etc/sudoers.d/paperless-ai-admin
      sed "s/PAPERLESS_UI_USER/${ui_user}/g" "${REPO_DIR}/systemd/paperless-model.sudoers.example" > /etc/sudoers.d/paperless-model
      chmod 440 /etc/sudoers.d/paperless-ai-admin /etc/sudoers.d/paperless-model

      sed "s/PAPERLESS_UI_USER/${ui_user}/g" "${REPO_DIR}/systemd/ollama-web.service" > /etc/systemd/system/ollama-web.service
      systemctl daemon-reload
      systemctl enable --now ollama-web.service
    fi
  fi
}

install_docker() {
  local compose_file="$1"
  local compose_dir="$2"
  local env_file="$3"
  local host_integration_dir="$4"
  local container_integration_dir="$5"
  local web_service="$6"
  local paperless_api_url="$7"
  local paperless_api_token="$8"
  local ollama_url="$9"
  local primary_model="${10}"
  local fallback_enabled="${11}"
  local fallback_model="${12}"
  local timeout_seconds="${13}"
  local content_chars="${14}"
  local confidence="${15}"
  local tag_color="${16}"

  run_or_echo mkdir -p "${host_integration_dir}"
  run_or_echo install -m 755 "${REPO_DIR}/hooks/ai_enrich.py" "${host_integration_dir}/ai_enrich.py"
  run_or_echo install -m 644 "${REPO_DIR}/prompts/ai_enrich_prompt.txt" "${host_integration_dir}/ai_enrich_prompt.txt"
  run_or_echo install -m 644 "${REPO_DIR}/scripts/ai_backfill.py" "${host_integration_dir}/ai_backfill.py"

  if [[ "${DRY_RUN}" == "true" ]]; then
    say "[dry-run] would write env file ${env_file}"
  else
    cat > "${env_file}" <<EOF
PAPERLESS_POST_CONSUME_SCRIPT=${container_integration_dir}/ai_enrich.py
PAPERLESS_API_URL=${paperless_api_url}
PAPERLESS_API_TOKEN=${paperless_api_token}
PAPERLESS_AI_PROVIDER=ollama
PAPERLESS_AI_OLLAMA_URL=${ollama_url}
PAPERLESS_AI_OLLAMA_MODEL=${primary_model}
PAPERLESS_AI_FALLBACK_ENABLED=${fallback_enabled}
PAPERLESS_AI_FALLBACK_MODEL=${fallback_model}
PAPERLESS_AI_FALLBACK_ON_TIMEOUT_ONLY=true
PAPERLESS_AI_HTTP_TIMEOUT_SECONDS=${timeout_seconds}
PAPERLESS_AI_FALLBACK_HTTP_TIMEOUT_SECONDS=${timeout_seconds}
PAPERLESS_AI_PROMPT_FILE=${container_integration_dir}/ai_enrich_prompt.txt
PAPERLESS_AI_CONTENT_CHARS=${content_chars}
PAPERLESS_AI_MIN_CONFIDENCE=${confidence}
PAPERLESS_AI_DEFAULT_TAG_COLOR=${tag_color}
PAPERLESS_AI_QWEN35_THINK=false
EOF
  fi

  if [[ "${DRY_RUN}" == "true" ]]; then
    say "[dry-run] would write override file ${compose_dir}/docker-compose.override.yml"
  else
    cat > "${compose_dir}/docker-compose.override.yml" <<EOF
services:
  ${web_service}:
    env_file:
      - $(basename "${env_file}")
    volumes:
      - ${host_integration_dir}:${container_integration_dir}:ro
EOF
  fi

  say ""
  say "Docker files written:"
  say "  Compose base:    ${compose_file}"
  say "  Override file:   ${compose_dir}/docker-compose.override.yml"
  say "  Env file:        ${env_file}"
  say "  Integration dir: ${host_integration_dir}"
  say ""
  say "Review the generated override if your Paperless service is not named '${web_service}'."
  if ask_yes_no "Run 'docker compose up -d ${web_service}' now" "y"; then
    if [[ "${DRY_RUN}" == "true" ]]; then
      say "[dry-run] (cd ${compose_dir} && docker compose up -d ${web_service})"
    else
      (
        cd "${compose_dir}"
        docker compose up -d "${web_service}"
      )
    fi
  fi
}

say "Paperless AI guided installer"
say ""
say "This installer will ask for the values it needs before writing files."
if [[ "${DRY_RUN}" == "true" ]]; then
  say "Dry-run mode is active. No files will be written."
fi
say ""
say "You should have ready:"
say "  - a Paperless API token"
say "  - the Paperless API URL"
say "  - the local or remote Ollama URL"
say "  - the primary model and optional fallback model"
say ""

native_detected="no"
docker_detected="no"
detected_compose_file=""
if [[ -f /opt/paperless/paperless.conf ]]; then
  native_detected="yes"
fi
if detected_compose_file="$(find_compose_file)"; then
  docker_detected="yes"
fi

say "Detected environment:"
say "  - native Paperless config: ${native_detected}"
say "  - docker compose candidate: ${docker_detected}"
if [[ -n "${detected_compose_file}" ]]; then
  say "  - compose file: ${detected_compose_file}"
fi
say ""

mode_default="native"
if [[ "${native_detected}" != "yes" && "${docker_detected}" == "yes" ]]; then
  mode_default="docker"
fi
mode="$(ask "Install mode (native/docker)" "${mode_default}")"
case "${mode}" in
  native|docker) ;;
  *) fail "Unsupported mode: ${mode}" ;;
esac

paperless_api_url="$(ask "Paperless API URL" "${DEFAULT_PAPERLESS_API_URL}")"
paperless_api_token="$(ask_required "Paperless API token")"
ollama_url="$(ask "Ollama URL" "${DEFAULT_OLLAMA_URL}")"
primary_model="$(ask "Primary Ollama model" "${DEFAULT_PRIMARY_MODEL}")"
fallback_enabled="false"
fallback_model=""
if ask_yes_no "Enable fallback model" "y"; then
  fallback_enabled="true"
  fallback_model="$(ask "Fallback Ollama model" "${DEFAULT_FALLBACK_MODEL}")"
else
  fallback_model="${DEFAULT_FALLBACK_MODEL}"
fi
timeout_seconds="$(ask "HTTP timeout in seconds" "${DEFAULT_TIMEOUT}")"
content_chars="$(ask "OCR characters per document" "${DEFAULT_CONTENT_CHARS}")"
confidence="$(ask "Minimum confidence" "${DEFAULT_CONFIDENCE}")"
tag_color="$(ask "Default tag color" "${DEFAULT_TAG_COLOR}")"

if [[ "${mode}" == "native" ]]; then
  conf_file="$(ask "Path to paperless.conf" "/opt/paperless/paperless.conf")"
  [[ -f "${conf_file}" ]] || fail "paperless.conf not found: ${conf_file}"
  install_dir="$(ask "Target directory for hook and prompt" "/opt/paperless")"
  install_native \
    "${conf_file}" \
    "${install_dir}" \
    "${paperless_api_url}" \
    "${paperless_api_token}" \
    "${ollama_url}" \
    "${primary_model}" \
    "${fallback_enabled}" \
    "${fallback_model}" \
    "${timeout_seconds}" \
    "${content_chars}" \
    "${confidence}" \
    "${tag_color}"
else
  compose_file="$(ask "Path to docker compose file" "${detected_compose_file:-${PWD}/docker-compose.yml}")"
  [[ -f "${compose_file}" ]] || fail "Compose file not found: ${compose_file}"
  compose_dir="$(cd "$(dirname "${compose_file}")" && pwd)"
  env_file="$(ask "Path for generated Paperless AI env file" "${compose_dir}/paperless-ai.env")"
  host_integration_dir="$(ask "Host directory for hook/prompt/backfill files" "${compose_dir}/paperless-ai")"
  container_integration_dir="$(ask "Container path for mounted integration files" "/usr/src/paperless-ai")"
  web_service="$(ask "Docker compose service name for Paperless webserver" "webserver")"
  install_docker \
    "${compose_file}" \
    "${compose_dir}" \
    "${env_file}" \
    "${host_integration_dir}" \
    "${container_integration_dir}" \
    "${web_service}" \
    "${paperless_api_url}" \
    "${paperless_api_token}" \
    "${ollama_url}" \
    "${primary_model}" \
    "${fallback_enabled}" \
    "${fallback_model}" \
    "${timeout_seconds}" \
    "${content_chars}" \
    "${confidence}" \
    "${tag_color}"
fi

say ""
say "Installation summary"
say "  mode:              ${mode}"
say "  Paperless API URL: ${paperless_api_url}"
say "  Ollama URL:        ${ollama_url}"
say "  primary model:     ${primary_model}"
say "  fallback enabled:  ${fallback_enabled}"
say "  fallback model:    ${fallback_model}"
say ""
say "Done."
