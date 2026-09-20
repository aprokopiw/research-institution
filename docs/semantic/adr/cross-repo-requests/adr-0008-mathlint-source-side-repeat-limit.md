---
id: ADR-0008
kind: request
status: drafted
target: mathlint
target-id: adr-pending-in-math
title: mathlint decide_next must count its own dispatches and refuse to return the same operation_id after N consecutive blocked outcomes
date: 2026-09-19
related:
  - AGENTS.md
  - ADR-0006
  - @INV-0093
origin-postmortem: @INV-0093 (mathlint institution-gate invariant)
---

# ADR-0008: mathlint `decide_next` source-side repeat limit

## Status

**Drafted in research-institution; pending ratification in math-engine.**

## Origin (postmortem)

The 187-attempt `blocked/stalled` loop on
`work.kaplansky.extract-minimal-rigidity-overlap` was driven by
`mathlint.orchestration.real_source.decide_next` returning the same
`operation_id` from `mathlint next-step` output every call. The
architecture-review gate was unresolved; the roadmap kept pointing at
the same op; `decide_next` had no memory of recent attempts.

The supervisor (`pi_monitor`) has its own circuit (this ADR's
sibling, `@ADR-0009`), but a circuit in the source itself is the
correct defense-in-depth layer: a source that knows it has asked the
supervisor to dispatch the same op 5 times with the same blocked
outcome should refuse to ask a 6th time.

## Requested behavior (in mathlint)

1. **In-process dispatch counter in `real_source.decide_next`.**
   - Keyed by `(source_identity, operation_id, work_key)`.
   - Incremented when `decide_next` returns the same op as the
     previous N calls AND the outcome on those attempts was
     `blocked` / `stalled` / `failed`.
   - When the counter reaches `MATHLINT_DECIDE_NEXT_REPEAT_LIMIT`
     (default 3), return `OperatorRequired` with reason
     `"decide_next: operation <id> had N consecutive blocked
     outcomes; operator decision required"`.

2. **Counter reset conditions:**
   - Operation changes (counter per-op, not global).
   - Outcome changes to anything other than `blocked` / `stalled` /
     `failed`.
   - Operator explicitly resets via `mathlint work-release` or
     `mathlint architect-apply` (these count as operator decisions).

3. **Audit event:** when the counter trips, write a
   `decide_next_repeat_limit_tripped` event to
   `MATHLINT_REPORT_LOG` (the source-reports JSONL).

## Why cross-repo

- `decide_next` lives in mathlint (`mathlint/orchestration/real_source.py:114`).
  research-institution cannot modify mathlint's source code.
- The counter belongs in the source's process-local state, not in the
  supervisor's audit chain (which is a sibling-defense, not a primary).

## Acceptance criteria

- [ ] `decide_next` honors `MATHLINT_DECIDE_NEXT_REPEAT_LIMIT` (default 3).
- [ ] After 3 consecutive `blocked` outcomes on the same
      `operation_id`, the 4th call returns `OperatorRequired` with
      the documented reason.
- [ ] A `decide_next_repeat_limit_tripped` event is written to
      `MATHLINT_REPORT_LOG`.
- [ ] The counter resets on op change, outcome change, or
      `mathlint work-release` / `mathlint architect-apply`.
- [ ] The kaplansky reproduction (187 attempts) terminates after 3
      attempts with the documented reason.

## Cross-references

- `@ADR-0006` — research-institution owns only catalog + bootstrap + green gate + dispatcher.
- `@ADR-0009` — sibling request: pi_monitor supervisor-side repeat circuit.
- `mathlint/orchestration/real_source.py:114` — the `decide_next`
  function this ADR targets.
- `research-institution/HARDENING-CHECKLIST.md §C.2` — original ask (deleted; archived in plan-011 closure audit, durable anchor `@INV-0093`).
