#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/jadinrobinson/ai-assistant"
LOG_DIR="${PROJECT_ROOT}/backend/logs"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
USER_ID="$(id -u)"

SERVICES=(
  "com.helix.backend"
  "com.helix.scanner"
  "com.helix.csv-refresh"
)

usage() {
  cat <<'USAGE'
Usage: scripts/status_mac_services.sh [status|restart|tail|logs]

Commands:
  status   Show launchd status for Helix services.
  restart  Kickstart loaded Helix services.
  tail     Tail all service logs.
  logs     List service log files.
USAGE
}

service_plist() {
  printf "%s/%s.plist" "${LAUNCH_AGENTS_DIR}" "$1"
}

show_status() {
  for service in "${SERVICES[@]}"; do
    echo "== ${service} =="
    if launchctl print "gui/${USER_ID}/${service}" >/dev/null 2>&1; then
      launchctl print "gui/${USER_ID}/${service}" | awk '
        /state =/ || /pid =/ || /last exit code =/ || /program =/ {
          gsub(/^[[:space:]]+/, "")
          print
        }
      '
    else
      echo "not loaded"
    fi
    echo
  done
}

restart_services() {
  for service in "${SERVICES[@]}"; do
    if launchctl print "gui/${USER_ID}/${service}" >/dev/null 2>&1; then
      launchctl kickstart -k "gui/${USER_ID}/${service}"
      echo "Restarted ${service}"
    else
      plist="$(service_plist "${service}")"
      echo "${service} is not loaded. Install with scripts/install_mac_services.sh (${plist})."
    fi
  done
}

tail_logs() {
  mkdir -p "${LOG_DIR}"
  touch \
    "${LOG_DIR}/backend.out.log" \
    "${LOG_DIR}/backend.err.log" \
    "${LOG_DIR}/scanner.out.log" \
    "${LOG_DIR}/scanner.err.log" \
    "${LOG_DIR}/csv-refresh.out.log" \
    "${LOG_DIR}/csv-refresh.err.log"

  tail -n 80 -F \
    "${LOG_DIR}/backend.out.log" \
    "${LOG_DIR}/backend.err.log" \
    "${LOG_DIR}/scanner.out.log" \
    "${LOG_DIR}/scanner.err.log" \
    "${LOG_DIR}/csv-refresh.out.log" \
    "${LOG_DIR}/csv-refresh.err.log"
}

list_logs() {
  mkdir -p "${LOG_DIR}"
  ls -la "${LOG_DIR}"
}

command="${1:-status}"

case "${command}" in
  status)
    show_status
    ;;
  restart)
    restart_services
    ;;
  tail)
    tail_logs
    ;;
  logs)
    list_logs
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    usage >&2
    exit 2
    ;;
esac
