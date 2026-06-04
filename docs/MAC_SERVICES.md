# Helix macOS Services

Helix can run selected local processes as user LaunchAgents on macOS. These services load under Jadin's user account, not as root daemons.

This runbook manages LaunchAgent support only. It does not start services unless Jadin explicitly runs `scripts/install_mac_services.sh`, `scripts/status_mac_services.sh restart`, or another launchctl command.

## Service Plan

Always-on recommended:

- `com.helix.backend`: FastAPI backend on `0.0.0.0:8000` for local and LAN/phone access.
- `com.helix.frontend`: Next.js frontend on `0.0.0.0:3000`, available from the phone at `http://192.168.8.119:3000`.
- `com.helix.scheduled-agents`: Morning Review, Evening Review, daily prioritization snapshot, and Morning Check-In fallback check loop.
- `com.helix.imessage-bridge`: local iMessage command/reply bridge, if Messages permissions and allowed-sender config are stable.

Optional always-on:

- `com.helix.scanner`: scheduled MES scanner, if automatic chart scanning is desired.
- `com.helix.csv-refresh`: scheduled CSV refresh loop, if automatic TradingView CSV refresh checks are desired.

Manual/optional:

- Wake listener v1: run manually with `python3 backend/wake_listener.py --once` or `--loop`.
- Voice trigger prototype: run manually with `python3 backend/voice_trigger.py`.

Required external dependency:

- Ollama must be running separately. The backend expects `OLLAMA_URL`, defaulting to `http://localhost:11434/api/generate`.

## Managed Services

| Service | Start script | LaunchAgent template | Logs |
| --- | --- | --- | --- |
| `com.helix.backend` | `scripts/start_backend.sh` | `scripts/launchagents/com.helix.backend.plist` | `backend/logs/backend.out.log`, `backend/logs/backend.err.log` |
| `com.helix.frontend` | `scripts/start_frontend.sh` | `scripts/launchagents/com.helix.frontend.plist` | `backend/logs/frontend.out.log`, `backend/logs/frontend.err.log` |
| `com.helix.scheduled-agents` | `scripts/start_scheduled_agents.sh` | `scripts/launchagents/com.helix.scheduled-agents.plist` | `backend/logs/scheduled-agents.out.log`, `backend/logs/scheduled-agents.err.log` |
| `com.helix.imessage-bridge` | `scripts/start_imessage_bridge.sh` | `scripts/launchagents/com.helix.imessage-bridge.plist` | `backend/logs/imessage-bridge.out.log`, `backend/logs/imessage-bridge.err.log` |
| `com.helix.scanner` | `scripts/start_scanner.sh` | `scripts/launchagents/com.helix.scanner.plist` | `backend/logs/scanner.out.log`, `backend/logs/scanner.err.log` |
| `com.helix.csv-refresh` | `scripts/start_csv_refresh.sh` | `scripts/launchagents/com.helix.csv-refresh.plist` | `backend/logs/csv-refresh.out.log`, `backend/logs/csv-refresh.err.log` |

Most managed services run from `/Users/jadinrobinson/ai-assistant/backend`. The frontend service runs from `/Users/jadinrobinson/ai-assistant/frontend`.

The frontend service prefers production mode when `.next` exists:

```bash
npm run start -- -H 0.0.0.0 -p 3000
```

If `.next` is missing, it safely falls back to dev mode:

```bash
npm run dev -- -H 0.0.0.0 -p 3000
```

`NEXT_PUBLIC_API_URL` is set to `http://192.168.8.119:8000`. The backend must remain bound to `0.0.0.0:8000` for phone access.

## Install

From the project root:

```bash
scripts/install_mac_services.sh
```

Default install target is `all`.

Install only the recommended core services:

```bash
scripts/install_mac_services.sh core
```

Install all managed services:

```bash
scripts/install_mac_services.sh all
```

Install explicit services:

```bash
scripts/install_mac_services.sh frontend
scripts/install_mac_services.sh backend scheduled-agents imessage-bridge
scripts/install_mac_services.sh scanner csv-refresh
```

The install script copies plist templates from `scripts/launchagents/` into `~/Library/LaunchAgents/`, validates them with `plutil`, and loads them into the current user's `launchctl` GUI domain.

The install script handles:

- `com.helix.backend`
- `com.helix.frontend`
- `com.helix.scheduled-agents`
- `com.helix.imessage-bridge`
- `com.helix.scanner`
- `com.helix.csv-refresh`

Wake listener v1 is intentionally not installed.

## Status

```bash
scripts/status_mac_services.sh status
```

The status command prints:

- launchd loaded/running state for each managed service
- each service's stdout/stderr log path
- backend health check at `http://127.0.0.1:8000/`
- scheduled agents API status from `/agents/scheduled/status` when the backend is reachable
- scanner API status from `/scan/status` when the backend is reachable
- the full list of log tail locations

Other status helper commands:

```bash
scripts/status_mac_services.sh logs
scripts/status_mac_services.sh tail
scripts/status_mac_services.sh restart
```

`restart` only kickstarts services that are already loaded.

## Uninstall

```bash
scripts/uninstall_mac_services.sh
```

This unloads the managed user LaunchAgents and removes the copied plist files from `~/Library/LaunchAgents/`.

## Notifications

Notification environment variables are conservative in the plist templates:

```text
SCAN_NOTIFY_ENABLED=false
SCAN_NOTIFY_IMESSAGE_ENABLED=false
SCAN_NOTIFY_TTS_ENABLED=false
SCAN_NOTIFY_IMESSAGE_RECIPIENT=
```

To enable scan notifications, edit the installed scanner plist:

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

Then reload the service:

```bash
scripts/uninstall_mac_services.sh
scripts/install_mac_services.sh
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

The backend also needs to remain reachable on the LAN address for phone access:

```bash
curl http://192.168.8.119:8000/
```

## Verify Frontend

The normal local and phone URL is:

```text
http://192.168.8.119:3000
```

tmux is no longer required for normal frontend startup once `com.helix.frontend` is installed. Check logs:

```bash
tail -n 80 backend/logs/frontend.out.log
tail -n 80 backend/logs/frontend.err.log
```

## Verify Scheduled Agents

```bash
curl http://127.0.0.1:8000/agents/scheduled/status
```

The scheduled-agent LaunchAgent runs `backend/scheduled_agents.py` continuously with `SCHEDULED_AGENTS_INTERVAL_SECONDS`, default `300`.

Manual one-shot check:

```bash
cd /Users/jadinrobinson/ai-assistant
backend/.venv/bin/python backend/scheduled_agents.py --once
```

## Verify iMessage Bridge

The bridge reads the local Messages database and sends replies through AppleScript. It requires:

- macOS Messages database access
- AppleScript permission for Messages
- a stable allowed sender in `backend/imessage_bridge.py`
- backend availability for chat, scan, TTS, and Morning Check-In routes

Check logs:

```bash
tail -n 80 backend/logs/imessage-bridge.out.log
tail -n 80 backend/logs/imessage-bridge.err.log
```

## Verify Scanner

```bash
curl http://127.0.0.1:8000/scan/status
```

You can also inspect:

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

## Manual TTS Test

This endpoint is for manual notification voice testing only. It does not run scanner alert eligibility and does not send iMessages.

```bash
curl -X POST "http://127.0.0.1:8000/notify/test-tts"
```

Optional custom message:

```bash
curl -X POST "http://127.0.0.1:8000/notify/test-tts?message=Helix%20voice%20test%20online"
```

## Manual iMessage Test

This endpoint is for manual notification iMessage testing only. It does not run scanner alert eligibility and does not trigger TTS.

```bash
curl -X POST "http://127.0.0.1:8000/notify/test-imessage"
```

Optional custom message:

```bash
curl -X POST "http://127.0.0.1:8000/notify/test-imessage?message=Helix%20iMessage%20test%20online"
```

Optional recipient:

```bash
curl -X POST "http://127.0.0.1:8000/notify/test-imessage?recipient=YOUR_RECIPIENT&message=Helix%20iMessage%20test%20online"
```

## Notification Config

This returns notification channel config and a masked default recipient.

```bash
curl http://127.0.0.1:8000/notify/config
```

## Manual All-Channel Test

This endpoint is for manual notification testing only. It sends a test iMessage and speaks a test TTS message without running scanner alert eligibility.

```bash
curl -X POST "http://127.0.0.1:8000/notify/test-all"
```

## Logs

Logs live in:

```text
/Users/jadinrobinson/ai-assistant/backend/logs/
```

Files:

- `backend.out.log`
- `backend.err.log`
- `frontend.out.log`
- `frontend.err.log`
- `scanner.out.log`
- `scanner.err.log`
- `csv-refresh.out.log`
- `csv-refresh.err.log`
- `scheduled-agents.out.log`
- `scheduled-agents.err.log`
- `imessage-bridge.out.log`
- `imessage-bridge.err.log`

Tail them together:

```bash
scripts/status_mac_services.sh tail
```

## Troubleshooting

- If a service is `not loaded`, run `scripts/install_mac_services.sh`.
- If backend health fails, check `backend/logs/backend.err.log`, confirm `backend/.venv/bin/uvicorn` exists, and confirm Ollama is running for chat/model routes.
- If the frontend is unavailable, check `backend/logs/frontend.err.log`, confirm `frontend/node_modules` exists, and confirm the backend is reachable at `http://192.168.8.119:8000`.
- If scheduled agents do not run, check `backend/logs/scheduled-agents.err.log`, `backend/.scheduled_agents_status.json`, and `GET /agents/scheduled/status`.
- If iMessage bridge does not reply, check Messages permissions, `backend/logs/imessage-bridge.err.log`, and backend health.
- If scanner status shows no heartbeat, check `backend/logs/scanner.err.log` and `backend/scan_runtime_status.json`.
- If CSV refresh does not run, check `backend/logs/csv-refresh.out.log`, `backend/logs/csv-refresh.err.log`, and `backend/csv_refresh_status.json`. Outside scheduled windows, CSV refresh records a skipped status.
- After editing a plist in `~/Library/LaunchAgents/`, fully reload changed plist files with `scripts/uninstall_mac_services.sh` and then `scripts/install_mac_services.sh`.
