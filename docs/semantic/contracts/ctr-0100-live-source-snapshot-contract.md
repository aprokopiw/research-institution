---
id: CTR-0100
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

# CTR-0100: Live source snapshot — math-side consult adapter for the source-decision flow

## Purpose

This contract specifies the math-side consult adapter that
research-institution's
`select_next_work_for_supervisor` calls before returning a
`SourceDecision`. The adapter is the single entry point
that exposes math's stagnation triggers, scheduler verdict,
and role-conditioned directive compiler to the source-decision
flow without forcing research-institution to import math's
internal `scheduler` / `architect` packages.

## Boundary

- **Math-engine** provides the wrapper
  `mathlint.orchestration.live_source_snapshot.consult(math_project, candidate, source_revision_unix)`
  with a typed `LiveSourceSnapshot` return value.
- **Research-institution** loads the `MathProject`
  (``mathlint.project.MathProject.load(start=repository)``)
  and calls the wrapper; it translates the verdict into a
  typed `SourceDecision` per
  `@ADR-0011-stagnation-handling-is-a-source-decision`.
- **Pi_monitor** never sees the wrapper, the verdict, or the
  role-conditioned directive; it consumes the resulting
  `SourceDecision` envelope and the `WorkRequest.payload`
  as opaque data per `@CTR-0001` non-guarantees.

## Signature

```python
# mathlint.orchestration.live_source_snapshot
from collections.abc import Mapping
from dataclasses import dataclass
from mathlint.deltas import StagnationTrigger   # noqa: F401 — type re-export
from mathlint.exchange.model import RoleProfileName  # noqa: F401
from mathlint.project import MathProject
from mathlint.scheduler import ActionKind, GlobalAction  # noqa: F401
from pi_monitor.work.work_source import SourceRevision, WorkRequest
from typing import Final, Literal


#: Verdict vocabulary (closed). The four kinds map deterministically
#: from the kernel's ``ActionKind``:
#:   * DISPATCH_RESEARCH          <- MATHEMATICAL_RESEARCH (with stagnation_count < 2 on candidate.operation_id)
#:   * DISPATCH_ARCHITECT         <- ARCHITECT_SYNTHESIS   (architect round mid-flight)
#:   * ARCHITECTURE_REVIEW_REQUIRED  <- ARCHITECTURE_REVIEW_REQUIRED
#:   * NO_ELIGIBLE_WORK           <- everything else (INFRASTRUCTURE_REPAIR, VERIFICATION_AUDIT, LEAN_FORMALIZATION when not the active, ...)
#:
#: Adding a new kind is a deliberate schema bump per
#: @CTR-0021-wire-protocol-version-pinned.
VerdictKind: Final = Literal[
    "DISPATCH_RESEARCH",
    "DISPATCH_ARCHITECT",
    "ARCHITECTURE_REVIEW_REQUIRED",
    "NO_ELIGIBLE_WORK",
]


@dataclass(frozen=True)
class LiveSourceSnapshot:
    """Read-only typed consultation result. Immutable.

    Fields:
      - verdict_kind:               one of the closed VerdictKind literals.
      - target:                     the operation_id under consult.
      - stagnation_session_count:   number of substantial NO_ROOT_RELEVANT_DELTA
                                    sessions observed for the target (0..N).
      - directive_content_hash:     sha256 content-hash of the role-conditioned
                                    ``MathematicalDirective`` / ``ArchitectureDirective``
                                    computed via math's existing
                                    ``compute_directive_content_hash``.
                                    Empty string for non-dispatch verdicts.
      - directive_template_hash:    sha256 of the role-conditioned template
                                    (``compute_directive_template_hash``).
                                    Empty string for non-dispatch verdicts.

    Invariants:
      - directive_content_hash is non-empty iff
        verdict_kind in {DISPATCH_RESEARCH, DISPATCH_ARCHITECT}.
      - directive_content_hash is empty iff
        verdict_kind in {ARCHITECTURE_REVIEW_REQUIRED, NO_ELIGIBLE_WORK}.
      - directive_content_hash is byte-stable across two
        compilations of the same role + request + query snapshot
        (math's existing invariant; the wrapper reuses the compiler).
    """
    verdict_kind: VerdictKind
    target: str
    stagnation_session_count: int
    directive_content_hash: str
    directive_template_hash: str


class StaleSourceRevision(ValueError):
    """``source_revision_unix`` is older than ``max_staleness_seconds``."""


class NoMathlintProject(RuntimeError):
    """Caller passed a ``MathProject`` that isn't loadable from this path."""


def consult(
    math_project: MathProject,
    candidate: WorkRequest,
    source_revision_unix: float,
    *,
    max_staleness_seconds: float = 60.0,
) -> LiveSourceSnapshot:
    """Read-only consultation.

    Reads (read-only):
      - mathlint.deltas.stagnation_trigger(math_project.root, candidate.operation_id)
      - mathlint.scheduler.select_global_action(math_project)
      - mathlint.exchange.directives.compile_mathematical_directive(...)
      - mathlint.exchange.directives.compile_architecture_directive(...)

    Writes: nothing.

    Pure with respect to its inputs: the function body never reaches
    the filesystem, clock, or RNG. ``MathProject.load()`` is the
    caller's responsibility; if the caller memoizes the project, the
    wrapper's purity holds across calls. Property-based tests assert
    that two ``consult(project, candidate, t)`` calls yield structurally
    equal ``LiveSourceSnapshot`` instances.

    Raises:
      StaleSourceRevision:   if ``source_revision_unix + max_staleness_seconds`` < time.time().
      NoMathlintProject:     defensively, if ``math_project.root`` is None or unreadable.
    """
```

## Guarantees

1. **Purity over inputs.** ``consult(project, candidate, t)`` is pure: same `MathProject`
   snapshot + same `candidate` + same `t` ⇒ the same `LiveSourceSnapshot`.
   The `MathProject.load()` call is the research-institution side's
   responsibility; the math-side wrapper reads only already-loaded state.
   The math-side property test asserts structural equality across 100+
   randomized MathProject + candidate inputs.
2. **No mutation.** The wrapper never writes to
   ``~/.local/state/mathlint/deltas.jsonl``, the horizon ledger, the
   audit chain, the canonical state, the canonical artifacts, or the
   work files. Tests snapshot the relevant state before and after.
3. **Verdict closed vocabulary.** `verdict_kind` is one of four
   literals drawn deterministically from math's existing ``ActionKind``
   StrEnum values. Adding a new kind requires:
      1. (math) a new ``ActionKind`` value plus the wrapper's translation table update;
      2. (research-institution) the matching `SourceDecision` translation;
      3. (pi_monitor) only if a NEW ``SourceDecision`` variant is needed
         (e.g. if a `Stop` needs a sub-shape) — never required under @ADR-0011.
4. **Byte-stable directive hash.** Two compilations of the same
   ``role_profile + request + ReadOnlyMathIRQuery`` yield identical
   ``compute_directive_content_hash(...)`` values. The wrapper stores the
   hash, not the directive object, so:
      - the dictionary-of-fields serialization can't drift when math adds
        a new optional field;
      - the per-compilation ``directive_id`` cannot break byte-stability
        (it is intentionally excluded from the hash per math's existing
        invariant).
5. **Opaque payload downstream.** The wrapper's output is consumed by
   research-institution's `select_next_work_for_supervisor`, which
   packages it into a `WorkRequest.payload`. Pi_monitor treats the
   payload as opaque per `@CTR-0001` non-guarantees.

## Preconditions / assumptions

- The caller (research-institution) supplies a fully-loaded
  ``MathProject`` built from the same repository the
  proof-program entry point used. The wrapper does NOT call
  ``MathProject.load()`` itself; that keeps the wrapper pure.
- The math kernel's deltas ledger exists at the conventional math
  ``math_project.root/docs/deltas/`` path (the standard ``DELTA_DIR``)
  and ``math_project.artifacts`` exposes the stalemated receipts.
- The ``candidate: WorkRequest`` is structurally valid per
  ``@CTR-0001`` — the wrapper does not re-validate; that's the
  supervisor's job.
- ``source_revision_unix`` is the unix timestamp the source provider
  observed the source revision; the wrapper uses it to refuse stale
  consults.

## Non-guarantees

- The wrapper does NOT promise that the next dispatch will succeed.
  The supervisor's liveness and recovery policy remain authoritative.
- The wrapper does NOT promise that the architecture-review horizon
  will be admitted on any specific timeline. It only reports the
  current verdict.
- The wrapper does NOT promise that the role-conditioned directive
  will fit the supervisor's bounded-pass-through budget. That's the
  dispatcher's responsibility to enforce.

## Compatibility / evolution

- The wrapper's signature is the canonical contract. New fields on
  ``LiveSourceSnapshot`` are added under
  ``@CTR-0021-wire-protocol-version-pinned`` discipline.
- Adding a new ``verdict_kind`` literal requires:
  1. A math-side ADR accepted; a new ``ActionKind`` value (or a
     new branch in the translation table) plus the wrapper's verdict
     table updated.
  2. A research-institution-side ADR that cites the math ADR and
     updates the translation table in
     ``select_next_work_for_supervisor``.
  3. A pi_monitor-side bump to
     ``pi_monitor.work.work_source.DecisionKind`` is **only**
     required if the new verdict translates to a NEW
     ``SourceDecision`` variant. Under @ADR-0011, all four verdicts
     translate to existing ``Dispatch | Wait`` variants (no pi_monitor
     bump needed).
- Removing or renaming a ``verdict_kind`` literal is a breaking
  change and requires the same coordinated update.

## Verification

- ``tests/integration/test_live_source_snapshot.py`` (math) —
  four property tests:
    1. **Purity** — same inputs ⇒ structurally equal
       ``LiveSourceSnapshot`` (100+ random inputs).
    2. **No mutation** — ``math_project.artifacts`` and deltas
       ledger bytes are equal before and after.
    3. **Verdict vocabulary** — synthetic fixtures with 0/1/2/3
       ``StagnationTrigger.no_delta_count`` values assert each of
       the four ``VerdictKind`` literals is reached for the right
       kernel ``ActionKind`` input.
    4. **Byte-stable directive hash** — two
       ``compute_directive_content_hash(...)`` calls with the
       same inputs yield identical hex strings.
- ``tests/test_source_decision_stagnation.py`` (research-
  institution) — six acceptance tests for the translation table.
- ``tests/test_wire_schema_unchanged.py`` (research-institution) —
  the wire schema is byte-identical to pre-CTR-0100; no new
  ``SourceDecision`` variants; ``WorkRequest.role`` values remain
  inside pi_monitor's existing ``RoleName`` Literal.
- ``tests/integration/test_wire_protocol_event_union.py`` (math)
  — the math + pi_monitor union test is unchanged.

## Boundary cases

- **No math project found.** If the caller could not load a
  ``MathProject`` (e.g., ``repository`` is not a mathlint repo),
  the caller emits ``Wait(reason_code="math_project_unavailable",
  wake_on_source_change=True)``. The wrapper is not invoked.
- **Stale source revision.** If ``source_revision_unix +
  max_staleness_seconds < time.time()``, the wrapper raises
  ``StaleSourceRevision``. The caller emits
  ``Wait(reason_code="stale_source_revision", wake_on_source_change=True)``.
- **Defensive default.** Any ``ActionKind`` that the wrapper's
  translation table doesn't classify is mapped to
  ``NO_ELIGIBLE_WORK``. The caller emits ``Wait(reason_code=
  "no_eligible_work", wake_on_source_change=True)``. The audit
  chain records the unrecognized kind for postmortem.

## Cross-references

- `@ADR-0011-stagnation-handling-is-a-source-decision` — the
  durable ADR this contract implements.
- `@INV-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult`
  — the invariant this contract enforces.
- `@CTR-0001-work-sources-and-runtimes-exchange-revisioned-execution-facts`
  (pi_monitor) — the `SourceDecision` vocabulary.
- `@CTR-0003-external-work-source-transport-is-bounded-and-fail-closed`
  (pi_monitor) — the freshness window.
- `@CTR-0021-wire-protocol-version-pinned` — the version
  discipline for any future verdict kind.
- `docs/operations/@ADR-0011-live-supervisor-authority.md` —
  the full plan with the 14-gate closure audit.
