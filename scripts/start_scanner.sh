#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/jadinrobinson/ai-assistant"
BACKEND_DIR="${PROJECT_ROOT}/backend"
LOG_DIR="${BACKEND_DIR}/logs"
PYTHON_BIN="${BACKEND_DIR}/.venv/bin/python"

mkdir -p "${LOG_DIR}"
cd "${BACKEND_DIR}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing Python executable: ${PYTHON_BIN}" >&2
  exit 1
fi

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"
export SCAN_NOTIFY_ENABLED="${SCAN_NOTIFY_ENABLED:-false}"
export SCAN_NOTIFY_IMESSAGE_ENABLED="${SCAN_NOTIFY_IMESSAGE_ENABLED:-false}"
export SCAN_NOTIFY_TTS_ENABLED="${SCAN_NOTIFY_TTS_ENABLED:-false}"
export SCAN_NOTIFY_IMESSAGE_RECIPIENT="${SCAN_NOTIFY_IMESSAGE_RECIPIENT:-}"

exec "${PYTHON_BIN}" scheduled_scan.py
