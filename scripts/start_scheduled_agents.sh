#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/jadinrobinson/ai-assistant"
BACKEND_DIR="${PROJECT_ROOT}/backend"
LOG_DIR="${BACKEND_DIR}/logs"
PYTHON_BIN="${BACKEND_DIR}/.venv/bin/python"
SCHEDULED_AGENTS_INTERVAL_SECONDS="${SCHEDULED_AGENTS_INTERVAL_SECONDS:-300}"

mkdir -p "${LOG_DIR}"
cd "${BACKEND_DIR}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  echo "Missing Python executable: ${PYTHON_BIN}" >&2
  exit 1
fi

export PYTHONUNBUFFERED="${PYTHONUNBUFFERED:-1}"

exec "${PYTHON_BIN}" scheduled_agents.py --interval-seconds "${SCHEDULED_AGENTS_INTERVAL_SECONDS}"
