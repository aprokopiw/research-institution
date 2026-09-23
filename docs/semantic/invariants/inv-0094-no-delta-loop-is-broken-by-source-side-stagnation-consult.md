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
  - @CTR-0100-live-source-snapshot-contract
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
`Dispatch(WorkRequest(role=maintenance, payload=...)` once the horizon
is admitted and the architect round begins), and MUST NOT
receive a third plain `Dispatch(WorkRequest(role=research, ...))` for the
same `operation_id`.

The wire `WorkRequest.role` value in all cases stays
within pi_monitor's existing `RoleName` Literal
(`default | primary | supporting | milestone | research |
intake | review | maintenance`). The math-internal
`MATHEMATICAL_RESEARCHER` / `MATHEMATICAL_ARCHITECT`
(`RoleProfileName`) are NEVER on the wire — they gate
which math compiler runs and which
`WorkerSubmission.kind` is intake-admissible, not which
worker the supervisor dispatches.

The supervisor (pi_monitor) is the wrong layer to enforce
this; the source (research-institution's
`select_next_work_for_supervisor`) is the right layer.

## Why it matters

The 2026-09-13 hardening session observed a 187-attempt
`blocked/stalled` loop on
`work.kaplansky.extract-minimal-rigidity-overlap`. The
2026-09-19 live supervisor session observed a four-attempt
no-delta loop on `K4-characteristic-two-restriction-obstruction`
(executions file
`~/.local/state/mathlint/pi-monitor/executions/750d7954282c886d2bbda84de04881a33151fb25183febe744d78693891e25bb.json`,
outcome digest
`aae2f6d576f9655b86bc535d465797c69da760921f71ca85d7926d0d6099b709`
×4). In both cases, the source produced the same
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

## How it composes with the existing surface

- `select_global_action(math_project)` already returns
  `ActionKind.ARCHITECTURE_REVIEW_REQUIRED` once
  `deltas.stagnation_trigger(root, target).no_delta_count >= 2`.
  The no-delta verdict is **already computed** inside math;
  plan-013 surfaces it to the OS layer that previously did not
  see it.
- `compile_mathematical_directive` / `compile_architecture_directive`
  accept `RoleProfile(role_name=MATHEMATICAL_RESEARCHER, ...)`
  / `MATHEMATICAL_ARCHITECT`. The compiled directive's
  `compute_directive_content_hash` is byte-stable across two
  compilations of the same inputs (math's existing invariant;
  `directive_id` is excluded).
- The wire schema's `WorkRequest.role: RoleName` is
  `Literal["default", "primary", "supporting", "milestone",
  "research", "intake", "review", "maintenance"]`. The source
  uses `dataclasses.replace(candidate, role="research" | "maintenance" | ...)`
  so the wire `RoleName` Literal stays exact.
- `WorkRequest.payload: dict[str, object]` carries the
  architect-required context (north star, certified reductions,
  open obligations) as a structured payload; pi_monitor does
  not read `payload`; the worker reads it. The OS injects
  ``{"directive_content_hash": snapshot.directive_content_hash,
  "target": snapshot.target, "stagnation_session_count":
  snapshot.stagnation_session_count}`` for the worker to verify
  against the math-side content hash.

## Enforcement

- `cd research-institution && .venv/bin/python -m pytest -q tests/test_source_decision_stagnation.py`
  is green and includes:
  - `test_no_stagnation_returns_dispatch_researcher` —
    0 no-delta → `Dispatch(role="research")`.
  - `test_one_no_delta_returns_dispatch_researcher` — 1
    no-delta is not yet stagnation; still dispatch.
  - `test_two_no_delta_returns_wait_architecture_review` —
    2+ no-delta flips to
    `Wait(reason_code="architecture_review_required",
    wake_on_source_change=True)`.
  - `test_three_no_delta_returns_dispatch_architect` — when
    the horizon admission is complete and the wrapper returns
    `DISPATCH_ARCHITECT`, dispatch with `role="maintenance"`.
  - `test_role_aware_payload_compiles_from_directive_compiler` —
    `WorkRequest.payload["directive_content_hash"]` is the
    byte-stable output of math's
    `compute_directive_content_hash(compile_architecture_directive(...))`.
  - `test_supervisor_authority_boundary_is_respected` —
    asserts no `SourceDecision` variant outside the existing
    `Dispatch | Wait | OperatorRequired | Stop` set is ever
    emitted; asserts no string like `"stagnation"`,
    `"architecture_review"`, `"MATHEMATICAL_RESEARCHER"`,
    `"MATHEMATICAL_ARCHITECT"` appears in the `kind` field
    that crosses the supervisor boundary; asserts the wire
    `role` is always inside the existing 8-value `RoleName`
    Literal.
- `cd math && .venv/bin/python -m pytest -q tests/integration/test_live_source_snapshot.py`
  is green and covers the wrapper's verdict kinds and
  purity property.
- `tests/test_wire_schema_unchanged.py` (research-institution)
  pins the wire schema to byte-identical-to-pre-INV-0094; no
  new `SourceDecision` variants; all `role` values in the
  existing `RoleName` Literal.

## Boundary cases

- **The wrapper is read-only.** It never mutates
  `~/.local/state/mathlint/deltas.jsonl`, the horizon
  ledger, or any canonical state. The caller (research-
  institution) is responsible for admission and intake.
- **The wrapper is pure over its inputs.** Same
  `MathProject` + same `candidate` + same
  `source_revision_unix` ⇒ the same `LiveSourceSnapshot`.
  The math-side property test asserts structural equality
  across 100+ randomized inputs.
- **The audit event is a strict extension.** No existing
  audit event kind is removed; the new fields
  (`verdict_kind`, `target`, `stagnation_session_count`,
  `directive_content_hash`) ride along on the existing
  `source_decision` event.
- **The supervisor's existing circuit breakers** (per
  `@ADR-0009-bounded-recovery-and-soft-circuit`,
  pi_monitor) are NOT replaced by this invariant. They
  remain as defense-in-depth for cases where the source
  itself misbehaves (returns malformed envelopes, never
  changes verdict, etc.). The invariant guards against
  the *normal* no-delta pattern; the supervisor's
  circuits guard against *abnormal* source behavior.
- **`--skip-gate` survives as a rare operator launch escape
  hatch.** It is a kernel-launch override, not a
  supervisor-cycle override: the source still runs every
  cycle, and `Wait(reason_code="architecture_review_required")`
  fires once 2 no-deltas accumulate even when the supervisor
  was launched with `--skip-gate`. The `--skip-gate` shape is
  owned by `cli.py::research start` (preflight), not by the
  supervisor cycle.

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
                 maintenance, payload=
                 {directive_content_hash, target})).
```

## Cross-references

- `@ADR-0011-stagnation-handling-is-a-source-decision` —
  the durable ADR this invariant anchors.
- `@CTR-0100-live-source-snapshot-contract` — the math-side
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
