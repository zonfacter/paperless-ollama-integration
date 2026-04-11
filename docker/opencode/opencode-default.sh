#!/usr/bin/env bash
set -euo pipefail

MODEL="${OPENCODE_DEFAULT_MODEL:-orfree/gpt-oss-20b-free}"
AGENT="${OPENCODE_DEFAULT_AGENT:-build}"
PROJECT_DIR="${1:-/workspace}"

exec opencode --model "${MODEL}" --agent "${AGENT}" "${PROJECT_DIR}"
