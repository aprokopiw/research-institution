---
id: ADR-0003
kind: decision
status: accepted
title: Kaplansky uses slow-iteration safeguards — token cap, attempt cap, shadow-mode by default
date: 2026-09-13
related:
  - docs/operations/kaplansky-operator-ux.md
  - ~/.config/mathlint/local-pi-monitor.toml
  - ADR-0001
supersedes: []
---

# ADR-0003: Kaplansky uses slow-iteration safeguards — token cap, attempt cap, shadow-mode by default

## Context

The first live launch (`@start_kaplansky`) ran `openai-codex/gpt-5.6-luna` with `thinking = "medium"`, `[efficiency].shadow_mode = false`, and no `[budgets]` configured. The worker ran 187 dispatch attempts in roughly seven minutes before the operator stopped it. Every attempt was a full LLM call; many were `blocked/stalled` because the worker escalates architecture-review decisions to the operator instead of making them itself.

The operator wants:

- **Slow iteration** — few dispatches per session, each one deliberate.
- **Better observability** — one-glance view of what the run is doing.
- **Better traceability** — every action attributable to a budget, scope, and correlation id.
- **Safeguards against LLM spam** — hard caps that the worker cannot bypass.

The operator is on OAuth / flat-rate plans, not per-token billing. Cost is therefore not the binding constraint; LLM-call count and total context growth are.

## Decision

The kaplansky operator config (`~/.config/mathlint/local-pi-monitor.toml`) is locked to a slow-iteration profile:

- `[worker].thinking = "medium"` (kept — the operator wants deep thought per call).
- `[efficiency].shadow_mode = false` — **REQUIRED** by math-engine's
  `@TOOL003` invariant (see `math/src/mathlint/local_readiness/system.py:306`).
  Live preflight aborts the launch if `shadow_mode` is not explicitly `false`.
  The safeguard that *would* have come from `shadow_mode = true` (audit-only,
  no autonomous recovery) is instead delivered by the `[budgets]` global caps
  and the slow `[recovery]` cooldowns below. See "Alternatives considered" for
  the rejected proposal.
- `[efficiency].stats_poll_seconds = 120` (was 60).
- `[efficiency].min_seconds_between_boundary_steers = 1800` (was 900).
- `[efficiency].min_turns_between_manual_compactions = 8` (was 3).
- `[recovery].cooldown_seconds = 900` (was 120) — 15 minutes minimum between recovery actions.
- `[recovery].max_nudges_per_hour = 1` (was 2).
- `[recovery].max_aborts_per_hour = 1` (was 2).
- `[recovery].max_same_session_restarts_per_hour = 1` (was 2).
- `[recovery].max_fresh_restarts_per_6h = 1` (was 3).
- `[recovery].max_total_interventions_per_6h = 3` (was 8).
- `[recovery].stop_if_same_fingerprint_repeats = 2` (was 4) — circuit-trip after 2 repeats.
- `[recovery].soft_circuit_hold_seconds = 3600` (was 1800) — 1 hour soft-trip.
- `[recovery].soft_circuit_max_trips_before_stop = 2` (was 3).
- `[health].poll_seconds = 120` (was 60).
- `[health].rpc_timeout_seconds = 30` (was 20).
- `[health].process_restart_backoff_seconds = 60` (was 10) — much slower restarts.
- `[health].long_running_stall_seconds = 1800` (was 900).
- `[health].wedge_seconds = 3600` (was 1800).
- `[budgets]` is enabled with cumulative caps at the global scope:
  - `max_tokens = 500_000` (token cap; bounds total LLM work).
  - `max_attempts = 5` (hard backstop; cannot be bypassed by skipping `usage_sample`).
  - `max_seconds = 3600` (wall-time cap).
  - `on_exceeded = "operator_required"` (fail-closed; supervisor stops, never retries past the cap).

## Rationale

- **Token cap > cost cap on OAuth plans.** When billing is flat-rate, dollars-per-run is not meaningful. Total tokens burned across the run is the operator's intuition of "how much did this cost me". The cost cap is preserved as a backstop but not the primary signal.
- **`max_attempts` is the hard backstop.** `usage_sample` is reported by the worker; a buggy worker can skip it. The attempt counter counts `WorkRequest` boundary crossings — it cannot be silently bypassed.
- **`max_seconds` bounds the run regardless of model speed.** Even if the worker is honest about tokens, a runaway loop that does 1 token per second can still spend an hour. Wall-time is the wall.
- **Shadow mode by default.** The supervisor's value is observation and audit, not autonomous action. The operator flips `shadow_mode = false` only after one dry run confirms the loop shape is what they expect.
- **Slow recovery cadence.** A 15-minute cooldown and 1 fresh restart per 6 hours means the supervisor can recover from one transient fault per afternoon, not many. The operator is the recovery loop.
- **Soft circuit, not hard stop, on budget exhaustion.** A one-day provider outage should not require a manual restart every morning. 1-hour soft-trip, resume automatically, hard-stop after 2 trips.

## Alternatives considered

- **Set `shadow_mode = true` for live launches.** Rejected: math-engine's
  `@TOOL003` invariant requires `shadow_mode = false` for live preflight to
  pass. The audit-only behavior `shadow_mode = true` would have given is
  instead approximated by the `[budgets]` global caps (`max_attempts = 5`,
  `max_tokens = 500_000`, `max_seconds = 3600`) plus the slow `[recovery]`
  cooldowns — the supervisor cannot dispatch past the cap, and any recovery
  action is gated by 15 minutes between attempts.
- **Hard cap on dispatches only (no token/seconds).** Rejected: a single dispatch with a 300k-token context is worse than 50 dispatches with 6k each. The token cap shapes the *quality* of each call.
- **Cost cap as primary signal.** Rejected: per-token pricing is meaningless on flat-rate plans. Kept as backstop.
- **Auto-restart on every transient RPC failure.** Rejected: process_restart_backoff_seconds=10 was too aggressive — any model hiccup restarted the worker, losing session context. 60s + wedge_seconds=3600 means transient faults wait out, persistent faults trip the circuit.
- **Disable the supervisor's audit chain to reduce noise.** Rejected: the audit chain is the primary traceability surface; the operator reads `audit.jsonl` to understand what happened.

## Consequences

- The first real run will produce ≤5 worker dispatches. After the 5th, the supervisor stops and waits for the operator.
- The supervisor acts on recovery suggestions but at a deliberately slow cadence: 15 minutes between any recovery action, 1 fresh restart per 6 hours. Combined with the `[budgets]` global caps, the supervisor cannot dispatch more than 5 attempts, 500k tokens, or 1 hour of execution time per session before stopping for operator review.
- Every dispatched attempt has a `correlation_id` and `attempt_ordinal`; the `scripts/kaplansky-attempt-timeline.sh` helper (added by this ADR) prints them as a one-glance table.
- Budgets are global; tightening for a specific operation requires per-`WorkRequest.budget` overrides (out of scope for this ADR).
- Removing or relaxing any of these knobs requires a new ADR (no silent tuning).

## Change triggers

Revisit if:

- The operator needs more than 5 dispatches per session for a single research operation. Raise `max_attempts` in a new ADR.
- The operator flips `shadow_mode = false` permanently and wants the audit-only behavior deprecated. ADR the transition.
- pi_monitor adds a per-`WorkRequest.budget` API and the operator wants per-operation caps. ADR the migration.
- The flat-rate plan changes to per-token billing. Promote `max_cost` to primary signal.
