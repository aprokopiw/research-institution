---
id: ADR-0009
kind: request
status: drafted
target: pi_monitor
target-id: adr-pending-in-pi-monitor
title: pi_monitor supervisor must refuse re-dispatch when N consecutive attempts share the same (operation_id, outcome, status)
date: 2026-09-19
related:
  - AGENTS.md
  - ADR-0006
  - HARDENING-CHECKLIST.md §C.3
origin-postmortem: research-institution/HARDENING-CHECKLIST.md §A
---

# ADR-0009: pi_monitor supervisor-side repeat circuit

## Status

**Drafted in research-institution; pending ratification in pi_monitor.**

## Origin (postmortem)

The 187-attempt `blocked/stalled` loop was the supervisor's fault as
much as the source's. Per `@ADR-0014` (a pi_monitor-side invariant),
the supervisor treats re-dispatch of the same key as `reactivate` —
a deliberate design choice for legitimate re-asks. That choice is
correct; the missing defense is "but NOT when the same key has
returned the same non-success outcome N times in a row."

The source-side counter (`@ADR-0008`) is the primary defense; the
supervisor-side circuit is defense-in-depth that catches:
- Cases where the source changed but the key didn't.
- Cases where the source has a bug that bypasses its own counter.
- Cases where the operator manually re-asks after a partial fix.

## Requested behavior (in pi_monitor)

1. **New config knob:**
   `[recovery].max_consecutive_same_outcome_per_op` (default 3).
   The existing knobs (`max_nudges_per_hour`, `max_same_session_restarts_per_hour`)
   are already tuned for slow iteration; this knob is per-op, not
   per-hour.

2. **In `_attempt_terminal_audit` or `_handle_dispatch`, on each
   attempt terminal:**
   - Look up the last N attempts on the same
     `(source_identity, operation_id, work_key)`.
   - If all N share `(outcome, status)` AND outcome is `blocked` /
     `stalled` / `failed`, increment a per-op counter.
   - When the counter ≥ N:
     - Emit `consecutive_same_outcome_circuit` audit event.
     - Return `OperatorRequired` to the source instead of re-dispatching.
     - Do NOT advance `next_ask_unix`.

3. **Counter reset conditions:**
   - Operation changes (counter per-op).
   - Outcome changes to anything other than `blocked` / `stalled` /
     `failed`.
   - Operator explicit intervention (`recovery_command`, `stop`,
     `restart`, `fresh`).

4. **Circuit coexists with existing `soft_circuit` and `recovery`
   knobs.** The new counter is per-op and reads from the audit chain;
   it does not touch the existing per-hour rate limits.

## Why cross-repo

- The supervisor's audit chain + circuit logic lives in pi_monitor
  (`pi_monitor/supervisor.py:1394` for the relevant code path).
  research-institution cannot modify it.
- The counter must be backed by the audit chain so it survives
  supervisor restarts (the same way `soft_circuit` does today).

## Acceptance criteria

- [ ] `max_consecutive_same_outcome_per_op` config knob exists and
      defaults to 3.
- [ ] After 3 consecutive `blocked` outcomes on the same
      `(source_identity, operation_id, work_key)`, the supervisor
      emits `consecutive_same_outcome_circuit` and does not
      re-dispatch.
- [ ] The counter resets on op change, outcome change, or operator
      intervention.
- [ ] The kaplansky reproduction (187 attempts) terminates after 3
      attempts with the audit event visible in
      `~/.local/state/mathlint/pi-monitor/audit.jsonl`.
- [ ] Coexists with existing knobs: `max_nudges_per_hour` etc. still
      fire independently.

## Cross-references

- `@ADR-0006` — research-institution owns only catalog + bootstrap + green gate + dispatcher.
- `@ADR-0008` — sibling request: mathlint source-side repeat limit.
- `@ADR-0014` — pi_monitor invariant: re-dispatch of the same key is
  `reactivate` (the design choice this circuit augments, not replaces).
- `pi_monitor/supervisor.py:1394` — the dispatch path this ADR targets.
- `research-institution/HARDENING-CHECKLIST.md §C.3` — original ask.
