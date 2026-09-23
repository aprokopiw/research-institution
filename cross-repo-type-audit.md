---
id: AUDIT-2026-09-22-cross-repo-type-canonicalization
title: Cross-Repo Type Canonicalization — Findings & Proposed Tasks
kind: audit
date: 2026-09-22
status: pending-decisions
related:
  - ADR-0014 # mathlint does not import program-named modules
  - ADR-0091 # mathlint does not ship program launchers
  - ADR-0092 # pi_monitor does not name mathlint (or any program)
  - ADR-0025 # supervisor decomposition
  - CTR-0020 # wire protocol authority
  - INV-0093 # institution green gate is canonical wiring evidence
  - CTR-0094 # WorkSourceProvider dispatch envelope
---

# Cross-Repo Type Canonicalization — Findings & Proposed Tasks

> **Status:** Pending operator decisions on Q1–Q4 below. No fixes executed yet.
> **Scope:** All four repos (`math/`, `pi_monitor/`, `kaplansky/`, `research-institution/`).
> **Goal:** Absolutely cleanest end-state — one canonical home for every wire-shape type, import rules enforced across all four repos, the live-launch bug fixed, and `@ADR-0092` re-asserted on pi_monitor's stable surface.

---

## 1. Background and root cause

The institution ran `python3 -m research_institution start kaplansky` and the supervisor crashed on the first `report_result` round-trip. The math subprocess (the `LiveSource` that backs `mathlint-source`) raised `LiveSourceError("invalid_report")` because the wire frame was missing two required keys: `report_id` and `envelope_digest`.

The root cause is structural, not a one-line fix. The wire protocol's emit path in pi_monitor bypasses its own canonical wire model. The "fix" surfaces four pre-existing patterns that all live in the same shape:

1. **Duplicate types.** Every wire-shape type exists in 2–5 repos. They drift.
2. **Wrong canonical owner.** Some types live in the repo that's furthest from the wire authority.
3. **Import rules not enforced.** Kaplansky imports pi_monitor; pi_monitor's stable surface names programs (`@ADR-0092` violations).
4. **Legacy emit paths.** The wire model exists on paper; the call site still uses a legacy `to_dict` that drops fields.

This document enumerates every duplicate and every violation, proposes a fix sequence, and lists the open questions the operator must decide before execution.

---

## 2. The import rule (operator-stated)

The operator's rule for cross-repo imports, as of this session:

| Repo | Knows about |
|---|---|
| `pi_monitor` | **nothing else** (zero project knowledge) |
| `math` | `pi_monitor` only (for the wire protocol) |
| `kaplansky` | `math` only |
| `research-institution` | all three |

### Verification against the current codebase

| Repo | Imports | Allowed by rule? | Status | Resolution |
|---|---|---|---|---|
| `pi_monitor/src/` | `^(from\|import) (mathlint\|math\|research_institution\|kaplansky)\b` → **0 matches** | yes | ✅ clean | n/a |
| `math/src/` | `from pi_monitor.work.work_source import DecisionKind` (4 sites) | yes | ✅ clean | n/a |
| `math/src/` | `from pi_monitor.protocol.*` → 0; `from research_institution.*` → 0; `from kaplansky.*` → 0 | yes | ✅ clean | commit `a207044` retired the TYPE_CHECKING-only `research_institution.*` imports |
| `kaplansky/src/` | `from mathlint.*` (15+ sites — `mathlint.orchestration`, `mathlint.models`, `mathlint.program_providers`, `mathlint.research_state_api`, `mathlint.autonomous_supervisor`, …) | yes | ✅ clean | n/a |
| `kaplansky/src/` | `from pi_monitor.work.work_source import DecisionKind` (`launcher/verify.py:31`) | **no** | ❌ **VIOLATION** → ✅ | commit `b56d2f2` — replaced with `from mathlint.protocol.wire_types import DecisionKind` |
| `kaplansky/src/` | `from pi_monitor.work.work_source import SourceRevision, WorkRequest` (`work_selection.py:47`) | **no** | ❌ **VIOLATION** → ✅ | commit `b56d2f2` — replaced with `from mathlint.protocol.wire_types import SourceRevision, WorkRequest` |
| `kaplansky/tests/` | `from pi_monitor.work.work_source import SourceRevision, WorkRequest` (`test_work_selection.py:36`) | **no** | ❌ **VIOLATION** → ✅ | commit `b56d2f2` — replaced via math facade |
| `research-institution/research_institution/` | `from mathlint.*` (4 sites in `providers/`, `dispatcher.py`, `tests/conftest.py`) | yes | ✅ clean | n/a |
| `research-institution/research_institution/` | `from pi_monitor.*` (4 sites — `supervisor.py`, `contracts/source_decision.py`, `status.py`) | yes | ✅ clean | n/a |
| `research-institution/tests/` | `from mathlint.*` and `from pi_monitor.*` (multiple sites — testing the composition) | yes | ✅ clean | n/a |

**Summary:**
- pi_monitor: ✅ 0 imports of any project. **Holds the rule.**
- math: ✅ imports pi_monitor only. **Holds the rule.**
- kaplansky: ❌ 3 violations (2 src + 1 test). Imports pi_monitor wire types directly.
- research-institution: ✅ imports both. **Holds the rule.**

The kaplansky violations are the structural reason the rest of this audit exists. Kaplansky produces `WorkRequest` instances because the wire-protocol output type lives in pi_monitor. To honor the operator's rule without changing ownership semantics, the proposal in §6 routes the import through a math re-export module.

---

## 3. The live-launch bug (the immediate defect)

### What happened

The supervisor started cleanly. The audit log showed:

```
22:34:21 [source_report_failed] err=WireError('external source closed stdout (request 2)')
mathlint.orchestration.live_source.LiveSourceError: invalid_report
  File ".../live_source.py", line 188, in handle
    raise LiveSourceError("invalid_report")
```

`LiveSource.handle('report_result')` reads two keys from the wire frame: `report_id` and `envelope_digest`. The frame the supervisor sent was missing both.

### Why it happened

The supervisor's emit path calls `execution_report_to_dict(report)` (in `pi_monitor/src/pi_monitor/work/work_source.py:426`). This function emits a dict with key `"digest"` (the dataclass field name), not `"envelope_digest"`. It also drops `report_id` entirely.

Pi_monitor *also* has the canonical wire model `ExecutionReportWireModel` (`protocol/wire_models.py:122`) which knows about `report_id` and `envelope_digest`. The wire model exists. It has `from_dataclass()` and `to_dataclass()` methods. The emit path bypasses it.

### The exact fix (commit 1 in §7)

Replace the call site at `pi_monitor/src/pi_monitor/work/external_source.py:217-220`:

```python
# before
frame = self._call(
    report_result_frame(
        request_id=self._next_request_id(),
        epoch=self._epoch,
        report=execution_report_to_dict(report),
    ),
    expect={TYPE_RESULT_ACK},
)

# after
frame = self._call(
    report_result_frame(
        request_id=self._next_request_id(),
        epoch=self._epoch,
        report=ExecutionReportWireModel.from_dataclass(
            report, include_envelope=False
        ).model_dump(),
    ),
    expect={TYPE_RESULT_ACK},
)
```

Then delete `execution_report_to_dict` from `work_source.py:426-440`.

### Why no test caught this

- Pi_monitor's wire-model tests pass because the wire model is correct.
- Pi_monitor's `execution_report_to_dict` tests pass because the legacy function emits exactly what it says it emits.
- Math's `LiveSource.handle('report_result')` tests pass because the malformed input is correctly rejected with `invalid_report`.
- No test exercises the call path the supervisor uses — `external_source.report_result()` → `report_result_frame()` → `execution_report_to_dict()` → subprocess → `LiveSource.handle()`.

The cross-repo round-trip test proposed in §7 commit 1 closes this gap.

---

## 4. The `@ADR-0092` violations

`@ADR-0092` (pi_monitor does not name mathlint or any program in source) was filed 2026-09-19. The audit found it partially violated:

### Pi_monitor src/ has program-name literals

| File:line | Literal | Status (at audit) | Resolution |
|---|---|---|---|
| `work/work_source.py:174-179` | `OperationKind = Literal["mathlint-research", "mathlint-verify", "mathlint-build", "speckit-task"]` | ❌ violation | ✅ commit `89bfb56` — `OperationKind = str` |
| `work/work_source.py:194-198` | `WorkspaceName = Literal["default", "kaplansky-workspace", "math-workspace"]` | ❌ violation | ✅ commit `89bfb56` — `WorkspaceName = str` |
| `work/work_source.py:155-156` | Docstring cites `"kaplansky-research-program"` and `"mathlint-research"` | ❌ violation | ✅ commit `89bfb56` — scrubbed |
| `work/work_source.py:368` | Docstring: "work-source identity is whatever program (e.g. mathlint) in its source" | ❌ violation | ✅ commit `89bfb56` — scrubbed |
| `protocol/work_envelopes.py:23` | Docstring citation of `kaplansky.roadmap_item.KaplanskyRoadmapItem` | ❌ violation | ✅ commit `89bfb56` — scrubbed |
| `protocol/work_envelopes.py:41` | Docstring citation of `mathlint.models` | ❌ violation | ✅ commit `89bfb56` — scrubbed |
| `work/work_source.py:50` | Docstring citation of `research_institution.contracts.source_decision.DecisionKind` | ❌ violation (RI is also a project) | ✅ commit `89bfb56` — scrubbed |

A second pass (commits `94e1576` + `9ba4d48`) caught the
remaining `research-institution` references that the
original commit missed: docstrings in
`work_source.py`, `external_source.py`, `config/config.py`,
`supervisor_status.py`, and the test files. The BC-4 and
BC-5 static checks were extended to flag
`research_institution` literals going forward, so any
reintroduction fails CI.

Note: `SourceIdentity` was already relaxed from `Literal[...]` to `str` (with a docstring acknowledging the `@ADR-0092` reason). The same pattern needs to apply to `OperationKind` and `WorkspaceName`.

### Pi_monitor src/ has zero `from kaplansky / from mathlint / from research_institution` imports

The import rule holds. The literals are docstring-level references, not code-level dependencies. They're still violations of `@ADR-0092`'s intent (pi_monitor's stable surface shouldn't know about programs), even though they don't break the import rule.

### The fix (commit 2 in §7)

- `OperationKind = str` (drop the Literal). Move the canonical list to `research-institution/research_institution/contracts/source_decision.py`.
- `WorkspaceName = str` (drop the Literal). Same.
- `RoleName` — see Q1 below.
- Scrub the docstring citations (`work_source.py:50, 155-156, 368`; `work_envelopes.py:23, 41`). Replace with generic terms ("the registered work source", "the math kernel" → "the upstream work-selection provider", etc.). Or delete the citations entirely.
- The canonical vocabulary lists (now in RI) drive validation; pi_monitor accepts any string and forwards verbatim.

---

## 5. Duplicate types — the full census

For every wire-shape concept, here is every class that exists, with file:line evidence. The audit is exhaustive — each row is a class definition; if a row is in the "delete" column, it's a re-declaration that should be removed.

### 5.1 `ExecutionReport` (runtime contract + jsonl stream)

| # | Repo | File:line | Class | Form | Use |
|---|---|---|---|---|---|
| 1 | pi_monitor | `work/work_source.py:405` | `ExecutionReport` | `@dataclass(frozen=True, slots=True)` | Runtime contract — what `WorkSource.report_result()` accepts |
| 2 | pi_monitor | `protocol/wire_models.py:122` | `ExecutionReportWireModel` | Pydantic BaseModel | Wire shape (canonical, has `report_id` + `envelope_digest`) |
| 3 | math | `orchestration/_deprecated_launcher/reports.py:30` | `ExecutionReport` | `@dataclass(frozen=True, slots=True)` | Reads the supervisor's jsonl stream (legacy) |
| 4 | kaplansky | `launcher/execution_report.py:31` | `ExecutionReport` | Pydantic BaseModel | Kaplansky's view of the same jsonl stream |
| 5 | kaplansky | `launcher/reports.py:32` | `ExecutionReport` | `@dataclass(frozen=True, slots=True)` | Dataclass mirror of kaplansky's Pydantic model |

**Canonical:** pi_monitor (both row 1 — the runtime contract, and row 2 — the wire shape). Math's row 3 lives in `_deprecated_launcher/` (already deprecated path); delete as part of the `_deprecated_launcher/` retirement. Kaplansky's rows 4 and 5 are duplicates; delete both, import from pi_monitor.

### 5.2 `SourceDecision`

| # | Repo | File:line | Class | Form |
|---|---|---|---|---|
| 1 | math | `orchestration/source_decisions.py:26` | `SourceDecision` | `@dataclass(frozen=True)` (uses `DecisionKind` from pi_monitor) |
| 2 | pi_monitor | `work/work_source.py` (via `Dispatch`, `Wait`, `OperatorRequired`, `Stop`) | 4 frozen dataclasses | `@dataclass(frozen=True, slots=True)` |
| 3 | pi_monitor | `protocol/wire_models.py:276` | `SourceDecisionWireModel` | Pydantic (tagged union on `kind` field) |
| 4 | research-institution | `contracts/source_decision.py:202` | `SourceDecisionWireDict` | Pydantic re-declaration |

**Canonical:** pi_monitor. Math's row 1 is the math-side in-process representation (not on the wire); it consumes pi_monitor's `DecisionKind` so the discriminator matches. RI's row 4 must be deleted.

### 5.3 `SourceRevision`

| # | Repo | File:line | Class | Form |
|---|---|---|---|---|
| 1 | pi_monitor | `work/work_source.py:205` | `SourceRevision` | `@dataclass(frozen=True, slots=True)` |
| 2 | pi_monitor | `protocol/wire_models.py:83` | `SourceRevisionWireModel` | Pydantic |
| 3 | research-institution | `contracts/source_decision.py:151` | `SourceRevisionWireDict` | Pydantic re-declaration |

**Canonical:** pi_monitor. RI's row 3 must be deleted.

### 5.4 `WorkRequest`

| # | Repo | File:line | Class | Form |
|---|---|---|---|---|
| 1 | pi_monitor | `work/work_source.py:243` | `WorkRequest` | `@dataclass(frozen=True, slots=True)` |
| 2 | pi_monitor | `protocol/wire_models.py:179` | `WorkRequestWireModel` | Pydantic |
| 3 | research-institution | `contracts/source_decision.py:168` | `WorkRequestWireDict` | Pydantic re-declaration |

**Canonical:** pi_monitor. RI's row 3 must be deleted.

### 5.5 `DecisionKind` (StrEnum)

| # | Repo | File:line | Status |
|---|---|---|---|
| 1 | pi_monitor | `work/work_source.py:42` | canonical |
| 2 | research-institution | `contracts/source_decision.py:108` | `OperationKind = PM_OperationKind` (re-export) |

**Canonical:** pi_monitor. RI's row 2 is an alias-only re-export; this is acceptable per the re-export convention. **No action needed** — but worth documenting as the precedent: aliases are fine; re-declarations are not.

### 5.6 Vocab Literals (`OperationKind`, `RoleName`, `WorkspaceName`)

| # | Repo | File:line | Class | Notes |
|---|---|---|---|---|
| 1 | pi_monitor | `work/work_source.py:173` | `OperationKind` | `Literal["mathlint-research", "mathlint-verify", "mathlint-build", "speckit-task"]` — `@ADR-0092` violation |
| 2 | pi_monitor | `work/work_source.py:181` | `RoleName` | `Literal["default", "primary", ..., "maintenance"]` — generic vocab, no program names |
| 3 | pi_monitor | `work/work_source.py:194` | `WorkspaceName` | `Literal["default", "kaplansky-workspace", "math-workspace"]` — `@ADR-0092` violation |
| 4 | research-institution | `contracts/source_decision.py:61,108` | `OperationKind` | Re-exports pi_monitor's literal (the source of `@ADR-0092` violation) |

**Canonical:** pi_monitor owns the *type* (string alias); research-institution owns the *vocabulary* (the canonical list of accepted values). After commit 2, pi_monitor's `OperationKind = str`; RI holds the Literal and validates.

### 5.7 `WorkEnvelope` and policy subclasses

| # | Repo | File:line | Class |
|---|---|---|---|
| 1 | pi_monitor | `protocol/work_envelopes.py:57` | `WorkEnvelope` (BaseModel) |
| 2 | pi_monitor | `protocol/work_envelopes.py:74` | `ExecutionPolicy(WorkEnvelope)` |
| 3 | pi_monitor | `protocol/work_envelopes.py:88` | `SessionPolicy(WorkEnvelope)` |
| 4 | pi_monitor | `protocol/work_envelopes.py:97` | `IsolationPolicy(WorkEnvelope)` |
| 5 | pi_monitor | `protocol/work_envelopes.py:111` | `BudgetPolicy(WorkEnvelope)` |
| 6 | pi_monitor | `protocol/work_envelopes.py:124` | `WorkRequestPayload(WorkEnvelope)` |
| 7 | pi_monitor | `protocol/work_envelopes.py:154` | `DispatchPayload(WorkEnvelope)` |
| 8 | pi_monitor | `protocol/work_envelopes.py:165` | `WaitPayload(WorkEnvelope)` |

**Canonical:** pi_monitor. These are referenced from RI as `dict[str, Any]` opaque payloads (RI parses them via `parse_work_request_envelopes`). **No duplicates exist.** No action.

### 5.8 Audit summary table

| Concept | Canonical | Duplicates to delete |
|---|---|---|
| `ExecutionReport` (runtime dataclass) | pi_monitor `work/work_source.py:405` | kaplansky `launcher/reports.py:32` |
| `ExecutionReportWireModel` (Pydantic wire) | pi_monitor `protocol/wire_models.py:122` | kaplansky `launcher/execution_report.py:31` (the entire `TypedExecutionReport` Pydantic class is a duplicate) |
| `ExecutionReport` math parse | math `orchestration/_deprecated_launcher/reports.py:30` | (delete as part of `_deprecated_launcher/` retirement; not a duplicate per se, but unmaintained) |
| `SourceDecisionWireModel` | pi_monitor `protocol/wire_models.py:276` | RI `contracts/source_decision.py:202` (`SourceDecisionWireDict`) |
| `SourceRevisionWireModel` | pi_monitor `protocol/wire_models.py:83` | RI `contracts/source_decision.py:151` (`SourceRevisionWireDict`) |
| `WorkRequestWireModel` | pi_monitor `protocol/wire_models.py:179` | RI `contracts/source_decision.py:168` (`WorkRequestWireDict`) |
| `DecisionKind` (StrEnum) | pi_monitor `work/work_source.py:42` | (RI alias is fine) |
| `OperationKind` Literal | should move from pi_monitor to RI | pi_monitor `work/work_source.py:173` (drop Literal; keep `= str`) |
| `WorkspaceName` Literal | should move from pi_monitor to RI | pi_monitor `work/work_source.py:194` (drop Literal; keep `= str`) |
| `RoleName` Literal | see Q1 | see Q1 |

---

## 6. The fix proposal — five commits, one per repo (in dependency order)

### Commit 1 — `pi_monitor`: fix the wire-drift bug (the live-launch defect)

**File:** `pi_monitor/src/pi_monitor/work/external_source.py:217-220`

Replace `report=execution_report_to_dict(report)` with:
```python
report=ExecutionReportWireModel.from_dataclass(
    report, include_envelope=False
).model_dump(),
```

**File:** `pi_monitor/src/pi_monitor/work/work_source.py:426-440`

Delete `execution_report_to_dict`. The function has no remaining callers after the call-site fix above. If a test depends on the legacy function, rewrite the test to use `ExecutionReportWireModel.from_dataclass(report, include_envelope=False).model_dump()` — same observable behavior with the wire keys present.

**New test:** `pi_monitor/tests/integration/test_cross_repo_wire_round_trip.py`

The test imports `mathlint.orchestration.live_source.LiveSource`, constructs a real `WorkRequest`, drives it through `ExecutionReportWireModel.from_dataclass().model_dump()` → json-encoded → `LiveSource.handle('report_result')` → `result_ack`. This is the first end-to-end cross-repo wire test in the institution.

**Why this is commit 1:** Without this fix, the supervisor cannot dispatch a worker. Every other fix in this doc is moot until live launches work.

### Commit 2 — `pi_monitor`: enforce `@ADR-0092` on the Literals

**File:** `pi_monitor/src/pi_monitor/work/work_source.py:173-179`

Change:
```python
OperationKind = Literal[
    "mathlint-research",
    "mathlint-verify",
    "mathlint-build",
    "speckit-task",
]
```
to:
```python
OperationKind = str
```

Add a docstring citing `@ADR-0092` (mirror the existing pattern on `SourceIdentity`).

**File:** `pi_monitor/src/pi_monitor/work/work_source.py:194-198`

Same change for `WorkspaceName`. (See Q1 for `RoleName`.)

**File:** `pi_monitor/src/pi_monitor/work/work_source.py:50, 155-156, 368` and `pi_monitor/src/pi_monitor/protocol/work_envelopes.py:23, 41`

Scrub docstring citations of project names. Replace with generic terms.

**Validation:** `python -m pytest tests/static/test_no_program_identity_in_fixtures.py` should report 0 violations after this commit. Currently it likely reports the `OperationKind`/`WorkspaceName` Literals (the static check scans source for these literals).

### Commit 3 — `research-institution`: delete duplicate wire classes + adopt the canonical vocabularies

**File:** `research-institution/research_institution/contracts/source_decision.py:151, 168, 202`

Replace the three local re-declarations with re-exports from pi_monitor:

```python
# before
class SourceRevisionWireDict(BaseModel): ...
class WorkRequestWireDict(BaseModel): ...
class SourceDecisionWireDict(BaseModel): ...

# after
from pi_monitor.protocol.wire_models import (
    SourceRevisionWireModel as SourceRevisionWireDict,
    WorkRequestWireModel as WorkRequestWireDict,
    SourceDecisionWireModel as SourceDecisionWireDict,
)
```

The local names (`SourceRevisionWireDict`, etc.) are kept as aliases for back-compat. New code may import `SourceRevisionWireModel` directly from pi_monitor.

**File:** `research-institution/research_institution/contracts/source_decision.py:61, 108`

Move the canonical `OperationKind` Literal here. RI is the OS composition layer; the program-identity vocabulary belongs here.

**File:** `research-institution/research_institution/contracts/source_decision.py` (new section)

Add a `WorkspaceName` Literal with the canonical list. Currently the list lives in pi_monitor at `work/work_source.py:194-198`; it moves here.

### Commit 4 — `kaplansky`: stop importing pi_monitor

**File:** math: `math/src/mathlint/protocol/wire_types.py` (new module)

```python
"""Math re-export of pi_monitor's wire types.

Per the institution's import rule:
- pi_monitor owns the wire protocol (zero project knowledge).
- math consumes pi_monitor (one direction only).
- kaplansky consumes math only.
- research-institution composes all three.

The re-exports here let kaplansky import wire types from math (its
only allowed import) without reaching across to pi_monitor. The
types are still defined in pi_monitor; math is a thin facade.
"""
from __future__ import annotations

from pi_monitor.work.work_source import (
    DecisionKind,
    SourceRevision,
    WorkRequest,
)
from pi_monitor.protocol.wire_models import (
    ExecutionReportWireModel,
    SourceDecisionWireModel,
    SourceRevisionWireModel,
    WorkRequestWireModel,
)

__all__ = [
    "DecisionKind",
    "SourceRevision",
    "WorkRequest",
    "ExecutionReportWireModel",
    "SourceDecisionWireModel",
    "SourceRevisionWireModel",
    "WorkRequestWireModel",
]
```

**File:** `kaplansky/src/kaplansky/launcher/verify.py:31`

Replace:
```python
from pi_monitor.work.work_source import DecisionKind
```
with:
```python
from mathlint.protocol.wire_types import DecisionKind
```

**File:** `kaplansky/src/kaplansky/work_selection.py:47`

Replace:
```python
from pi_monitor.work.work_source import SourceRevision, WorkRequest
```
with:
```python
from mathlint.protocol.wire_types import SourceRevision, WorkRequest
```

**File:** `kaplansky/tests/test_work_selection.py:36`

Same replacement.

**File:** `kaplansky/src/kaplansky/launcher/execution_report.py`

Delete the entire module. Kaplansky's `ExecutionReport` Pydantic class is a duplicate of pi_monitor's `ExecutionReportWireModel`. Replace all callers with `from mathlint.protocol.wire_types import ExecutionReportWireModel` (or directly from pi_monitor for tests).

**File:** `kaplansky/src/kaplansky/launcher/reports.py:32`

Delete the local `ExecutionReport` dataclass and the `last_n_report_lines` function (which produces a 4-tuple not a 5-tuple — a separate bug). Replace callers with the typed `ExecutionReportWireModel`.

### Commit 5 — `math`: optional `_deprecated_launcher/` cleanup (out of scope but adjacent)

**File:** `math/src/mathlint/orchestration/_deprecated_launcher/reports.py`

The `ExecutionReport` dataclass here is in the `_deprecated_launcher/` namespace, which is already slated for retirement per `@INV-0086`. After commits 1–4, this file may be deleted if it has no callers. If callers exist, migrate them to `ExecutionReportWireModel` (from pi_monitor, imported via `mathlint.protocol.wire_types`).

This commit is **optional and out of immediate scope.** Track separately if needed.

---

## 7. Open questions for the operator (Q1–Q4)

These four questions block execution of the proposed commits. Each is a deliberate design choice, not a fact to verify.

### Q1 — `RoleName` Literal: keep in pi_monitor or move to RI?

`pi_monitor/src/pi_monitor/work/work_source.py:181-190` declares:
```python
RoleName = Literal[
    "default",
    "primary",
    "supporting",
    "milestone",
    "research",
    "intake",
    "review",
    "maintenance",
]
```

These are generic domain role names. None of them name a specific program. But they're a closed vocabulary — does that violate `@ADR-0092`'s spirit (pi_monitor shouldn't enforce a list of accepted values), or is it OK because the values are generic?

**Option A — Keep as-is.** `RoleName` stays a `Literal[...]` in pi_monitor. Rationale: the values are generic; pi_monitor's role semantics are an internal concern.

**Option B — Move to RI.** Same treatment as `OperationKind` and `WorkspaceName`: pi_monitor says `RoleName = str`; RI owns the closed list. Rationale: consistency with the other two Literals.

**Recommendation:** Option B, for consistency. But the operator should decide.

### Q2 — Math re-export module location and naming

`mathlint.protocol.wire_types` is the proposed location for the re-export module. Alternatives:

| Name | Rationale |
|---|---|
| `mathlint.protocol.wire_types` | Matches pi_monitor's `protocol.wire_models` naming. |
| `mathlint.protocol.work_source` | Mirrors pi_monitor's `work.work_source` module path. |
| `mathlint.wire` | Shortest; clear. |

**Recommendation:** `mathlint.protocol.wire_types`. But the operator should confirm the convention they want for math's protocol-namespace module layout.

### Q3 — `ExecutionReport` parse in kaplansky: import directly or via math re-export?

Kaplansky reads the supervisor's `source-reports.jsonl`. The per-line shape is pi_monitor's `ExecutionReportWireModel`. Kaplansky has two import paths:

**Option A — Direct:** `from pi_monitor.protocol.wire_models import ExecutionReportWireModel`

Violates the operator's import rule (kaplansky should only import math). Same shape as the violations being fixed in commit 4.

**Option B — Via math re-export:** `from mathlint.protocol.wire_types import ExecutionReportWireModel`

Honors the rule; math is a thin facade. The re-export module from commit 4 already includes `ExecutionReportWireModel`.

**Recommendation:** Option B. This is consistent with the operator's stated rule.

### Q4 — Plan file: track this work as one doc or per-commit plan docs?

This audit document lives at the repo root: `research-institution/cross-repo-type-audit.md`.

**Option A — Single doc (this one).** All five commits stay here as a checklist. The plan is updated as commits land.

**Option B — Per-commit plan docs.** Each commit gets its own small plan doc under `research-institution/docs/operations/`. The audit doc cross-references them.

**Recommendation:** Option A for now (lower friction); promote to Option B if the operator wants audit-grade traceability per commit.

---

## 8. Cross-references

### Durable anchors cited in this document

- `@ADR-0014` — mathlint does not import program-named modules
- `@ADR-0091` — mathlint does not ship program launchers
- `@ADR-0092` — pi_monitor does not name mathlint (or any program)
- `@ADR-0025` — supervisor decomposition
- `@CTR-0020` — wire protocol authority (pi_monitor)
- `@INV-0093` — institution green gate is canonical wiring evidence
- `@CTR-0094` — WorkSourceProvider dispatch envelope
- `@INV-0086` — composition-root authority (the `_deprecated_launcher/` retirement)

### Related docs

- `docs/operations/wire-contracts.md` — operator-readable index of typed contracts in research-institution. (This audit focuses on cross-repo drift; `wire-contracts.md` documents the RI-side contracts.)
- `docs/operations/test-hardening-plan.md` — the Track 1 + Track 2 + Track 3 work that exposed the live-launch bug.
- `docs/operations/verification-gates.md` — the V-tier gate definitions and the `[v-wire]` tier that catches cross-repo composition defects.
- `docs/operations/launch-kaplansky-autonomously.md` — the operator's one-pager for live launches; references the institution gate.

### Related static checks

- `math/tests/static/test_no_program_named_modules.py` — math src/ has no program-name literals (BC-1 part 1).
- `math/tests/static/test_no_program_named_modules_in_tests.py` — math tests/scripts have no program-name literals (BC-1 part 2).
- `pi_monitor/tests/static/test_no_program_identity_in_fixtures.py` — pi_monitor tests have no program-identity literals (BC-4).
- `pi_monitor/tests/static/test_no_program_identity_in_src.py` — pi_monitor src/ has no program-identity literals (BC-5).
- `research-institution/research_institution/gates/aggregate.py::_repo_boundary_check` — runs BC-1 (math tests/scripts) + BC-4 (pi_monitor tests) + BC-5 (pi_monitor src/); reports `[repo-boundary] ok` or RED.

Both BC-4 and BC-5 were extended in commit `9ba4d48` to
also flag `research_institution` literals — the audit doc §4
noted that "RI is also a project" and pi_monitor's stable
surface shouldn't name it either.

`@ADR-0092` Literals on the pi_monitor side (in src/, tests/, and the wire-envelope docstrings) are now caught by the BC-4 + BC-5 pair: BC-4 scans `pi_monitor/tests/` and BC-5 scans `pi_monitor/src/`. Before BC-5 landed (commit `94e1576`), the Literals in `work_source.py:173-179, 194-198` were not caught by any static check — that gap is now closed.

### Static check (BC-5) — shipped

The proposed BC-5 static check landed in commit `94e1576`
(pi_monitor) + commit `1de8a6f` (research-institution). It
scans `pi_monitor/src/` for any program-identity literal
(`kaplansky`, `riemann`, `navier_stokes`, etc.) — code,
docstrings, comments, and config files (`.py`, `.toml`,
`.md`, `.txt`). No grandfather list: a program-identity
literal under `src/` is a code smell; the fix is to
refactor (extract a generic term, move the example to a
docstring outside `src/`, etc.), not to grandfather.

The check was extended in commit `9ba4d48` to also flag
``research_institution`` literals — the audit doc §4
noted that "RI is also a project" and pi_monitor's
stable surface shouldn't name it either. The sibling
BC-4 check (tests/) was extended the same way for
consistency.

This check is the durable enforcement of `@ADR-0092`
going forward. After commits 2 + BC-5 land, any future
reintroduction of program literals in pi_monitor src
fails CI.

---

## 9. Status checklist

- [x] Q1–Q4 written, awaiting operator answers
- [x] Operator answers Q1–Q4 (Q1: RoleName Literal stays in pi_monitor; Q2: mathlint.protocol.wire_types; Q3: via math re-export as ExecutionReportWireModel; Q4: single audit doc)
- [x] Commit 1 — pi_monitor wire-drift fix + cross-repo round-trip test (`91eb118`)
- [x] Commit 2 — pi_monitor `@ADR-0092` Literal cleanup + docstring scrub (`89bfb56`)
- [x] Commit 3 — RI duplicate wire class deletion + canonical vocabularies (`09ccc7d`)
- [x] Commit 4a — math adds `mathlint.protocol.wire_types` facade + facade-contract test (`abfdc95`)
- [x] Commit 4b — kaplansky imports via math re-export; execution_report.py / reports.py retained (`b56d2f2`)
- [x] BC-5 — pi_monitor src/ static check for program-identity literals (commits `94e1576` + `1de8a6f`)
- [x] AGENTS.md carve-out documentation (commit `5ad6bba`)
- [x] Commit 5a — pi_monitor ExecutionReportWireModel absorbs `recorded_unix` (`504ad51`)
- [x] Commit 5b — kaplansky readers delegate to canonical wire model; legacy `ts` field preserved via `LegacyCompatibleReport` wrapper (`6630b3f`)
- [~] Commit 5c — math `_deprecated_launcher/reports.py` cleanup: NOT DONE. The deprecated namespace is scheduled for retirement as a unit; its only consumer is the deprecated `activity.py` (which is itself only consumed by other deprecated modules). Out of scope per `@INV-0086`.
- [x] Commit 6 — math/src/ drops the two TYPE_CHECKING-only imports of `research_institution.*`; `SourceDecision` is now imported from `pi_monitor.work.work_source` (the canonical wire owner). `configured_provider`'s dishonest `-> SourceDecision` annotation fixed to `-> dict[str, object]` (matches the actual return). (`a207044`)
- [x] Institution gate GREEN via canonical recipe (`RESEARCH_INSTITUTION_VWIRE_DIRECT=1 bash scripts/verify-institution.sh`): all 7 tiers pass
- [ ] Live launch succeeds (operator-driven; not part of this plan's automated verification)

## 10. Corrections to the audit (resolved)

- **Section 5.1 / Section 6 commit 4** listed kaplansky's `launcher/execution_report.py` and `launcher/reports.py` as duplicates of pi_monitor's `ExecutionReportWireModel`. RESOLVED via commit 5a/5b: the canonical wire model absorbed `recorded_unix`; kaplansky's readers now delegate to it via the math facade. The legacy `ts` field (older supervisor version) is preserved by a thin `LegacyCompatibleReport` wrapper that adds only the `ts` fallback on top of the canonical model.
- The deprecated math `_deprecated_launcher/reports.py` is NOT DONE: the deprecated namespace retirement is tracked separately per `@INV-0086`. The namespace is already isolated (only consumed by other deprecated modules); retiring it requires the broader deprecated-namespace cleanup.
- **Section 2 import-rule grep** found two `TYPE_CHECKING`-only imports of `research_institution.contracts.source_decision.SourceDecision` in math (`mathlint.program_providers:45`, `mathlint.orchestration.real_source:43`). RESOLVED in commit `a207044`: the imports were replaced with direct runtime imports of `pi_monitor.work.work_source.SourceDecision` (pi_monitor already exposes the same union type, so no semantic change). In `real_source.py`, the `configured_provider` annotation was also fixed: it claimed `-> SourceDecision` but the body returned a `dict[str, object]` after `decision_to_dict(decision)`. The annotation now reads `-> dict[str, object]`, the `cast(...)` wrapper and `# type: ignore` comment are dropped. After this commit, math/src/ has zero imports of `research_institution.*` (runtime or static).

## 11. End state

After commits 1–5 + BC-5, the cross-repo wire-canonicalization audit is complete:

| Concern | Before | After |
|---|---|---|
| Live-launch wire-drift bug | `execution_report_to_dict` emitted `digest` not `envelope_digest`; math's `LiveSource` rejected every round-trip | `ExecutionReportWireModel.from_dataclass()` is the sole emit path; first `report_result` round-trip succeeds |
| `OperationKind` / `WorkspaceName` Literals in pi_monitor | Pin program identities (mathlint-research, kaplansky-workspace, etc.) on the stable surface — @ADR-0092 violations | Both are `str` on pi_monitor's surface; canonical Literals live in research-institution's `contracts.source_decision` |
| `RoleName` Literal | Stays in pi_monitor (generic vocabulary, not program identities) | Unchanged — confirmed Q1 |
| Duplicate wire-dict classes in RI | `SourceRevisionWireDict`, `WorkRequestWireDict`, `SourceDecisionWireDict` (Pydantic re-declarations) | Deleted; replaced with re-export aliases for pi_monitor's canonical wire models |
| Kaplansky's direct pi_monitor imports | `from pi_monitor.work.work_source import ...` in 3 places | All 3 import via `mathlint.protocol.wire_types` |
| Kaplansky's duplicate `ExecutionReport` readers | Local Pydantic + dataclass (modeled the on-disk JSONL shape, not the wire frame) | Replaced with a thin `LegacyCompatibleReport` wrapper that delegates core fields to `ExecutionReportWireModel` (via math facade); preserves legacy `ts` field fallback |
| BC-4 (pi_monitor tests) | Scans `tests/` for program-identity literals | Wired into institution gate's `repo-boundary` check |
| BC-5 (pi_monitor src/) | Not scanned | New static check; wired into institution gate alongside BC-4. Extended to flag `research_institution` literals (the audit doc §4 noted "RI is also a project"). |
| AGENTS.md exempt-file documentation | Implicit grandfather | Explicit carve-out for `tests/mathlint_fixture/`, `tests/static/`, and BC-5's no-grandfather policy for `src/` |
| Deprecated math `_deprecated_launcher/reports.py` | Reads on-disk JSONL shape | Not deleted; deprecated namespace retirement is tracked separately per `@INV-0086` |
| Cross-repo TYPE_CHECKING exceptions (math → RI) | 2 hits (pre-existing) | RESOLVED (commit `a207044`); math now imports `SourceDecision` from pi_monitor (the canonical wire owner) instead of RI (the OS layer). |

Institution gate: GREEN (all 7 tiers pass via canonical recipe).
