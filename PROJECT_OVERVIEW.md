# Helix Project Overview

Last refreshed: June 3, 2026

Helix is Jadin's local-first assistant and operating layer. It combines a chat assistant, Orbit life operating system, agent framework, trading assistant, schedule platform, voice/TTS surface, and local messaging workflows into one system.

This document is the source of truth for the current implementation before the next major feature phase.

---

# Executive Summary

Helix today is:

* **AI Assistant**: a FastAPI-backed chat assistant with local Ollama model fallback, tool execution, image/chart analysis, history, and Command Center UI.
* **Orbit Life Operating System**: a structured SQLite-backed system for major events, milestones, goals, tasks, reviews, readiness, schedule blocks, progress history, recommendations, trade-session records, and agent run records.
* **Agent Framework**: a read-only/recommendation-first agent layer with manual runs, scheduled runs, prioritization, stored outputs, and Morning Check-In workflow.
* **Trading Assistant**: a TradingView/CSV-based scanner and analysis stack for MES/MNQ/NQ/ES context, liquidity, behavior classification, alert eligibility, CSV freshness, and gated notifications.
* **Scheduling Platform**: Orbit Schedule Blocks v1 plus a frontend Schedule Board with fixed/flexible blocks, week navigation, and date-aware block placement.
* **Voice-enabled Assistant**: macOS `say` TTS, configurable voice profiles, speech formatting, manual voice trigger prototype, manual wake phrase listener, and iMessage-backed morning fallback delivery.

Helix remains the central intelligence layer. Orbit stores durable planning data. Agents perform specialized read-only analysis. Scanner logic remains separate from Orbit and does not write planning state.

---

# Core Principles

## Single Brain Architecture

Helix is the only AI assistant.

Future systems should not create separate assistants. Instead:

* Helix decides how to respond.
* Agents perform specialized analysis.
* Orbit stores planning and execution data.
* Scanner and trading subsystems provide market context without owning life-planning state.

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
* Current displayed price when CSV freshness is limited
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

* Major events
* Calculated major event progress
* Milestones
* Goals
* Tasks and Inbox tasks
* Task-milestone links
* Reviews
* Readiness tracking
* Schedule blocks
* Trade sessions
* Progress history
* Recommendations and strategic gaps
* Agent definitions and agent run records

### User

The user always overrides Helix.

---

# Current Architecture

## Backend

Technology:

* FastAPI
* SQLite
* Python
* Ollama
* macOS `say`, Messages, AppleScript, and LaunchAgents for local voice, messaging, and service glue

Primary modules:

* `backend/main.py`: FastAPI app, `/chat`, deterministic Command Router v1 entry point, scanner routes, CSV refresh routes, TTS, notification tests, history, and tool logs.
* `backend/chat_intents.py`: deterministic Command Center intent routing before LLM fallback.
* `backend/tools.py`: Helix tool layer for Orbit, trading, web/search helpers, reminders, file tools, and TradingView workflows.
* `backend/orbit/database.py`: Orbit schema, initial agent definitions, and migrations-on-init style schema maintenance.
* `backend/orbit/service.py`: Orbit data access, calculated progress, recommendations, priority scoring, morning briefing, daily closeout, schedule blocks, and readiness logic.
* `backend/orbit/routes.py`: Orbit API surface.
* `backend/agent_service.py`: agent definitions, manual runs, stored outputs, agent prioritization, Web Search Agent output, and Readiness Advisory output.
* `backend/agent_routes.py`: agent API surface.
* `backend/scheduled_agents.py`: scheduled Morning Review, Evening Review, daily prioritization snapshot, and morning fallback check loop.
* `backend/morning_checkin.py`: Morning Check-In acknowledgement, Morning Review run reuse/creation, fallback state, iMessage fallback delivery, and speech condensation.
* `backend/scheduled_scan.py`: MES scanner, chart capture, deterministic analysis, state comparison, alert eligibility, and gated scan notifications.
* `backend/csv_refresh.py`: scheduled and forced TradingView CSV refresh with verification before active file replacement.
* `backend/tts.py`: speech formatter, macOS voice discovery/config, and TTS dispatch.
* `backend/imessage_bridge.py`: local iMessage polling bridge and command router into backend endpoints.
* `backend/voice_trigger.py`: manual push-to-talk / typed Morning Check-In trigger prototype.
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
* React client components for Command Center, Orbit, schedule, major events, agents, scanner controls, and trade-session surfaces

Primary surfaces:

* `/`: Helix Core home surface with navigation and current Orbit morning status.
* `/command-center`: Helix Command Center chat, tool mode selection, image/chart upload, scanner status, latest scan, force scan, history reset, and history display.
* `/orbit`: Orbit Operating Board with Major Events, calculated progress, milestones, Inbox tasks, recommendations, readiness, Schedule Board, Morning Check-In, Scheduled Agent status, agent prioritization, and manual agent runs.
* `/trade-journal`: basic Trade Journal/trade-session display surface.
* `/orbit/trade-journal`: Orbit-linked trade journal route.
* `/ascend`: future-facing Ascend/training/readiness concept surface.

Current frontend capabilities:

* Command Center calls `/chat`, scanner endpoints, image analysis, reset, and history.
* Orbit page preloads major events, milestones, reviews, readiness, morning briefing, daily closeout, recommendations, inbox tasks, progress advisory/history, agents, agent prioritization, scheduled-agent status, Morning Check-In status, and schedule blocks.
* Schedule Board supports fixed and flexible schedule blocks, week navigation, date-aware placement, recurring day-of-week display, specific-date blocks, active/archive state, editing, deletion, and category/priority metadata.
* Agent views expose Morning Check-In, scheduled-agent checks, prioritization, manual agent runs, Web Search Agent output, Readiness Advisory suggestions, and recent run summaries.

## Voice

Voice and speech are local and intentionally conservative:

* TTS uses macOS `say`.
* `/tts/voices` lists available voices.
* `/tts/config` reports configured voice/rate and resolved voice.
* `/tts/say` formats and speaks text.
* `HELIX_TTS_VOICE` and `HELIX_TTS_RATE` configure the profile.
* `format_text_for_speech` removes markdown/code/URLs, expands percentages, normalizes labels, and caps spoken text length.
* Morning Check-In condenses long Morning Review summaries before speech.
* `voice_trigger.py` is a manual push-to-talk / typed prototype.
* `wake_listener.py` is a manual microphone listener or typed simulation for morning wake phrases.

Voice prototypes do not install always-on microphone services.

## Messaging

iMessage integration is local:

* `backend/imessage_bridge.py` polls `~/Library/Messages/chat.db` read-only.
* It sends through AppleScript and the macOS Messages app.
* It routes help, current time, latest MES scan, forced MES scan, TTS commands, Morning Check-In, and normal `/chat`.
* Morning fallback summaries use iMessage after the local 06:30 cutoff when no check-in has been acknowledged and no fallback has already been sent.
* Delivery requires allowed-sender and recipient configuration plus macOS permissions.

## Agents

Implemented agent types:

* Morning Review Agent
* Evening Review Agent
* Executive Assistant Agent
* Trading Coach Agent
* Web Search Agent
* Readiness Advisory Agent

Agent system rules:

* Agents are stored in Orbit and include latest run metadata.
* Manual runs use `POST /agents/{agent_id}/run`.
* Agents store summary and structured output in `agent_runs`.
* Agents are read-only/recommendation-only unless an explicit future approval workflow is added.
* Agents do not create tasks, update readiness, send notifications, or modify scanner state.
* Scheduled/background automation should call `agent_service.run_agent(agent_id)` rather than duplicating agent logic.

---

# Orbit Capabilities

## Major Events v1

Major Events are manageable Orbit records rather than a hardcoded Corporate Escape-only view.

Current behavior:

* Create, edit, select, and archive major events.
* Support objectives such as Corporate Escape, boxing goals, trading capital goals, business launches, and real estate goals.
* Preserve archived events rather than cascade-deleting them from the UI workflow.
* Link milestones and readiness categories to major events.
* Show selected/active major event context in Orbit Overview.

## Calculated Major Event Progress v1

Major event progress is calculated from multiple Orbit signals:

* Stored major event progress
* Linked milestone progress
* Linked readiness scores
* Recent activity/progress signals

The frontend labels calculated progress separately so manual progress and computed progress are not confused.

## Milestones

Milestones belong to major events and track:

* Title and description
* Status
* Progress percent
* Target/current values
* Due date
* Progress history
* Linked tasks
* Progress advisory

## Tasks

Orbit supports:

* Goals
* Tasks
* Inbox tasks
* Task completion
* Task priority scoring
* Task-milestone links
* Recommendation task drafts
* Explicit user-approved creation from recommendations

Tasks can stay in the Inbox while being linked to milestones, so milestone context does not forcibly move a task out of Inbox.

## Reviews

Reviews support daily, weekly, monthly, and closeout-style reflections. Reviews feed Orbit summaries, recommendations, agents, and future readiness evidence.

## Readiness

Readiness categories are stored per major event and include:

* Category name
* Current score
* Target score
* Notes
* Last updated timestamp

Readiness Advisory Agent can suggest score changes from Orbit evidence, but it never applies updates automatically.

## Schedule Blocks

Schedule Blocks v1 supports:

* Fixed blocks
* Flexible blocks
* Category
* Day of week
* Specific date
* Start/end time
* Duration
* Recurrence
* Priority
* Notes
* Active/archive state

Fixed blocks require a day-of-week or specific date plus start/end time. Flexible blocks require duration.

## Schedule Board

The Orbit frontend includes a Schedule Board with:

* Week navigation
* Current week heading
* Seven-day display
* Date-aware scheduling through `specific_date`
* Day-of-week recurring block display
* Unscheduled/flexible block list
* Create/edit/delete/archive controls

Schedule Intelligence is not implemented yet. The board displays stored blocks but does not infer free time, conflicts, capacity, or auto-placement.

---

# Agent System

## Morning Review Workflow

Morning Review is available through:

* `GET /orbit/morning-briefing`
* Morning Review Agent manual run
* Scheduled Agent Runs morning window
* Morning Check-In endpoint
* iMessage bridge command routing
* Voice Trigger prototype
* Wake Listener prototype
* Command Router v1 intents

Morning Check-In behavior:

* Ensures a Morning Review Agent run exists for the current day.
* Reuses the run if one already exists.
* Marks the morning acknowledged.
* Optionally speaks when `speak=true` or when voice-originated.
* Fallback sends the Morning Review summary by iMessage after 06:30 local only when no acknowledgement/fallback already exists.

## Evening Review Agent

Evening Review Agent calls/generates the Orbit daily closeout and stores the result in `agent_runs`.

## Executive Assistant Agent

Executive Assistant Agent summarizes open tasks, blockers, and milestone progress history without taking actions.

## Trading Coach Agent

Trading Coach Agent summarizes recent trade sessions and readiness evidence. It does not change scanner state, create trading signals, or update readiness.

## Web Search Agent

Web Search Agent v1 inspects top recommendations and strategic gaps, selects a research target, and returns:

* Research target
* Reason
* Suggested queries
* Required source types
* `actions_taken: []`
* `web_search_performed: false`

Despite the name, current Web Search Agent behavior is research-plan-only and does not perform cited browsing yet.

## Readiness Advisory Agent

Readiness Advisory Agent reviews Orbit evidence and suggests readiness score improvements. It records suggestions, confidence, evidence, observations, and approval requirement. It never updates readiness automatically.

## Agent Prioritization

`GET /agents/prioritize` ranks enabled agents based on current Orbit state, recent runs, readiness, strategic gaps, recommendations, reviews, open tasks, blockers, and recent trade sessions.

The prioritization layer is read-only and recommendation-only. It does not run agents.

## Scheduled Agent Runs

Scheduled Agent Runs v1:

* Runs Morning Review Agent once per day inside the 06:00-09:00 local window.
* Runs Evening Review Agent once per day inside the 18:00-22:00 local window.
* Takes one daily Agent Prioritization snapshot.
* Invokes Morning Check-In fallback check after the scheduled-agent pass.
* Can run once through `POST /agents/scheduled/run-once`.
* Can run as a loop through `backend/scheduled_agents.py --interval-seconds`.
* Has LaunchAgent support through `com.helix.scheduled-agents`.

---

# Command Router v1

Command Router v1 lives in `backend/chat_intents.py` and is called from `/chat` before Ollama fallback when `tool_mode` is `auto`.

It uses deterministic keyword/phrase routing, not a full LLM planner.

Supported natural language intents include:

* `good morning helix`
* `morning briefing`
* `what should I focus on today`
* `show my schedule`
* `where do I have free time`
* `which agent should run`
* `what should helix check next`
* `prioritize agents`
* `show my major events`
* `how close am I to corporate escape`
* `how ready am I`
* `check readiness`
* `readiness advisory`

Routing behavior:

* Morning check-in phrases call Morning Check-In or Morning Briefing paths.
* Schedule phrases read Orbit schedule blocks and return a natural summary.
* Agent priority phrases call `/agents/prioritize` equivalent service logic.
* Major event phrases read major events and selected/Corporate Escape status.
* Readiness status phrases read readiness categories.
* Readiness advisory phrases run the Readiness Advisory Agent.
* Unmatched prompts preserve existing `/chat` behavior and fall back to Ollama/tool prompting.

Operational note: backend restart is required after Command Router changes because the running FastAPI process must import the updated `chat_intents.py`.

---

# Current Endpoints

## Core

* `GET /`: backend health check.
* `POST /chat`: primary chat, deterministic intent routing, and tool-routing endpoint.
* `POST /chat/stream`: streaming chat endpoint.
* `POST /analyze-image`: uploaded chart/image analysis.
* `POST /reset`: clear chat memory.
* `GET /history`: recent chat history.
* `GET /tool-logs`: recent tool calls.

## Scanner and CSV

* `POST /scan/force`
* `GET /scan/latest`
* `GET /scan/status`
* `GET /csv-refresh/status`
* `POST /csv-refresh/force`

## TTS and Notifications

* `GET /tts/voices`
* `GET /tts/config`
* `POST /tts/say`
* `GET /notify/config`
* `POST /notify/test-tts`
* `POST /notify/test-imessage`
* `POST /notify/test-all`

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
* `GET /orbit/schedule-blocks`
* `POST /orbit/schedule-blocks`
* `PATCH/DELETE /orbit/schedule-blocks/{schedule_block_id}`
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

* `GET /agents`
* `GET /agents/runs/recent`
* `GET /agents/prioritize`
* `GET /agents/scheduled/status`
* `POST /agents/scheduled/run-once`
* `GET /agents/morning/status`
* `POST /agents/morning/check-in`
* `POST /agents/morning/fallback-check`
* `GET /agents/{agent_id}`
* `POST /agents/{agent_id}/run`

---

# Service Map

## Always-on Recommended

### Backend API

* Service: FastAPI app from `backend/main.py`
* Local URL: `http://127.0.0.1:8000`
* Start script: `scripts/start_backend.sh`
* LaunchAgent: `scripts/launchagents/com.helix.backend.plist`
* Command: `backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000`
* Logs: `backend/logs/backend.out.log`, `backend/logs/backend.err.log`

### Ollama

* Service: local model runtime used by Helix chat and vision/text workflows.
* Default text model: `qwen3.5:9b`, configurable through `OLLAMA_MODEL`.
* Default vision model: `qwen2.5vl:7b`, configurable through `VISION_MODEL`.
* Limitation: model-backed chat fails if Ollama is unavailable or configured models are missing.

### Scheduled Agents

* Service: scheduled Morning Review, Evening Review, prioritization snapshot, and morning fallback check loop.
* Start script: `scripts/start_scheduled_agents.sh`
* LaunchAgent: `scripts/launchagents/com.helix.scheduled-agents.plist`
* Interval: `SCHEDULED_AGENTS_INTERVAL_SECONDS`, default 300 seconds.
* Logs: `backend/logs/scheduled-agents.out.log`, `backend/logs/scheduled-agents.err.log`

### iMessage Bridge

* Service: local Messages polling bridge.
* Start script: `scripts/start_imessage_bridge.sh`
* LaunchAgent: `scripts/launchagents/com.helix.imessage-bridge.plist`
* Logs: `backend/logs/imessage-bridge.out.log`, `backend/logs/imessage-bridge.err.log`

## Optional / Manual

### Frontend Dev Server

* Service: Next.js frontend.
* Local URL: `http://localhost:3000`
* Directory: `frontend`
* Command: `npm run dev`
* Backend base URL: `NEXT_PUBLIC_API_URL` or `http://127.0.0.1:8000`
* Classification: manual/optional during local development.

### Scheduled Scanner

* Service: MES scheduled chart scanner.
* Module: `backend/scheduled_scan.py`
* Start script: `scripts/start_scanner.sh`
* LaunchAgent: `scripts/launchagents/com.helix.scanner.plist`
* Classification: optional always-on, install when automatic chart scanning is desired.
* Default symbol/timeframes: MES, scheduled 4H/1H/15M/5M with 15M primary.
* Interval: 5 minutes during active market sessions.
* Logs: `backend/logs/scanner.out.log`, `backend/logs/scanner.err.log`

### CSV Refresh

* Service: TradingView CSV refresh scheduler.
* Module: `backend/csv_refresh.py`
* Start script: `scripts/start_csv_refresh.sh`
* LaunchAgent: `scripts/launchagents/com.helix.csv-refresh.plist`
* Classification: optional always-on, install when automatic TradingView CSV refresh checks are desired.
* Interval wrapper: `CSV_REFRESH_INTERVAL_SECONDS`, default 60 seconds.
* Active data directory: `backend/csv_data`
* Logs: `backend/logs/csv-refresh.out.log`, `backend/logs/csv-refresh.err.log`

### Wake Listener

* Service: manual local wake phrase listener prototype.
* Module: `backend/wake_listener.py`
* CLI: `python3 backend/wake_listener.py --once`, `python3 backend/wake_listener.py --loop`, or typed simulation with `--text`.
* Wake phrases: `good morning helix`, `morning helix`, `start my morning`.
* Target endpoint: `POST /agents/morning/check-in` with `source="voice"` and `speak=true`.
* Classification: manual/optional; intentionally not installed as a LaunchAgent.

### Voice Trigger Prototype

* Service: manual push-to-talk / typed morning trigger prototype.
* Module: `backend/voice_trigger.py`
* Classification: manual/optional; intentionally not installed as a LaunchAgent.

---

# Trading Intelligence / Scanner

The scanner is centered in `backend/scheduled_scan.py`.

Current scanner capabilities:

* TradingView screenshot capture
* Scheduled scanner loop with runtime status and scan history
* Forced scan endpoint
* Multi-timeframe scanner capture for 4H, 1H, 15M, and 5M context
* CSV freshness checks
* Deterministic CSV-backed chart analysis
* Vision/context merge for visible chart markings and labels
* Liquidity Draw Engine
* Behavior Classification
* Continuation compression and expansion detection
* Opportunity Watch generation
* Alert Eligibility Engine
* Gated iMessage/TTS notification infrastructure

Core flow:

1. Determine whether the current time is inside an active scan window.
2. Capture the primary TradingView chart context.
3. Optionally collect scheduled multi-timeframe captures.
4. Run vision and deterministic CSV-backed chart analysis.
5. Attach data freshness and source-of-truth context.
6. Compare current state against recent scan history.
7. Attach liquidity draw output.
8. Attach behavior classification output.
9. Attach alert eligibility.
10. Deliver scan notifications only when notification infrastructure is enabled and alert eligibility allows it.
11. Persist scan history and runtime status.

Notifications remain intentionally gated. Smart scan notifications default disabled and only deliver when scanner logic has already determined notification eligibility. Manual notification test endpoints exist so TTS and iMessage delivery can be verified without fabricating a real trading alert.

## Trading Framework Notes

The durable trading framework still matters for future scanner and coaching work:

* Determine higher-timeframe bias first.
* Identify draw on liquidity: previous day/week highs/lows, session highs/lows, and significant swing highs/lows.
* Identify reaction zones and FVGs by timeframe.
* Classify behavior around draw, structure, reaction zones, and multi-timeframe evidence.
* Treat 4H/1H as context, 15M as primary scan/review timeframe, 5M as continuation/compression/expansion evidence, and 1M as execution-only.
* Use if/then language.
* Never claim certainty or advise immediate entry without confirmation.
* Do not use VWAP.

Supported trading symbols remain:

* MNQ
* MES
* NQ
* ES

---

# Notifications and Voice

Notification and voice paths are separate from scanner decision logic.

Environment/configuration:

* `SCAN_NOTIFY_ENABLED`
* `SCAN_NOTIFY_IMESSAGE_ENABLED`
* `SCAN_NOTIFY_TTS_ENABLED`
* `SCAN_NOTIFY_IMESSAGE_RECIPIENT`
* `HELIX_TTS_VOICE`
* `HELIX_TTS_RATE`

Rules:

* Scanner notifications remain gated by scanner alert eligibility.
* Manual notification tests are only delivery checks.
* TTS depends on macOS `say`.
* iMessage depends on Messages, AppleScript, sender/recipient config, and local permissions.
* Morning Check-In speaks only when explicitly requested or voice-originated.

---

# Current Limitations

## Orbit and Scheduling

* Schedule Intelligence is not implemented.
* Schedule Board displays stored blocks but does not calculate free time, capacity, conflicts, day density, or auto-placement.
* Auto Schedule Placement is not implemented.
* Full Trade Journal v1 is not implemented. Basic trade-session records and display surfaces exist, but full journaling workflows, analytics, and readiness evidence generation are not complete.

## Trading

* Scanner still uses interval-based logic.
* Trading model refinement is not complete.
* Scanner refinement is not complete.
* Pattern Discovery is not implemented.
* Advanced Trade Coach is not implemented.
* Narrative Scanner is not implemented.
* Scanner alerts are chart-review notifications, not trade entries.

## Agents

* Agents are read-only/recommendation-only in v1.
* Web Search Agent is research-plan-only and does not perform cited browsing yet.
* Readiness Advisory Agent suggests score changes but never applies them.
* Agent Prioritization recommends only and does not run agents.

## Voice and Messaging

* Wake Listener remains manual/optional and has no LaunchAgent.
* Voice Trigger Prototype remains manual/optional.
* No full conversational voice loop is implemented.
* iMessage delivery depends on macOS Messages and AppleScript availability.
* TTS delivery depends on macOS `say`.

---

# Current Roadmap

## Next

1. Schedule Intelligence v1
2. Trade Journal v1

## Trading Evolution

3. Trading Model Refinement
4. Scanner Refinement
5. Presence Modes
6. Narrative Scanner

## Future

7. Pattern Discovery
8. Advanced Trade Coach
9. Auto Schedule Placement

Completed roadmap items removed from active priority lists include Agent Foundation v1, Web Search Agent v1 scaffolding, Readiness Advisory Agent v1, Agent Prioritization, Scheduled Agent Runs, Morning Check-In/Fallback Summary, Schedule Blocks v1, Schedule Board v1, Major Events v1, and Command Router v1.

---

# Stability Checklist

## Backend and Command Router

* Restart backend after Command Router or backend code changes.
* Running LaunchAgent processes do not automatically import changed Python files until restarted.
* Use `scripts/status_mac_services.sh restart` to kickstart loaded services.
* Confirm backend health with `GET http://127.0.0.1:8000/`.
* Confirm deterministic router behavior through `/chat` after restart.

## LaunchAgent Setup

Install services:

* `scripts/install_mac_services.sh core`: backend, scheduled agents, iMessage bridge.
* `scripts/install_mac_services.sh all`: backend, scheduled agents, iMessage bridge, scanner, CSV refresh.
* `scripts/install_mac_services.sh SERVICE...`: selected services.

Uninstall services:

* `scripts/uninstall_mac_services.sh`

Status/log management:

* `scripts/status_mac_services.sh status`
* `scripts/status_mac_services.sh restart`
* `scripts/status_mac_services.sh logs`
* `scripts/status_mac_services.sh tail`

## Logging Locations

* Backend: `backend/logs/backend.out.log`, `backend/logs/backend.err.log`
* Scheduled agents: `backend/logs/scheduled-agents.out.log`, `backend/logs/scheduled-agents.err.log`
* iMessage bridge: `backend/logs/imessage-bridge.out.log`, `backend/logs/imessage-bridge.err.log`
* Scanner: `backend/logs/scanner.out.log`, `backend/logs/scanner.err.log`
* CSV refresh: `backend/logs/csv-refresh.out.log`, `backend/logs/csv-refresh.err.log`

## Pre-build Checks

Before a major feature build:

1. Confirm backend health.
2. Confirm Orbit direct endpoints still return data.
3. Confirm `/chat` deterministic intents still route before Ollama fallback.
4. Confirm `GET /agents`, `GET /agents/prioritize`, `GET /agents/scheduled/status`, and `GET /agents/morning/status`.
5. Confirm Morning Check-In fallback has a configured recipient before relying on iMessage fallback.
6. Confirm TTS config through `GET /tts/config` before adding new voice interactions.
7. Confirm scanner and CSV refresh services are only installed when desired.
8. Do not add autonomous task creation, readiness updates, notifications, scanner state changes, or schedule placement without explicit approval gates.

---

# Deferred / Future Systems

These remain part of the Helix vision but are intentionally deferred until Orbit, Schedule Intelligence, Trade Journal, and scanner refinements are stable:

* Planning Agent
* Reflection Agent
* Reminder Agent
* Cited Web Research execution
* Advanced Trading Coach
* Auto schedule placement
* Pattern Discovery
* Narrative Scanner
* Full conversational voice loop
* Automatic readiness updates from evidence
* Proactive autonomous task creation

---

# Guidance For Coding Agents

When working on Helix:

1. Read this file first.
2. Preserve the Single Brain Architecture.
3. Treat Orbit as the planning source of truth.
4. Keep scanner logic separate from Orbit planning data.
5. Keep agents read-only unless an explicit approval workflow is requested.
6. Keep scheduling deterministic until Schedule Intelligence v1 is intentionally designed.
7. Do not add migrations or service behavior changes during documentation-only refreshes.
8. Do not add autonomous notifications, readiness updates, or task creation without explicit approval gates.
9. Prefer deterministic routing for common Command Center requests before adding a full LLM planner.
10. Update this overview when major architecture, service, or roadmap state changes.
