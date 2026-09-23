---
id: INV-0094
kind: invariant
status: active
title: No-delta loop is broken by source-side stagnation consult, not by supervisor-side circuit
introduced: 2026-09-20
related:
  - @ADR-0006-research-institution-scope
  - @ADR-0007-research-institution-owns-work-source-provider
  - @ADR-0011-stagnation-handling-is-a-source-decision
  - @CTR-0095-live-source-snapshot-contract
  - @CTR-0001-work-sources-and-runtimes-exchange-revisioned-execution-facts  (pi_monitor)
  - @ADR-0014-execution-authority-boundary     (pi_monitor)
scope: research_institution, math-engine, pi_monitor
---

# INV-0094: No-delta loop is broken by source-side stagnation consult, not by supervisor-side circuit

## Statement

A live supervisor session that observes two consecutive
`WorkerOutcomeEnvelope(outcome=no_delta)` for the same
`operation_id` MUST receive a non-`Dispatch`
`SourceDecision` from its work source on the next poll
cycle (either `Wait(reason_code="architecture_review_required", ...)`
while the horizon admission is pending, or
`Dispatch(WorkRequest(role=MATHEMATICAL_ARCHITECT, ...))`
once the horizon is admitted), and MUST NOT receive a
third `Dispatch(WorkRequest(role=MATHEMATICAL_RESEARCHER, ...))`
for the same `operation_id`.

The supervisor (pi_monitor) is the wrong layer to enforce
this; the source (research-institution's
`select_next_work_for_supervisor`) is the right layer.

## Why it matters

The 2026-09-13 hardening session observed a 187-attempt
`blocked/stalled` loop on
`work.kaplansky.extract-minimal-rigidity-overlap`. The
2026-09-19 live supervisor session observed a four-attempt
no-delta loop on `K4-characteristic-two-restriction-obstruction`.
In both cases, the source produced the same
`Dispatch(WorkRequest(...))` on each cycle despite the
worker returning identical no-delta outcomes.

The naive fix is to add a circuit on the supervisor
("after N consecutive same-outcome dispatches, refuse to
re-ask the source"). This is **explicitly forbidden** by
`@ADR-0014-execution-authority-boundary` (pi_monitor):
"pi_monitor never reproduces a scheduler or DAG internally,
even when the source is internally enormous". A supervisor
circuit is exactly the DAG smell ADR-0014 names.

The correct fix is to teach the source to consult math's
existing stagnation triggers before returning `Dispatch`.
The source is the layer that already owns meaning
(`@CTR-0001-work-sources-and-runtimes-exchange-revisioned-execution-facts`,
pi_monitor §3 "Vocabulary"). It already owns the dispatch
policy (`@ADR-0007-research-institution-owns-work-source-provider`).
It already owns the typed `SourceDecision` envelope. Adding
a stagnation consult is a one-step composition.

## Enforcement

- `cd research-institution && .venv/bin/python -m pytest -q tests/test_source_decision_stagnation.py`
  is green and includes:
  - `test_no_stagnation_returns_dispatch_researcher` —
    0 no-delta → `Dispatch(role=MATHEMATICAL_RESEARCHER)`.
  - `test_one_no_delta_returns_dispatch_researcher` — 1
    no-delta is not yet stagnation; still dispatch.
  - `test_two_no_delta_returns_wait_architecture_review` —
    2+ no-delta flips to
    `Wait(reason_code="architecture_review_required",
    wake_on_source_change=True)`.
  - `test_three_no_delta_returns_dispatch_architect` — when
    the horizon admission is complete and math returns
    `MATHEMATICAL_ARCHITECT_NEXT`, dispatch with role=ARCHITECT.
  - `test_supervisor_authority_boundary_is_respected` —
    asserts no `SourceDecision` variant outside the existing
    `Dispatch | Wait | OperatorRequired | Stop` set is ever
    emitted; asserts no string like `"stagnation"`,
    `"architecture_review"`, `"architect_role"` appears in
    the `kind` field that crosses the supervisor boundary.
- `cd math && .venv/bin/python -m pytest -q tests/integration/test_live_source_snapshot.py`
  is green and covers the wrapper's verdict kinds and
  purity property.
- `tests/integration/test_wire_protocol_event_union.py`
  (math) and `tests/test_wire_protocol_unchanged.py`
  (research-institution) both pass; the wire schema is
  byte-identical to pre-INV-0094.

## Boundary cases

- **The wrapper is read-only.** It never mutates
  `~/.local/state/mathlint/deltas.jsonl`, the horizon
  ledger, or any canonical state. The caller (research-
  institution) is responsible for admission and intake.
- **The wrapper is pure.** Same inputs → same verdict. No
  clock, no random IDs, no I/O. Property-based tests
  assert this.
- **The audit event is a strict extension.** No existing
  audit event kind is removed; the new fields
  (`verdict_kind`, `target`, `stagnation_session_count`)
  ride along on the existing `source_decision` event.
- **The supervisor's existing circuit breakers** (per
  `@ADR-0009-bounded-recovery-and-soft-circuit`,
  pi_monitor) are NOT replaced by this invariant. They
  remain as defense-in-depth for cases where the source
  itself misbehaves (returns malformed envelopes, never
  changes verdict, etc.). The invariant guards against
  the *normal* no-delta pattern; the supervisor's
  circuits guard against *abnormal* source behavior.

## Live evidence

Pre-INV-0094 (the loop this invariant closes):

```text
executions file: ~/.local/state/mathlint/pi-monitor/executions/750d7954282c886d2bbda84de04881a33151fb25183febe744d78693891e25bb.json

attempt ordinals 3, 4, 5, 6 published identical
WorkerOutcomeEnvelope digests:

  aae2f6d576f9655b86bc535d465797c69da760921f71ca85d7926d0d6099b709

each ~4700 tokens, ~$0.20/each, no progress.
The supervisor kept dispatching
the same K4 work each cycle.
Operator killed the supervisor manually
on attempt 7 with SIGTERM.
```

Post-INV-0094 (the invariant in action):

```text
attempts 1, 2  → WorkerOutcomeEnvelope(outcome=no_delta)
attempts 3, 4  → WorkerOutcomeEnvelope(outcome=no_delta)
                          ▲
                          │ source.decide() consults
                          │ math.stagnation_triggers(root);
                          │ returns Wait(reason_code=
                          │ "architecture_review_required",
                          │ wake_on_source_change=True,
                          │ retry_after_seconds=300).
                          │
attempts 5+   → horizon admission completes (architect
                 submitted a StrategicReviewHorizon via
                 the 7-check gate).
                 source.decide() returns
                 Dispatch(WorkRequest(role=
                 MATHEMATICAL_ARCHITECT, payload=
                 compile_architecture_directive output)).
```

## Cross-references

- `@ADR-0011-stagnation-handling-is-a-source-decision` —
  the durable ADR this invariant anchors.
- `@CTR-0095-live-source-snapshot-contract` — the math-side
  wrapper's typed contract.
- `@CTR-0001-work-sources-and-runtimes-exchange-revisioned-execution-facts`
  (pi_monitor) — the `SourceDecision` vocabulary.
- `@ADR-0014-execution-authority-boundary` (pi_monitor) —
  the loop-not-DAG guardrail that protects this invariant's
  authority split.
- `docs/operations/plan-013-live-supervisor-authority.md` —
  the full plan with the 14-gate closure audit.
- `docs/concepts/cross-repo-decision-boundary.md` — the
  supervisor / judge / source / worker four-way split.
