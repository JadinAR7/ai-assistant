# Helix Project Overview

Last refreshed: June 19, 2026

Helix is Jadin's local-first assistant and operating layer. It combines a chat assistant, Orbit life operating system, agent framework, trading assistant, schedule platform, voice/TTS surface, and local messaging workflows into one system.

This document is the source of truth for the current implementation before the next major feature phase.

---

# Executive Summary

Helix today is:

* **AI Assistant**: a FastAPI-backed chat assistant with local Ollama model fallback, tool execution, image/chart analysis, history, and Command Center UI.
* **Orbit Life Operating System**: a structured SQLite-backed system for major events, milestones, goals, tasks, reviews, readiness, schedule blocks, progress history, recommendations, trade-session records, Trade Journal records, and agent run records.
* **Agent Framework**: a read-only/recommendation-first agent layer with manual runs, scheduled runs, prioritization, stored outputs, and Morning Check-In workflow.
* **Trading Assistant**: a TradingView scanner and analysis stack for MES/MNQ/NQ/ES context. It uses HTF CSV as the structural map, LTF vision screenshots as live chart context, model-aware Ollama vision extraction, conservative confidence caps, scanner system-health state, market/chart alert state, gated notifications, and Trade Journal data capture.
* **Scheduling Platform**: Orbit Schedule Blocks, Calendar, Blocks grouped view, and Schedule Intelligence for recurring/fixed/flexible schedule rules, day-level calendar placements, grouped schedule patterns, finite recurrence, multi-day edits, day density, free-time windows, overloaded-day detection, and placement recommendations.
* **Voice-enabled Assistant**: macOS `say` TTS, configurable voice profiles, TTS routing, speech formatting, manual Voice Trigger prototype, Wake Phrase Listener v1, Morning Briefing condenser, and iMessage-backed morning fallback delivery.

Helix remains the central intelligence layer. Orbit stores durable planning data. Agents perform specialized read-only analysis. Scanner logic remains separate from Orbit and does not write planning state.

---

# Current Status

## Completed Recently

* Scanner HTF CSV + LTF vision refactor
* Qwen3-VL vision evaluation and JSON repair
* Scanner system health separation from market/chart alert state
* TradingView profile lock for scanner/CSV browser automation
* Screenshot capture fallback/recovered issue tracking
* Response-quality guardrails for incomplete local-model fragments
* Orbit Schedule block/rule cleanup
* Fixed schedule multi-day edit/apply behavior
* Flexible multi-day scheduling
* Finite recurrence controls
* Blocks grouped by schedule pattern
* Calendar day-level placements from schedule rules

## Known Limitations / Next Work

* Scanner vision quality is improving but still needs repeated live validation.
* Qwen3-VL can still require JSON repair.
* Scanner is usable for review/watch/alert context, not autonomous trade decisions.
* Scanner should not generate trade signals or entries.
* Strategy teaching overhaul is under consideration.
* Calendar scheduling logic should continue to be tested with real weekly planning.
* Full backend test discovery can be blocked by optional local dependencies or unrelated local test drift; run targeted Orbit/scanner tests when discovery is blocked.

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

* Higher-timeframe structural context
* FVG reaction-zone mapping
* Liquidity mapping
* Market structure analysis
* Historical context and backup price-action context

Default HTF CSV timeframes:

* `1D`
* `4H`
* `1H`

Vision analysis is responsible for:

* Live visible chart context
* Current displayed price when CSV freshness is limited
* User markings
* Labels
* Session context
* Visual confirmation

Default live vision timeframes:

* `15M`
* `5M`

`1M` is conditional execution context only and should not run by default.

Freshness rules:

* Fresh CSVs may be used for structure and price context.
* Stale CSVs may only be used for structure and FVG reaction-zone mapping.
* Stale CSV is degraded structural context, not automatically a failed scanner state.
* CSV parse/load failure is failed.
* When CSV is stale, vision becomes the primary live-context source.
* Helix must never present stale CSV prices as confirmed live market prices.
* Stale CSV Guardrail v1 separates HTF structural context from live execution state: CSV can keep old FVGs on the map, but live vision decides whether price is inside, above, below, reclaiming, or invalidating those zones.
* If live vision shows price below a stale CSV bullish FVG/support zone, the scanner treats that zone as below/failed support and requires reclaim before any bullish execution review.
* Command Center CSV analysis follows the same rule: stale CSV closes are labeled as stale CSV reference closes, not live/current price, and live vision/latest scanner context is preferred for current price.

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
* `backend/response_quality.py`: incomplete-response detection, retry-once repair prompt construction, and fallback text for bad local-model fragments.
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
* `backend/scheduled_scan.py`: configured-symbol scanner, HTF CSV + LTF vision orchestration, screenshot capture recovery, deterministic analysis, state comparison, Scanner Refinement v1 signal tiers, narrative state, market alert state, system health state, alert eligibility, repeat suppression, confidence caps, and gated scan notifications.
* `backend/csv_refresh.py`: scheduled and forced TradingView CSV refresh with verification before active file replacement.
* `backend/tradingview_profile_lock.py`: browser/profile lock used to keep TradingView automation from colliding across scanner and CSV refresh processes.
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
* `backend/csv_data/`: active TradingView CSV files.
* `backend/pictures/tradingview_screenshots/`: scanner and vision-evaluation screenshot artifacts.

## Frontend

Technology:

* Next.js app router
* React client components for Command Center, Orbit, schedule, major events, agents, scanner controls, and trade-session surfaces

Primary surfaces:

* `/`: Helix Core home surface with navigation and current Orbit morning status.
* `/command-center`: Helix Command Center chat, tool mode selection, image/chart upload, scanner status, scanner system health, latest scan, force scan, CSV refresh controls/status, history reset, history display, and frontend incomplete-fragment safety net.
* `/orbit`: Orbit Operating Board with dashboard tabs for overview/workflows, Major Events, calculated progress, milestones, Inbox tasks, recommendations, strategic gaps, readiness, Schedule/Calendar/Blocks, Morning Check-In, Scheduled Agent status, agent prioritization, and manual agent runs.
* `/trade-journal`: Trade Journal data-capture surface with manual entry, PDF import preview, import draft review, list/detail/edit/delete workflows, and attachment path capture.
* `/orbit/trade-journal`: Orbit-linked trade journal route.
* `/ascend`: future-facing Ascend/training/readiness concept surface.

Current frontend capabilities:

* Command Center calls `/chat`, scanner endpoints, CSV refresh endpoints, image analysis, reset, and history.
* Orbit page preloads major events, milestones, reviews, readiness, morning briefing, daily closeout, recommendations, inbox tasks, progress advisory/history, agents, agent prioritization, scheduled-agent status, Morning Check-In status, schedule blocks, and schedule intelligence.
* Schedule Board supports fixed and flexible schedule blocks, week navigation, Calendar day placements, Blocks grouped by unique schedule pattern, date-aware placement, recurring day-of-week display, specific-date blocks, active/archive state, editing, deletion, multi-day fixed edits, flexible preferred days, finite recurrence, category/priority metadata, subtle current-day column highlighting, and compact Schedule Intelligence display.
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
* Orbit Schedule rule/pattern cleanup
* Fixed schedule multi-day edit/apply behavior
* Flexible multi-day scheduling
* Finite schedule recurrence
* Blocks grouped by schedule pattern
* Trade Journal v1
* Trade Journal PDF Import v1
* Trading Coach v2 / Journal Review Intelligence v1
* Scanner + Journal Correlation v1
* Pattern Discovery v1
* Trading Model Refinement v1
* Scanner Refinement v1
* Stale CSV Guardrail v1
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
* Task editing
* Task priority scoring
* Task-milestone links
* Strategic gap review
* Task creation from strategic gaps and recommendations
* Recommendation task drafts
* Explicit user-approved creation from recommendations

Tasks can stay in the Inbox while being linked to milestones, so milestone context does not forcibly move a task out of Inbox.

Strategic gaps are read from Orbit evidence and can feed user-approved task creation. Recommendations remain advisory until the user explicitly creates or edits a task.

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

Schedule blocks are rules/patterns, not raw day duplicates. The backend stores schedule rows with recurrence and timing metadata, while the frontend renders those rows either as day-level Calendar placements or grouped Blocks patterns.

Fixed blocks support:

* Selected days
* Same time across selected days
* Per-day different times
* Edit/update without duplicate creation
* Applying edits to multiple selected days
* Existing grouped-pattern editing and expansion to more days
* Replacement of conflicting old patterns for the same block/category/title/day selection
* Duplicate-pattern merge behavior through grouped display and schedule update cleanup

When Same time is checked, all selected days use the global `start_time` and `end_time`, stale per-day fields are ignored, and existing per-day variations for selected days are overwritten. When Same time is unchecked, selected days use per-day times and the global time controls are disabled/ignored.

Flexible blocks support:

* Multiple preferred days
* Whenever-free mode
* Suggested placements
* Candidate placement controls
* Finite recurrence
* Duration-based scheduling

Recurrence supports:

* Once
* Daily
* Weekly
* Every other week
* End controls: never, end date, occurrences, or weeks

Time inputs support clear/reset behavior. Global time inputs are disabled/ignored when using per-day times.

Examples:

* Work Mon-Thu with the same time is one grouped schedule pattern.
* Boxing Mon/Wed with the same time plus Tue/Thu with different times is displayed as multiple unique patterns.

## Schedule Board

The Orbit frontend includes a Schedule Board with:

* Week navigation
* Current week heading
* Seven-day display
* Calendar tab with day-level placements
* Blocks tab grouped by unique schedule pattern
* Date-aware scheduling through `specific_date`
* Day-of-week recurring block display
* Unscheduled/flexible block list
* Create/edit/delete/archive controls
* Fixed-block multi-day selection
* Flexible-block preferred-day selection
* Candidate placement for flexible blocks

The Today button returns the visible week to the current week. When the visible week includes today, the current day is indicated by a subtle turquoise column highlight rather than a separate day-header badge.

Calendar view answers "what appears on this day?" Blocks view answers "what schedule patterns exist?" The two should agree after edits: for example, a Work Mon-Thu same-time block should show one grouped child row in Blocks and four day-level placements in Calendar.

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

# Response Quality Guardrails

Response-quality protection is implemented in `backend/response_quality.py`, `backend/main.py`, and the Command Center frontend.

Backend behavior:

* Detects incomplete local-model fragments such as `Based`, `Based on`, `Sure`, `The`, and other tiny/dangling responses.
* Allows legitimate short answers such as yes/no/done/ok when appropriate.
* Retries once with a repair prompt that includes the user message and the rejected incomplete response.
* Uses a fixed fallback message if repair also fails or Ollama is unavailable.
* Saves only the repaired or fallback assistant message to history.
* Does not save the original bad fragment as an assistant response.
* Streaming chat performs the same final-response validation and appends the repaired/fallback response when needed.

Frontend behavior:

* Command Center applies a safety net for obvious assistant fragments loaded from history or returned by chat.
* Obvious fragments are shown as system/error-style fallback content rather than polished assistant answers.
* Tool/system responses are not treated as ordinary assistant fragments.

---

# Current Endpoints

## Core

* `GET /`: backend health check.
* `POST /chat`: primary chat, deterministic intent routing, and tool-routing endpoint.
* `POST /chat/stream`: streaming chat endpoint.
* `POST /analyze-image`: uploaded chart/image analysis.
* `POST /vision/evaluate-chart`: evaluate one saved chart screenshot across `VISION_MODEL` / `VISION_MODEL_CANDIDATES`; supports debug response fields.
* `GET /presence`: current Presence Mode config, `updated_at`, and available modes.
* `POST /presence`: set manual Presence Mode with `{ "mode": "home|trading|away|focus" }`.
* `POST /reset`: clear chat memory.
* `GET /history`: recent chat history.
* `GET /tool-logs`: recent tool calls.

## Scanner and CSV

* `GET /scanner/settings`
* `POST /scanner/settings`
* `POST /scan/force`
* `POST /scan/force?symbol=MES`
* `GET /scan/latest`
* `GET /scan/latest?symbol=MES`
* `GET /scan/status`
* `GET /csv-refresh/status`
* `POST /csv-refresh/force`
* `POST /csv-refresh/force?symbol=MES`

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
* `PATCH /orbit/schedule-blocks/{schedule_block_id}/apply-days`
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
* Vision bakeoff/evaluation candidates are configurable through comma-separated `VISION_MODEL_CANDIDATES`.
* Qwen3-VL models are supported through model-aware `/api/chat` transport with `/api/generate` fallback attempts; older vision models generally try `/api/generate` first.
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
* Default symbol/timeframes: `scanner_settings.json` default symbol, HTF CSV `1D`/`4H`/`1H`, live vision `15M`/`5M`, and conditional-only `1M`.
* Interval: 5 minutes during active market sessions.
* Logs: `backend/logs/scanner.out.log`, `backend/logs/scanner.err.log`
* TradingView automation uses profile locking so scanner and CSV refresh do not fight over the same browser profile.

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
* CSV remains the source of truth for HTF historical structure, FVG mapping, liquidity mapping, and backup price-action context.
* Vision remains responsible for live visible chart context and user markings.
* Stale CSVs must not be treated as confirmed live price.
* Stale CSV is degraded structural context; CSV parse/load failure is failed.
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
* HTF CSV structural map from `1D`, `4H`, and `1H`
* LTF live vision chart context from `15M` and `5M`
* Conditional `1M` execution context only, not default scanner capture
* CSV freshness checks
* CSV stale/degraded versus CSV parse/load failure distinction
* Deterministic CSV-backed chart analysis
* Vision/context merge for visible chart markings and labels
* Qwen3-VL and qwen2.5vl-compatible chart extraction
* JSON repair fallback for chart-vision output
* Vision quality scoring and confidence caps
* Screenshot capture fallback and recovered issue tracking
* Separate scanner system health and market/chart alert state
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
2. Read HTF CSV structure from `1D`, `4H`, and `1H`.
3. Capture live LTF TradingView screenshots for `15M` and `5M`.
4. Recover from capture metadata gaps when a saved screenshot exists and track recovered issues separately.
5. Run vision and deterministic CSV-backed chart analysis.
6. Attach data freshness and source-of-truth context.
7. Compare current state against recent scan history.
8. Attach liquidity draw output.
9. Attach behavior classification output.
10. Attach Narrative-Based Scanner state.
11. Attach scanner signal tier output.
12. Cap scanner confidence when vision quality is degraded, CSV is stale, or only partial live timeframe evidence exists.
13. Attach market/chart alert state.
14. Attach scanner system health state.
15. Attach Presence Mode notification eligibility.
16. Deliver scan notifications only when notification infrastructure is enabled, alert eligibility allows it, and Presence Mode permits it.
17. Persist scan history and runtime status.

Notifications remain intentionally gated. Smart scan notifications default disabled and only deliver when scanner logic has already determined notification eligibility. Manual notification test endpoints exist so TTS and iMessage delivery can be verified without fabricating a real trading alert.

Scanner output is review/watch/alert context only. It must not generate autonomous trade signals, entries, or execution instructions.

Scanner system health can be:

* `healthy`
* `degraded`
* `failed`

Market/chart alert state is separate from system health. A degraded scanner can still preserve useful structural review context, and a clean system-health state does not itself imply a chart alert. Recovered screenshot issues are tracked separately and should not count as active failures when recovery succeeded.

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

## Stale CSV Guardrail v1

Stale CSV Guardrail v1 prevents scanner/chart analysis and Command Center CSV analysis from over-weighting old CSV-derived FVG zones when the live TradingView screenshot shows price has moved away from them.

Guardrail rules:

* When CSV is stale, CSV-derived zones are structural references only.
* Live vision is primary for current price and zone interaction.
* The scanner must not describe stale CSV close values as current price.
* Command Center `analyze_market_csv` must label stale CSV close values as stale CSV reference closes, not live/current price.
* If a live screenshot or latest scanner context has current-price information, that live/vision source is preferred over stale CSV close.
* The scanner must not call a stale bullish FVG active support if live vision places price below it.
* If live price is below a stale bullish FVG/support zone, zone status becomes `below_zone` or `failed_support`, and execution readiness becomes reclaim-needed/no-long-until-reclaim.
* If live price is above a stale bearish FVG/resistance zone, zone status becomes `above_zone` or `failed_resistance`, and rejection is needed before bearish execution review.
* HTF structural bias, intraday behavior, and execution readiness are separated in scanner output.

This guardrail does not change scanner interval, notifications, CSV refresh cadence, Presence Modes, or scanner service behavior.

## Vision Model Evaluation

Vision extraction is implemented in `backend/tools.py` and exposed through `POST /vision/evaluate-chart`.

Model configuration:

* `VISION_MODEL`: primary chart-vision model.
* `VISION_MODEL_CANDIDATES`: optional comma-separated bakeoff/evaluation list. If set, `VISION_MODEL` is inserted first when missing.
* Qwen3-VL is supported.
* qwen2.5vl-compatible fallback remains supported.

Transport behavior:

* Qwen3-VL models try Ollama `/api/chat` first.
* Older vision models generally try `/api/generate` first.
* The transport can fall back between `/api/chat` and `/api/generate` when the first attempt fails or returns no usable text.

Extraction behavior:

* The chart extraction prompt asks for JSON-only visible chart facts: timeframe, current price marker, visible labels, levels, drawn boxes/FVG zones, PDH/PDL, session context, behavior evidence, and uncertainty flags.
* If the model returns malformed or truncated JSON, Helix attempts JSON repair with the text model.
* Debug mode on `/vision/evaluate-chart` includes endpoint attempts, parse strategy, response keys, raw preview, JSON parse error, and repair preview when relevant.
* Vision quality is scored as `usable`, `degraded`, or `unreliable`.
* Low-quality vision caps scanner confidence; unreliable vision is not trusted for behavior interpretation.

Example:

```bash
curl -s -X POST "http://127.0.0.1:8000/vision/evaluate-chart" \
  -H "Content-Type: application/json" \
  -d '{
    "image_path": "/Users/jadinrobinson/ai-assistant/backend/pictures/tradingview_screenshots/MES_15M_YYYY-MM-DD_HHMMSS.png",
    "symbol": "MES",
    "timeframe": "15M",
    "debug": true
  }' | jq
```

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
* Calendar scheduling logic should continue to be tested against real weekly planning, especially grouped-pattern edits, finite recurrence, and flexible preferred-day placement.
* Mobile UI Pass v1 is a real-world testing pass, not final app-quality mobile polish; remaining mobile refinements should be collected during actual phone usage.
* Conflict detection is not implemented.
* Protected time, recovery buffers, and workload balancing are not implemented.
* Auto Schedule Placement is not implemented.

## Trading

* Scanner still uses interval-based logic.
* Scanner uses one configured default symbol at a time.
* Watchlist rotation is not implemented.
* Scanner vision quality is improving but still needs repeated live validation.
* Qwen3-VL can require JSON repair.
* Scanner system health is separate from market alert state; degraded health may still leave usable review context.
* Trading Model Refinement v1 is implemented as a framework/profile refinement.
* Scanner Refinement v1 is implemented for signal tiers, FVG reaction-zone alert quality, and repeat suppression.
* Stale CSV Guardrail v1 is implemented so stale CSV zones remain structural context while live vision controls current price/zone validity and execution readiness. Command Center CSV analysis shares this guardrail and labels stale CSV close values as reference closes.
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
* Scanner is usable for review/watch/alert context, not autonomous trade decisions.
* Strategy teaching overhaul is under consideration.

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

1. Trading Strategy Teaching Overhaul design pass
2. Advanced scanner refinements and live validation
3. Schedule Intelligence v2 later

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

1. Trading Strategy Teaching Overhaul design pass
2. Advanced scanner refinements and live validation
3. Schedule Intelligence v2 later

## Upcoming: Trading Strategy Teaching Overhaul

Jadin is considering redesigning how Helix learns the trading strategy.

Current scanner logic uses rules, CSV, vision, and narrative classification. It has improved from generic chart commentary into Liquidity Narrative Continuation review context, but the next step may be a clearer teaching/evaluation workflow rather than more ad hoc scanner rules.

Future direction may include:

* Clearer strategy ontology
* Annotated examples
* Golden setups
* Bad setup examples
* Session-based playbooks
* Explicit entry models
* Scenario-based rules
* Feedback loop from user corrections
* Trade Journal integration
* Model evaluation against labeled screenshots

Do not implement this overhaul during documentation refreshes. Treat it as an upcoming design topic.

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
* Full conversational voice loop
* Automatic readiness updates from evidence
* Proactive autonomous task creation

---

# June 2026 Audit Report

Files audited for this refresh:

* `PROJECT_OVERVIEW.md`
* `frontend/README.md`
* `docs/MAC_SERVICES.md`
* `backend/main.py`
* `backend/tools.py`
* `backend/scheduled_scan.py`
* `backend/csv_refresh.py`
* `backend/tradingview_profile_lock.py`
* `backend/response_quality.py`
* `backend/orbit/models.py`
* `backend/orbit/service.py`
* `backend/orbit/routes.py`
* `frontend/app/command-center/page.tsx`
* `frontend/app/orbit/OrbitBoard.tsx`
* `frontend/app/orbit/page.tsx`
* Relevant `backend/tests` discovered by search

Docs updated:

* `PROJECT_OVERVIEW.md`

Important mismatches corrected:

* Scanner docs still described broad multi-timeframe screenshot capture instead of HTF CSV plus LTF vision.
* Vision docs did not mention Qwen3-VL, `VISION_MODEL_CANDIDATES`, model-aware Ollama transport, debug evaluation, or JSON repair.
* Schedule docs still described simple Schedule Blocks v1 instead of rule/pattern grouping, Calendar day placements, finite recurrence, flexible preferred days, and multi-day edit behavior.
* Response-quality guardrails were not documented.
* Roadmap text still treated some completed capabilities as future/deferred.

Current source-of-truth assumptions:

* `backend/main.py` is the FastAPI route source of truth.
* `backend/tools.py` is the source of truth for local model, vision extraction, JSON repair, CSV analysis, and TradingView helper behavior.
* `backend/scheduled_scan.py` is the source of truth for scanner timing, HTF/LTF roles, health state, alert state, confidence caps, screenshots, and scan-history records.
* `backend/orbit/service.py`, `backend/orbit/models.py`, and `frontend/app/orbit/OrbitBoard.tsx` are the source of truth for Orbit Schedule behavior.
* `docs/MAC_SERVICES.md` and `scripts/launchagents/*.plist` are the source of truth for LaunchAgent service naming and startup expectations.

Still needs manual validation:

* Live scanner runs with the current TradingView layout and current Qwen3-VL/qwen2.5vl model availability.
* Repeated screenshot capture/recovery behavior during real market sessions.
* Orbit weekly planning with real recurring work, boxing, flexible blocks, and finite recurrence examples.
* Full backend test discovery when optional local dependencies and unrelated local test drift are resolved.

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
