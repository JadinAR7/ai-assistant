#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/Users/jadinrobinson/ai-assistant"
LOG_DIR="${PROJECT_ROOT}/backend/logs"
LAUNCH_AGENTS_DIR="${HOME}/Library/LaunchAgents"
USER_ID="$(id -u)"

SERVICES=(
  "com.helix.backend"
  "com.helix.frontend"
  "com.helix.scheduled-agents"
  "com.helix.imessage-bridge"
  "com.helix.scanner"
  "com.helix.csv-refresh"
)

LOG_FILES=(
  "backend.out.log"
  "backend.err.log"
  "frontend.out.log"
  "frontend.err.log"
  "scanner.out.log"
  "scanner.err.log"
  "csv-refresh.out.log"
  "csv-refresh.err.log"
  "scheduled-agents.out.log"
  "scheduled-agents.err.log"
  "imessage-bridge.out.log"
  "imessage-bridge.err.log"
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
    echo "logs: ${LOG_DIR}/$(log_prefix "${service}").out.log"
    echo "      ${LOG_DIR}/$(log_prefix "${service}").err.log"
    echo
  done

  show_backend_health
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
  local paths=()

  for log_file in "${LOG_FILES[@]}"; do
    touch "${LOG_DIR}/${log_file}"
    paths+=("${LOG_DIR}/${log_file}")
  done

  tail -n 80 -F "${paths[@]}"
}

list_logs() {
  mkdir -p "${LOG_DIR}"
  ls -la "${LOG_DIR}"
}

log_prefix() {
  case "$1" in
    com.helix.backend)
      printf "backend"
      ;;
    com.helix.frontend)
      printf "frontend"
      ;;
    com.helix.scheduled-agents)
      printf "scheduled-agents"
      ;;
    com.helix.imessage-bridge)
      printf "imessage-bridge"
      ;;
    com.helix.scanner)
      printf "scanner"
      ;;
    com.helix.csv-refresh)
      printf "csv-refresh"
      ;;
    *)
      printf "%s" "$1"
      ;;
  esac
}

curl_json() {
  curl -fsS --max-time 3 "$1" 2>/dev/null
}

print_endpoint_status() {
  local label="$1"
  local url="$2"
  local response

  echo "== ${label} =="
  if response="$(curl_json "${url}")"; then
    echo "${response}"
  else
    echo "unavailable: ${url}"
  fi
  echo
}

show_backend_health() {
  echo "== Backend Health =="
  if curl_json "http://127.0.0.1:8000/" >/dev/null; then
    curl_json "http://127.0.0.1:8000/"
    echo
    echo
    print_endpoint_status "Scheduled Agents API" "http://127.0.0.1:8000/agents/scheduled/status"
    print_endpoint_status "Scanner API" "http://127.0.0.1:8000/scan/status"
  else
    echo "backend health check failed: http://127.0.0.1:8000/"
    echo "API status endpoints skipped because backend is unavailable."
    echo
  fi

  echo "== Log Tail Locations =="
  for log_file in "${LOG_FILES[@]}"; do
    echo "${LOG_DIR}/${log_file}"
  done
  echo
  echo "Tail logs with: scripts/status_mac_services.sh tail"
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
