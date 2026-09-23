---
id: ADR-0011
kind: cross-repo-request
status: shipped
target: research-institution, math-engine
target-id: adr-pending-in-research-institution
title: Stagnation handling is a source decision, not a supervisor decision
date: 2026-09-20
shipped-on: 2026-09-20
shipped-by:
  - research-institution PR-A (durable record landing) commit 4f97c78
  - research-institution PR-A.1 (wire-vocab corrections) commit 1405be6
  - research-institution PR-C (consult-and-translate step) commit 68f4500
  - research-institution PR-D (14-gate closure audit) commit 5ad2748
  - math PR-B (consult adapter) commit 15c7017
  - math PR-B.1 (program-named literals cleanup) commit 06cec6c
  - math PR-D (math-side ledger; later retired) commit 8eeaa65
supersedes:
  - docs/semantic/adr/cross-repo-requests/adr-0009-pi-monitor-supervisor-side-repeat-circuit.md
related:
  - AGENTS.md
  - @ADR-0006-research-institution-scope
  - @ADR-0007-research-institution-owns-work-source-provider
  - @ADR-0014-execution-authority-boundary     (pi_monitor)
  - @ADR-0019-live-campaign-sequencing         (pi_monitor)
  - @CTR-0001-work-sources-and-runtimes-exchange-revisioned-execution-facts  (pi_monitor)
  - @INV-0093-institution-green-gate-is-canonical-wiring-evidence
  - docs/semantic/adr/cross-repo-requests/adr-0008-mathlint-source-side-repeat-limit.md
  - docs/semantic/adr/cross-repo-requests/adr-0010-mathlint-decide-next-kind-case.md
  - docs/concepts/cross-repo-decision-boundary.md
  - docs/operations/plan-013-live-supervisor-authority.md
postmortem:
  - 2026-09-13 — 187-attempt `blocked/stalled` loop on `work.kaplansky.extract-minimal-rigidity-overlap` (see @ADR-0007, @ADR-0008, @ADR-0009 origin-postmortem sections).
  - 2026-09-19 — live supervisor 4-attempt no-delta loop on `K4-characteristic-two-restriction-obstruction` (executions file `~/.local/state/mathlint/pi-monitor/executions/750d7954282c886d2bbda84de04881a33151fb25183febe744d78693891e25bb.json`, outcome digest `aae2f6d576f9655b86bc535d465797c69da760921f71ca85d7926d0d6099b709` ×4).
---

# ADR-0011: Stagnation handling is a source decision, not a supervisor decision

## Status

**Shipped in plan-013 (2026-09-20).** The institution-side
implementation is in `research-institution/providers/
research_institution_provider.py::_consult_math_and_translate`
and is wired through `select_next_work_for_supervisor`. The
math-side sibling is `math/src/mathlint/orchestration/
live_source_snapshot.py::consult` (sibling ADR
`@ADR-0097-live-source-snapshot-consult-adapter`, status
`proposed`). Wire shape is byte-identical to pre-plan-013;
pi_monitor is byte-identical pre/post. Closure audit:
`docs/operations/plan-013-closure-audit.md`.

**Original status (2026-09-20, pre-ship):** Drafted in
research-institution; pending ratification in math-engine.
This ADR documented the institution's request to math-engine
maintainers. It is durable in this repo (the
request is an institution-owned record); the implementation
lands in math-engine via a sibling ADR that cites this one.

**Supersedes `@ADR-0009-pi-monitor-supervisor-side-repeat-circuit`.**
The earlier cross-repo request asked pi_monitor to add a
supervisor-side repeat circuit; that request is withdrawn
because the authority boundary is in the wrong place. This
ADR documents the corrected request.

## Context (postmortem)

The 2026-09-13 hardening session root-caused the
187-attempt `blocked/stalled` loop on
`work.kaplansky.extract-minimal-rigidity-overlap` to a
missing source-side refusal. Three cross-repo ADRs were
drafted (`@ADR-0007`, `@ADR-0008`, `@ADR-0009`) but none
landed. The 2026-09-19 live supervisor session observed a
four-attempt no-delta loop on
`K4-characteristic-two-restriction-obstruction` (4 identical
`WorkerOutcomeEnvelope` digests). The operator killed the
supervisor manually.

Reviewing all three ADRs together against
`@ADR-0014-execution-authority-boundary` (pi_monitor)
reveals that all three ask the wrong layer:

- `@ADR-0009` asks pi_monitor to count consecutive
  same-outcome dispatches and refuse to re-ask the source.
  This violates `@ADR-0014`'s "loop, not DAG" guardrail:
  the supervisor would learn `depends_on`, `blocked_by`,
  `advances`-style concepts by another name.
- `@ADR-0008` asks math's `real_source.decide_next` to
  cap the same `operation_id` after N consecutive blocked
  outcomes. Closer to correct, but still a *circuit*: it
  stops asking the same op, when the right answer is to
  ask a *different* op (the architect) once stagnation
  fires.
- `@ADR-0007` asks math's CLI to expose a programmatic
  gate verdict. Useful but tangential: the live supervisor
  doesn't need the CLI; it needs the verdict as part of
  the source-decision flow.

## Decision

**Stagnation handling is a source decision.** The source
(research-institution's `select_next_work_for_supervisor`)
consults math's `stagnation_triggers` and the role-
conditioned directive compiler, then emits one of:

| Math verdict (kernel `ActionKind`) | `LiveSourceSnapshot.verdict_kind` (PR-B wrapper) | `SourceDecision` |
| --- | --- | --- |
| `MATHEMATICAL_RESEARCH` (with stagnation_session_count < 2 on the active item) | `DISPATCH_RESEARCH` | `Dispatch(WorkRequest(role="research", payload=<compile_mathematical_directive output hash>))` |
| `ARCHITECT_SYNTHESIS` (admission complete; architect round mid-flight) | `DISPATCH_ARCHITECT` | `Dispatch(WorkRequest(role="maintenance", payload=<compile_architecture_directive output hash>))` |
| `ARCHITECTURE_REVIEW_REQUIRED` (admission pending; stagnation trigger fired) | `ARCHITECTURE_REVIEW_REQUIRED` | `Wait(reason_code="architecture_review_required", reason=..., wake_on_source_change=True, retry_after_seconds=300)` |
| Any other (no eligible active item) | `NO_ELIGIBLE_WORK` | `Wait(reason_code="no_eligible_work", wake_on_source_change=True)` |

The wire `WorkRequest.role` values are drawn **exclusively**
from pi_monitor's existing `RoleName` Literal
(`default`/`primary`/`supporting`/`milestone`/`research`/
`intake`/`review`/`maintenance`). The math-internal
`MATHEMATICAL_RESEARCHER` / `MATHEMATICAL_ARCHITECT` are
`RoleProfileName` values that gate the directive compiler
input — they are NEVER placed on the wire. The supervisor
(pi_monitor) never learns what "stagnation",
"architecture review", or "role" means in this context. It
sees one `SourceDecision` per cycle using the existing
`Dispatch | Wait | OperatorRequired | Stop` vocabulary.

## Rationale

### Why the supervisor is the wrong place

- `@ADR-0014-execution-authority-boundary` (pi_monitor)
  forbids the supervisor from learning domain concepts.
  A counter on the supervisor is exactly the DAG smell
  ADR-0014 names.
- The supervisor's job is liveness and recovery
  (`@ADR-0009-bounded-recovery-and-soft-circuit`,
  pi_monitor). Liveness and recovery are runtime-neutral;
  stagnation is a domain concept.

### Why the source is the right place

- The source already owns the meaning of work
  (`@CTR-0001-work-sources-and-runtimes-exchange-revisioned-execution-facts`,
  pi_monitor §3 "Vocabulary" table).
- The source already owns the work-selection call into the
  proof program (`@ADR-0007-research-institution-owns-work-source-provider`).
- The source already owns the typed `SourceDecision`
  envelope. Translating math's verdict into that envelope
  is a one-step composition.

### Why the math-side adapter is the right interface

- Math already has `stagnation_triggers` (2+ no-delta),
  `select_global_action` (typed verdict),
  `compile_mathematical_directive` /
  `compile_architecture_directive` (role-conditioned
  prompt compilation). Reimplementing any of these in
  research-institution would violate
  `@ADR-0014-research-institution-scope`.
- Adding one thin wrapper
  (`mathlint.orchestration.live_source_snapshot.consult_work_source_snapshot`)
  gives research-institution one entry point that returns a
  typed verdict, without importing the whole
  `frontier_scheduler` package.

## Requested behavior

### In math-engine

1. **Add `mathlint.orchestration.live_source_snapshot.py`**:
   a thin pure wrapper that takes
   `(math_project: MathProject, candidate: WorkRequest,
   source_revision_unix: float)` and returns a typed
   `LiveSourceSnapshot` with verdict kind
   `DISPATCH_RESEARCH | DISPATCH_ARCHITECT |
   ARCHITECTURE_REVIEW_REQUIRED | NO_ELIGIBLE_WORK`,
   plus the byte-stable
   ``compute_directive_content_hash(...)`` of the
   role-conditioned `MathematicalDirective` /
   `ArchitectureDirective` payload. The caller
   (research-institution) is responsible for the
   `MathProject.load(start=repository)` call so the
   wrapper itself remains pure (same
   `MathProject` + same `candidate` -> same snapshot).
2. **No wire schema change.** No `SourceDecision` variant
   is added; no `WorkRequest` field is added; no
   `WIRE_VERSION` / `API_VERSION` bump.
3. **One new math-side property test**
   (`tests/integration/test_live_source_snapshot.py`)
   exercises the wrapper against a synthetic kaplansky-style
   repo with 0, 1, 2, 3 no-delta attempts and asserts the
   typed verdict matches.

### In research-institution

1. **Extend `select_next_work_for_supervisor`** to call
   math's `consult(math_project, candidate)` after the
   program's `next_active_work` returns a candidate.
   The OS performs the `MathProject.load(start=repository)`
   and catches a `NoMathlintProjectError` so a mathlint-
   unrelated repo falls back to existing dispatch behavior.
2. **Translate** the snapshot into a typed `SourceDecision`
   per the table above. When the verdict is a dispatch,
   the OS uses ``dataclasses.replace(candidate, role=...)``
   with a wire-allowed `RoleName` (``"research"`` /
   ``"maintenance"`` / ...) so the wire `RoleName` Literal
   in pi_monitor remains exact. Math's internal
   ``MATHEMATICAL_RESEARCHER`` / ``MATHEMATICAL_ARCHITECT``
   are present only inside the directive compiler's
   `RoleProfileName`; they never cross the wire.
3. **Audit log** the structured verdict (`verdict_kind`,
   `target`, `stagnation_session_count`,
   `directive_content_hash`) on the `source_decision` audit
   event.
4. **Six acceptance tests** in
   `tests/test_source_decision_stagnation.py` cover the
   0/1/2/3 no-delta cases, the role-aware payload
   compilation, and the authority-boundary test (no string
   like `"stagnation"` / `"architecture_review"` /
   `"MATHEMATICAL_RESEARCHER"` in the `kind` field of the
   `SourceDecision` envelope that crosses the supervisor
   boundary; wire `role` remains within the existing
   `RoleName` Literal).

### In pi_monitor

**No changes.** The supervisor's existing poll-`decide()`-
execute loop, judge, `RecoveryPolicy`, `ExecutionRecord`,
and `WorkerRuntime` remain as-is. The boundary is preserved.

## Acceptance criteria

- `RESEARCH_INSTITUTION_VWIRE_DIRECT=1 bash scripts/verify-institution.sh`
  prints GREEN across all 7 tiers.
- `cd math && .venv/bin/python -m pytest -q tests/integration/test_live_source_snapshot.py`
  is green.
- `cd research-institution && .venv/bin/python -m pytest -q tests/test_source_decision_stagnation.py tests/test_wire_protocol_unchanged.py`
  is green.
- `tests/integration/test_wire_protocol_event_union.py`
  (math) and `tests/test_wire_protocol_unchanged.py`
  (research-institution) both pass; the wire schema is
  byte-identical to pre-ADR-0011.
- `git status` in kaplansky and research-institution is
  clean of the 2026-09-19 uncommitted patches.
- Live supervisor on a no-delta target emits
  `Wait(reason_code="architecture_review_required")`
  after the 2nd no-delta, not a third `Dispatch`.

## Boundary cases

- **The wrapper is read-only.** It never mutates
  `~/.local/state/mathlint/deltas.jsonl`, the horizon
  ledger, or any canonical state. The caller (research-
  institution) is responsible for admission and intake.
- **The wrapper is pure.** Same inputs → same verdict. No
  clock, no random IDs, no I/O. The test suite asserts
  this with property-based tests.
- **The role-conditioned directive compiler is pure and
  byte-stable.** Two compilations of the same role + request
  + query snapshot yield the same bytes (asserted by the
  existing math-side property tests).
- **The audit event is a strict extension.** No existing
  audit event kind is removed; the new fields
  (`verdict_kind`, `target`, `stagnation_session_count`)
  ride along on the existing `source_decision` event.

## Consequences

- **Positive.** The no-delta loop closes without
  compromising the supervisor's authority boundary. Math's
  existing kernel machinery is composed (not reimplemented)
  into the source-decision flow. The operator stays out of
  the loop. The wire schema is preserved, so no `pi_monitor`
  schema bump is required.
- **Neutral.** The three historical cross-repo requests
  (`@ADR-0007`, `@ADR-0008`, `@ADR-0009`) become siblings
  of this ADR. `@ADR-0009` is explicitly withdrawn; the
  other two remain valid historical postmortem records but
  are not the canonical path forward.
- **Negative.** The plan touches two repos in lockstep
  (math + research-institution). The cross-repo conformance
  test must be maintained across releases. The role
  vocabulary on `WorkRequest.role` becomes more visible to
  the source side; if pi_monitor ever decides to validate
  `WorkRequest.role` itself, the role vocabulary must be
  mirrored per `@CTR-0021-wire-protocol-version-pinned`.

## Cross-references

- `@ADR-0014-execution-authority-boundary` (pi_monitor) —
  the loop-not-DAG guardrail.
- `@ADR-0019-live-campaign-sequencing` (pi_monitor) —
  the four-step live-campaign build order plan-013
  respects.
- `@CTR-0001-work-sources-and-runtimes-exchange-revisioned-execution-facts`
  (pi_monitor) — the source-decision vocabulary.
- `@INV-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult`
  — the durable invariant this ADR anchors.
- `@CTR-0100-live-source-snapshot-contract` — the
  math-side wrapper's typed contract.
- `docs/operations/plan-013-live-supervisor-authority.md` —
  the full plan with the 14-gate closure audit.
- `docs/concepts/cross-repo-decision-boundary.md` — the
  supervisor / judge / source / worker four-way split.
