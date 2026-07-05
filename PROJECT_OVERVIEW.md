# Helix / Orbit Project Overview

Last refreshed: July 5, 2026

This document is the source of truth for the current Helix/Orbit implementation. It reflects an audit of the backend, frontend, Orbit services, scanner, CSV refresh, Trade Journal, tests, and local service scripts.

Helix is Jadin's local-first assistant and operating layer. It combines a FastAPI chat assistant, Command Center, Orbit life operating system, schedule platform, Trade Journal, TradingView scanner, CSV refresh automation, local model/vision workflows, iMessage bridge, TTS, and macOS LaunchAgent service support.

Helix remains the single assistant. Orbit stores durable planning data. Scanner and trading subsystems provide market context without owning life-planning state.

## Current Product Direction: Mobile-First Helix

Helix is shifting from a desktop-first command center into a mobile-first daily assistant. The existing web/desktop routes remain the admin portal for deep work, debugging, scanner review, Trade Journal analysis, and Orbit management. The mobile layer should focus on quick daily use: briefing, chat, schedule, reminders, trading snapshot, journal quick capture, and notifications.

Mac mini remains the local backend and automation host. iPhone becomes the primary daily interface.

Strategy Teaching Overhaul is paused for now. The current product priority is validating a phone-first assistant experience through the existing Next.js/FastAPI stack before deciding whether a private native iOS app is worth building.

### Desktop vs Mobile Responsibilities

Desktop/admin portal:

* Command Center full scanner controls.
* Full Orbit board.
* Full Schedule editor.
* Full Trade Journal import, review, and coaching workflows.
* Scanner diagnostics.
* CSV, vision, and debug panels.
* System and admin settings.

Mobile daily assistant:

* Morning Briefing.
* Ask Helix.
* Quick actions.
* Today's schedule.
* Reminders.
* Add task.
* Add schedule block.
* Trading snapshot.
* Profit Calendar summary.
* Latest scanner review/status.
* Quick journal/trade note.
* Notification center.

### Mobile MVP Plan

Mobile bottom navigation:

* Home.
* Chat.
* Schedule.
* Trading.
* Journal.

Home should include:

* Morning Briefing card.
* Top priority task.
* Next schedule block.
* Today reminders.
* Trading performance snapshot.
* Scanner status.
* Quick actions.

Chat should include:

* Simple assistant thread.
* Natural command confirmations.
* Image upload later.
* Voice later.

Schedule should include:

* Today list.
* This week compact list.
* Add flexible block.
* Suggested slots.
* Complete/edit reminders.

Trading should include:

* PnL snapshot.
* Latest scanner review.
* Scanner On/Off.
* Manual scan.
* Capital checkpoint snapshot later.

Journal should include:

* Quick log.
* Recent entries.
* Profit Calendar summary.
* Full import/review stays desktop for now.

### PWA Foundation Audit

Current frontend readiness:

* `frontend/app/layout.tsx` still has default Create Next App metadata.
* `frontend/next.config.ts` only configures `allowedDevOrigins`.
* Global CSS includes useful mobile safety basics: `overflow-x: hidden`, `box-sizing: border-box`, `min-width: 0`, and `touch-action: manipulation`.
* There is no dedicated mobile shell route yet.

Missing for iPhone Home Screen/PWA readiness:

* Web app manifest.
* App icons and Apple touch icon.
* Apple mobile web app metadata.
* Theme color and viewport/safe-area polish.
* Service worker/offline strategy.
* Web push foundation.
* Authentication/security model for mobile access.

### Backend Mobile API Plan

The current backend exposes the needed raw material through existing chat, Orbit, scanner, schedule, and Trade Journal endpoints. A phone interface should add a narrow mobile composition layer so the mobile UI can ask for daily assistant state directly instead of loading desktop-sized bundles.

Potential endpoints:

* `GET /mobile/home`
* `GET /mobile/schedule/today`
* `GET /mobile/trading/summary`
* `GET /mobile/scanner/status`
* `POST /mobile/quick-action`
* `GET /mobile/notifications`
* `POST /mobile/notifications/{id}/ack`

Do not expose Helix beyond trusted local access without authentication.

### Connectivity And Security Notes

Open decisions:

* iPhone connection method: LAN, VPN, or secure tunnel to the Mac mini.
* Authentication is required before exposing Helix beyond the local LAN.
* PWA/mobile web should be the first validation layer.
* Native iOS/TestFlight/private install can come later after mobile workflows are proven.
* Push notifications, reminders, badges, and notification acknowledgement need a dedicated design.
* Avoid exposing the local assistant publicly without auth, rate limits, and transport security.

## Current Status

### Complete / Usable

* FastAPI backend with `/chat`, `/chat/stream`, history, tool logs, scanner routes, CSV refresh routes, Orbit routes, agent routes, notification tests, TTS routes, and vision evaluation.
* Deterministic Command Router before local model fallback for common Orbit, readiness, presence, morning, schedule, trading coach, scanner correlation, pattern discovery, and strategy-profile requests.
* Response-quality guardrails that prevent incomplete one-word or dangling local-model fragments such as `Based`, retry once with a repair prompt, then use a deterministic fallback.
* Command Center with chat/history, image upload, scanner controls, scanner status, manual scan, default symbol selection, scanner On/Off toggle, presence mode controls, iMessage/TTS status display, latest scan summaries, and frontend incomplete-fragment safety.
* Orbit Operating Board with Major Events, milestones, goals, tasks, inbox workflows, recommendations, strategic gaps, readiness, reviews, Morning Briefing, scheduled-agent status, Morning Check-In status, Schedule/Calendar/Blocks, and manual agent runs.
* Orbit Schedule with fixed and flexible blocks, finite recurrence, preferred days, same-time and per-day multi-day fixed edits, flexible suggested placement, Calendar day rendering, grouped Blocks view, active/archive state, duplicate cleanup, and natural-language schedule command creation.
* Trade Journal with manual entry, PDF import preview/save, entry CRUD, Trading Coach, scanner match/correlation, pattern discovery, Profit Calendar, calendar-only import, and separation between strategy journal trades and raw performance/calendar-only records.
* Morning Briefing with Orbit tasks/readiness plus 30-day trading performance context from the Trade Journal Profit Calendar summary.
* Scanner HTF CSV plus LTF vision architecture: `1D`, `4H`, `1H` CSV provide structural context; `15M` and `5M` screenshots provide live visual context; `1M` is conditional execution context only.
* Scanner state includes narrative state, alert eligibility, market alert state, system health state, presence gating, repeat suppression, confidence caps, screenshot cleanup, screenshot recovery, TradingView profile lock handling, and `current_attempt_valid_market_state`.
* Scanner On/Off setting is the shared automation gate for scheduled chart scans and scheduled CSV refresh. The setting is stored as `scanner_enabled`; manual scan, manual CSV refresh, and vision evaluation remain available.
* CSV refresh has scheduled and forced modes, validates replacement CSVs before active file replacement, preserves last success details on skipped/failed runs, and reports paused/skipped status when scanner automation is disabled.
* Vision evaluation supports `VISION_MODEL`, `VISION_MODEL_CANDIDATES`, model-aware Ollama transport, Qwen3-VL JSON prompts, qwen2.5vl compatibility, JSON repair fallback, and quality statuses: `usable`, `degraded`, `unreliable`.
* macOS LaunchAgent scripts exist for backend, frontend, scheduled agents, iMessage bridge, scanner, and CSV refresh.

### Partially Complete / Needs Validation

* Scanner vision scoring and narrative classification are usable for review/watch context but need repeated live-session validation against real charts.
* Qwen3-VL support exists, but JSON repair may still be required and model quality should continue to be tested across market conditions.
* Stale CSV guardrails exist conceptually and in tests, but full backend test discovery currently shows unrelated scanner/test drift in this area.
* Orbit readiness is functional but still partly checklist-like. Financial and Trading readiness need deeper data-driven scoring from account cushion, realized payouts, consistency, reviews, task progress, and strategy compliance.
* Trade Journal Profit Calendar tracks raw performance and calendar-only imports, but account equity/cushion and prop-firm/account-specific checkpoints are not yet first-class.
* Schedule Intelligence can summarize windows, overload, and placement candidates, but conflict detection and smarter recurring flexible placement should be validated over real weeks.
* iMessage and TTS are implemented but local-permission gated and intentionally conservative. They are not treated as cloud-grade production messaging.

### Stubbed / Placeholder

* `/ascend` exists as a future-facing surface.
* Voice Trigger and Wake Listener are manual prototypes, not always-on installed services.
* Strategy Teaching Overhaul is paused and intentionally not implemented yet.

### Not Started

* Dedicated strategy ontology, screenshot annotation dataset, golden setup library, bad-example library, session playbooks, and formal user-correction feedback loop.
* Account-equity/capital-cushion dashboard with prop-firm account-specific checkpoints.
* Full strategy-learning pipeline that trains/evaluates Helix against labeled screenshots and journaled trades.
* Mobile-first Helix shell and narrow mobile API facade.

### Deprecated / Remove Later

* Older scanner wording that implies autonomous trade signals should be cleaned up if found. The scanner should remain review/watch/context only.
* Runtime/generated files, old `.env.bak` files, lock files, logs, screenshots, and generated caches should stay ignored or be cleaned up where appropriate.

## Completed Recently

* Response-quality guardrails prevent incomplete one-word fragments like `Based`.
* Command Center can route simple schedule requests into Orbit Schedule, for example "Can you add 30 minutes of reading to my schedule?"
* Orbit Schedule supports fixed/flexible blocks, finite recurrence, multi-day flexible preferences, grouped block display, Calendar day rendering, and multi-day edit updates.
* Trade Journal Profit Calendar aggregates daily PnL, win/loss counts, trade counts, symbols, and source splits.
* Calendar-only trading performance import exists and is separated from strategy coaching/scanner-matching data unless promoted later.
* Morning Briefing can include trading performance data for readiness context.
* Scanner now uses HTF CSV for structural map and `15M`/`5M` vision for live context.
* `1M` scanner view is conditional only.
* Scanner separates market alert state from system health.
* Scanner On/Off pauses scheduled CSV refresh too.
* TradingView profile lock prevents overlapping scanner/CSV automation from corrupting the browser profile.
* Qwen3-VL vision evaluation path exists with JSON repair and scoring.
* Screenshot fallback can recover saved screenshots when capture return plumbing is missing.
* Command Center scanner card separates service running, automation paused, running scan, CSV automation, heartbeat, last scan, and interval state.

## Architecture

### Backend

Technology:

* FastAPI
* SQLite
* Python
* Ollama local text and vision models
* macOS `say`, Messages/AppleScript, and LaunchAgents for local service glue

Primary modules:

* `backend/main.py`: FastAPI app, `/chat`, `/chat/stream`, deterministic Command Router entry point, scanner endpoints, CSV refresh endpoints, image analysis, vision evaluation, TTS, notification tests, history, and tool logs.
* `backend/chat_intents.py`: deterministic Command Center routing before LLM fallback, including schedule-management intent creation.
* `backend/database.py`: chat message and tool-log SQLite tables.
* `backend/response_quality.py`: incomplete-response detection, repair prompt construction, fallback text.
* `backend/tools.py`: local model calls, tool layer, TradingView helpers, CSV analysis, vision extraction, JSON repair, market narration, and Orbit tool adapters.
* `backend/presence.py`: local Presence Modes for home, trading, away, and focus.
* `backend/scanner_settings.py`: scanner default symbol and `scanner_enabled` setting.
* `backend/scheduled_scan.py`: scheduled scanner loop, scanner state, HTF/LTF orchestration, screenshot handling, system health, market alerts, presence gating, notifications, and runtime status.
* `backend/csv_refresh.py`: scheduled/manual CSV refresh, replacement verification, status persistence, scanner-enabled automation gate.
* `backend/tradingview_profile_lock.py`: cross-process lock around TradingView browser profile automation.
* `backend/orbit/database.py`: Orbit schema and migrations-on-init.
* `backend/orbit/models.py`: Pydantic models for Orbit, schedule, Trade Journal, Profit Calendar, imports, readiness, and agents.
* `backend/orbit/service.py`: Orbit data access, schedule intelligence, recommendations, readiness, Morning Briefing, daily closeout, Trade Journal CRUD/import/performance calendar, and progress history.
* `backend/orbit/routes.py`: Orbit API surface.
* `backend/orbit/trade_journal_import.py`: deterministic parser/enricher for Performance PDFs and Orders PDFs, including calendar-only save flow.
* `backend/trading_coach.py`: read-only journal review and strategy-context coaching.
* `backend/trading_correlation.py`: scanner-to-journal matching.
* `backend/pattern_discovery.py`: early pattern discovery from saved trades and scanner matches.
* `backend/agent_service.py`, `backend/agent_routes.py`, `backend/scheduled_agents.py`: agent definitions, runs, prioritization, scheduled Morning/Evening workflows.
* `backend/morning_checkin.py`: Morning Check-In acknowledgement, Morning Review reuse/creation, fallback state, and iMessage fallback delivery.
* `backend/imessage_bridge.py`: local iMessage polling bridge.
* `backend/tts.py`: speech formatting and macOS TTS dispatch.
* `backend/voice_trigger.py`, `backend/wake_listener.py`: manual voice prototypes.

### Frontend

Technology:

* Next.js app router
* React client/server components
* Tailwind CSS

Primary surfaces:

* `/`: Core home/navigation surface.
* `/command-center`: chat, scanner, presence, history, image upload, manual scan, scanner toggle, status cards.
* `/orbit`: Orbit Operating Board, Schedule/Calendar/Blocks, agents, Morning Check-In, readiness, recommendations.
* `/trade-journal`: Trade Journal home/import/manual/entries/coach/scanner match/patterns/Profit Calendar.
* `/orbit/trade-journal`: Orbit-linked Trade Journal route.
* `/ascend`: future placeholder.

### Local Models

* Text model defaults to `OLLAMA_MODEL`, currently falling back to `qwen3.5:9b` if unset.
* Vision model defaults to `VISION_MODEL`, currently falling back to `qwen2.5vl:7b` if unset.
* `VISION_MODEL_CANDIDATES` can provide a comma-separated bakeoff list.
* Qwen3-VL uses model-aware `/api/chat` preference and stricter JSON-only prompts.
* qwen2.5vl compatibility remains through the older generate/chat fallback path.

### Data Storage

* `backend/assistant.db`: chat/tool logs plus Orbit tables.
* Orbit tables: major events, milestones, goals, tasks, task-milestone links, progress history, reviews, readiness categories, schedule blocks, trade sessions, trade journal, agent definitions/runs, recommendations/strategic gaps as implemented.
* `backend/scan_history.jsonl`: scanner records.
* `backend/scan_runtime_status.json`: scanner heartbeat/runtime state.
* `backend/scanner_settings.json`: default scanner symbol and `scanner_enabled`.
* `backend/csv_refresh_status.json`: CSV refresh status, last attempt, last success, skipped/paused state.
* `backend/csv_data/`: active TradingView CSV files.
* `backend/pictures/tradingview_screenshots/`: scanner and evaluation screenshots.
* `backend/presence_status.json`: current Presence Mode.
* `backend/.scheduled_agents_status.json`: scheduled-agent state.
* `backend/.morning_checkin_status.json`: Morning Check-In/fallback state.
* `.env`, `backend/.env`, `frontend/.env.local`: local configuration. These should remain local and reviewed for repo hygiene.

### Services

LaunchAgent support lives in `scripts/` and `docs/MAC_SERVICES.md`.

Managed services:

* `com.helix.backend`: `scripts/start_backend.sh`, FastAPI on `0.0.0.0:8000`.
* `com.helix.frontend`: `scripts/start_frontend.sh`, Next.js on port `3000`.
* `com.helix.scheduled-agents`: `scripts/start_scheduled_agents.sh`.
* `com.helix.imessage-bridge`: `scripts/start_imessage_bridge.sh`.
* `com.helix.scanner`: `scripts/start_scanner.sh`.
* `com.helix.csv-refresh`: `scripts/start_csv_refresh.sh`.

Common service commands:

* `scripts/install_mac_services.sh core`
* `scripts/install_mac_services.sh all`
* `scripts/status_mac_services.sh`
* `scripts/status_mac_services.sh restart`
* `scripts/uninstall_mac_services.sh`

## Core Systems

### Command Center

Status: Complete / usable, with ongoing UI polish.

Implemented:

* Chat against `/chat`, including tool modes for market CSV, CSV refresh, TradingView analysis, and auto mode.
* Streaming endpoint exists at `/chat/stream`.
* History reset and recent message display.
* Image/chart upload via `/analyze-image`.
* Deterministic intent routing before local model fallback.
* Natural language schedule command routing into Orbit Schedule.
* Frontend fragment fallback handling in addition to backend response-quality guardrails.
* Presence Mode display and controls for home/trading/away/focus.
* Scanner card with default symbol selection, manual scan, latest scan, service status, automation status, running scan, CSV automation status, heartbeat age, last scan, interval, HTF source, live vision timeframes, and conditional `1M`.
* iMessage/TTS status display from Presence Mode and notification config.

Partial / needs validation:

* Command Center does not yet expose every CSV refresh detail as a dedicated panel; CSV automation state is surfaced through scanner status.
* Streaming chat path is simpler than non-streaming and should be validated if it becomes a primary UI route.

### Orbit Operating Board

Status: Complete / usable.

Implemented:

* Overview/workflows.
* Major Events, including Corporate Escape status/progress.
* Milestones and goals.
* Inbox tasks, task creation/editing/completion, due dates, and task-milestone links.
* Strategic gaps and recommendations.
* Readiness categories with manual update APIs.
* Reviews, Morning Briefing, Daily Closeout.
* Agent status, scheduled-agent status, prioritization, and manual runs.
* Current blocker logic in briefing/recommendations based on overdue/stalled tasks, readiness, recent reviews, and trading performance.

Partial / needs validation:

* Readiness scoring is still partly manual/static and should become more data-driven.
* Business readiness needs more concrete workflows and metrics.

### Orbit Schedule

Status: Complete / usable, needs real-week validation.

Implemented:

* Fixed and flexible schedule blocks.
* Categories, priorities, notes, active/archive state.
* Day-of-week and specific-date anchors.
* Duration-based flexible blocks.
* `whenever_free` and `preferred_day` flexible placement modes.
* Preferred days for flexible blocks.
* Recurrence: once, daily, weekly/every-other-week style support, plus finite end modes by date, occurrence count, or weeks.
* Multi-day fixed edits with same-time or per-day times.
* Duplicate-aware schedule block creation/update.
* Flexible placement suggestions from available windows and `/schedule-blocks/{id}/place`.
* Schedule Intelligence: week summaries, overload/underutilized days, available windows, placement candidates, recommendations.
* Calendar day-level rendering and grouped Blocks tab pattern display.
* Natural language schedule commands such as "Add 30 minutes of reading to my schedule" create flexible Orbit blocks without invoking the local model.

Partial / needs validation:

* Continue real-week testing for Calendar rendering and recurrence edge cases.
* Conflict detection and smarter placement intelligence are future improvements.
* Recurring flexible placement could become more sophisticated.

### Trade Journal

Status: Complete / usable, with financial-readiness expansion still needed.

Implemented:

* Trade Journal home, import, manual entry, entries/detail/edit/delete, coach, scanner match, patterns, Profit Calendar.
* PDF import preview from Performance PDFs and Orders PDFs.
* Save selected import drafts as journal entries.
* Calendar-only trading performance import from Performance PDF data.
* `entry_type`: `journal` vs `calendar_only`.
* `include_in_performance_calendar` separates raw performance tracking from strategy coaching datasets.
* Profit Calendar aggregates daily PnL, trade counts, win/loss counts, best/worst days, symbols, and source splits.
* Calendar-only records are intentionally excluded from coaching, scanner correlation, and pattern discovery unless promoted later.
* Trading Coach reviews saved strategy journal entries.
* Scanner Match and Pattern Discovery are read-only/recommendation surfaces.
* Morning Briefing uses 30-day performance summary for readiness/blocker context.

Partial / needs validation:

* Account equity, account cushion, payout status, and prop-firm account-specific tracking are not yet first-class.
* Need labels to distinguish true strategy trades from eval/random trades beyond calendar-only performance rows.

### Scanner

Status: Partially complete / needs live validation.

Implemented:

* Configured-symbol scanner for MES/MNQ/ES/NQ.
* Default symbol stored in scanner settings.
* `scanner_enabled` controls scheduled chart scans and scheduled CSV refresh.
* Manual `POST /scan/force` still works when scanner automation is off.
* HTF CSV timeframes: `1D`, `4H`, `1H`.
* Scheduled live vision timeframes: `15M`, `5M`.
* Conditional execution context: `1M` only when scanner enters execution-watch conditions.
* HTF CSV is structural map; LTF screenshots are live visible context.
* CSV freshness/staleness limitations are attached to scanner context and narration.
* Screenshot cleanup before new scans.
* Screenshot recovery when capture return data is missing but a recent saved screenshot exists.
* TradingView profile lock prevents overlapping scanner/CSV browser automation.
* Narrative state, liquidity draw, reaction zone, behavior classification, opportunity watch, and alert eligibility.
* Market alert state is separate from system health.
* System health can be healthy/degraded/failed and includes recovered issues.
* Presence gating controls notification eligibility after scanner alert eligibility.
* `current_attempt_valid_market_state` distinguishes usable market reads from failed system attempts.

Partial / needs validation:

* Scanner should remain review/watch/context only, not autonomous trade signal generation.
* Need repeated checks that scanner narrative matches actual chart behavior.
* Reaction-zone extraction and behavior classification need more live validation.
* Stale CSV guardrail behavior should continue to be tested against live/realistic cases.

### Vision Evaluation

Status: Complete / usable for bakeoffs, needs model validation.

Implemented:

* `POST /vision/evaluate-chart`.
* `VISION_MODEL` and `VISION_MODEL_CANDIDATES`.
* Model-aware Ollama transport for qwen2.5vl and Qwen3-VL families.
* JSON-only extraction prompts.
* Qwen3-VL-specific JSON prompt path.
* JSON parsing from model output.
* JSON repair fallback through text model.
* Normalized visual extraction schema.
* Quality scoring with `usable`, `degraded`, and `unreliable`.
* Debug payloads with raw response, parse strategy, repair status, strengths, issues, and score.

Partial / needs validation:

* Qwen3-VL may still require JSON repair.
* Scoring thresholds are useful but should be calibrated over more screenshots.
* Chart-marking extraction quality must be validated before raising trust in scanner conclusions.

### CSV Refresh

Status: Complete / usable, with TradingView automation brittleness noted.

Implemented:

* Scheduled refresh cadence anchored around the session reset hour.
* Due timeframes currently focus on HTF scheduled refresh: session reset `1D`/`4H`/`1H`, recurring `4H`, and `1H` windows.
* Forced/manual CSV refresh route at `POST /csv-refresh/force`.
* Status route at `GET /csv-refresh/status`.
* Safe replacement: export to temp directory, verify required CSV columns, then replace active files.
* Last success fields are preserved across failures/skips.
* Scheduled CSV refresh checks `scanner_enabled` before refresh windows, profile lock, TradingView, or export work.
* Scanner-off CSV skip records `last_attempt_result: skipped`, `last_attempt_reason: scanner_disabled`, and message/logs indicating automation is disabled.

Partial / needs validation:

* TradingView export automation can fail if the UI changes, profile lock is busy, downloads fail, or browser permissions shift.
* Manual file export into `backend/csv_data` remains a fallback.
* Lower timeframe CSV refresh is not the source of truth for scheduled scanner logic; LTF live context is visual.

### iMessage / TTS

Status: Partially complete / locally gated.

Implemented:

* TTS routes: `/tts/voices`, `/tts/config`, `/tts/say`, `/notify/test-tts`.
* Speech formatting removes markdown/code/URLs and normalizes text for macOS `say`.
* Notification test routes exist for iMessage, TTS, and combined notification.
* Scanner notifications can dispatch through iMessage/TTS when explicitly enabled and allowed by Presence Mode.
* Morning fallback delivery can use iMessage after the configured cutoff.
* iMessage bridge polls local Messages database read-only and sends through AppleScript/Messages.

Partial / needs validation:

* iMessage requires macOS permissions, allowed sender/recipient configuration, and Messages availability.
* TTS requires local voice availability and environment configuration.
* Voice Trigger and Wake Listener are manual prototypes, not production always-on voice systems.

## Current Workflows

### Morning Briefing

Flow:

1. User triggers Morning Check-In, scheduled Morning Review, or Command Center morning intent.
2. Orbit loads active major events, tasks, milestones, readiness categories, reviews, blockers, and Trade Journal performance summary.
3. Morning Briefing formats a compact focus summary.
4. Trading performance contributes 30-day PnL, trade count, winning/losing days, and latest trade date.
5. If no check-in is acknowledged by cutoff, Morning fallback can deliver through iMessage when configured.

Status: Complete / usable. Trading performance integration is present; readiness logic still needs deeper data-driven scoring.

### Schedule Command Flow

Flow:

1. `/chat` saves the user message.
2. `route_chat_intent` runs before local model fallback.
3. Schedule-management detector looks for action verbs, duration, schedule/calendar/free-time context, days, and activity.
4. Simple requests default to flexible, once, medium priority, Personal category, `whenever_free`, `anytime`.
5. Orbit creates a `ScheduleBlockCreate` through the existing schedule service.
6. Exact duplicate blocks are not duplicated.
7. The assistant returns a deterministic confirmation and does not run the local model.

Status: Complete / usable for simple flexible schedule requests. Complex natural language scheduling remains intentionally simple.

### Trading Scanner Flow

Flow:

1. Scheduled scanner loop checks `scanner_enabled` and active session windows.
2. Manual scan bypasses automation-off gate.
3. Screenshot cleanup runs.
4. HTF CSV analysis provides structural map.
5. `15M` and `5M` screenshots provide live visual context.
6. Conditional `1M` screenshot may be captured only for execution-watch context.
7. Vision extraction returns normalized JSON, possibly repaired.
8. Scanner attaches narrative state, behavior classification, opportunity watch, alert eligibility, system health, market alert, presence gating, and notification status.
9. Record is written to `scan_history.jsonl`; runtime status is updated.

Status: Partially complete / needs live validation. Use as review/watch context only.

### Trade Journal / Profit Calendar Flow

Flow:

1. User creates manual journal entries or imports PDFs.
2. Performance PDF and Orders PDF parser creates draft trades and/or daily summary data.
3. Selected drafts save as strategy journal entries.
4. Calendar-only performance import saves raw daily/trade performance rows with `entry_type: calendar_only`.
5. Profit Calendar aggregates included entries by day/month/source.
6. Coaching, scanner match, and pattern discovery use strategy journal entries, not calendar-only eval/random performance rows by default.
7. Morning Briefing reads performance summary for readiness context.

Status: Complete / usable for journal and raw performance tracking. Capital/account dashboards remain future work.

## Known Limitations

### Trading Strategy Teaching Overhaul Paused

* Helix does not yet have a redesigned system for learning Jadin's real trading strategy.
* This work is paused while the product direction shifts to Mobile-First Helix.
* Need a strategy ontology for liquidity draws, reaction zones, confirmations, entry models, invalidations, and no-trade conditions.
* Need annotated screenshots.
* Need golden setup examples and bad examples.
* Need session playbooks for Asia, London, New York, after-hours, news days, and eval constraints.
* Need feedback loop from user corrections.
* Need trade journal integration into strategy learning.
* Need labels separating eval/random trades from true strategy trades.

### Scanner Validation

* Vision scoring is improving but must be validated over real sessions.
* Qwen3-VL may still need JSON repair.
* Scanner should remain review/watch, not autonomous trade signal.
* Need repeated checks that narrative matches chart.
* Need stronger reaction-zone extraction and behavior classification validation.
* Stale CSV guardrail tests currently show drift in full discovery and should be revisited.

### Trade Journal / Financial Readiness

* Profit Calendar exists, but account equity/cushion tracking is still needed.
* Need target/checkpoint progress based on account balances, realized payout, cushion, drawdown, and consistency data.
* Need better capital checkpoint dashboard.
* Need possible Apex/prop-firm account-specific tracking.

### Orbit Readiness

* Readiness scoring should continue moving from static checklist to data-driven metrics.
* Financial/Trading readiness should use real PnL, consistency, account cushion, reviews, and task progress.
* Business readiness still needs more concrete workflows.

### Schedule

* Continue real-week testing.
* Need stronger conflict detection.
* Need smarter placement intelligence.
* Need recurring flexible placement improvements.

### iMessage / Voice / TTS

* Current state is local and gated by macOS permissions.
* Voice Trigger and Wake Listener are prototypes.
* TTS is useful but not a full voice assistant runtime.
* iMessage bridge should remain conservative and allowlisted.

### Cleanup / Repo Hygiene

* Check untracked `.env`, `.env.bak`, lock files, generated files, logs, screenshots, and caches.
* Make sure runtime files are ignored.
* Identify old/deprecated scanner wording or dead code.
* Full backend test discovery can be blocked by optional local dependencies or unrelated local test drift; run focused tests when needed.

## Next Work

Recommended next priorities:

1. Build mobile shell / mobile home route.
2. Create mobile home briefing endpoint or compose from existing APIs.
3. Add mobile bottom navigation.
4. Build mobile Chat command surface.
5. Build mobile Schedule/today view.
6. Build mobile Trading snapshot.
7. Build notification/reminder architecture.
8. Decide PWA vs private native iOS after mobile workflow validation.

## Paused Design: Trading Strategy Teaching Overhaul

This is intentionally not implemented yet and is not the current priority.

The user may later overhaul how Helix learns the strategy before continuing major scanner expansion. The future system should separate:

* Raw trading performance tracking.
* Strategy-compliant trades.
* Eval/random trades.
* Annotated learning examples.
* Scanner-generated observations.
* User corrections.
* Golden setup examples.
* Bad/no-trade examples.
* Session playbooks.

The strategy system should eventually train/evaluate Helix against labeled screenshots and journaled trades. It should make scanner review more grounded without turning Helix into an autonomous signal generator. For now, it remains behind the Mobile-First Helix work.

## Validation / Common Commands

Backend:

```bash
backend/.venv/bin/python -m compileall -q backend
backend/.venv/bin/python -m unittest discover backend/tests
backend/.venv/bin/python -m unittest backend/tests/test_scanner_enabled_setting.py -q
backend/.venv/bin/python -m unittest backend/tests/test_trade_journal_import.py -q
backend/.venv/bin/python -m unittest backend/tests/test_trade_journal_crud_import_save.py -q
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

Diff hygiene:

```bash
git diff --check
grep -n "Mobile-First Helix\|Strategy Teaching Overhaul\|admin portal\|Qwen3-VL\|Profit Calendar\|calendar-only\|scanner_enabled\|current_attempt_valid_market_state" PROJECT_OVERVIEW.md
```

Service status:

```bash
scripts/status_mac_services.sh
scripts/status_mac_services.sh restart
```

Install/uninstall LaunchAgents:

```bash
scripts/install_mac_services.sh core
scripts/install_mac_services.sh all
scripts/uninstall_mac_services.sh
```

Manual API checks:

```bash
curl -s http://127.0.0.1:8000/
curl -s http://127.0.0.1:8000/scan/status
curl -s http://127.0.0.1:8000/csv-refresh/status
curl -s http://127.0.0.1:8000/orbit/morning-briefing
```

## Audit Summary By Area

| Area | Status | Notes |
| --- | --- | --- |
| Core Helix backend | Complete / usable | FastAPI routes, chat, stream, history, tools, response-quality guardrails, deterministic intents. |
| Command Center | Complete / usable | Chat, scanner controls, presence, service vs automation state, manual scan, fragment fallback. |
| Scanner / trading automation | Partially complete / needs validation | Architecture is in place; use as review/watch only. |
| Vision models | Complete / usable for bakeoffs | Qwen3-VL path exists; quality still needs live validation. |
| CSV refresh | Complete / usable | Safe replacement and scanner-enabled automation gate are implemented. |
| Orbit Operating Board | Complete / usable | Readiness needs more data-driven scoring. |
| Orbit Schedule / Calendar | Complete / usable | Continue real-week validation. |
| Trade Journal | Complete / usable | Profit Calendar and calendar-only imports exist; account tracking remains future work. |
| iMessage / TTS | Partially complete / locally gated | Works through local permissions/configuration. |
| Data/storage | Complete / usable | SQLite plus JSON/status/runtime files. |
| Services/local runtime | Complete / usable | LaunchAgent scripts and docs exist. |
| Mobile-first Helix | Not started | Current product direction; mobile shell and narrow mobile API facade are next. |
| Strategy teaching overhaul | Paused | Revisit after mobile workflows are validated. |

## Source-of-Truth Files

* Backend app/routes: `backend/main.py`
* Command routing: `backend/chat_intents.py`
* Tool/model/vision layer: `backend/tools.py`
* Response quality: `backend/response_quality.py`
* Scanner: `backend/scheduled_scan.py`
* Scanner settings: `backend/scanner_settings.py`
* CSV refresh: `backend/csv_refresh.py`
* TradingView profile lock: `backend/tradingview_profile_lock.py`
* Orbit models/service/routes: `backend/orbit/models.py`, `backend/orbit/service.py`, `backend/orbit/routes.py`
* Trade Journal import: `backend/orbit/trade_journal_import.py`
* Command Center UI: `frontend/app/command-center/page.tsx`
* Orbit UI: `frontend/app/orbit/page.tsx`, `frontend/app/orbit/OrbitBoard.tsx`
* Trade Journal UI: `frontend/app/trade-journal/page.tsx`
* Tests: `backend/tests`
* Service docs/scripts: `docs/MAC_SERVICES.md`, `scripts/*.sh`, `scripts/launchagents/*.plist`
