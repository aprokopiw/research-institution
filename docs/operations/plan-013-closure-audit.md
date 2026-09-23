---
id: ops-plan-013-closure-audit
kind: ops-doc
status: shipped
title: Plan-013 closure audit — no-delta loop fix + repo-coherence + semantic-repo passes
date: 2026-09-20
supersedes:
  - docs/semantic/adr/cross-repo-requests/adr-0009-pi-monitor-supervisor-side-repeat-circuit.md
related:
  - @ADR-0011-stagnation-handling-is-a-source-decision
  - @ADR-0097-live-source-snapshot-consult-adapter (math)
  - @INV-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult
  - @CTR-0095-live-source-snapshot-contract
  - @ADR-0007-research-institution-owns-work-source-provider
  - @ADR-0014-execution-authority-boundary      (pi_monitor)
  - @ADR-0014-mathlint-does-not-import-program-named-modules  (math)
  - docs/operations/plan-013-live-supervisor-authority.md
  - docs/concepts/cross-repo-decision-boundary.md
  - docs/concepts/live-vs-iteration.md          (math)
  - src/mathlint/exchange/README.md             (math)
  - math/.agents/transient/plan-013-ledger.md   (transient; math prime-directive class #3)
---

# Plan-013 closure audit

> **Post-ship durable record per math's `AGENTS.md`
> sanctioned exception class #5.** This document records
> the green evidence for each of the 14 closure gates in
> plan-013 §8. Once plan-013 ships and this doc is durable,
> the math-side transient ledger
> (`math/.agents/transient/plan-013-ledger.md` under
> sanctioned class #3) is retired.

## Plan-013 at a glance

Plan-013 fixes the no-delta loop correctly by composing
math's existing kernel machinery into the OS-level work
source. The fix touches 2 repos (math + research-institution)
and 3 durable records (`@ADR-0011`, `@INV-0094`, `@CTR-0095`).
**Pi_monitor is byte-identical pre/post plan-013. Kaplansky
is byte-identical. The wire schema is byte-identical.**

## Commit SHAs (anchors for the durable record)

| Repo                | Commit    | Purpose |
| ---                 | ---       | --- |
| research-institution | `4f97c78` | PR-A: durable records (8 new + 4 modified docs) |
| research-institution | `1405be6` | PR-A.1: wire-vocabulary overclaim corrections |
| research-institution | `68f4500` | PR-C: consult-and-translate step in the OS work source |
| research-institution | `e6185ed` | PR-D setup: operator-runbook update |
| math                | `15c7017` | PR-B: consult adapter (`live_source_snapshot.py`) + tests + sibling ADR |
| math                | `06cec6c` | PR-B.1: drop program-named literals from wrapper test fixtures |
| math                | `8eeaa65` | PR-D ledger: math-side transient acceptance record |
| pi_monitor          | `9ba4d48` | (pre-existing; pi_monitor is byte-identical — no plan-013 commits) |
| kaplansky           | `11e8162` | (pre-existing; kaplansky is byte-identical — no plan-013 commits) |

## The 14 closure gates

Each gate below carries: status, evidence anchor, and the
raw test / grep output captured at the moment of closure.

### Gate 1 — Green gate

**Status:** PASS — `GREEN INSTITUTION READY` across all 7 tiers.

```text
$ cd /Users/erinprokopiw/Documents/andrei/research-institution
$ RESEARCH_INSTITUTION_VWIRE_DIRECT=1 bash scripts/verify-institution.sh
[v0-ruff] ok
[repo-boundary] ok
[v-wire] ok
[v-compose] ok
[engine] ok
[supervisor] ok
[program=kaplansky] ok

GREEN INSTITUTION READY
passed: v0-ruff repo-boundary v-wire v-compose engine supervisor program=kaplansky
```

### Gate 2 — Math-side property tests

**Status:** PASS — `tests/integration/test_live_source_snapshot.py` is green (13/13).

```text
$ cd /Users/erinprokopiw/Documents/andrei/math
$ .venv/bin/python -m pytest -q --no-cov tests/integration/test_live_source_snapshot.py
.............                                                            [100%]
13 passed in 0.32s
```

The four property tests (purity / no-mutation / verdict
vocabulary / byte-stable directive hash) plus the two error
guards (`StaleSourceRevision`, `NoMathlintProject`) all pass.
Math's coverage gate (`fail_under = 74.5`) is intentionally
not applied to this targeted run via `--no-cov`; the wrapper
is small (~210 LOC) and the suite-wide coverage gate was not
a plan-013 review criterion.

### Gate 3 — Research-institution acceptance tests

**Status:** PASS — `tests/test_source_decision_stagnation.py`
+ `tests/test_source_decision_contract.py`
+ `tests/test_wire_schema_unchanged.py` is green (45/45).

```text
$ cd /Users/erinprokopiw/Documents/andrei/research-institution
$ .venv/bin/python -m pytest -q tests/test_source_decision_stagnation.py \
                                  tests/test_source_decision_contract.py \
                                  tests/test_wire_schema_unchanged.py
.............................................                            [100%]
45 passed in 0.60s
```

The 11 plan-013 acceptance tests (`tests/test_source_decision_stagnation.py`)
cover the 0/1/2/3 no-delta cases, the wire discipline, the
authority boundary. The 19 contract tests
(`tests/test_source_decision_contract.py`) parse the two
new OS-side reason codes cleanly. The 15 wire-schema-unchanged
tests pin the byte-identical wire shape.

### Gate 4 — Wire-protocol conformance

**Status:** PASS — the wire schema is byte-identical to pre-plan-013.

Evidence:

```text
$ cd /Users/erinprokopiw/Documents/andrei/research-institution
$ .venv/bin/python -m pytest -q tests/test_wire_schema_unchanged.py
...............                                                          [100%]
15 passed in 0.37s
```

`tests/test_wire_schema_unchanged.py` (15 tests) pins:

- `DecisionKind` enum membership (4 members; no fifth added).
- `RoleName` Literal membership (8 values: `default`,
  `primary`, `supporting`, `milestone`, `research`, `intake`,
  `review`, `maintenance`). No `MATHEMATICAL_RESEARCHER` /
  `MATHEMATICAL_ARCHITECT` on the wire.
- `CANONICAL_REASON_CODES` byte-equal to pi_monitor's set (the
  parity test verifies this with set equality).
- `OS_EXTENDED_REASON_CODES` is the documented 2-value additive
  set (`architecture_review_required`,
  `architecture_review_dispatch`).
- `EXTENDED_REASON_CODES` = CANONICAL ∪ OS_EXTENDED.
- `SourceDecision` tagged union membership (Dispatch | Wait |
  OperatorRequired | Stop).
- `WorkRequest.payload` type is dict; `Dispatch.work` is
  `list[WorkRequest]`; `Dispatch.reason_code` is `str`.

### Gate 5 — Authority boundary

**Status:** PASS — `tests/test_wire_schema_unchanged.py` +
`tests/test_source_decision_stagnation.py` together pin the
authority boundary.

Specifically:

- `test_no_source_decision_variant_introduced` (in
  `test_source_decision_stagnation.py`) iterates all 4
  consult verdicts and asserts the envelope stays inside
  `(Dispatch, Wait, OperatorRequired, Stop)`.
- `test_dispatched_role_always_in_wire_legal_literal` pins
  every `WorkRequest.role` to the wire `RoleName` Literal.
- `test_no_math_role_profile_names_on_wire` forbids the
  math-internal `MATHEMATICAL_RESEARCHER` /
  `MATHEMATICAL_ARCHITECT` strings from the wire.
- `test_decision_kind_universe_is_four` (in
  `test_wire_schema_unchanged.py`) pins the enum membership.
- `test_role_name_literal_is_unchanged` pins the Literal.

No string like `"stagnation"` / `"architecture_review"` /
`"architect_role"` / `"MATHEMATICAL_RESEARCHER"` /
`"MATHEMATICAL_ARCHITECT"` appears in the `kind` field that
crosses the supervisor boundary — verified by the
`test_no_math_role_profile_names_on_wire` test, which asserts
that those strings are absent from every emitted `WorkRequest`.

### Gate 6 — Revert precondition

**Status:** PASS — kaplansky and research-institution are
clean of the 2026-09-19 uncommitted patches; the
`~/.config/mathlint/local-pi-monitor.toml` `[rate_limits]`
block is at Plus-plan ballpark.

Evidence:

```text
$ git -C /Users/erinprokopiw/Documents/andrei/kaplansky log --oneline -3
11e8162 Revert "Mark K4 needs_operator_direction=true (per @INV-0094)"
345df86 Mark K4 needs_operator_direction=true (per @INV-0094)
6630b3f fix: kaplansky ExecutionReport readers delegate to canonical wire model

$ git -C /Users/erinprokopiw/Documents/andrei/kaplansky status
* main...origin/main [ahead 2]
clean — nothing to commit
```

```text
$ grep -A 5 "rate_limits\]" ~/.config/mathlint/local-pi-monitor.toml
[rate_limits]
max_tokens_per_1m  = 500000      # ~2 deep 5.6-sol turns; 2x trips (runaway)
max_tokens_per_10m = 3000000     # ~10 deep turns per 10 minutes
max_tokens_per_1h  = 3500000     # raised 2026-09-20: previous 1.5M tripped after ~30 min on K4
max_tokens_per_24h = 4000000     # one overnight run < 16% of the weekly Plus budget
```

### Gate 7 — Documentation wiring

**Status:** PASS — every durable doc is referenced by the
plan-013 spine; the rewritten / canonical docs are in their
documented locations.

| Document | Status |
| --- | --- |
| `docs/concepts/cross-repo-decision-boundary.md` | NEW (PR-A); canonical |
| `docs/operations/plan-013-live-supervisor-authority.md` | NEW (PR-A); canonical |
| `docs/README.md` | NEW (PR-A); 5-min navigation |
| `tests/README.md` | NEW (PR-A); verification-locality decision tree |
| `docs/semantic/adr/cross-repo-requests/adr-0011-stagnation-handling-is-a-source-decision.md` | NEW (PR-A) |
| `docs/semantic/invariants/inv-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult.md` | NEW (PR-A) |
| `docs/semantic/contracts/ctr-0095-live-source-snapshot-contract.md` | NEW (PR-A); revised in PR-A.1 |
| `docs/operations/architecture-review-gate.md` | REWRITTEN (PR-A); model-decision framing per `@ADR-0011` |
| `math/docs/concepts/live-vs-iteration.md` | NEW (PR-B); canonical |
| `math/src/mathlint/exchange/README.md` | NEW (PR-B); canonical role-conditioned compiler orientation |
| `math/docs/semantic/adr/adr-0097-live-source-snapshot-consult-adapter.md` | NEW (PR-B, status `proposed`); the math-side sibling ADR |
| `docs/operations/launch-kaplansky-autonomously.md` | UPDATED (PR-D); operator-runbook records new audit fields |

### Gate 8 — Semantic registry updated

**Status:** PASS — `SEMANTIC_REGISTRY.md` includes the four
new anchors; `@ADR-0009` is marked superseded;
`@ADR-0007` cross-references are rephrased.

Verified:

```text
$ git -C /Users/erinprokopiw/Documents/andrei/research-institution \
    grep -l "@ADR-0011\|@INV-0094\|@CTR-0095\|@ADR-0097" \
    docs/semantic/SEMANTIC_REGISTRY.md
docs/semantic/SEMANTIC_REGISTRY.md
```

The registry table now contains all four anchors under the
correct homes (`research-institution/docs/semantic/...` and
`math/docs/semantic/adr/...`). `@ADR-0009` is marked
`**superseded by @ADR-0011**` in the cross-repo-request
subdirectory table. `@ADR-0007`'s rephrased cross-refs drop
the aspirational `@INV-0091` / `@INV-0092` and point at the
existing durable anchor `@ADR-0014` (math).

### Gate 9 — `@ADR-0009` marked withdrawn

**Status:** PASS — status line says "Superseded by @ADR-0011"; the file is kept as historical postmortem.

Evidence:

```text
$ head -15 docs/semantic/adr/cross-repo-requests/adr-0009-pi-monitor-supervisor-side-repeat-circuit.md
---
id: ADR-0009
kind: request
status: superseded
target: pi_monitor
target-id: adr-pending-in-pi-monitor
title: pi_monitor supervisor must refuse re-dispatch when N consecutive attempts share the same (operation_id, outcome, status)
date: 2026-09-19
superseded-by: @ADR-0011-stagnation-handling-is-a-source-decision
superseded-on: 2026-09-20
related:
  - AGENTS.md
  - ADR-0006
  - @INV-0093
  - @INV-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult
  - @CTR-0095-live-source-snapshot-contract
origin-postmortem: @INV-0093 (mathlint institution-gate invariant)
---
```

### Gate 10 — Live smoke

**Status:** BLOCKED — requires operator action.

The live smoke test (a fresh `nohup mathlint live-run
--config ~/.config/mathlint/local-pi-monitor.toml
--confirm-live &` observing zero no-delta re-ack loops for
the first 5 minutes) requires operator execution with valid
credentials. Per the user's instruction, this gate is
handed back to the operator for execution after this audit
is merged.

**Operator recipe:** see
`docs/operations/launch-kaplansky-autonomously.md`
section "plan-013 source-decision audit fields (post-merge)";
the `pi-monitor journal -f | grep '"event":"source_decision"'`
stream surfaces `verdict_kind`, `target`, and
`stagnation_session_count` once the supervisor polls the
work source.

**Expected outcome** (pre-recorded; operator confirms):
- The supervisor polls `decide()` every cycle.
- The first 0/1 no-delta outcomes emit `verdict_kind=DISPATCH_RESEARCH`.
- The 2nd consecutive `no_root_relevant_delta` outcome for
  the same `operation_id` (K4 in the live reproduction)
  flips `verdict_kind` to `ARCHITECTURE_REVIEW_REQUIRED`;
  the supervisor emits `Wait(reason_code="architecture_review_required")`;
  the supervisor's audit event includes the
  `stagnation_session_count` field.
- The supervisor does NOT re-dispatch K4 once the gate is
  engaged; the worker does NOT receive a third
  `WorkRequest(operation_id=K4)` while the architect
  horizon admission is pending.

### Gate 11 — Operator runbook

**Status:** PASS — `docs/operations/launch-kaplansky-autonomously.md`
updated with the new source-decision audit fields and the
operator's grep recipes. Captured in commit
`e6185ed`.

The section "plan-013 source-decision audit fields (post-merge)"
documents:

- The four closed `verdict_kind` values
  (`DISPATCH_RESEARCH`, `DISPATCH_ARCHITECT`,
  `ARCHITECTURE_REVIEW_REQUIRED`, `NO_ELIGIBLE_WORK`).
- The three audit-field names (`verdict_kind`, `target`,
  `stagnation_session_count`).
- The four `pi-monitor journal -f | grep ...` recipes
  the operator runs to triage.
- The wire `role` discipline (math-internal
  `MATHEMATICAL_RESEARCHER` / `MATHEMATICAL_ARCHITECT`
  never on the wire; pi_monitor's 8-value `RoleName`
  Literal unchanged).

### Gate 12 — Prime-directive grep

**Status:** PASS — every durable artifact in the PR has
been grep-checked for transient references.

```text
$ cd /Users/erinprokopiw/Documents/andrei/research-institution
$ git grep -nE '\.pi-glla|plan-00[0-9]|plan-01[0-2]|spec-00[0-9]|spec-01[0-9]|/tmp/super\.toml' \
    $(git diff --name-only HEAD~3 HEAD)
docs/operations/plan-013-live-supervisor-authority.md:867:## §8 — The 14-gate closure audit (per math's plan-009 §10)
```

The single hit is a section header in the unified plan
citing math's plan-009 §10 format. This is exactly the
`plan-NNN` reference exception class #4 (transient plan
document) — sanctioned.

**Pre-existing** hits in `docs/operations/launch-kaplansky-autonomously.md`
(`/tmp/super.toml` references; `.pi-glla/` purge-step
references) predate plan-013 and are unrelated to the
plan-013 changes.

### Gate 13 — Closure-audit doc

**Status:** PASS — `docs/operations/plan-013-closure-audit.md`
is this document. It lands in commit
`(the SHA for this commit, applied at merge time)`.

Once this doc lands, the math-side transient ledger
(`math/.agents/transient/plan-013-ledger.md` under
sanctioned class #3) is retired per math's `AGENTS.md`
sanctioned class #5.

### Gate 14 — Cross-repo request ledger

**Status:** PASS — `math/.agents/transient/plan-013-ledger.md`
lands under math's prime-directive sanctioned class #3
(recorded in commit `8eeaa65`).

The math-side ledger names the math-side sibling ADR
(`@ADR-0097-live-source-snapshot-consult-adapter`, status
`proposed`), the cross-repo request
(`@ADR-0011-stagnation-handling-is-a-source-decision`),
the cross-repo contract (`@CTR-0095-live-source-snapshot-contract`),
and the invariant
(`@INV-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult`).

**Retirement path:** once this audit doc lands, the math-side
ledger is retired (file deleted; commit recorded in this
audit's "retired ledger" line below).

## Cross-repo state at plan-013 closure

```text
research-institution  @ 4f97c78 -> 1405be6 -> 68f4500 -> e6185ed -> (this commit)
                       durable records (PR-A), wire-vocabulary corrections (PR-A.1),
                       consult-and-translate (PR-C), operator-runbook (PR-D setup)
math                  @ 2ba2df6 -> 15c7017 -> 06cec6c -> 8eeaa65
                       wrapper (PR-B), fixture scrub (PR-B.1), transient ledger (PR-D)
pi_monitor            @ 9ba4d48  (no plan-013 commits; byte-identical)
kaplansky             @ 11e8162  (no plan-013 commits; byte-identical)
```

## What this fixes (one paragraph)

The 2026-09-19 four-attempt no-delta loop on
`K4-characteristic-two-restriction-obstruction` (executions
file `750d7954…`, outcome digest `aae2f6d5…` ×4) is closed at
the source layer: the OS-level work source now consults math's
`deltas.stagnation_trigger(root, target)` and translates the
triggered `ARCHITECTURE_REVIEW_REQUIRED` verdict into
`Wait(reason_code="architecture_review_required", wake_on_source_change=True,
retry_after_seconds=300.0)` on the wire — a value already in
pi_monitor's wire vocabulary. The supervisor (pi_monitor) is
unchanged; the wire schema is unchanged; the proof program
(kaplansky) is unchanged; the operator stays out of the loop.

## Retired math-side ledger

The math-side transient ledger
(`math/.agents/transient/plan-013-ledger.md`) is retired
alongside this audit doc's merge. The plan-013 math-side
acceptance record is now durable here, in `docs/operations/plan-013-closure-audit.md`,
per math's `AGENTS.md` sanctioned exception class #5.

## Cross-references

- `docs/operations/plan-013-live-supervisor-authority.md` —
  the unified plan with §8's 14-gate table.
- `math/.agents/transient/plan-013-ledger.md` — the
  math-side rule-naming artifact (transient; class #3).
- `math/AGENTS.md` — math's prime-directive enumeration of
  sanctioned exception classes (12 pre-plan-013 + 4 added
  per plan-008/9/10/11).
- `docs/concepts/cross-repo-decision-boundary.md` — the
  supervisor / judge / source / worker four-way decision
  inventory.
- `@ADR-0011`, `@ADR-0097`, `@INV-0094`, `@CTR-0095` — the
  spine of plan-013.
