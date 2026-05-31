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
