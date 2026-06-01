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
* Bias determination
* Opportunity Watch generation
* News Risk analysis

### Capture

* TradingView screenshot capture
* Forced 15M scans
* Multi-timeframe capture

  * 4H
  * 1H
  * 15M

### Safety

* CSV freshness awareness
* Source-of-truth enforcement
* Scan status monitoring

### Current Outputs

* Market State
* News Risk
* Data Freshness
* Opportunity Watch
* Deterministic Market Summary

---

## Future Scanner Capabilities

* Liquidity Draw Engine
* Behavior Classification Engine
* Alert Eligibility Engine
* Execution Confirmation Layer
* Automated Opportunity Detection
* Enhanced News Integration

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

1. Liquidity Draw Engine
2. Behavior Classification Engine
3. Opportunity Recognition Refinement
4. Alert Eligibility Engine
5. Execution Confirmation Layer

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
