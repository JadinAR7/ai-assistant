#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/jadinrobinson/ai-assistant"
TEMPLATE_DIR="${PROJECT_ROOT}/scripts/launchagents"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
USER_ID="$(id -u)"

SERVICES=(
  "com.helix.backend"
  "com.helix.scanner"
  "com.helix.csv-refresh"
)

mkdir -p "${LAUNCH_AGENTS_DIR}" "${PROJECT_ROOT}/backend/logs"
chmod +x \
  "${PROJECT_ROOT}/scripts/start_backend.sh" \
  "${PROJECT_ROOT}/scripts/start_scanner.sh" \
  "${PROJECT_ROOT}/scripts/start_csv_refresh.sh" \
  "${PROJECT_ROOT}/scripts/install_mac_services.sh" \
  "${PROJECT_ROOT}/scripts/uninstall_mac_services.sh" \
  "${PROJECT_ROOT}/scripts/status_mac_services.sh"

for service in "${SERVICES[@]}"; do
  source_plist="${TEMPLATE_DIR}/${service}.plist"
  target_plist="${LAUNCH_AGENTS_DIR}/${service}.plist"

  if [[ ! -f "${source_plist}" ]]; then
    echo "Missing plist template: ${source_plist}" >&2
    exit 1
  fi

  cp "${source_plist}" "${target_plist}"
  plutil -lint "${target_plist}"

  if launchctl print "gui/${USER_ID}/${service}" >/dev/null 2>&1; then
    launchctl bootout "gui/${USER_ID}" "${target_plist}" >/dev/null 2>&1 || true
  fi

  launchctl bootstrap "gui/${USER_ID}" "${target_plist}"
  launchctl enable "gui/${USER_ID}/${service}"
  echo "Loaded ${service}"
done

echo "Helix LaunchAgents installed."
