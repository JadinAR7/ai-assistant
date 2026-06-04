#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/jadinrobinson/ai-assistant"
TEMPLATE_DIR="${PROJECT_ROOT}/scripts/launchagents"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
USER_ID="$(id -u)"

ALL_SERVICES=(
  "com.helix.backend"
  "com.helix.frontend"
  "com.helix.scheduled-agents"
  "com.helix.imessage-bridge"
  "com.helix.scanner"
  "com.helix.csv-refresh"
)

CORE_SERVICES=(
  "com.helix.backend"
  "com.helix.frontend"
  "com.helix.scheduled-agents"
  "com.helix.imessage-bridge"
)

usage() {
  cat <<'USAGE'
Usage: scripts/install_mac_services.sh [all|core|SERVICE...]

Groups:
  all    Install backend, frontend, scheduled-agents, imessage-bridge, scanner, and csv-refresh. Default.
  core   Install backend, frontend, scheduled-agents, and imessage-bridge.

Services:
  backend
  frontend
  scheduled-agents
  imessage-bridge
  scanner
  csv-refresh
USAGE
}

service_label() {
  case "$1" in
    com.helix.*)
      printf "%s\n" "$1"
      ;;
    backend|frontend|scheduled-agents|imessage-bridge|scanner|csv-refresh)
      printf "com.helix.%s\n" "$1"
      ;;
    *)
      echo "Unknown service: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
}

selected_services() {
  if [[ "$#" -eq 0 || "$1" == "all" ]]; then
    printf "%s\n" "${ALL_SERVICES[@]}"
    return
  fi

  if [[ "$1" == "core" ]]; then
    printf "%s\n" "${CORE_SERVICES[@]}"
    return
  fi

  for service in "$@"; do
    service_label "${service}"
  done
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" || "${1:-}" == "help" ]]; then
  usage
  exit 0
fi

mkdir -p "${LAUNCH_AGENTS_DIR}" "${PROJECT_ROOT}/backend/logs"
chmod +x \
  "${PROJECT_ROOT}/scripts/start_backend.sh" \
  "${PROJECT_ROOT}/scripts/start_frontend.sh" \
  "${PROJECT_ROOT}/scripts/start_scheduled_agents.sh" \
  "${PROJECT_ROOT}/scripts/start_imessage_bridge.sh" \
  "${PROJECT_ROOT}/scripts/start_scanner.sh" \
  "${PROJECT_ROOT}/scripts/start_csv_refresh.sh" \
  "${PROJECT_ROOT}/scripts/install_mac_services.sh" \
  "${PROJECT_ROOT}/scripts/uninstall_mac_services.sh" \
  "${PROJECT_ROOT}/scripts/status_mac_services.sh"

while IFS= read -r service; do
  [[ -n "${service}" ]] || continue

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
done < <(selected_services "$@")

echo "Helix LaunchAgents installed."
