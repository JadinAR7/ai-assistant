# Helix Project Overview

## Vision

Helix is a local-first AI assistant designed to help Jadin manage trading, planning, automation, learning, and long-term life goals.

Helix is intended to become a personal operating system rather than a simple chatbot.

The long-term objective is to create an assistant capable of:

* Trading awareness and market monitoring
* Daily planning and organization
* Reminder management
* Research assistance
* Voice interaction
* Personal knowledge management
* Goal tracking
* Life progress tracking
* Automation workflows

Helix remains the central intelligence layer across all connected systems.

---

# Core Principles

## Single Brain Architecture

Helix is the only AI assistant.

Future systems should not create separate AI assistants.

Instead:

* Helix makes decisions
* Agents perform specialized tasks
* Orbit stores planning and execution data

## Source of Truth Rules

### Trading

CSV data is responsible for:

* Historical structure
* FVG mapping
* Liquidity mapping
* Market structure analysis
* Historical context

Vision analysis is responsible for:

* Live visible chart context
* Current displayed price
* User markings
* Labels
* Session context
* Visual confirmation

Freshness rules:

* Fresh CSVs may be used for structure and price context.
* Stale CSVs may only be used for structure and FVG mapping.
* When CSV is stale, vision becomes the primary live-context source.
* Helix must never present stale CSV prices as confirmed live market prices.

### Orbit

Orbit is the source of truth for:

* Tasks
* Goals
* Milestones
* Reviews
* Trade sessions
* Readiness tracking
* Major events
* Progress tracking
* Agent run records

### User

The user always overrides Helix.

---

# Current Architecture

## Backend

Technology:

* FastAPI
* SQLite
* Ollama
* Python
* macOS `say`, Messages, and LaunchAgents for local voice/notification/service glue

Primary modules:

* `backend/main.py`: FastAPI app, chat, scanner, CSV refresh, TTS, notification, history, and tool-log routes.
* `backend/tools.py`: Helix tool layer for Orbit, trading, web/search helpers, reminders, file tools, and TradingView workflows.
* `backend/orbit/service.py`: Orbit data and planning logic.
* `backend/orbit/routes.py`: Orbit API surface.
* `backend/agent_service.py`: Agent definitions, prioritization, manual runs, and read-only agent output.
* `backend/scheduled_agents.py`: scheduled Morning Review, Evening Review, daily prioritization snapshot, and morning fallback check loop.
* `backend/morning_checkin.py`: Morning Check-In acknowledgement, fallback state, iMessage fallback delivery, and speech condensation.
* `backend/scheduled_scan.py`: MES scanner, chart capture, analysis, state comparison, alert eligibility, and gated scan notifications.
* `backend/csv_refresh.py`: scheduled and forced CSV refresh with verification before active file replacement.
* `backend/tts.py`: speech formatter, macOS voice discovery/config, and TTS dispatch.
* `backend/imessage_bridge.py`: local iMessage polling bridge and command router.
* `backend/voice_trigger.py`: manual push-to-talk / typed morning trigger prototype.
* `backend/wake_listener.py`: manual wake phrase listener prototype.

Storage:

* `backend/assistant.db`: chat/tool logs plus Orbit tables.
* `backend/scan_history.jsonl`: scanner records.
* `backend/scan_runtime_status.json`: scanner heartbeat/status.
* `backend/csv_refresh_status.json`: CSV refresh status.
* `backend/.scheduled_agents_status.json`: scheduled-agent and prioritization snapshot status.
* `backend/.morning_checkin_status.json`: daily morning acknowledgement/fallback state.

## Frontend

Technology:

* Next.js app router
* React client components for interactive Orbit and Command Center controls

Responsibilities:

* Helix Core home surface at `/`
* Command Center at `/command-center`
* Orbit Operating Board at `/orbit`
* Trade Journal surfaces at `/trade-journal` and `/orbit/trade-journal`
* Scanner controls and status displays
* Agent controls, scheduled-agent status, Morning Check-In controls, and prioritization display
* Future reporting and Ascend surfaces

---

# Current State

Helix is now a working local-first assistant with an operational trading scanner, Orbit planning APIs, Agent Foundation v1, Web Search Agent v1, Readiness Advisory Agent v1, Agent Prioritization Layer v1, Scheduled Agent Runs v1, Morning Check-In / Fallback Summary v1, a Next.js frontend, macOS service automation, CSV refresh automation, TTS, speech formatting, voice profile configuration, iMessage notification infrastructure, a manual voice trigger prototype, a manual wake phrase listener, and the cleaned-up Orbit Overview layout.

The trading system has moved beyond basic scan summaries. It performs multi-timeframe chart capture and deterministic analysis, combines CSV structure with live TradingView visuals, identifies liquidity draw, classifies behavior, detects continuation compression and expansion, evaluates alert eligibility, and can deliver controlled notifications when enabled.

Notifications remain intentionally gated. Smart scan notifications default disabled and only deliver when the scanner has already determined notification eligibility. Manual notification test endpoints exist so TTS and iMessage delivery can be verified without fabricating a real Medium or High trading alert.

Helix remains the central intelligence layer. Orbit stores structured planning, progress, trade-session, readiness, and agent-run data. Scanner logic remains separate from Orbit.

---

# Current Service Map

## Backend API

* Service: FastAPI app from `backend/main.py`
* Local URL: `http://127.0.0.1:8000`
* Start script: `scripts/start_backend.sh`
* LaunchAgent: `scripts/launchagents/com.helix.backend.plist`
* Command: `backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000`
* Logs: `backend/logs/backend.out.log`, `backend/logs/backend.err.log`

## Frontend Dev Server

* Service: Next.js frontend
* Local URL: `http://localhost:3000`
* Directory: `frontend`
* Command: `npm run dev`
* Backend base URL: `NEXT_PUBLIC_API_URL` or `http://127.0.0.1:8000`

## Scheduled Scanner

* Service: MES scheduled chart scanner
* Module: `backend/scheduled_scan.py`
* Start script: `scripts/start_scanner.sh`
* LaunchAgent: `scripts/launchagents/com.helix.scanner.plist`
* Default symbol/timeframes: MES, scheduled 4H/1H/15M/5M with 15M primary
* Interval: 5 minutes during active market sessions
* Status endpoint: `GET /scan/status`
* Latest scan endpoint: `GET /scan/latest`
* Force endpoint: `POST /scan/force`
* Logs: `backend/logs/scanner.out.log`, `backend/logs/scanner.err.log`

## CSV Refresh

* Service: TradingView CSV refresh scheduler
* Module: `backend/csv_refresh.py`
* Start script: `scripts/start_csv_refresh.sh`
* LaunchAgent: `scripts/launchagents/com.helix.csv-refresh.plist`
* Interval wrapper: `CSV_REFRESH_INTERVAL_SECONDS`, default 60 seconds
* Refresh windows: New York session hourly, futures reopen, and Friday post-close review refresh
* Active data directory: `backend/csv_data`
* Status endpoint: `GET /csv-refresh/status`
* Force endpoint: `POST /csv-refresh/force`
* Logs: `backend/logs/csv-refresh.out.log`, `backend/logs/csv-refresh.err.log`

## Scheduled Agents

* Service: Python scheduler module, currently API-callable and CLI-runnable
* Module: `backend/scheduled_agents.py`
* CLI: `python3 backend/scheduled_agents.py --once` or loop with `--interval-seconds`
* Morning window: 06:00-09:00 local, runs Morning Review Agent once per day
* Evening window: 18:00-22:00 local, runs Evening Review Agent once per day
* Daily snapshot: Agent Prioritization Layer snapshot once per day
* Fallback check: invokes Morning Check-In fallback check after the scheduled-agent pass
* Status endpoint: `GET /agents/scheduled/status`
* Run-once endpoint: `POST /agents/scheduled/run-once`
* Status file: `backend/.scheduled_agents_status.json`
* Limitation: no dedicated LaunchAgent plist is currently present for scheduled agents.

## iMessage Bridge

* Service: local polling bridge for macOS Messages
* Module: `backend/imessage_bridge.py`
* Polls: `~/Library/Messages/chat.db` read-only
* Sends: AppleScript through the Messages app
* Allowed sender: configured in code as `ALLOWED_SENDER`
* Routes: help, time, latest MES scan, forced MES scan, TTS commands, Morning Check-In, and normal `/chat`
* Backend dependencies: `/chat`, `/scan/latest`, `/scan/force`, `/tts/say`, `/agents/morning/check-in`
* Limitation: no LaunchAgent plist is currently present for the bridge.

## Wake Listener

* Service: manual local wake phrase listener prototype
* Module: `backend/wake_listener.py`
* CLI: `python3 backend/wake_listener.py --once`, `python3 backend/wake_listener.py --loop`, or typed simulation with `--text`
* Wake phrases: `good morning helix`, `morning helix`, `start my morning`
* Target endpoint: `POST /agents/morning/check-in` with `source="voice"` and `speak=true`
* Optional dependencies: `SpeechRecognition`, `PyAudio`, `pocketsphinx`
* Limitation: manual only; no auto-starting service or full conversational voice loop.

## Ollama

* Service: local model runtime used by Helix chat and vision/text workflows
* Default generate URL: `http://localhost:11434/api/generate`
* Config variables: `OLLAMA_URL`, `OLLAMA_MODEL`, `VISION_MODEL`
* Current defaults in backend: `qwen3.5:9b` for text and `qwen2.5vl:7b` for vision
* Limitation: backend chat fails if Ollama is unavailable or the configured models are missing.

---

# Helix Core Platform

Helix Core is now a compact command surface rather than a stacked dashboard.

Current capabilities:

* Compact home layout with the Helix body as the main assistant presence
* Orbit-backed Morning Briefing status below the Helix body
* Compact module navigation
* Chat and tool execution through the FastAPI backend
* Local memory/history storage
* Access to Orbit tools for planning, task capture, reviews, readiness, and trade sessions
* Command Center access for chat, tool modes, image upload, scanner status, and manual scanner actions
* Trade Journal access for logging and reviewing trade sessions

Helix can generate a Morning Briefing when Jadin asks for a morning briefing, daily briefing, or what to focus on today. The briefing uses real Orbit data rather than hardcoded focus or blocker content.

---

# Orbit Operating Board

Orbit is the planning and execution platform powered by Helix. Orbit is not another AI assistant.

Orbit is now organized as a minimalist tab-based operating board.

Tabs:

* Overview
* Tasks
* Milestones
* Reviews
* Readiness
* Agents

Overview shows the most important operating signals:

* Corporate Escape countdown and progress
* Suggested Next Action
* Top priority tasks
* Current blockers
* Overall readiness

## Morning Briefing

Morning Briefing is backed by real Orbit data.

It includes:

* Active major event context
* Overall readiness
* Priority milestones
* Top tasks
* Current blockers
* Suggested next action
* Recent reviews
* Recent trade sessions

Morning Briefing prioritizes open tasks linked to active or in-progress milestones above untagged Inbox tasks.

Morning Briefing is used by:

* Helix chat tool routing
* Helix Core home status line
* Orbit Overview
* Morning Review Agent
* Morning Check-In
* Morning fallback iMessage summary
* Voice trigger and wake listener prototypes

## Daily Closeout

Daily Closeout is implemented and available from Orbit.

It includes:

* Tasks completed today
* Remaining open tasks
* Milestone progress changes
* Readiness summary
* Trade session summary
* Recent reviews
* Recommended review prompt

Daily Closeout reviews can be saved back into Orbit.

## Inbox Controls

Orbit Inbox controls are the current task capture and task management layer.

Current capabilities:

* Add task from the Orbit Tasks tab
* Optional due date
* Multiline descriptions, notes, and checklist-style text
* Preserved line breaks in task row display
* Status actions: Queue, Start, Complete
* Open tasks show queued, open, and in-progress work
* Completed tasks leave the active list immediately
* Completed today and older completed tasks are hidden behind compact toggles

## Milestone Task Links

Tasks remain in the Orbit Inbox. Milestones act as structured tags, not folders.

Current capabilities:

* Many-to-many task/milestone link table
* One task can link to multiple milestones
* One milestone can have multiple linked tasks
* Duplicate task/milestone links are prevented
* Task creation can optionally include milestone links
* Task rows display linked milestone chips
* Milestones show linked task counts
* Milestones can expand to show linked tasks

## Progress Advisory and History

Milestone progress remains manual.

Linked tasks provide an advisory signal only:

* Total linked tasks
* Completed linked tasks
* Open linked tasks
* In-progress linked tasks
* Queued linked tasks
* Suggested task completion percent

The Milestones tab can show current progress, linked task completion count, task-based progress suggestion, latest progress history, and a manual Apply suggested progress button when the advisory differs from current progress.

Progress is applied only when Jadin explicitly presses Apply suggested progress. Orbit stores progress history for manual changes and task-advisory applications.

## Recommendations and Suggested Task Creation

Suggested Task Creation v1 is implemented for Orbit recommendations.

Current capabilities:

* Recommendations can produce task drafts.
* Task creation requires explicit user approval.
* Strategic gap recommendations can create milestone-linked Inbox tasks.
* Created tasks remain Inbox tasks and use milestone links as structured tags.
* No autonomous task creation yet.

Confirmed Orbit flow:

1. Strategic Gap
2. Recommendation
3. Preview Task
4. Create Task
5. Linked Inbox Task
6. Priority Score
7. Morning Briefing

## Priority and Recommendation State

Current state:

* Task priority scoring works.
* Strategic gap detection works.
* Recommendations work.
* Suggested task creation works.
* Agent prioritization works.
* Agents are still read-only and do not create tasks.
* Recommendation task creation remains explicit user-approved creation from the UI/API.

---

# Current Endpoints

## Core

* `GET /`: backend health check.
* `POST /chat`: primary chat and tool-routing endpoint.
* `POST /chat/stream`: streaming chat endpoint.
* `POST /analyze-image`: uploaded chart/image analysis.
* `POST /reset`: clear chat memory.
* `GET /history`: recent chat history.
* `GET /tool-logs`: recent tool calls.

## Scanner and CSV

* `POST /scan/force`: run a forced scan.
* `GET /scan/latest`: load latest scan record.
* `GET /scan/status`: scanner runtime status.
* `GET /csv-refresh/status`: CSV refresh status.
* `POST /csv-refresh/force`: force CSV refresh.

## TTS and Notifications

* `GET /tts/voices`: list macOS `say` voices.
* `GET /tts/config`: current TTS voice/rate/formatter config.
* `POST /tts/say`: format and speak text.
* `GET /notify/config`: notification config.
* `POST /notify/test-tts`: manual TTS notification test.
* `POST /notify/test-imessage`: manual iMessage test.
* `POST /notify/test-all`: manual iMessage plus TTS test.

## Orbit

* `GET /orbit/health`
* `GET /orbit/morning-briefing`
* `GET /orbit/daily-closeout`
* `POST /orbit/daily-closeout/review`
* `GET /orbit/recommendations`
* `POST /orbit/recommendations/{recommendation_id}/task-draft`
* `POST /orbit/recommendations/{recommendation_id}/create-task`
* `GET /orbit/major-events`
* `POST /orbit/major-events`
* `GET/PATCH/DELETE /orbit/major-events/{event_id}`
* `GET /orbit/milestones`
* `POST /orbit/milestones`
* `GET/PATCH/DELETE /orbit/milestones/{milestone_id}`
* `GET /orbit/milestones/progress-advisory`
* `GET /orbit/milestones/{milestone_id}/progress-advisory`
* `GET /orbit/milestones/{milestone_id}/progress-history`
* `GET /orbit/progress-history/recent`
* `GET /orbit/milestones/{milestone_id}/tasks`
* `GET /orbit/goals`
* `POST /orbit/goals`
* `GET/PATCH/DELETE /orbit/goals/{goal_id}`
* `GET /orbit/tasks`
* `POST /orbit/tasks`
* `GET/PATCH/DELETE /orbit/tasks/{task_id}`
* `GET /orbit/inbox-tasks`
* `POST /orbit/inbox-tasks`
* `GET /orbit/tasks/{task_id}/milestones`
* `POST/DELETE /orbit/tasks/{task_id}/milestones/{milestone_id}`
* `GET /orbit/task-priorities`
* `GET /orbit/strategic-gaps`
* `GET /orbit/reviews`
* `POST /orbit/reviews`
* `GET /orbit/readiness`
* `PATCH /orbit/readiness/{readiness_id}`
* `GET /orbit/trade-sessions`
* `POST /orbit/trade-sessions`
* `GET/PATCH/DELETE /orbit/trade-sessions/{trade_session_id}`

## Agents

* `GET /agents`: list agent definitions with latest run.
* `GET /agents/runs/recent`: recent agent runs.
* `GET /agents/prioritize`: read-only agent prioritization.
* `GET /agents/scheduled/status`: scheduled-agent window and snapshot status.
* `POST /agents/scheduled/run-once`: run due scheduled agents and fallback check once.
* `GET /agents/morning/status`: morning acknowledgement/fallback state.
* `POST /agents/morning/check-in`: acknowledge/run Morning Check-In.
* `POST /agents/morning/fallback-check`: send fallback iMessage if due.
* `GET /agents/{agent_id}`: get one agent.
* `POST /agents/{agent_id}/run`: manually run one enabled agent.

---

# Trading Intelligence / Scanner

The scanner is centered in `backend/scheduled_scan.py`.

Current scanner capabilities:

* TradingView screenshot capture
* Scheduled scanner loop with runtime status and scan history
* Forced scan endpoint
* Multi-timeframe scanner capture for 4H, 1H, 15M, and 5M context
* CSV auto-refresh with freshness checks and source-of-truth handling
* Vision plus CSV chart analysis pipeline
* Liquidity Draw Engine
* Behavior Classification v3
* Continuation Pattern Detection
* Expansion Detection
* Opportunity Watch generation
* Chart Alert Eligibility Engine
* News risk gating and context
* Smart scan notification infrastructure for iMessage and TTS
* Mac service support for backend, scanner, and CSV refresh

Core flow:

1. Determine whether the current time is inside an active scan window.
2. Capture the primary TradingView chart context.
3. Optionally collect scheduled multi-timeframe captures.
4. Run vision and deterministic CSV-backed chart analysis.
5. Attach data freshness and source-of-truth context.
6. Compare current state against recent scan history.
7. Attach Liquidity Draw Engine output.
8. Attach Behavior Classification v3 output.
9. Attach chart alert eligibility.
10. Deliver scan notifications only when notification infrastructure is enabled and alert eligibility allows it.
11. Persist scan history and runtime status.

Key endpoints:

* `POST /scan/force`
* `GET /scan/latest`
* `GET /scan/status`

## CSV Refresh Automation

CSV refresh is implemented in `backend/csv_refresh.py`.

Current capabilities:

* Scheduled CSV refresh windows
* Force refresh endpoint
* Temporary export directory
* Verification before replacing active CSV files
* Status file at `backend/csv_refresh_status.json`
* LaunchAgent-backed refresh loop through `com.helix.csv-refresh`
* Logs in `backend/logs/csv-refresh.out.log` and `backend/logs/csv-refresh.err.log`

Key endpoints:

* `GET /csv-refresh/status`
* `POST /csv-refresh/force`

## Multi-Timeframe Analysis

The scanner separates higher-timeframe context from lower-timeframe confirmation:

* 4H and 1H provide directional context, larger FVGs, liquidity context, and draw alignment.
* 15M is the primary scheduled scan and review timeframe.
* 5M provides continuation, compression, breakout, and expansion evidence.
* 1M remains reserved for execution confirmation and is not used for HTF bias.

CSV data contributes historical structure and FVG mapping. Vision remains primary for current displayed price and live visual evidence when CSV freshness is limited.

## Liquidity Draw

The Liquidity Draw Engine determines the most likely draw on liquidity from CSV and visual context.

Examples of draw references:

* Previous day high and low
* Previous New York session high and low
* Asia high and low
* London high and low
* Previous week high and low
* Visible chart liquidity labels

The scanner uses liquidity draw output downstream in behavior classification, opportunity recognition, alert eligibility, and notification formatting.

## Behavior Classification

Behavior Classification v3 classifies how price is behaving relative to draw, structure, reaction zones, and multi-timeframe visual evidence.

Current classifications include:

* Acceptance
* Rejection
* Reclaim
* Sweep
* Displacement
* Consolidation
* Bullish continuation compression
* Bullish continuation expansion
* Unknown

The classifier attaches evidence, confidence, data limitations, missing confirmations, liquidity draw status, continuation pattern checks, and expansion pattern checks to each scan record.

## Continuation Compression and Expansion

Continuation detection identifies structured continuation contexts rather than treating every FVG touch as an alert.

The current golden-pattern logic looks for:

* HTF FVG sweep or reaction context
* 1H reclaim or retest behavior
* 5M continuation FVG
* Continuation breakout evidence
* Upside liquidity draw alignment
* Fresh or recent supporting data

Expansion detection identifies when a prior bullish continuation compression begins moving away from the continuation structure.

Bullish continuation expansion is treated as a stronger review condition than compression, but still requires sufficient freshness or strong visual evidence before notification eligibility is upgraded.

## Alert Eligibility

Alert eligibility is a chart-review triage layer. It does not create trade signals, entries, or execution instructions.

Current levels:

* None
* Low
* Medium
* High

Only Medium and High chart-review states are notification-worthy. Low and None remain scanner output only.

Trigger refinement is currently paused. Future scanner work should refine alert triggers, opportunity language, bearish parity, and execution confirmation without weakening source-of-truth rules.

---

# Agent System

Agent Foundation v1 has been added for future Orbit and Helix automation.

Purpose:

* Define agents
* Manually run agents
* Log agent output
* Create a stable foundation for scheduled automation

Agent tables:

* `agent_definitions`
* `agent_runs`

Current routes:

* `GET /agents`
* `GET /agents/prioritize`
* `GET /agents/morning/status`
* `POST /agents/morning/check-in`
* `POST /agents/morning/fallback-check`
* `GET /agents/scheduled/status`
* `POST /agents/scheduled/run-once`
* `GET /agents/{agent_id}`
* `POST /agents/{agent_id}/run`
* `GET /agents/runs/recent`

Initial agents:

* Morning Review Agent
* Evening Review Agent
* Executive Assistant Agent
* Trading Coach Agent
* Web Search Agent
* Readiness Advisory Agent

Current behavior:

* Agents can still be run manually
* Scheduled Agent Runs v1 can check due scheduled agents through `POST /agents/scheduled/run-once` or `backend/scheduled_agents.py`
* Agents read existing Orbit data
* Agents store summaries and structured output in `agent_runs`
* Morning Review Agent calls/generates Morning Briefing
* Evening Review Agent calls/generates Daily Closeout
* Executive Assistant Agent summarizes open tasks, blockers, and milestone progress history
* Trading Coach Agent summarizes recent trade sessions and readiness evidence
* Web Search Agent inspects top recommendations and strategic gaps, then creates a research plan for one target that may need current or external context
* Readiness Advisory Agent suggests readiness score improvements from Orbit evidence
* Agent Prioritization Layer v1 recommends which agent should run next based on Orbit state
* Scheduled Agent Runs v1 schedules only Morning Review Agent, Evening Review Agent, and a daily Agent Prioritization snapshot
* Scheduled Agent Runs v1 can be run manually via endpoint or CLI loop; a dedicated LaunchAgent has not been added yet
* Morning Check-In / Fallback Summary v1 lets Jadin initiate a morning check-in through UI, iMessage, manual calls, or a future voice path
* Voice Trigger Prototype v1 lets Jadin manually trigger Morning Check-In from a push-to-talk CLI script or typed test phrase
* Wake Phrase Listener v1 lets Jadin manually run a local microphone listener for simple Morning Check-In wake phrases
* Morning fallback sends the Morning Review summary by iMessage after the 6:30 AM local cutoff only when no check-in has been acknowledged

Current restrictions:

* Agents are read-only for now.
* Scheduling is limited to Morning Review Agent, Evening Review Agent, and a read-only prioritization snapshot.
* No agent-created tasks yet.
* No readiness updates yet.
* No agent-originated notifications yet outside Morning Check-In fallback.
* No scanner changes.
* No trading signals.
* Readiness Advisory Agent is advisory only: it does not update readiness, create tasks, create reviews, send notifications, schedule itself, or modify milestones or major events.
* Readiness Advisory Agent suggestions require manual approval before any readiness score can change.
* Web Search Agent v1 does not browse the web. It outputs `research_target`, `reason`, `suggested_queries`, `sources_required`, `actions_taken: []`, and `web_search_performed: false`.
* Actual cited web search is reserved for a later version.
* Agent Prioritization Layer v1 is read-only and recommendation-only. It does not run agents, create tasks, update readiness, create reviews, or send notifications.
* Scheduled Agent Runs v1 does not install a LaunchAgent yet. Actual LaunchAgent install can come later.
* Wake Phrase Listener v1 is manual CLI only. It does not auto-start, install a service, send iMessage, create tasks, update readiness, change scanner behavior, or implement full conversational voice.
* Voice Trigger Prototype v1 is manual/push-to-talk only and does not install or run an always-on microphone listener.
* Morning Check-In only uses TTS when the endpoint is explicitly called with `speak=true`.

Scheduled or background automation should call `run_agent(agent_id)` rather than duplicating agent behavior.

---

# Notifications and Voice

Notification infrastructure is implemented but gated.

Current working outputs:

* TTS output works through macOS `say`.
* TTS text is passed through `format_text_for_speech`, which removes markdown/code/URLs, expands percentages, normalizes short labels, and caps spoken text length.
* TTS voice profile settings are read from `HELIX_TTS_VOICE` and `HELIX_TTS_RATE`; unavailable voices are rejected back to the system default.
* TTS config and voice listing are exposed through `/tts/config` and `/tts/voices`.
* iMessage output works through the local Messages bridge.
* Voice Trigger Prototype v1 can manually call Morning Check-In with `source="voice"` and `speak=true`.
* Wake Phrase Listener v1 can manually listen once or loop for supported morning wake phrases.
* Smart scan notifications work when explicitly enabled and when alert eligibility allows delivery.
* Manual notification test endpoints verify delivery without fabricating scanner alerts.
* Morning Check-In speech uses the Morning Briefing condenser rather than reading the full Orbit summary verbatim.

Channels:

* iMessage
* Text-to-speech

Configuration:

* `SCAN_NOTIFY_ENABLED`
* `SCAN_NOTIFY_IMESSAGE_ENABLED`
* `SCAN_NOTIFY_TTS_ENABLED`
* `SCAN_NOTIFY_IMESSAGE_RECIPIENT`

Manual test endpoints:

* `GET /notify/config`
* `POST /notify/test-tts`
* `POST /notify/test-imessage`
* `POST /notify/test-all`

Voice Trigger Prototype v1:

* Manual CLI script: `python3 backend/voice_trigger.py`
* Typed test mode: `python3 backend/voice_trigger.py --text "good morning helix"`
* Supported phrases: `good morning helix`, `morning helix`, `start my morning`
* Calls `POST /agents/morning/check-in` with `source="voice"` and `speak=true`
* Uses optional local microphone/STT dependencies when available
* Falls back to typed input and prints setup instructions when audio/STT dependencies are missing
* Does not run automatically
* Does not install a service

Wake Phrase Listener v1:

* Manual CLI script: `python3 backend/wake_listener.py --once`
* Loop mode: `python3 backend/wake_listener.py --loop`
* Supported phrases: `good morning helix`, `morning helix`, `start my morning`
* Calls `POST /agents/morning/check-in` with `source="voice"` and `speak=true`
* Uses a configurable cooldown to prevent duplicate triggers
* Prints setup instructions and exits cleanly when microphone/STT dependencies are missing
* Does not run automatically
* Does not install a service or LaunchAgent
* Does not send iMessage

Conversational voice mode is not implemented yet.

Future "Good morning Helix" audible workflow requires:

* Mic listener
* Wake phrase detection
* Speech-to-text
* Helix intent routing
* TTS response

Future wake phrase detection should reuse `POST /agents/morning/check-in` for Morning Check-In delivery rather than duplicating check-in behavior.

## iMessage Capabilities

The iMessage bridge is a local command surface, not a cloud messaging service.

Current capabilities:

* Polls new inbound messages from one allowed sender in the local Messages database.
* Ignores old messages on startup by starting after the latest inbound row ID.
* Remembers recently sent replies so synced outbound messages are not processed as inbound commands.
* Sends replies through AppleScript and the Messages app.
* Supports wake prefixes: `hey helix`, `ok helix`, and `helix`.
* Routes help, current time, latest MES scan summary, forced MES scan, TTS commands, Morning Check-In, and normal Helix chat.
* Truncates long replies to `MAX_REPLY_CHARS`.

Current limitations:

* Requires macOS Messages database access and AppleScript permission.
* Only one allowed sender is configured in code.
* No group chat, multi-user routing, delivery queue, retry queue, or LaunchAgent plist is present.
* It can call scanner and TTS endpoints but does not bypass scanner alert eligibility.

## Morning Check-In and Fallback Behavior

Morning Check-In state is stored per local date in `backend/.morning_checkin_status.json`.

Current behavior:

* `POST /agents/morning/check-in` ensures a Morning Review Agent run exists for today, marks the morning as acknowledged, and returns the summary.
* `source` can be `ui`, `imessage`, `voice`, or `manual`.
* `speak=true` forces TTS; when `speak` is omitted, voice-originated check-ins speak by default.
* Spoken morning output is condensed by the Morning Briefing Condenser before passing through the speech formatter.
* `GET /agents/morning/status` reports acknowledgement, fallback, cutoff, local time, and delivery channel.
* `POST /agents/morning/fallback-check` sends the Morning Review summary by iMessage after 06:30 local only when the morning has not been acknowledged and no fallback has already been sent.
* `POST /agents/scheduled/run-once` also invokes the fallback check after scheduled-agent checks.

Fallback safety:

* Acknowledged mornings do not send fallback.
* Already-sent fallbacks do not send again.
* Before 06:30 local, fallback does not send.
* Fallback delivery requires a configured iMessage recipient.

---

# Mac Services

Helix can run as macOS user LaunchAgents.

Current services:

* `com.helix.backend`: FastAPI backend on `127.0.0.1:8000`
* `com.helix.scanner`: scheduled market scanner
* `com.helix.csv-refresh`: scheduled CSV refresh loop

Service scripts:

* `scripts/install_mac_services.sh`
* `scripts/uninstall_mac_services.sh`
* `scripts/status_mac_services.sh`
* `scripts/start_backend.sh`
* `scripts/start_scanner.sh`
* `scripts/start_csv_refresh.sh`

Runbook:

* `docs/MAC_SERVICES.md`

---

# Current Limitations

* Helix is local-first and depends on local services, local files, macOS permissions, Ollama, Playwright, TradingView access, and the Messages app.
* TradingView capture and CSV export can fail if the browser profile, session, layout, or page state changes.
* CSV freshness still matters. Stale CSVs cannot be treated as confirmed live price.
* Vision remains necessary for current displayed price, user markings, live labels, and visible confirmation.
* Scanner alerts are chart-review notifications, not trade entries.
* Execution confirmation is not complete.
* Trigger refinement is paused while higher-priority Orbit, agent, voice, and automation foundations are clarified.
* Smart notifications are disabled by default and require explicit environment configuration.
* iMessage delivery depends on macOS Messages and AppleScript availability.
* TTS delivery depends on macOS `say`.
* Always-on speech input and conversational voice mode are not implemented yet.
* Morning Check-In / Fallback Summary v1 supports the manual Voice Trigger Prototype and manual Wake Phrase Listener through `source="voice"` and `speak=true`, but no auto-starting microphone service has been implemented.
* Orbit readiness scoring still requires manual judgment and Helix-assisted updates.
* Orbit milestone progress remains manual unless Jadin explicitly applies the task-derived advisory.
* Suggested task creation is user-approved only.
* No autonomous task creation exists yet.
* Agents are read-only in v1.
* Scheduled Agent Runs v1 is limited to Morning Review Agent, Evening Review Agent, and a daily prioritization snapshot.
* Agents do not create tasks, update readiness, send notifications, or modify scanner state.
* Web Search Agent v1 is research-plan-only and does not perform cited browsing yet.
* Readiness Advisory Agent v1 suggests score changes but never applies them.
* Agent Prioritization Layer v1 recommends only and does not run agents.
* Scheduled Agent Runs v1 has no dedicated LaunchAgent plist yet.
* Task reminders are not connected yet.
* Free-form task tags are not implemented yet. Milestone links are structured tags only.
* News risk is useful but not yet a complete economic-calendar intelligence layer.

---

# Next Development Priorities

1. Cited Web Search Agent execution for tasks requiring current or external information.
2. Dedicated scheduled-agent LaunchAgent/service wrapper using `backend/scheduled_agents.py`.
3. Controlled agent notification approvals for scheduled or manual run summaries.
4. Apply-readiness workflow that lets Jadin approve Readiness Advisory suggestions before updating scores.
5. Helix Core Agent Summary so the home surface can show recent agent output without becoming noisy.
6. Always-on voice wake / speech input prototype that reuses the Morning Check-In endpoint.
7. Daily and weekly automation loops for planning review, trading review, Morning Review, and Evening Review.
8. Task reminder support connected to Orbit tasks.
9. Expanded Orbit review workflows for daily and weekly synthesis.
10. Scanner frontend visibility for liquidity draw, behavior classification, alert eligibility, notification status, and CSV freshness.
11. 1M execution confirmation layer while preserving source-of-truth rules.
12. Trade Journal analytics and readiness evidence generation.
13. iMessage bridge hardening: config-driven senders, service wrapper, retry behavior, and command audit trail.

## Before Next Major Build

Checklist:

1. Confirm backend API runs at `http://127.0.0.1:8000` and `GET /` returns backend health.
2. Confirm frontend dev server runs at `http://localhost:3000` and Orbit loads against the intended backend URL.
3. Confirm Ollama is running and the configured `OLLAMA_MODEL` and `VISION_MODEL` are available.
4. Confirm Orbit DB initializes cleanly and existing `assistant.db` data is not overwritten.
5. Confirm `GET /agents`, `GET /agents/prioritize`, `GET /agents/scheduled/status`, and `GET /agents/morning/status` return current state.
6. Confirm `POST /agents/scheduled/run-once` behavior in a safe window before installing any scheduled-agent service.
7. Confirm Morning Check-In fallback has a configured recipient before relying on iMessage fallback.
8. Confirm TTS config through `GET /tts/config` before adding new voice interactions.
9. Confirm wake listener remains manual unless an explicit always-on service is being built.
10. Confirm scanner notification env vars before changing scan notification behavior.
11. Confirm CSV refresh status and freshness before interpreting scanner price context.
12. Preserve source-of-truth rules: CSV for historical structure/FVGs, vision for live visible chart context when CSV is stale.
13. Keep agents read-only unless the feature explicitly adds a user-approval write path.
14. Do not add autonomous task creation, readiness updates, notifications, or scanner state changes without explicit approval gates.
15. Run backend compile/tests if backend code changes; run frontend lint/build if frontend code changes.

## Web Search Agent Note

Web Search Agent v1 is manual, read-only, and research-plan-only. It should be used only for tasks requiring current or external information, including:

* News
* Travel
* Market and economic context
* Product or service research
* Laws, rules, or policies
* Milestone-related research

It does not perform actual web browsing in v1. A later version should perform cited search and save research output into Orbit and `agent_runs`.

---

# Deferred / Future Systems

These remain part of the Helix vision but are intentionally deferred until the scanner, Orbit, agent foundation, and daily operating loop are more stable.

* Fully autonomous agents
* Conversational voice mode
* Always-on voice activation
* Mobile push notifications
* Planning Agent
* Reflection Agent
* Reminder Agent
* Research Agent
* Trading Agent as a distinct worker under Helix
* Ascend integration
* Achievement systems
* Skill progression systems
* Full performance analytics dashboard
* Screenshot-linked trade journal review
* Automated execution confirmation and trade-entry coaching
* Automatic readiness updates from evidence
* Automatic task creation from agent output
* Automatic Morning Briefing push

---

# Trading Framework

## Strategy Name

Liquidity-Driven ICT with BRTC Execution

## Core Philosophy

Price seeks liquidity.

FVGs are reaction zones, not targets.

The purpose of an FVG is to reveal whether price intends to continue toward liquidity or reject away from it.

The scanner should never treat touching an FVG as a trade signal.

## Analysis Framework

### Step 1: Determine HTF Bias

Timeframes:

* Daily
* 4H
* 1H

Questions:

* Bullish, bearish, or neutral?
* What liquidity has already been taken?
* What liquidity remains?

### Step 2: Identify Draw on Liquidity

Examples:

* PDH
* PDL
* PDNYH
* PDNYL
* Asia High
* Asia Low
* London High
* London Low
* Previous Week High
* Previous Week Low

Question:

Where is price trying to go?

### Step 3: Identify Reaction Zones

Priority:

1. Daily FVG
2. 4H FVG
3. 1H FVG
4. 15M FVG

Question:

Where should price make a decision?

### Step 4: Classify Behavior

Examples:

* Acceptance
* Rejection
* Reclaim
* Sweep
* Displacement
* Consolidation

Question:

How is price behaving inside the reaction zone?

### Step 5: Structure Confirmation

Timeframes:

* 15M MSS/BOS
* 5M MSS/BOS

Question:

Is the market changing direction or continuing?

### Step 6: Opportunity Recognition

Possible outputs:

* Bullish Continuation Watch
* Bearish Continuation Watch
* Reversal Watch
* Range / Chop Warning
* No Opportunity

### Step 7: Alert Eligibility

Possible outputs:

* None
* Low
* Medium
* High

Purpose:

Determine whether the market state is important enough to notify the user.

### Step 8: Execution Confirmation

Execution timeframe:

* 1M

Examples:

* BRTC
* FVG retest
* Sweep and reclaim
* MSS after displacement

The 1M chart is used for execution confirmation only.

It is not used for HTF bias.

## Supported Symbols

* MES
* ES
* MNQ
* NQ

---

# Orbit Vision

Orbit is a planning and execution platform powered by Helix.

Orbit is not another AI.

Orbit stores structured data and allows Helix to manage daily execution.

## Major Events System

Major Events represent significant life objectives.

Examples:

* Corporate Escape
* Trading Capital Goals
* Business Launches
* Boxing Milestones
* Travel Goals

Each Major Event contains:

* Title
* Target date
* Countdown
* Progress
* Milestones
* Metrics
* Status

## Current Major Event

### Corporate Escape

Objective:

Leave corporate employment and replace income through trading, business, and other ventures.

Target date:

2027-02-28

Orbit tracks:

* Progress percentage
* Milestones
* Tasks
* Reviews
* Readiness score
* Capital accumulation progress

## Orbit Architecture

Major Events are top-level objectives.

Current example:

* Corporate Escape

Milestones are structured bodies of work.

Current examples:

* Define income replacement target
* Build trading review cadence
* Create business launch plan
* Set capital accumulation checkpoints
* Inbox / General

Goals are planning containers.

Current:

* Inbox Goal

Tasks support capture, completion, due dates, status, milestone links, and daily planning integration.

Reviews support daily, weekly, and monthly reflections that can feed future readiness and automation systems.

## Readiness System

Purpose:

Measure actual readiness for major life objectives.

Current categories:

* Financial
* Trading
* Business
* Personal

Current state:

Manual updates with Helix assistance.

Future state:

Evidence-based readiness scoring.

---

# Trade Journal

Purpose:

Capture trading performance and generate readiness evidence.

Current capabilities:

* Trade session logging
* PnL tracking
* Rule adherence tracking
* Confidence tracking
* Session grading
* Notes and lessons

Future capabilities:

* Screenshot linking
* Setup tagging
* Mistake tracking
* Performance analytics
* Readiness evidence generation

---

# Helix Orbit Tools

## Read Tools

* `get_orbit_major_events`
* `get_orbit_milestones`
* `get_orbit_goals`
* `get_orbit_tasks`
* `get_orbit_reviews`
* `get_corporate_escape_status`
* `get_corporate_escape_readiness`
* `get_trade_sessions`

## Write Tools

* `create_orbit_task`
* `create_orbit_goal`
* `complete_orbit_task`
* `create_orbit_review`
* `create_trade_session`
* `update_orbit_milestone_progress`
* `update_orbit_major_event_progress`
* `update_readiness_category`

## Planning Tools

* `generate_orbit_daily_summary`
* `generate_orbit_focus`
* `suggest_trading_readiness_update`

---

# Guidance For Coding Agents

Before implementing features:

1. Read this file completely.
2. Preserve Helix as the single AI assistant.
3. Follow existing architecture patterns.
4. Avoid introducing duplicate systems.
5. Prefer extending existing modules over creating parallel systems.
6. Keep trading logic isolated from Orbit planning logic.
7. Maintain separation between Helix, Orbit, Agents, and scanner services.
8. Do not treat scanner alerts as execution signals.
9. Do not make agents autonomous unless explicitly requested.

When unsure:

Ask for clarification rather than making architectural decisions.
