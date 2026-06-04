#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/jadinrobinson/ai-assistant"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
LOG_DIR="${PROJECT_ROOT}/backend/logs"

mkdir -p "${LOG_DIR}"
cd "${FRONTEND_DIR}"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export NEXT_PUBLIC_API_URL="http://192.168.8.119:8000"

if ! NPM_BIN="$(command -v npm)"; then
  echo "npm not found. PATH=${PATH}" >&2
  exit 127
fi

if [[ -d ".next" ]]; then
  exec "${NPM_BIN}" run start -- -H 0.0.0.0 -p 3000
fi

exec "${NPM_BIN}" run dev -- -H 0.0.0.0 -p 3000
