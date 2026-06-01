# Helix macOS Services

Helix can run as user LaunchAgents on macOS. These services load under your user account, not as root daemons.

## Services

- `com.helix.backend`: runs the FastAPI backend with `backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000`.
- `com.helix.scanner`: runs `backend/scheduled_scan.py`, which performs automatic market scans during configured scan windows.
- `com.helix.csv-refresh`: runs `scripts/start_csv_refresh.sh`, a small loop that calls `csv_refresh.run_csv_refresh(force=False)` every 60 seconds so the existing CSV refresh schedule can fire at its configured windows.

All services run from `/Users/jadinrobinson/ai-assistant/backend` and write launchd logs to `/Users/jadinrobinson/ai-assistant/backend/logs/`.

## Install

From the project root:

```bash
scripts/install_mac_services.sh
```

This copies plist templates from `scripts/launchagents/` into `~/Library/LaunchAgents/`, validates them with `plutil`, and loads them into the current user's `launchctl` GUI domain.

## Uninstall

```bash
scripts/uninstall_mac_services.sh
```

This unloads the user LaunchAgents and removes the copied plist files from `~/Library/LaunchAgents/`.

## Service Commands

```bash
scripts/status_mac_services.sh status
scripts/status_mac_services.sh restart
scripts/status_mac_services.sh tail
scripts/status_mac_services.sh logs
```

You can also unload everything with:

```bash
scripts/uninstall_mac_services.sh
```

## Notifications

Notifications are disabled by default in both the plist templates and start scripts:

```text
SCAN_NOTIFY_ENABLED=false
SCAN_NOTIFY_IMESSAGE_ENABLED=false
SCAN_NOTIFY_TTS_ENABLED=false
SCAN_NOTIFY_IMESSAGE_RECIPIENT=
```

To enable them, edit the installed scanner plist at:

```text
~/Library/LaunchAgents/com.helix.scanner.plist
```

Set only the channels you want, for example:

```xml
<key>SCAN_NOTIFY_ENABLED</key>
<string>true</string>
<key>SCAN_NOTIFY_IMESSAGE_ENABLED</key>
<string>true</string>
<key>SCAN_NOTIFY_TTS_ENABLED</key>
<string>false</string>
<key>SCAN_NOTIFY_IMESSAGE_RECIPIENT</key>
<string>recipient@example.com</string>
```

Then restart services:

```bash
scripts/status_mac_services.sh restart
```

Do not put secrets in plist files.

## Verify Backend

```bash
curl http://127.0.0.1:8000/
```

Expected response:

```json
{"status":"backend running"}
```

## Verify Scanner

```bash
curl http://127.0.0.1:8000/scan/status
```

You can also inspect the runtime status file:

```bash
cat /Users/jadinrobinson/ai-assistant/backend/scan_runtime_status.json
```

## Verify CSV Refresh

```bash
curl http://127.0.0.1:8000/csv-refresh/status
```

You can also inspect:

```bash
cat /Users/jadinrobinson/ai-assistant/backend/csv_refresh_status.json
```

## Logs

Logs live in:

```text
/Users/jadinrobinson/ai-assistant/backend/logs/
```

Files:

- `backend.out.log`
- `backend.err.log`
- `scanner.out.log`
- `scanner.err.log`
- `csv-refresh.out.log`
- `csv-refresh.err.log`

Tail them together:

```bash
scripts/status_mac_services.sh tail
```

## Troubleshooting

- If a service is `not loaded`, run `scripts/install_mac_services.sh`.
- If backend health fails, check `backend/logs/backend.err.log` and confirm `backend/.venv/bin/uvicorn` exists.
- If scanner status shows no heartbeat, check `backend/logs/scanner.err.log` and `backend/scan_runtime_status.json`.
- If CSV refresh does not run, check `backend/logs/csv-refresh.out.log`, `backend/logs/csv-refresh.err.log`, and `backend/csv_refresh_status.json`. Outside scheduled windows, CSV refresh records a skipped status.
- After editing a plist in `~/Library/LaunchAgents/`, run `scripts/status_mac_services.sh restart`.
- To fully reload changed plist files, run `scripts/uninstall_mac_services.sh` and then `scripts/install_mac_services.sh`.
