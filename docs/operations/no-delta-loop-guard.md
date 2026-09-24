# OS-Layer No-Delta Loop Guard

## Problem

The brief's Section D requires:

> 6. Ensure same `(operation_id, revision, directive hash, outcome=no_delta)` cannot dispatch indefinitely.
> 7. `Wait(no_eligible_work)` must include a real wake condition: source revision change, retry time, or terminal completion. A wait with no possible wake is a defect.

Math's ``live_source_snapshot.consult`` enforces this via the
``deltas`` ledger (DOC §14, §32-5.2). When the program repo IS
a math project, the consult step's stagnation trigger
(``stagnation_trigger()``) reads the ledger and emits
``VERDICT_ARCHITECTURE_REVIEW_REQUIRED`` after two+ substantial
no-delta sessions, which the OS translates to
``Wait(reason_code="architecture_review_required")``.

But when the program repo is NOT a math project (e.g.
kaplansky uses its own roadmap, not math's project config),
``MathProject.load()`` raises and the consult falls through to
dispatch. Math's stagnation tracker is unreachable. The OS
would keep dispatching the same target indefinitely.

## Solution

Add an OS-layer defensive guard inside
``select_next_work_for_supervisor`` that runs BEFORE the
consult step. The guard reads the supervisor's
``source-reports.jsonl`` ledger directly and counts consecutive
trailing ``no_delta`` reports per ``operation_id``. After
``NO_DELTA_LOOP_THRESHOLD`` (3, matching math's
``STAGNATION_THRESHOLD``) consecutive no-deltas, the OS emits
``Wait(reason_code="no_delta_loop_guard")`` with
``wake_on_source_change=True``.

## Why source-reports.jsonl

The supervisor already records every worker outcome report
in ``source-reports.jsonl`` (idempotently). The OS already has
write access to this file (the
``MATHLINT_REPORT_LOG`` env var points there). The guard
reads the file as a flat JSONL stream — no schema migration,
no new wire field, no math-side change.

## Wire shape

```python
@dataclass(frozen=True)
class Wait:
    source_revision: SourceRevision
    decided_unix: float
    reason_code: str  # = "no_delta_loop_guard"
    reason: str      # = "OS-layer no-delta loop guard: N consecutive
                     #   no_delta reports for op-K4; the dispatch is
                     #   held until either the operator rotates the
                     #   work (deactivate the roadmap item, add a new
                     #   active item) or math's project consult
                     #   authorizes a fresh directive"
    wake_on_source_change: bool   # True
    retry_after_seconds: float    # 600.0
```

## Wake condition

The Wait envelope includes a real wake condition:

* ``wake_on_source_change=True`` — supervisor re-decides
  when the source revision (git HEAD or roadmap
  fingerprint) changes. The operator rotates the work by
  editing ``programs/kaplansky-roadmap.toml`` (changes the
  fingerprint) or by activating a different item.
* ``retry_after_seconds=600.0`` — supervisor re-decides
  after 10 minutes even without a source change, so a
  stale Wait cannot park the supervisor forever.

A Wait without a possible wake is a defect; this guard
satisfies the brief's requirement.

## Tests

``tests/test_no_delta_loop_guard.py`` (13 tests) pins:

* Empty / missing ledger returns ``None`` (no escalation).
* Malformed JSONL lines are skipped (tolerance).
* Single no-delta report does not trigger.
* Threshold-many consecutive no-deltas trigger the Wait.
* A success outcome breaks the trailing run.
* Different operation IDs are tracked independently
  (trailing-run counter anchored at the most recent report).
* The Wait envelope carries the operation id in the reason.

## Live evidence

Unix 1790227275: source_decision emitted with
``kind=wait reason_code=no_delta_loop_guard reason="OS-layer
no-delta loop guard: 30 consecutive no_delta reports for
op-K4; the dispatch is held until ..."``.

Status surface transition: ``kaplansky: source-wait
[installed: com.local.research-institution.kaplansky]
— last: no_delta [next ask: 2026-09-24 01:31:15
(trigger=source_wait)] [last cycle: 2026-09-24 01:19:23]``.

The supervisor correctly parked K4 instead of dispatching
the same target for a 31st time.

## When math's own consult IS reachable

If the program repo IS a math project, math's
``live_source_snapshot.consult`` runs first and its verdict
takes precedence. The OS-layer guard never sees the dispatch
because math's stagnation trigger returns
``VERDICT_ARCHITECTURE_REVIEW_REQUIRED`` or
``VERDICT_NO_ELIGIBLE_WORK`` BEFORE the dispatch would fire.
The two layers are complementary, not redundant.

## When to retire the guard

When every program repo is a math project and math's
stagnation trigger runs unconditionally, the OS-layer guard
becomes dead code. Track via
``test_check_no_delta_loop_guard_at_threshold_returns_wait``;
when that test fails to trigger on a real ledger, the guard
can be removed.
