---
id: CTR-0095
kind: contract
status: drafted
title: Live source snapshot — math-side consult adapter for the source-decision flow
introduced: 2026-09-20
related:
  - @ADR-0011-stagnation-handling-is-a-source-decision
  - @INV-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult
  - @CTR-0001-work-sources-and-runtimes-exchange-revisioned-execution-facts  (pi_monitor)
  - @CTR-0003-external-work-source-transport-is-bounded-and-fail-closed      (pi_monitor)
  - @CTR-0021-wire-protocol-version-pinned                                    (cross-repo)
parties:
  - math-engine  (provides the wrapper)
  - research-institution  (calls the wrapper, translates verdict)
  - pi_monitor  (consumes the resulting SourceDecision; unchanged)
---

# CTR-0095: Live source snapshot — math-side consult adapter for the source-decision flow

## Purpose

This contract specifies the math-side consult adapter that
research-institution's
`select_next_work_for_supervisor` calls before returning a
`SourceDecision`. The adapter is the single entry point
that exposes math's stagnation triggers, scheduler verdict,
and role-conditioned directive compiler to the source-decision
flow without forcing research-institution to import the
whole `frontier_scheduler` package.

## Boundary

- **Math-engine** provides the wrapper
  `mathlint.orchestration.live_source_snapshot.consult_work_source_snapshot(repository, candidate, source_revision)`
  with a typed `LiveSourceSnapshot` return value.
- **Research-institution** calls the wrapper and translates
  the verdict into a typed `SourceDecision` per
  `@ADR-0011-stagnation-handling-is-a-source-decision`.
- **Pi_monitor** never sees the wrapper, the verdict, or the
  role-conditioned directive; it consumes the
  `SourceDecision` envelope and the `WorkRequest.payload` as
  opaque data per `@CTR-0001` non-guarantees.

## Signature

```python
# mathlint.orchestration.live_source_snapshot
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from mathlint.orchestration.protocol import SourceRevision
from pi_monitor.work.work_source import WorkRequest


VerdictKind: Final = Literal[
    "MATHEMATICAL_RESEARCHER_NEXT",
    "MATHEMATICAL_ARCHITECT_NEXT",
    "ARCHITECTURE_REVIEW_REQUIRED",
    "NO_ELIGIBLE_WORK",
]


@dataclass(frozen=True)
class LiveSourceSnapshot:
    verdict_kind: VerdictKind
    target: str  # the operation_id or work_key under consult
    stagnation_session_count: int  # 0..N
    role_conditioned_directive: bytes  # byte-stable; the output of
                                       # compile_mathematical_directive
                                       # or compile_architecture_directive
                                       # or b"" for Wait verdicts
    directive_template_hash: str  # sha256 of the role-conditioned
                                  # directive's template; matches
                                  # WorkerSubmission.template_hash
                                  # at audit time

    # Invariants:
    # - role_conditioned_directive is non-empty iff
    #   verdict_kind in {MATHEMATICAL_RESEARCHER_NEXT,
    #   MATHEMATICAL_ARCHITECT_NEXT}.
    # - role_conditioned_directive is empty iff
    #   verdict_kind in {ARCHITECTURE_REVIEW_REQUIRED,
    #   NO_ELIGIBLE_WORK}.


def consult_work_source_snapshot(
    repository: Path,
    candidate: WorkRequest,
    source_revision: SourceRevision,
) -> LiveSourceSnapshot:
    """Read-only consultation.

    Reads:
      - math.src.mathlint.deltas.stagnation_triggers(repository)
      - math.src.mathlint.scheduler.select_global_action(project_snapshot)
      - math.src.mathlint.exchange.directives.compile_mathematical_directive(role, request, query_snapshot)
      - math.src.mathlint.exchange.directives.compile_architecture_directive(role, request, query_snapshot)

    Writes: nothing.

    Same inputs -> same output (pure). No clock, no random IDs,
    no I/O. Property-based tests assert this.
    """
```

## Guarantees

1. **Purity.** `consult_work_source_snapshot` is a pure
   function. Same `(repository, candidate, source_revision)`
   yields the same `LiveSourceSnapshot` bytes. Property-based
   tests (`tests/integration/test_live_source_snapshot.py`)
   assert this across 100+ randomized inputs.
2. **No mutation.** The wrapper never writes to
   `~/.local/state/mathlint/deltas.jsonl`, the horizon ledger,
   the audit chain, the canonical state, the canonical
   artifacts, or the work files. Tests assert this by
   snapshotting the relevant files before and after.
3. **Verdict closed vocabulary.** `verdict_kind` is one of
   four literals. Adding a new kind requires bumping
   `WIRE_VERSION` and updating
   `@CTR-0021-wire-protocol-version-pinned`.
4. **Role-conditioned directive is byte-stable.** Two
   compilations of the same role + request + query snapshot
   yield identical bytes. The existing math-side property
   tests assert this for `compile_mathematical_directive`
   and `compile_architecture_directive`; the wrapper
   reuses those compilers unchanged.
5. **Opaque payload downstream.** The wrapper's output is
   consumed by research-institution's
   `select_next_work_for_supervisor`, which packages it
   into a `WorkRequest.payload`. Pi_monitor treats the
   payload as opaque per `@CTR-0001` non-guarantees.

## Preconditions / assumptions

- The math kernel's deltas ledger exists at
  `~/.local/state/mathlint/deltas.jsonl` (or its configured
  path) and is readable.
- The math kernel's horizon admission ledger is reachable
  in read-only mode.
- The `candidate: WorkRequest` is structurally valid
  (per `@CTR-0001` source-decision contract) — the wrapper
  does not re-validate; that's the supervisor's job.
- `source_revision` carries a recent git fingerprint (the
  same value pi_monitor recorded when it last asked the
  source); the wrapper uses it to refuse stale consults.

## Non-guarantees

- The wrapper does NOT promise that the next dispatch will
  succeed. The supervisor's liveness and recovery policy
  remain authoritative for that.
- The wrapper does NOT promise that the architecture-review
  horizon will be admitted on any specific timeline. It
  only reports the current verdict.
- The wrapper does NOT promise that the role-conditioned
  directive will fit the supervisor's bounded-pass-through
  budget. That's the dispatcher's responsibility to enforce.

## Compatibility / evolution

- The wrapper's signature is the canonical contract. New
  fields on `LiveSourceSnapshot` are added under
  `@CTR-0021-wire-protocol-version-pinned` discipline.
- Adding a new `verdict_kind` literal requires:
  1. A math-side ADR accepted and a math-side bump to
     `WIRE_VERSION`.
  2. A research-institution-side ADR that cites the math
     ADR and updates the translation table in
     `select_next_work_for_supervisor`.
  3. A pi_monitor-side bump to
     `pi_monitor.work.work_source.DecisionKind` (only if
     the new verdict translates to a new `SourceDecision`
     variant; if it translates to existing `Wait(reason)`
     variants, no pi_monitor bump is needed).
- Removing or renaming a `verdict_kind` literal is a
  breaking change and requires the same three-repo
  coordinated update.

## Verification

- `tests/integration/test_live_source_snapshot.py` (math) —
  property tests for purity, no-mutation, and verdict
  vocabulary across 0/1/2/3 no-delta fixtures.
- `tests/test_source_decision_stagnation.py` (research-
  institution) — six acceptance tests for the translation
  table.
- `tests/test_wire_protocol_unchanged.py` (research-
  institution) — the wire schema is byte-identical to
  pre-CTR-0095; no new `SourceDecision` variants.
- `tests/integration/test_wire_protocol_event_union.py`
  (math) — the math + pi_monitor union test is unchanged.

## Boundary cases

- **Missing deltas ledger.** If the ledger file is missing
  (fresh operator install), the wrapper returns
  `LiveSourceSnapshot(verdict_kind=MATHEMATICAL_RESEARCHER_NEXT,
  stagnation_session_count=0, ...)` and emits one
  `source_snapshot_ledger_missing` audit event. The source
  translates this to `Dispatch(candidate)` and the
  supervisor continues.
- **Stale source revision.** If `source_revision.observed_unix`
  is older than the freshness window configured in math's
  source CLI (per `@CTR-0003-external-work-source-transport-is-bounded-and-fail-closed`),
  the wrapper returns
  `LiveSourceSnapshot(verdict_kind=NO_ELIGIBLE_WORK, ...)`
  with reason `stale_source_revision`. The source translates
  this to `Wait(reason_code="stale_source_revision",
  wake_on_source_change=True)`.
- **Defensive default.** Any verdict that the wrapper
  cannot classify (a future verdict kind introduced before
  this contract is updated) is mapped to
  `NO_ELIGIBLE_WORK`. The source translates this to
  `Wait(reason_code="unknown_math_verdict")` and the audit
  chain records the unrecognized verdict for postmortem.

## Cross-references

- `@ADR-0011-stagnation-handling-is-a-source-decision` —
  the durable ADR this contract implements.
- `@INV-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult` —
  the invariant this contract enforces.
- `@CTR-0001-work-sources-and-runtimes-exchange-revisioned-execution-facts`
  (pi_monitor) — the `SourceDecision` vocabulary.
- `@CTR-0003-external-work-source-transport-is-bounded-and-fail-closed`
  (pi_monitor) — the freshness window.
- `@CTR-0021-wire-protocol-version-pinned` — the version
  discipline for any future verdict kind.
- `docs/operations/plan-013-live-supervisor-authority.md` —
  the full plan with the 14-gate closure audit.
