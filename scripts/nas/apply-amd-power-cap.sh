#!/usr/bin/env bash
set -euo pipefail

GPU_CARD="${AMD_GPU_CARD:-auto}"
POWER_CAP_WATTS="${AMD_GPU_POWER_CAP_WATTS:-150}"
HWMON_DIR=""

if [[ "${GPU_CARD}" == "auto" ]]; then
  for card_path in /sys/class/drm/card[0-9]*; do
    [[ -d "${card_path}/device" ]] || continue
    vendor="$(cat "${card_path}/device/vendor" 2>/dev/null || true)"
    [[ "${vendor}" == "0x1002" ]] || continue
    for candidate in "${card_path}/device/hwmon"/hwmon*; do
      if [[ -d "${candidate}" && -f "${candidate}/power1_cap" ]]; then
        GPU_CARD="$(basename "${card_path}")"
        HWMON_DIR="${candidate}"
        break 2
      fi
    done
  done
fi

DRM_ROOT="/sys/class/drm/${GPU_CARD}/device"

if [[ ! -d "${DRM_ROOT}" ]]; then
  echo "GPU path not found: ${DRM_ROOT}" >&2
  exit 1
fi

if [[ -z "${HWMON_DIR}" ]]; then
  for candidate in "${DRM_ROOT}"/hwmon/hwmon*; do
    if [[ -d "${candidate}" && -f "${candidate}/power1_cap" ]]; then
      HWMON_DIR="${candidate}"
      break
    fi
  done
fi

if [[ -z "${HWMON_DIR}" ]]; then
  echo "No hwmon power cap interface found below ${DRM_ROOT}" >&2
  exit 1
fi

current_uW="$(cat "${HWMON_DIR}/power1_cap")"
min_uW="$(cat "${HWMON_DIR}/power1_cap_min")"
max_uW="$(cat "${HWMON_DIR}/power1_cap_max")"
target_uW="$(awk -v watts="${POWER_CAP_WATTS}" 'BEGIN { printf "%.0f", watts * 1000000 }')"

if (( target_uW < min_uW )); then
  target_uW="${min_uW}"
fi
if (( target_uW > max_uW )); then
  target_uW="${max_uW}"
fi

if [[ "${current_uW}" != "${target_uW}" ]]; then
  echo "${target_uW}" > "${HWMON_DIR}/power1_cap"
fi

printf 'MI50 power cap active: %.1f W (requested %.1f W, range %.1f-%.1f W)\n' \
  "$(awk -v v="${target_uW}" 'BEGIN { print v / 1000000 }')" \
  "${POWER_CAP_WATTS}" \
  "$(awk -v v="${min_uW}" 'BEGIN { print v / 1000000 }')" \
  "$(awk -v v="${max_uW}" 'BEGIN { print v / 1000000 }')"
