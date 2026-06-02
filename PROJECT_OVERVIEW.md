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

Responsibilities:

* Chat endpoints
* Tool execution
* Trading analysis
* Scan scheduling
* TTS
* Memory/history
* Orbit APIs
* Agent APIs
* Trade Journal APIs
* API integrations

## Frontend

Technology:

* Next.js

Responsibilities:

* Helix Core home surface
* Command Center
* Orbit Operating Board
* Trade Journal
* Scanner controls and status displays
* Minimal Agent controls
* Future reporting

---

# Current State

Helix is now a working local-first assistant with an operational trading scanner, Orbit planning APIs, Agent Foundation v1, a Next.js frontend, macOS service automation, CSV refresh automation, TTS, and iMessage notification infrastructure.

The trading system has moved beyond basic scan summaries. It performs multi-timeframe chart capture and deterministic analysis, combines CSV structure with live TradingView visuals, identifies liquidity draw, classifies behavior, detects continuation compression and expansion, evaluates alert eligibility, and can deliver controlled notifications when enabled.

Notifications remain intentionally gated. Smart scan notifications default disabled and only deliver when the scanner has already determined notification eligibility. Manual notification test endpoints exist so TTS and iMessage delivery can be verified without fabricating a real Medium or High trading alert.

Helix remains the central intelligence layer. Orbit stores structured planning, progress, trade-session, readiness, and agent-run data. Scanner logic remains separate from Orbit.

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
* Agents are still read-only and do not create tasks.

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
* Scheduled Agent Runs v1 can check due scheduled agents manually through `POST /agents/scheduled/run-once`
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
* Scheduled Agent Runs v1 can be run manually via endpoint or by a future macOS LaunchAgent
* Morning Check-In / Fallback Summary v1 lets Jadin initiate a morning check-in through UI, iMessage, manual calls, or a future voice path
* Morning fallback sends the Morning Review summary by iMessage after the 6:30 AM local cutoff only when no check-in has been acknowledged

Current restrictions:

* Agents are read-only for now.
* Scheduling is limited to Morning Review Agent, Evening Review Agent, and a read-only prioritization snapshot.
* No task creation yet.
* No readiness updates yet.
* No notifications yet.
* No scanner changes.
* No trading signals.
* Readiness Advisory Agent is advisory only: it does not update readiness, create tasks, create reviews, send notifications, schedule itself, or modify milestones or major events.
* Readiness Advisory Agent suggestions require manual approval before any readiness score can change.
* Web Search Agent v1 does not browse the web. It outputs `research_target`, `reason`, `suggested_queries`, `sources_required`, `actions_taken: []`, and `web_search_performed: false`.
* Actual cited web search is reserved for a later version.
* Agent Prioritization Layer v1 is read-only and recommendation-only. It does not run agents, create tasks, update readiness, create reviews, or send notifications.
* Scheduled Agent Runs v1 does not install a LaunchAgent yet. Actual LaunchAgent install can come later.
* Morning Check-In / Fallback Summary v1 does not implement microphone wake phrase detection or full conversational voice.
* Morning Check-In only uses TTS when the endpoint is explicitly called with `speak=true`.

Scheduled or background automation should call `run_agent(agent_id)` rather than duplicating agent behavior.

---

# Notifications and Voice

Notification infrastructure is implemented but gated.

Current working outputs:

* TTS output works through macOS `say`.
* iMessage output works through the local Messages bridge.
* Smart scan notifications work when explicitly enabled and when alert eligibility allows delivery.
* Manual notification test endpoints verify delivery without fabricating scanner alerts.

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

Speech input and wake phrase are not implemented yet.

Future "Good morning Helix" audible workflow requires:

* Mic listener
* Wake phrase detection
* Speech-to-text
* Helix intent routing
* TTS response

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
* Speech input, wake phrase detection, and conversational voice mode are not implemented yet.
* Morning Check-In / Fallback Summary v1 supports a future voice path through `speak=true`, but no microphone wake phrase or speech input has been implemented.
* Orbit readiness scoring still requires manual judgment and Helix-assisted updates.
* Orbit milestone progress remains manual unless Jadin explicitly applies the task-derived advisory.
* Suggested task creation is user-approved only.
* No autonomous task creation exists yet.
* Agents are read-only in v1.
* Scheduled Agent Runs v1 is limited to Morning Review Agent, Evening Review Agent, and a daily prioritization snapshot.
* Agents do not create tasks, update readiness, send notifications, or modify scanner state.
* Task reminders are not connected yet.
* Free-form task tags are not implemented yet. Milestone links are structured tags only.
* News risk is useful but not yet a complete economic-calendar intelligence layer.

---

# Next Development Priorities

1. Cited Web Search Agent execution for tasks requiring current or external information.
2. Scheduled Agent Runs using `run_agent(agent_id)` as the shared execution path.
3. Voice wake / speech input prototype for the future "Good morning Helix" workflow.
4. Agent notification approvals for controlled summaries after scheduled or manual runs.
5. Readiness update advisory.
6. Agent Prioritization Layer so Helix can decide which agent should run and why.
7. Helix Core Agent Summary so the home surface can show recent agent output without becoming noisy.
8. Daily and weekly automation loops for Morning Review, Evening Review, planning review, and trading review.
9. Task reminder support connected to Orbit tasks.
10. Expanded Orbit review workflows for daily and weekly synthesis.
11. Scanner frontend visibility for liquidity draw, behavior classification, alert eligibility, notification status, and CSV freshness.
12. 1M execution confirmation layer while preserving source-of-truth rules.
13. Trade Journal analytics and readiness evidence generation.

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
* Voice activation
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
