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

CSV market data is the source of truth.

Vision analysis is used only to identify:

* User markings
* Drawn zones
* Labels
* Visual chart context

If CSV and vision disagree:

CSV wins.

### Orbit

Orbit is the source of truth for:

* Tasks
* Goals
* Milestones
* Events
* Reviews
* Progress tracking

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
* API integrations

---

## Frontend

Technology:

* Next.js

Responsibilities:

* Dashboard
* Scan controls
* Status displays
* Orbit views
* Future reporting

---

## Trading System

Features:

* TradingView screenshot capture
* CSV analysis
* FVG detection
* Market structure analysis
* Scheduled scans
* Alert eligibility engine
* Deterministic market summaries

Supported Symbols:

* MES
* ES
* MNQ
* NQ

---

## Communication Layer

Current:

* Dashboard
* iMessage
* Text-to-Speech

Future:

* Voice activation
* Mobile notifications

---

# Orbit Vision

Orbit is a planning and execution platform powered by Helix.

Orbit is NOT another AI.

Orbit stores structured data and allows Helix to manage daily execution.

---

## Orbit Responsibilities

* Tasks
* Goals
* Daily plans
* Weekly reviews
* Reminders
* Milestones
* Major events
* Progress tracking

---

# Major Events System

Major Events represent significant life objectives.

Examples:

* Quit Corporate World
* Reach Trading Capital Target
* Launch Business
* Boxing Milestone
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

Target Timeline:

Approximately 9 months.

Orbit should track:

* Days remaining
* Progress percentage
* Milestone completion
* Trading performance
* Capital accumulation
* Readiness score

---

# Planned Agents

Agents are specialized workers operating under Helix.

Helix decides when to use agents.

Users interact only with Helix.

Examples:

## Planning Agent

Responsibilities:

* Daily plans
* Prioritization
* Scheduling

## Reminder Agent

Responsibilities:

* Reminder creation
* Follow-ups
* Deadlines

## Trading Agent

Responsibilities:

* Scan interpretation
* Alert generation
* Market summaries

## Reflection Agent

Responsibilities:

* Daily reviews
* Weekly reviews
* Lesson extraction

## Research Agent

Responsibilities:

* Information gathering
* Summaries
* Knowledge collection

---

# Development Roadmap

## Helix v1

Completed / In Progress:

* FastAPI backend
* Trading analysis
* Dashboard
* iMessage integration
* TTS
* Scheduled scans

---

## Orbit v1

Planned:

* Major Events
* Milestones
* Goals
* Tasks
* Daily Plans
* Reviews

---

## Orbit v2

Planned:

* Agent integration
* Enhanced dashboards
* Progress tracking
* Trading journal integration

---

## Orbit v3

Planned:

* Life progression system
* Skill trees
* XP
* Milestone verification
* Achievement system

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

## Orbit Module Status (Current)

### Purpose

Orbit is Helix's planning, execution, and reflection system.

Orbit exists to help track major life objectives, break them into milestones and tasks, measure progress, and generate actionable planning guidance.

Current flagship Major Event:

* Corporate Escape
* Target Date: 2027-02-28

---

## Orbit Architecture

### Major Events

Top-level objectives.

Example:

* Corporate Escape

Stored Data:

* title
* description
* target date
* status
* progress percentage

---

### Milestones

Major checkpoints that support a Major Event.

Current Examples:

* Define income replacement target
* Build trading review cadence
* Create business launch plan
* Set capital accumulation checkpoints

---

### Goals

Secondary planning layer.

Currently used primarily as task containers.

Includes:

* Inbox Goal

---

### Tasks

Actionable work items.

Capabilities:

* Create tasks through Helix
* View tasks in Orbit Dashboard
* Complete tasks by title
* Store completion timestamps

Example:

* Review my trading journal tonight

---

### Reviews

Reflection and learning layer.

Supported Types:

* Daily
* Weekly
* Monthly

Capabilities:

* Save reviews through Helix
* View reviews in Orbit Dashboard
* Include reviews in planning summaries

---

## Orbit Dashboard

Current Sections:

* Major Event Countdown
* Progress Tracking
* Inbox Tasks
* Milestones
* Reviews
* Blockers
* Weekly Focus

Data Source:

* Live Orbit API
* SQLite backend

---

## Helix Orbit Tools

Read Tools:

* get_orbit_major_events
* get_orbit_milestones
* get_orbit_goals
* get_orbit_tasks
* get_corporate_escape_status
* get_orbit_reviews

Write Tools:

* create_orbit_task
* create_orbit_goal
* complete_orbit_task
* update_orbit_milestone_progress
* update_orbit_major_event_progress
* create_orbit_review

Planning Tools:

* generate_orbit_daily_summary
* generate_orbit_focus

---

## Current Orbit Workflow

Helix can:

1. Create tasks
2. Complete tasks
3. Update progress
4. Save reviews
5. Generate daily summaries
6. Generate focus recommendations

Example:

"What should I focus on today?"

↓

Helix analyzes:

* Major events
* Open tasks
* Milestones
* Reviews

↓

Returns:

* Highest leverage priority
* Top 3 actions
* Biggest blocker
* Suggested next milestone

---

## Next Development Phase

Priority 1:

* Context-aware planning recommendations

Priority 2:

* Trading Journal integration

Priority 3:

* Planning Agent

Future:

* Ascend
* Reflection Agent
* Voice-first planning
* Helix Avatar / Core Interface

