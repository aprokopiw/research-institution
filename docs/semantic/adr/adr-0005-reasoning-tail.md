---
id: ADR-0005
kind: decision
status: superseded
title: Reasoning tail surfaces the worker's chain-of-thought from the Pi session JSONL
date: 2026-09-13
superseded_by: ADR-0006 (research-institution owns no application code)
related:
  - ADR-0006
---

# ADR-0005: Reasoning tail surfaces the worker's chain-of-thought (SUPERSEDED)

## Status

Superseded by `ADR-0006` (research-institution owns no application code).
The reasoning-tail surface belongs to **pi** (which owns the session JSONL
at `~/.pi/agent/sessions/...`), not to research-institution.

The skill wrapper, the helper script, and the operator-UX doc that
referenced this ADR have been removed. The functionality is a candidate
for pi or pi_monitor, not this repo.

## Original decision (kept for the durable record)

The original decision was to add `scripts/kaplansky-reasoning-tail.sh`
that reads mathlint's `executions/<digest>.json` (which carries
`session_file` per attempt) and parses the worker's reasoning blocks
from the Pi session JSONL.

This was incorrect. The reasoning text is owned by pi's session recorder
and the supervisor's activity feed (pi-monitor watch) is the canonical
operator surface for it. Research-institution was duplicating logic
that belongs to pi or pi_monitor.
