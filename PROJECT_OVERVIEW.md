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

---

## Source of Truth Rules

### Trading

#### CSV Responsibilities

CSV data is responsible for:

* Historical structure
* FVG mapping
* Liquidity mapping
* Market structure analysis
* Historical context

#### Vision Responsibilities

Vision analysis is responsible for:

* Live visible chart context
* Current displayed price
* User markings
* Labels
* Session context
* Visual confirmation

#### Freshness Rules

* Fresh CSVs may be used for structure and price context.
* Stale CSVs may only be used for structure and FVG mapping.
* When CSV is stale, vision becomes the primary live-context source.
* Helix must never present stale CSV prices as confirmed live market prices.

---

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

---

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
* Trade Journal APIs
* API integrations

---

## Frontend

Technology:

* Next.js

Responsibilities:

* Dashboard
* Command Center
* Orbit
* Trade Journal
* Scan controls
* Status displays
* Future reporting

---

# Current State

Helix is now a working local-first assistant with an operational trading scanner, Orbit planning APIs, a Next.js frontend, macOS service automation, CSV refresh automation, TTS, and iMessage notification infrastructure.

The trading system has moved beyond basic scan summaries. It now performs multi-timeframe chart capture and deterministic analysis, combines CSV structure with live TradingView visuals, identifies liquidity draw, classifies behavior, detects continuation and expansion patterns, evaluates alert eligibility, and can deliver controlled notifications when enabled.

Notifications remain intentionally gated. Smart scan notifications default disabled and only deliver when the scanner has already determined notification eligibility. Manual notification test endpoints exist so TTS and iMessage delivery can be verified without fabricating a real Medium or High trading alert.

Helix remains the central intelligence layer. Orbit stores structured planning and progress data. Scanner logic remains separate from Orbit.

---

# Completed Systems

## Completed Milestones

* FastAPI backend with chat, history, tool execution, image analysis, scanner, CSV refresh, notification, and Orbit endpoints
* SQLite-backed assistant memory and Orbit storage
* Next.js frontend with dashboard, Command Center, Orbit, Trade Journal, scan controls, and status surfaces
* TradingView chart capture through Playwright-backed tooling
* Vision plus CSV chart analysis pipeline
* Scheduled scanner loop with runtime status and scan history
* Multi-timeframe scanner capture for 4H, 1H, 15M, and 5M context
* CSV freshness checks and source-of-truth handling
* CSV refresh automation with scheduled windows, safe verification, status reporting, and force refresh endpoint
* Liquidity Draw Engine
* Behavior Classification v3
* Continuation Pattern Detection
* Expansion Detection
* Chart Alert Eligibility Engine
* Smart scan notification infrastructure for iMessage and TTS
* Manual notification test endpoints for TTS, iMessage, and all-channel testing
* Persistent default iMessage recipient resolution with masked config reporting
* macOS LaunchAgent service setup for backend, scanner, and CSV refresh
* Orbit major events, milestones, goals, tasks, reviews, readiness, and trade-session APIs
* Trade Journal session logging and readiness evidence foundation

## Scanner Architecture

The scanner is centered in `backend/scheduled_scan.py`.

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

Scheduled scans use 15M as the primary analysis timeframe while collecting broader context from 4H, 1H, 15M, and 5M. Forced scans can be triggered through the backend.

Key endpoints:

* `POST /scan/force`
* `GET /scan/latest`
* `GET /scan/status`

## Multi-Timeframe Analysis

The scanner now separates higher-timeframe context from lower-timeframe confirmation:

* 4H and 1H provide directional context, larger FVGs, liquidity context, and draw alignment.
* 15M is the primary scheduled scan and review timeframe.
* 5M provides continuation, compression, breakout, and expansion evidence.
* 1M remains reserved for execution confirmation and is not used for HTF bias.

Multi-timeframe visual context is attached to scan records and summarized in the scanner output. CSV data contributes historical structure and FVG mapping while vision remains primary for current displayed price and live visual evidence when CSV freshness is limited.

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

## Liquidity Draw Engine

The Liquidity Draw Engine determines the most likely draw on liquidity from CSV and visual context. It scores visible and historical liquidity references, checks directional alignment with HTF bias, and records primary and secondary draw candidates with confidence and reasoning.

Examples of draw references:

* Previous day high and low
* Previous New York session high and low
* Asia high and low
* London high and low
* Previous week high and low
* Visible chart liquidity labels

The scanner uses liquidity draw output downstream in behavior classification, opportunity recognition, alert eligibility, and notification formatting.

## Behavior Classification v3

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

## Continuation Pattern Detection

Continuation detection identifies structured continuation contexts rather than treating every FVG touch as an alert.

The current golden-pattern logic looks for:

* HTF FVG sweep or reaction context
* 1H reclaim or retest behavior
* 5M continuation FVG
* Continuation breakout evidence
* Upside liquidity draw alignment
* Fresh or recent supporting data

When present, this can upgrade ambiguous consolidation into bullish continuation compression or support displacement-style continuation reads.

## Expansion Detection

Expansion detection identifies when a prior bullish continuation compression begins moving away from the continuation structure.

It considers:

* Prior or current compression context
* 5M continuation breakout or displacement evidence
* Holding above key level or FVG structure
* Liquidity draw still pointing above
* News risk and freshness constraints before notification eligibility is upgraded

Bullish continuation expansion is treated as a stronger review condition than compression, but still requires sufficient freshness or strong visual evidence before notification.

## Alert Eligibility

Alert eligibility is a chart-review triage layer. It does not create trade signals, entries, or execution instructions.

Current levels:

* None
* Low
* Medium
* High

Eligibility considers:

* Behavior classification
* Liquidity draw confidence
* Major state change versus recent scan history
* News risk
* CSV freshness
* Live visual clarity
* Continuation and expansion pattern evidence
* Blockers and next confirmation needed

Only Medium and High chart-review states are notification-worthy. Low and None remain scanner output only.

## Notification Infrastructure

Notification infrastructure is implemented but disabled by default.

Channels:

* iMessage through the local Messages bridge
* TTS through macOS `say`

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

Smart scan notifications use alert eligibility. Manual test endpoints bypass scan alert eligibility and exist only to verify delivery channels safely.

Default iMessage recipient resolution order:

1. Explicit endpoint recipient parameter
2. `SCAN_NOTIFY_IMESSAGE_RECIPIENT`
3. Existing configured fallback recipient
4. Clear no-recipient error

Recipient config responses mask the full recipient value.

## Mac Services

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

# In Progress Systems

## Execution Confirmation Layer

The framework defines 1M execution confirmation, but this remains a controlled future layer. The current scanner can identify review-worthy context, continuation compression, and expansion, but it should not be treated as an execution engine.

Still needed:

* 1M BRTC confirmation logic
* 1M FVG retest validation
* Sweep and reclaim confirmation
* MSS after displacement confirmation
* Clear separation between review alert and execution readiness

## Opportunity Recognition Refinement

Opportunity watch generation exists, but continued refinement is needed so labels, next confirmations, and blocker language stay aligned with the evolving Behavior Classification v3 output.

Focus areas:

* Better distinction between compression, expansion, displacement, and reversal watch states
* Cleaner bearish continuation parity
* More consistent next-confirmation language
* Better treatment of news-risk windows

## News Integration

News risk analysis exists, but it remains a gating and context layer rather than a full economic-calendar intelligence system.

Still needed:

* More robust calendar sourcing
* Better event freshness and relevance handling
* Stronger treatment of speaker events, FOMC days, CPI, NFP, and high-impact surprise conditions

## Frontend Status Surfaces

The frontend exposes scanner controls and status views, but deeper reporting remains in progress.

Still needed:

* Better visualization of scan history
* Behavior classification and liquidity draw panels
* Notification configuration controls
* CSV refresh status panels
* Clearer trend over time for readiness and trading performance

## Orbit Readiness Automation

Orbit stores readiness and trade session data. Evidence-based automatic readiness updates remain in progress.

Still needed:

* Automated readiness evidence from trade sessions
* Better weekly and monthly review synthesis
* Progress deltas tied to concrete completed work

---

# Deferred Systems

These remain part of the Helix vision but are intentionally deferred until the scanner, Orbit, and daily operating loop are more stable.

* Conversational voice mode
* Voice activation
* Mobile push notifications
* Planning Agent
* Reflection Agent
* Research Agent
* Reminder Agent
* Trading Agent as a distinct worker under Helix
* Ascend integration
* Achievement systems
* Skill progression systems
* Full performance analytics dashboard
* Screenshot-linked trade journal review
* Automated execution confirmation and trade-entry coaching

---

# Current Limitations

* Helix is local-first and depends on local services, local files, macOS permissions, Ollama, Playwright, TradingView access, and the Messages app.
* TradingView capture and CSV export can fail if the browser profile, session, layout, or page state changes.
* CSV freshness still matters. Stale CSVs cannot be treated as confirmed live price.
* Vision remains necessary for current displayed price, user markings, live labels, and visible confirmation.
* Smart notifications are disabled by default and require explicit environment configuration.
* iMessage delivery depends on macOS Messages and AppleScript availability.
* TTS delivery depends on macOS `say`.
* Scanner alerts are chart-review notifications, not trade entries.
* Execution confirmation is not complete.
* Orbit readiness scoring still requires manual judgment and Helix-assisted updates.
* News risk is useful but not yet a complete economic-calendar intelligence layer.

---

# Next Development Priorities

1. Harden scanner status surfaces and expose clearer frontend views for liquidity draw, behavior classification, alert eligibility, and notification status.
2. Improve CSV refresh observability and make stale-data limitations more visible in the frontend.
3. Refine Opportunity Watch language so compression, expansion, reversal, and no-opportunity states are easier to act on.
4. Build the 1M execution confirmation layer without weakening the current source-of-truth rules.
5. Add stronger news-event handling and explicit high-impact event gating.
6. Expand Trade Journal analytics and connect trade-session evidence to Orbit readiness.
7. Improve notification controls in the frontend while keeping smart notifications disabled by default.
8. Add richer scan-history review tools for end-of-day and end-of-week trading review.

---

# Trading Framework

## Strategy Name

Liquidity-Driven ICT with BRTC Execution

---

## Core Philosophy

Price seeks liquidity.

FVGs are reaction zones, not targets.

The purpose of an FVG is to reveal whether price intends to continue toward liquidity or reject away from it.

The scanner should never treat touching an FVG as a trade signal.

---

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

---

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

---

### Step 3: Identify Reaction Zones

Priority:

1. Daily FVG
2. 4H FVG
3. 1H FVG
4. 15M FVG

Question:

Where should price make a decision?

---

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

---

### Step 5: Structure Confirmation

Timeframes:

* 15M MSS/BOS
* 5M MSS/BOS

Question:

Is the market changing direction or continuing?

---

### Step 6: Opportunity Recognition

Possible outputs:

* Bullish Continuation Watch
* Bearish Continuation Watch
* Reversal Watch
* Range / Chop Warning
* No Opportunity

---

### Step 7: Alert Eligibility

Possible outputs:

* None
* Low
* Medium
* High

Purpose:

Determine whether the market state is important enough to notify the user.

---

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

---

# Trading System

## Current Scanner Capabilities

### Analysis

* Market structure analysis
* FVG detection
* Liquidity analysis
* Liquidity Draw Engine
* Bias determination
* Behavior Classification v3
* Continuation Pattern Detection
* Expansion Detection
* Opportunity Watch generation
* Chart Alert Eligibility
* News Risk analysis

### Capture

* TradingView screenshot capture
* Forced 15M scans
* Multi-timeframe capture

  * 4H
  * 1H
  * 15M
  * 5M

### Safety

* CSV freshness awareness
* Source-of-truth enforcement
* Scan status monitoring
* Alert eligibility gating before smart notification delivery
* Manual notification test endpoints that bypass scan eligibility only for delivery verification

### Current Outputs

* Market State
* News Risk
* Data Freshness
* Liquidity Draw
* Behavior Classification v3
* Continuation Pattern Check
* Expansion Pattern Check
* Opportunity Watch
* Alert Eligibility
* Notification Status
* Deterministic Market Summary

---

## Future Scanner Capabilities

Historical roadmap note:

The Liquidity Draw Engine, Behavior Classification Engine, Alert Eligibility Engine, Continuation Pattern Detection, and Expansion Detection have been implemented. Future scanner work now focuses on hardening, clearer frontend visibility, better bearish parity, stronger news handling, and execution confirmation.

Remaining future scanner capabilities:

* Execution Confirmation Layer
* More robust Automated Opportunity Detection
* Enhanced News Integration
* Rich scan-history analytics
* Frontend notification controls
* Stronger 1M confirmation workflows

---

## Supported Symbols

* MES
* ES
* MNQ
* NQ

---

# Communication Layer

## Current

* Dashboard
* iMessage
* Text-to-Speech
* Manual notification test endpoints
* Masked notification config endpoint
* Smart scan notification delivery when explicitly enabled

## Future

* Voice activation
* Mobile notifications
* Conversational voice mode

---

# Orbit Vision

Orbit is a planning and execution platform powered by Helix.

Orbit is not another AI.

Orbit stores structured data and allows Helix to manage daily execution.

---

# Major Events System

Major Events represent significant life objectives.

Examples:

* Corporate Escape
* Trading Capital Goals
* Business Launches
* Boxing Milestones
* Travel Goals

Each Major Event contains:

* Title
* Target Date
* Countdown
* Progress
* Milestones
* Metrics
* Status

---

## Current Major Event

### Corporate Escape

Objective:

Leave corporate employment and replace income through trading, business, and other ventures.

Target Date:

2027-02-28

Orbit tracks:

* Progress percentage
* Milestones
* Tasks
* Reviews
* Readiness score
* Capital accumulation progress

---

# Orbit Architecture

## Major Events

Top-level objectives.

Current Example:

* Corporate Escape

---

## Milestones

Current Examples:

* Define income replacement target
* Build trading review cadence
* Create business launch plan
* Set capital accumulation checkpoints

---

## Goals

Planning containers.

Current:

* Inbox Goal

---

## Tasks

Capabilities:

* Create tasks
* Complete tasks
* Store completion timestamps
* Daily planning integration

---

## Reviews

Supported:

* Daily
* Weekly
* Monthly

Capabilities:

* Save reviews
* Display reviews
* Feed planning recommendations
* Feed future readiness systems

---

## Readiness System

Purpose:

Measure actual readiness for major life objectives.

Current Categories:

* Financial
* Trading
* Business
* Personal

Current State:

Manual updates with Helix assistance.

Future State:

Evidence-based readiness scoring.

---

# Trade Journal

Purpose:

Capture trading performance and generate readiness evidence.

Current Capabilities:

* Trade session logging
* PnL tracking
* Rule adherence tracking
* Confidence tracking
* Session grading
* Notes and lessons

Future Capabilities:

* Screenshot linking
* Setup tagging
* Mistake tracking
* Performance analytics
* Readiness evidence generation

---

# Orbit Dashboard

Current Sections:

* Major Event Countdown
* Readiness Tracking
* Inbox Tasks
* Milestones
* Reviews
* Blockers
* Weekly Focus

---

# Helix Orbit Tools

## Read Tools

* get_orbit_major_events
* get_orbit_milestones
* get_orbit_goals
* get_orbit_tasks
* get_orbit_reviews
* get_corporate_escape_status
* get_corporate_escape_readiness
* get_trade_sessions

## Write Tools

* create_orbit_task
* create_orbit_goal
* complete_orbit_task
* create_orbit_review
* create_trade_session
* update_orbit_milestone_progress
* update_orbit_major_event_progress
* update_readiness_category

## Planning Tools

* generate_orbit_daily_summary
* generate_orbit_focus
* suggest_trading_readiness_update

---

# Planned Agents

Agents are specialized workers operating under Helix.

Helix decides when to use agents.

Users interact only with Helix.

Examples:

* Planning Agent
* Reminder Agent
* Trading Agent
* Reflection Agent
* Research Agent

---

# Development Roadmap

## Current Focus

Trading Intelligence

Priority Order:

1. Scanner status and frontend visibility
2. Opportunity Recognition Refinement
3. Execution Confirmation Layer
4. Enhanced News Integration
5. Trade Journal analytics and Orbit readiness evidence
6. Notification controls and observability

Completed from earlier roadmap:

* Liquidity Draw Engine
* Behavior Classification Engine / Behavior Classification v3
* Alert Eligibility Engine
* Continuation Pattern Detection
* Expansion Detection

---

## Orbit Roadmap

Future:

* Planning Agent
* Reflection Agent
* Voice-first planning
* Ascend integration
* Achievement systems
* Skill progression systems

---

# Guidance For Coding Agents

Before implementing features:

1. Read this file completely.
2. Preserve Helix as the single AI assistant.
3. Follow existing architecture patterns.
4. Avoid introducing duplicate systems.
5. Prefer extending existing modules over creating parallel systems.
6. Keep trading logic isolated from Orbit planning logic.
7. Maintain separation between:

   * Helix (brain)
   * Orbit (planner)
   * Agents (workers)

When unsure:

Ask for clarification rather than making architectural decisions.
