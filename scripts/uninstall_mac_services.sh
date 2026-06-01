#!/usr/bin/env bash
set -euo pipefail

LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
USER_ID="$(id -u)"

SERVICES=(
  "com.helix.backend"
  "com.helix.scanner"
  "com.helix.csv-refresh"
)

for service in "${SERVICES[@]}"; do
  target_plist="${LAUNCH_AGENTS_DIR}/${service}.plist"

  if launchctl print "gui/${USER_ID}/${service}" >/dev/null 2>&1; then
    launchctl bootout "gui/${USER_ID}" "${target_plist}" || true
    echo "Unloaded ${service}"
  else
    echo "${service} is not loaded"
  fi

  if [[ -f "${target_plist}" ]]; then
    rm "${target_plist}"
    echo "Removed ${target_plist}"
  fi
done

echo "Helix LaunchAgents uninstalled."
