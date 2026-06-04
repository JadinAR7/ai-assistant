#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/jadinrobinson/ai-assistant"
FRONTEND_DIR="${PROJECT_ROOT}/frontend"
LOG_DIR="${PROJECT_ROOT}/backend/logs"

mkdir -p "${LOG_DIR}"
cd "${FRONTEND_DIR}"

export NEXT_PUBLIC_API_URL="http://192.168.8.119:8000"

if [[ -d ".next" ]]; then
  exec npm run start -- -H 0.0.0.0 -p 3000
fi

exec npm run dev -- -H 0.0.0.0 -p 3000
