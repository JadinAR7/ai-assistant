# Helix Project Overview

Last refreshed: June 4, 2026

Helix is Jadin's local-first assistant and operating layer. It combines a chat assistant, Orbit life operating system, agent framework, trading assistant, schedule platform, voice/TTS surface, and local messaging workflows into one system.

This document is the source of truth for the current implementation before the next major feature phase.

---

# Executive Summary

Helix today is:

* **AI Assistant**: a FastAPI-backed chat assistant with local Ollama model fallback, tool execution, image/chart analysis, history, and Command Center UI.
* **Orbit Life Operating System**: a structured SQLite-backed system for major events, milestones, goals, tasks, reviews, readiness, schedule blocks, progress history, recommendations, trade-session records, Trade Journal records, and agent run records.
* **Agent Framework**: a read-only/recommendation-first agent layer with manual runs, scheduled runs, prioritization, stored outputs, and Morning Check-In workflow.
* **Trading Assistant**: a TradingView/CSV-based scanner and analysis stack for MES/MNQ/NQ/ES context, liquidity, behavior classification, alert eligibility, CSV freshness, gated notifications, and Trade Journal data capture.
* **Scheduling Platform**: Orbit Schedule Blocks v1, Schedule Board v1, and Schedule Intelligence v1 for read-only day density, free-time windows, overloaded-day detection, and placement recommendations.
* **Voice-enabled Assistant**: macOS `say` TTS, configurable voice profiles, TTS routing, speech formatting, manual Voice Trigger prototype, Wake Phrase Listener v1, Morning Briefing condenser, and iMessage-backed morning fallback delivery.

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
* FVG reaction-zone mapping
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
* Stale CSVs may only be used for structure and FVG reaction-zone mapping.
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
* Trade Journal entries

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
* `backend/presence.py`: local Presence Modes v1 storage and mode definitions for home, trading, away, and focus.
* `backend/tools.py`: Helix tool layer for Orbit, trading, web/search helpers, reminders, file tools, and TradingView workflows.
* `backend/orbit/database.py`: Orbit schema, initial agent definitions, Trade Journal tables, and migrations-on-init style schema maintenance.
* `backend/orbit/service.py`: Orbit data access, calculated progress, recommendations, priority scoring, morning briefing, daily closeout, schedule blocks, Schedule Intelligence v1, Trade Journal CRUD, import-save behavior, and readiness logic.
* `backend/orbit/routes.py`: Orbit API surface, including schedule intelligence and Trade Journal endpoints.
* `backend/orbit/trade_journal_import.py`: deterministic Trade Journal PDF import parser for Performance PDFs, Orders PDFs, preview generation, and draft enrichment.
* `backend/trading_coach.py`: Trading Coach v2 / Journal Review Intelligence v1 read-only Trade Journal review service for Liquidity Narrative Continuation alignment, missing-context guidance, and deterministic coaching summaries.
* `backend/trading_correlation.py`: Scanner + Journal Correlation v1 read-only service that matches Trade Journal entries to nearby scan history records by symbol, date/time, and session.
* `backend/pattern_discovery.py`: Pattern Discovery v1 read-only service that analyzes Trade Journal and scanner-correlation data for early recurring behavior patterns with small-sample caution.
* `backend/agent_service.py`: agent definitions, manual runs, stored outputs, agent prioritization, Web Search Agent output, and Readiness Advisory output.
* `backend/agent_routes.py`: agent API surface.
* `backend/scheduled_agents.py`: scheduled Morning Review, Evening Review, daily prioritization snapshot, and morning fallback check loop.
* `backend/morning_checkin.py`: Morning Check-In acknowledgement, Morning Review run reuse/creation, fallback state, iMessage fallback delivery, and speech condensation.
* `backend/scheduled_scan.py`: configured-symbol scanner, chart capture, deterministic analysis, state comparison, Scanner Refinement v1 signal tiers, narrative state, alert eligibility, repeat suppression, and gated scan notifications.
* `backend/csv_refresh.py`: scheduled and forced TradingView CSV refresh with verification before active file replacement.
* `backend/tts.py`: speech formatter, macOS voice discovery/config, and TTS dispatch.
* `backend/imessage_bridge.py`: local iMessage polling bridge and command router into backend endpoints.
* `backend/voice_trigger.py`: manual push-to-talk / typed Morning Check-In trigger prototype.
* `backend/wake_listener.py`: manual wake phrase listener prototype.

Storage:

* `backend/assistant.db`: chat/tool logs plus Orbit tables.
* `backend/scan_history.jsonl`: scanner records.
* `backend/scan_runtime_status.json`: scanner heartbeat/status.
* `backend/scanner_settings.json`: scanner settings, including the selected default futures symbol.
* `backend/presence_status.json`: current manual Presence Mode.
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
* `/trade-journal`: Trade Journal data-capture surface with manual entry, PDF import preview, import draft review, list/detail/edit/delete workflows, and attachment path capture.
* `/orbit/trade-journal`: Orbit-linked trade journal route.
* `/ascend`: future-facing Ascend/training/readiness concept surface.

Current frontend capabilities:

* Command Center calls `/chat`, scanner endpoints, image analysis, reset, and history.
* Orbit page preloads major events, milestones, reviews, readiness, morning briefing, daily closeout, recommendations, inbox tasks, progress advisory/history, agents, agent prioritization, scheduled-agent status, Morning Check-In status, schedule blocks, and schedule intelligence.
* Schedule Board v1 supports fixed and flexible schedule blocks, week navigation, date-aware placement, recurring day-of-week display, specific-date blocks, active/archive state, editing, deletion, category/priority metadata, subtle current-day column highlighting, and compact Schedule Intelligence display.
* Trade Journal supports manual create/edit/delete/detail, import preview, step-by-step imported draft review, and save-from-import confirmation.
* Agent views expose Morning Check-In, scheduled-agent checks, prioritization, manual agent runs, Web Search Agent output, Readiness Advisory suggestions, and recent run summaries.
* Mobile UI Pass v1 improves phone testing usability with tighter page shells, scrollable navigation, stacked mobile layouts, larger tap targets, and preserved desktop layouts across Core, Command Center, Orbit, Schedule rooms, and Trade Journal rooms.

## Voice

Voice and speech are local and intentionally conservative:

* TTS uses macOS `say`.
* TTS routing is available through backend endpoints, notification tests, Morning Check-In voice-originated flows, and scanner notification delivery when explicitly enabled.
* `/tts/voices` lists available voices.
* `/tts/config` reports configured voice/rate and resolved voice.
* `/tts/say` formats and speaks text.
* `HELIX_TTS_VOICE` and `HELIX_TTS_RATE` configure the profile.
* `format_text_for_speech` removes markdown/code/URLs, expands percentages, normalizes labels, and caps spoken text length.
* Morning Briefing condenser logic shortens long Morning Review summaries before speech and fallback delivery.
* `voice_trigger.py` is a manual push-to-talk / typed prototype.
* `wake_listener.py` is Wake Phrase Listener v1: a manual microphone listener or typed simulation for morning wake phrases.

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

# Completed Feature State

The following major feature milestones are complete as of this overview:

* Major Events Management v1
* Calculated Major Event Progress
* Schedule Blocks v1
* Schedule Board v1
* Schedule Intelligence v1
* Trade Journal v1
* Trade Journal PDF Import v1
* Trading Coach v2 / Journal Review Intelligence v1
* Scanner + Journal Correlation v1
* Pattern Discovery v1
* Trading Model Refinement v1
* Scanner Refinement v1
* Presence Modes v1
* Narrative-Based Scanner v1
* Default Scanner Symbol v1
* Command Router v1
* Voice Trigger Prototype
* Wake Phrase Listener v1
* TTS Routing
* Morning Briefing Condenser
* Service Management / LaunchAgent support

These features are considered implemented baseline capabilities. Future work should extend them deliberately rather than re-scaffold them.

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

The Today button returns the visible week to the current week. When the visible week includes today, the current day is indicated by a subtle turquoise column highlight rather than a separate day-header badge.

## Schedule Intelligence v1

Schedule Intelligence v1 is implemented as read-only analysis and recommendation generation.

Current behavior:

* Reads Schedule Blocks, Major Events, Milestones, and Tasks.
* Produces daily summaries for the current week.
* Calculates total scheduled time and remaining available time.
* Counts high-priority commitments and flexible blocks by day.
* Flags days as `healthy`, `busy`, or `overloaded` using simple v1 thresholds.
* Identifies available windows inside a bounded planning day.
* Lists overloaded and underutilized days.
* Generates text-only placement recommendations such as open windows, possible flexible-block fits, and overloaded-day warnings.
* Exposes `GET /orbit/schedule/intelligence`.
* Displays a compact Schedule Intelligence card in the Schedule tab.
* Feeds Command Router schedule intents such as free-time, packed-schedule, and next-scheduling questions.

Schedule Intelligence v1 does not auto-place blocks, move blocks, modify calendar state, send notifications, or perform conflict resolution.

## Trade Journal v1

Trade Journal v1 is implemented as a data-capture foundation for future trading intelligence.

Current behavior:

* Trade Journal page exists at `/trade-journal`.
* Manual journal entry supports create, edit, delete, and detail view workflows.
* Journal entries capture trade information, trade context, narrative, review notes, and attachment paths.
* Trade information includes symbol, direction, entry, stop, take profit, exit, result, contracts, and session.
* Trade context includes HTF bias, draw on liquidity, reaction zone, behavior tags, and execution tags.
* Narrative and review fields preserve Jadin's own reasoning, intent, liquidity target, what went well, what went wrong, and lesson learned.
* Attachment path fields support screenshot and CSV references.

Trade Journal v1 is the coaching source data for Trading Coach v2 / Journal Review Intelligence v1. It does not provide pattern discovery, automatic scanner refinement, automatic strategy changes, or performance analytics dashboards.

## Trading Coach v2 / Journal Review Intelligence v1

Trading Coach v2 is implemented as deterministic, read-only journal review.

Current behavior:

* Reads saved Trade Journal entries and the Liquidity Narrative Continuation strategy profile.
* Reviews total trades, wins/losses when result data exists, total PnL, average PnL, strategy mode distribution, session distribution, common behavior tags, common execution tags, common liquidity draws, common reaction zones, recurring lessons, and missing narrative/context fields.
* Compares journal entries against required model context: HTF bias, draw on liquidity, reaction zone, behavior tags, execution tags, narrative explanation, target liquidity, and review/lesson.
* Returns structured JSON plus a readable coaching summary through `GET /orbit/trading-coach/review`.
* Supports optional filters: `limit`, `symbol`, `session`, and `strategy_mode`.
* Supports Command Router phrases such as `review my trades`, `how did I trade today`, `what did I do well trading`, `what should I improve in my trading`, `review my trade journal`, and `trading coach review`.
* Displays a compact Trading Coach Review panel on the Trade Journal page.
* Returns the empty state `No journal entries available yet. Import or create trades first.` when no journal entries are available.

Boundaries:

* Does not produce trade signals or financial advice.
* Does not build Pattern Discovery.
* Does not modify scanner triggers, scanner interval, default scanner symbol, presence modes, scanner notifications, PDF import parser, or Trade Journal import UX.
* Does not auto-update the strategy model, auto-create tasks, send notifications, or write back to journal entries.

## Scanner + Journal Correlation v1

Scanner + Journal Correlation v1 is implemented as deterministic, read-only correlation between saved Trade Journal entries and scanner JSONL records.

Current behavior:

* Reads saved Trade Journal entries and `backend/scan_history.jsonl`.
* Matches journal entries to nearby scanner records by symbol, trade date, entry time when available, and session.
* Uses a default matching window of 90 minutes before trade entry and 30 minutes after trade entry.
* If entry time is missing, falls back to same symbol, same date, and same session with lower confidence.
* Returns per-trade scanner context: nearest before/after scans, narrative phase, signal level, liquidity draw, reaction zone, behavior, structure confirmation, execution readiness, alignment label, reasons, mismatches, and missing data.
* Uses conservative labels: `aligned`, `partially_aligned`, `conflicted`, and `insufficient_data`.
* Returns summary counts, common mismatches, suggested data to capture, and readable text through `GET /orbit/trading-correlation/review`.
* Supports optional filters: `limit`, `symbol`, `session`, and `strategy_mode`.
* Supports Command Router phrases such as `compare my trades to the scanner`, `did my trades align with Helix`, `scanner journal review`, `trade scanner correlation`, and `did I follow the scanner narrative`.
* Displays a compact Scanner Correlation panel on the Trade Journal page.
* Supports Trading Coach with an optional Scanner Correlation summary when matched scanner context exists.

Boundaries:

* Does not produce trade signals or financial advice.
* Does not build Pattern Discovery.
* Does not modify scanner triggers, scanner interval, scanner notifications, default scanner symbol, presence modes, PDF import parser, Trade Journal import UX, strategy model, tasks, or journal entries.

## Pattern Discovery v1

Pattern Discovery v1 is implemented as deterministic, read-only pattern detection from Trade Journal entries and optional Scanner + Journal Correlation results.

Current behavior:

* Reads saved Trade Journal entries, the Liquidity Narrative Continuation strategy profile, and Scanner + Journal Correlation review data when available.
* Reviews recurring patterns across trade metadata, strategy context, narrative/review fields, and scanner-correlation fields.
* Returns summary, sample-size warning, recurring strengths, recurring weaknesses, profitable contexts, weak contexts, best/weakest session so far, best/weakest strategy mode so far, scanner alignment observations, missing-data patterns, suggested next review questions, and pattern confidence.
* Uses conservative pattern confidence: low under 10 trades, medium for 10-30 trades, and higher after 30 trades while still avoiding certainty.
* Includes the warning `Sample size is small. Treat these as early observations, not conclusions.` when fewer than 10 trades are reviewed.
* Uses cautious language such as early pattern, appears, so far, and worth watching.
* Returns structured JSON plus a readable summary through `GET /orbit/pattern-discovery/review`.
* Supports optional filters: `limit`, `symbol`, `session`, and `strategy_mode`.
* Supports Command Router phrases such as `find patterns in my trades`, `what patterns do you see`, `what trading patterns are showing up`, `where am I doing best`, `where am I struggling`, and `pattern discovery`.
* Displays a compact Pattern Discovery panel on the Trade Journal page.

Boundaries:

* Does not claim statistical certainty from small sample sizes.
* Does not modify scanner triggers, scanner interval, scanner notifications, default scanner symbol, presence modes, PDF import parser, Trade Journal import UX, strategy model, tasks, or journal entries.
* Does not auto-update the strategy model, auto-create tasks, send notifications, or build a performance analytics dashboard.

## Trade Journal PDF Import v1

Trade Journal PDF Import v1 is implemented as a deterministic preview-and-confirm workflow.

Current behavior:

* Performance PDF import is supported.
* Orders PDF import is supported.
* Combined Performance PDF plus Orders PDF import is supported.
* Import preview returns daily summary, trade drafts, unmatched orders, warnings, and source file metadata.
* Import preview does not save journal entries.
* Save-from-import only creates journal entries from user-confirmed drafts.
* Manual entry remains preserved alongside import workflows.

Parser behavior:

* Performance PDF acts as the trade source.
* Orders PDF acts as execution, order, and stop enrichment.
* Performance parser extracts daily summary, individual trades, direction, entry/exit, PnL, duration, contracts, and session inference.
* Orders parser extracts filled orders, canceled stop orders, limit entry/exit, market entry/exit, and related order IDs.
* Short direction for trades is inferred by comparing buy and sell timestamps, which fixed the Trade 3 short-direction issue.
* Parser failures return warnings instead of crashing where possible.

Real PDF parser validation:

* Parser was fixed against actual extracted PDF text from `Performance.20260603.051807.pdf` and `Orders.20260603.051923.pdf`.
* Backend fixtures were added from real extracted PDF text:
  * `backend/tests/fixtures/performance_20260603.txt`
  * `backend/tests/fixtures/orders_20260603.txt`
* Parser test file:
  * `backend/tests/test_trade_journal_import.py`

Import UX refinement:

* Trade Journal has a mode switch for Import Trades and Manual Entry.
* Import Trades is the default mode.
* Manual form is hidden during the import workflow.
* Imported drafts use a step-by-step review queue.
* Only one active draft is shown at a time.
* User can Save Draft, Skip Draft, or go to Previous Draft.
* Saving advances to the next pending draft.
* Skipped drafts are not saved.
* Completion state appears after all drafts are saved or skipped.
* Manual smoke coverage is documented in `docs/TRADE_JOURNAL_SMOKE_TEST.md`.

Future source-of-truth role:

Trade Journal will become the primary dataset for:

* Trading Model Refinement
* Scanner Refinement
* Presence Modes
* Narrative-Based Trading Analysis
* Pattern Discovery
* Trading Coach v2
* Performance Analytics

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
* `is my schedule packed`
* `what should I schedule next`
* `which agent should run`
* `what should helix check next`
* `prioritize agents`
* `show my major events`
* `how close am I to corporate escape`
* `how ready am I`
* `check readiness`
* `readiness advisory`
* `review my trades`
* `how did I trade today`
* `what did I do well trading`
* `what should I improve in my trading`
* `review my trade journal`
* `trading coach review`
* `compare my trades to the scanner`
* `did my trades align with Helix`
* `scanner journal review`
* `trade scanner correlation`
* `did I follow the scanner narrative`
* `find patterns in my trades`
* `what patterns do you see`
* `what trading patterns are showing up`
* `where am I doing best`
* `where am I struggling`
* `pattern discovery`
* `I’m home`
* `I’m trading`
* `I’m away`
* `focus mode`
* `turn on focus mode`
* `what mode is Helix in`
* `what is my presence mode`

Routing behavior:

* Morning check-in phrases call Morning Check-In or Morning Briefing paths.
* Schedule phrases read Schedule Intelligence v1 and return a natural summary of available days, overloaded days, available windows, unplaced flexible blocks, and recommendations.
* Agent priority phrases call `/agents/prioritize` equivalent service logic.
* Major event phrases read major events and selected/Corporate Escape status.
* Readiness status phrases read readiness categories.
* Readiness advisory phrases run the Readiness Advisory Agent.
* Trading coach phrases read Trade Journal entries and return the Trading Coach v2 deterministic review summary.
* Scanner correlation phrases read Trade Journal entries plus scanner history records and return a deterministic read-only correlation summary.
* Pattern discovery phrases read Trade Journal and scanner-correlation evidence and return conservative early pattern observations.
* Presence phrases read or update Presence Modes v1 through deterministic local storage.
* Unmatched prompts preserve existing `/chat` behavior and fall back to Ollama/tool prompting.

Operational note: backend restart is required after Command Router changes because the running FastAPI process must import the updated `chat_intents.py`.

---

# Current Endpoints

## Core

* `GET /`: backend health check.
* `POST /chat`: primary chat, deterministic intent routing, and tool-routing endpoint.
* `POST /chat/stream`: streaming chat endpoint.
* `POST /analyze-image`: uploaded chart/image analysis.
* `GET /presence`: current Presence Mode config, `updated_at`, and available modes.
* `POST /presence`: set manual Presence Mode with `{ "mode": "home|trading|away|focus" }`.
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
* `GET /orbit/schedule/intelligence`
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
* `GET /orbit/trading-coach/review`
* `GET /orbit/trading-correlation/review`
* `GET /orbit/pattern-discovery/review`
* `GET /orbit/trade-journal`
* `POST /orbit/trade-journal`
* `GET/PATCH/DELETE /orbit/trade-journal/{journal_entry_id}`
* `POST /orbit/trade-journal/import-pdf`
* `POST /orbit/trade-journal/import-pdf/save`

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
* LAN/phone URL: `http://192.168.8.119:8000`
* Start script: `scripts/start_backend.sh`
* LaunchAgent: `scripts/launchagents/com.helix.backend.plist`
* Command: `backend/.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000`
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

### Frontend

* Service: Next.js frontend.
* LAN/phone URL: `http://192.168.8.119:3000`
* Start script: `scripts/start_frontend.sh`
* LaunchAgent: `scripts/launchagents/com.helix.frontend.plist`
* Directory: `frontend`
* Command: `npm run start -- -H 0.0.0.0 -p 3000` when `.next` exists; otherwise `npm run dev -- -H 0.0.0.0 -p 3000`
* Backend base URL: `NEXT_PUBLIC_API_URL=http://192.168.8.119:8000`
* Logs: `backend/logs/frontend.out.log`, `backend/logs/frontend.err.log`
* Classification: always-on recommended; tmux is no longer required for normal frontend startup after the LaunchAgent is installed.

## Optional / Manual

### Scheduled Scanner

* Service: configured-symbol scheduled chart scanner.
* Module: `backend/scheduled_scan.py`
* Start script: `scripts/start_scanner.sh`
* LaunchAgent: `scripts/launchagents/com.helix.scanner.plist`
* Classification: optional always-on, install when automatic chart scanning is desired.
* Default symbol/timeframes: `scanner_settings.json` default symbol, scheduled 4H/1H/15M/5M with 15M primary.
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

CSV refresh reminder:

* CSV refresh follows the selected/default scanner symbol when no explicit symbol is provided.
* CSV refresh can be forced for an explicit supported symbol such as `MNQ`, `MES`, `NQ`, or `ES`.
* CSV remains the source of truth for historical structure, FVG mapping, liquidity mapping, and backup price-action context.
* Vision remains responsible for live visible chart context and user markings.
* Stale CSVs must not be treated as confirmed live price.
* Watchlist refresh and refresh-all behavior are not implemented.

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
* Default Scanner Symbol v1 for choosing MES, MNQ, ES, or NQ as the single default scan symbol
* Multi-timeframe scanner capture for 4H, 1H, 15M, and 5M context
* CSV freshness checks
* Deterministic CSV-backed chart analysis
* Vision/context merge for visible chart markings and labels
* Liquidity Draw Engine
* Behavior Classification
* Continuation compression and expansion detection
* Opportunity Watch generation
* Narrative-Based Scanner v1 state enrichment
* Scanner Refinement v1 signal tiers
* Same-state repeat suppression
* Presence Modes v1 notification/noise gating
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
9. Attach Narrative-Based Scanner state.
10. Attach scanner signal tier output.
11. Attach alert eligibility.
12. Attach Presence Mode notification eligibility.
13. Deliver scan notifications only when notification infrastructure is enabled, alert eligibility allows it, and Presence Mode permits it.
14. Persist scan history and runtime status.

Notifications remain intentionally gated. Smart scan notifications default disabled and only deliver when scanner logic has already determined notification eligibility. Manual notification test endpoints exist so TTS and iMessage delivery can be verified without fabricating a real trading alert.

## Default Scanner Symbol v1

Default Scanner Symbol v1 lets Jadin choose which supported futures symbol Helix scans by default.

Supported default symbols:

* `MES`
* `MNQ`
* `ES`
* `NQ`

The setting is stored locally in `backend/scanner_settings.json` as `default_symbol`, defaulting to `MES` when no settings file exists or when stored settings are invalid. The current tested default is `MNQ`.

Implemented API behavior:

* `GET /scanner/settings` returns the saved scanner settings.
* `POST /scanner/settings` updates the saved default symbol, for example `{ "default_symbol": "MNQ" }`.
* `POST /scan/force` uses the saved default symbol.
* `POST /scan/force?symbol=MES` can override the saved default for that forced scan.
* `GET /scan/latest` returns the latest scan for the saved default symbol.
* `GET /scan/latest?symbol=MNQ` returns the latest scan for that explicit supported symbol.
* `POST /csv-refresh/force` refreshes CSVs for the saved default symbol.
* `POST /csv-refresh/force?symbol=MNQ` refreshes CSVs for that explicit supported symbol.

Scheduled scans, forced scans without an explicit symbol, CSV refresh without an explicit symbol, scanner status, latest-scan lookup, screenshot cleanup, and scan history records use the configured default symbol. Changing the default symbol does not run a scan automatically, does not enable notifications, does not change scanner interval, and does not implement watchlist rotation or refresh-all behavior.

## Presence Modes v1

Presence Modes v1 is manual-only. It lets Jadin choose how noisy or active Helix should be without changing scanner cadence, scan execution, scan history persistence, location behavior, calendar behavior, wake listener behavior, iMessage internals, or TTS internals.

Current modes:

* `home`: review-level scanner notifications allowed, notifications on, iMessage on, TTS off, normal scan noise profile.
* `trading`: alert-level scanner notifications only, notifications on, iMessage on, TTS off, quiet scan noise profile.
* `away`: review-level scanner notifications allowed, notifications on, iMessage on, TTS off, active scan noise profile.
* `focus`: alert-level scanner threshold, notifications off, iMessage off, TTS off, silent scan noise profile.

Scanner behavior:

* Presence Mode never stops scans from running.
* Presence Mode never stops scan history from saving.
* Presence Mode only affects alert/notification eligibility and delivery-channel noise.
* Scanner records include `presence_mode`, `notification_allowed_by_presence`, and `presence_reason`.
* Focus Mode can allow the scanner to classify `signal_level` while setting `notification_allowed_by_presence` to `false`.
* Trading Mode suppresses review-level notifications but can allow alert-level notifications when the existing scanner eligibility and global notification gates also allow them.

Future automatic presence detection is not implemented yet. There is no location detection, calendar detection, wake listener integration, or automatic mode switching in v1.

## Scanner Refinement v1

Scanner Refinement v1 aligns scanner output with Liquidity Narrative Continuation and reduces noisy scanner behavior while preserving the existing interval-based scanner loop.

Signal levels:

* informational: normal scan update; no action needed.
* watch: price is approaching important liquidity or an FVG reaction zone; no confirmation yet.
* review: price is interacting with a reaction zone and meaningful behavior is forming or confirmed; worth manual review.
* alert: stronger narrative shift or confirmation exists and may become eligible for notification later.

Scanner rules:

* FVGs are reaction zones, not automatic entries.
* FVG touch/contact alone is not notification-worthy.
* Price inside or interacting with an FVG reaction zone is watch context until behavior confirms acceptance, rejection, reclaim, sweep, displacement, structure shift, continuation compression/expansion, or liquidity-draw alignment.
* Medium/High alert eligibility requires meaningful behavior confirmation.
* `SCAN_ALERT_MIN_LEVEL` defaults to `review`.
* `SCAN_SUPPRESS_REPEATS_MINUTES` defaults to `15`.
* Repeat-suppressed scans still save scan history but are not marked notification-worthy inside the suppression window.

Scanner records now include `signal_level`, `signal_reason`, `narrative_state`, `reaction_zone_status`, `behavior_confirmation`, `liquidity_draw_alignment`, `repeat_suppressed`, `presence_mode`, `notification_allowed_by_presence`, and `presence_reason`.

## Narrative-Based Scanner v1

Narrative-Based Scanner v1 makes scanner output track the Liquidity Narrative Continuation trade story instead of presenting isolated chart facts. It is scanner state and display enrichment only.

Scanner records now include structured narrative state.

Narrative fields:

* `liquidity_draw`
* `liquidity_draw_direction`
* `htf_reaction_zone`
* `reaction_zone_timeframe`
* `reaction_zone_type`
* `reaction_zone_status`
* `behavior_inside_zone`
* `structure_confirmation`
* `execution_readiness`
* `target_liquidity`
* `invalidation_context`
* `narrative_phase`
* `narrative_confidence`
* `missing_confirmations`

Narrative phases:

* `no_clear_narrative`
* `draw_identified`
* `approaching_reaction_zone`
* `interacting_with_reaction_zone`
* `behavior_forming`
* `structure_confirming`
* `execution_watch`
* `continuation_confirmed`
* `narrative_invalidated`

Scanner output now tracks the trade story rather than only isolated chart facts.

The phase now influences scanner signal level conservatively: no clear narrative and draw-only states remain informational/watch context, reaction-zone approach/interaction stays watch, behavior and structure states move to review, execution watch can become review/alert depending confidence, continuation confirmed is alert, and invalidated narratives are review. Simple FVG contact is still not an alert.

Narrative-Based Scanner v1 does not increase automatic notification noise. It does not enable notifications globally, does not bypass alert eligibility, does not bypass Presence Mode gating, and does not change `SCAN_INTERVAL_SECONDS`.

## Trading Framework Notes

Trading Model Refinement v1 adds Jadin's actual framework:
Liquidity Narrative Continuation.

Core thesis:

* Price seeks liquidity.
* FVGs are not automatic entries.
* FVGs are reaction zones where price reveals whether it intends to continue toward or away from liquidity.
* The primary question is: where is price trying to go?

Framework:

* Determine higher-timeframe bias first.
  * Daily
  * 4H
  * 1H
* Identify draw on liquidity.
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
* Mark HTF reaction zones.
  * Daily FVG
  * 4H FVG
  * 1H FVG
  * 15M FVG
* Evaluate behavior inside the zone.
  * Acceptance
  * Rejection
  * Sweep
  * Reclaim
  * Displacement
  * Consolidation
* Confirm structure.
  * 15M MSS/BOS
  * 5M MSS/BOS
* Execute only after behavior and structure confirm.
  * 1M BRTC
  * 1M FVG retest
  * Sweep + reclaim
  * MSS after displacement
* Target liquidity first.
  * Nearest liquidity
  * Session liquidity
  * PDH/PDL
  * Weekly liquidity
  * Fixed RR only when liquidity is unclear or too far
* Use if/then language.
* Never claim certainty or advise immediate entry without confirmation.
* Do not use VWAP.

Strategy Modes:

* Scalp Mode: short hold time, usually 1-5 minutes. Uses HTF context but targets immediate liquidity. Execution is more aggressive and useful during funded-account rebuilds or small controlled targets.
* Day Trade Mode: longer hold time, usually 15-90+ minutes. The HTF narrative drives the trade, targets larger liquidity pools, and requires more selective execution.

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

# Trade Journal Data Foundation

Trade Journal is the durable trading dataset layer for future Helix trading intelligence. It currently captures raw trade records, imported trade drafts, order enrichment, narrative, context, strategy profile/mode, review fields, and attachment paths.

Current role:

* Preserve Jadin's manual strategy context and narrative after each trade.
* Attach the Liquidity Narrative Continuation strategy profile and strategy mode where available.
* Convert broker Performance and Orders PDFs into user-confirmed journal entries.
* Keep imported trades in preview/draft form until Jadin explicitly saves them.
* Store execution facts and user reasoning for read-only Trading Coach v2 review.
* Support read-only Scanner + Journal Correlation by comparing saved journal entries with nearby scan history records.
* Support read-only Pattern Discovery with small-sample caution.
* Help validate what Jadin actually trades versus what he thinks he trades without automatic scanner or strategy changes.

Future role:

Trade Journal is now the primary source for:

* Trading Coach v2 / Journal Review Intelligence v1
* Scanner + Journal Correlation v1
* Pattern Discovery v1

Trade Journal remains the planned primary source for:

* Future Trading Model Refinement
* Future Scanner Refinement after explicit approval workflow
* Presence Modes
* Narrative-Based Trading Analysis
* Performance Analytics

Current boundaries:

* Trade Journal data is not yet used for automatic scanner changes.
* Trade Journal data is used for read-only coaching and scanner-correlation summaries only.
* Trade Journal data is used for read-only Pattern Discovery only.
* Trade Journal data is not used for automatic strategy model updates.
* Screenshot, PDF, and CSV artifacts are referenced through paths but are not yet learned from directly by a model.

---

# Current Limitations

## Orbit and Scheduling

* Schedule Intelligence v1 is implemented as read-only recommendation logic only.
* Schedule Board displays stored blocks and Schedule Intelligence v1 output, but it does not automatically place, move, or rebalance blocks.
* Mobile UI Pass v1 is a real-world testing pass, not final app-quality mobile polish; remaining mobile refinements should be collected during actual phone usage.
* Conflict detection is not implemented.
* Protected time, recovery buffers, and workload balancing are not implemented.
* Auto Schedule Placement is not implemented.

## Trading

* Scanner still uses interval-based logic.
* Scanner uses one configured default symbol at a time.
* Watchlist rotation is not implemented.
* Trading Model Refinement v1 is implemented as a framework/profile refinement.
* Scanner Refinement v1 is implemented for signal tiers, FVG reaction-zone alert quality, and repeat suppression.
* Narrative-Based Scanner v1 is implemented for narrative phase/state enrichment and latest-scan display.
* Default Scanner Symbol v1 is implemented for MES, MNQ, ES, and NQ as selectable scanner defaults.
* Trading Coach v2 / Journal Review Intelligence v1 is implemented as read-only Trade Journal review.
* Scanner + Journal Correlation v1 is implemented as read-only matching between journal entries and scanner records.
* Pattern Discovery v1 is implemented as read-only early pattern observation with small-sample caution.
* No automatic scanner refinement is implemented from Trade Journal data yet.
* Advanced Trading Coach is not implemented.
* No automatic strategy changes are implemented from Trade Journal data.
* No direct screenshot/PDF/CSV model learning is implemented yet.
* User still provides strategy context and narrative manually after import.
* Trade Journal strategy mode classification is available as backend logic, and Trading Coach counts saved strategy modes without changing them.
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

Completed roadmap items removed from active priority lists include Agent Foundation v1, Web Search Agent v1 scaffolding, Readiness Advisory Agent v1, Agent Prioritization, Scheduled Agent Runs, Morning Check-In/Fallback Summary, Major Events Management v1, Calculated Major Event Progress, Schedule Blocks v1, Schedule Board v1, Schedule Intelligence v1, Trade Journal v1, Trade Journal PDF Import v1, Trading Coach v2 / Journal Review Intelligence v1, Scanner + Journal Correlation v1, Pattern Discovery v1, Trading Model Refinement v1, Scanner Refinement v1, Presence Modes v1, Narrative-Based Scanner v1, Default Scanner Symbol v1, Command Router v1, Voice Trigger Prototype, Wake Phrase Listener v1, TTS Routing, Morning Briefing Condenser, Service Management / LaunchAgent support, and Mobile UI Pass v1.

## Next Major Development Priorities

Priority order:

1. Advanced scanner refinements
2. Schedule Intelligence v2 later

## Schedule Intelligence v2 (Future)

Planned features:

* Auto placement of flexible blocks
* Priority-aware scheduling
* Conflict detection
* Protected time blocks
* Family time planning
* Reading time planning
* Recovery/buffer time
* Schedule compression warnings
* Daily workload balancing
* Calendar notifications
* Google Calendar integration later

Status: Not started.

## Trading System Refinement Backlog

Purpose:

Improve Helix's understanding of Jadin's actual trading model rather than generic ICT concepts.

Completed:

* Schedule Intelligence v1
* Trade Journal v1
* Trade Journal PDF Import v1
* Trading Coach v2 / Journal Review Intelligence v1
* Scanner + Journal Correlation v1
* Pattern Discovery v1
* Trading Model Refinement v1
* Scanner Refinement v1
* Presence Modes v1
* Narrative-Based Scanner v1
* Default Scanner Symbol v1

Next:

1. Advanced scanner refinements
2. Schedule Intelligence v2 later

## Presence Modes (Future)

Examples:

* Home Mode
* Trading Mode
* Focus Mode
* Away Mode

Goals:

* Reduce scanner noise
* Modify notification behavior
* Adjust scan frequency
* Adjust assistant behavior based on availability

---

# Stability Checklist

## Backend and Command Router

* Restart backend after Command Router or backend code changes.
* Running LaunchAgent processes do not automatically import changed Python files until restarted.
* Use `scripts/status_mac_services.sh restart` to kickstart loaded services.
* Confirm backend health with `GET http://127.0.0.1:8000/`.
* Confirm phone frontend access at `http://192.168.8.119:3000/`.
* Confirm deterministic router behavior through `/chat` after restart.

## LaunchAgent Setup

Install services:

* `scripts/install_mac_services.sh core`: backend, frontend, scheduled agents, iMessage bridge.
* `scripts/install_mac_services.sh all`: backend, frontend, scheduled agents, iMessage bridge, scanner, CSV refresh.
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
* Frontend: `backend/logs/frontend.out.log`, `backend/logs/frontend.err.log`
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
6. Keep Schedule Intelligence v1 read-only and deterministic; do not add auto-placement or calendar mutation without an explicit approved v2 workflow.
7. Do not add migrations or service behavior changes during documentation-only refreshes.
8. Do not add autonomous notifications, readiness updates, or task creation without explicit approval gates.
9. Prefer deterministic routing for common Command Center requests before adding a full LLM planner.
10. Update this overview when major architecture, service, or roadmap state changes.
