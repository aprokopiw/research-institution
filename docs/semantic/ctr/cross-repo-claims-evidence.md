---
created: 2026-09-23
status: live
tier: V2
---

# Cross-repo composed-state evidence matrix

**Companion file**: `scripts/cross_repo_claims_evidence.py` (executable).

**Purpose.** Distill the eight most-consequential cross-repo behavioral
claims into a single evidence tier (V2) that an operator can re-run to
confirm the institution's composed state is wired correctly.

Each claim is backed by one or more existing test files. The harness
runs them in aggregate and reports per-claim pass/fail. All eight claims
must pass; any failure is a **RED-GREEN** failure on that claim.

## How to run

```sh
cd research-institution
.venv/bin/python scripts/cross_repo_claims_evidence.py
```

Output:

```
=== Cross-repo claim-by-claim evidence harness ===
=== generated at <utc-iso> ===
repos under test: research-institution, math, pi_monitor

CLAIM-1  PASS        15/0   rc=0    ...
CLAIM-2  PASS         2/0   rc=0    ...
...

Total: 8/8 claims PASS
Matrix saved to /tmp/verify/claims-matrix.json
```

Exit code `0` if 8/8 pass; `1` otherwise.

## Claim matrix

| ID | Claim | Tier | Evidence files | Status 2026-09-23 |
|-----|-------|------|----------------|---------------------|
| CLAIM-1 | Wire schema byte-identical to pre-plan-013 (`@CTR-0021`) | V2 | `research-institution/tests/test_wire_schema_unchanged.py` | PASS |
| CLAIM-2 | pi_monitor <-> math cross-repo wire round-trip | V2 | `pi_monitor/tests/test_cross_repo_wire_round_trip.py` | PASS |
| CLAIM-3 | math `consult()` wrapper purity | V2 | `math/tests/integration/test_live_source_snapshot.py` | PASS |
| CLAIM-4 | `compute_directive_content_hash()` byte-stability | V2 | `math/tests/integration/test_live_source_snapshot.py` | PASS |
| CLAIM-5 | Stagnation -> verdict_kind translation table | V2 | `math/tests/integration/test_live_source_snapshot.py` | PASS |
| CLAIM-6 | OS-side WorkRequest payload injection | V2 | `research-institution/tests/test_source_decision_stagnation.py`, `...contract.py` | PASS |
| CLAIM-7 | CANONICAL_REASON_CODES cross-repo byte-identity | V2 | `research-institution/tests/test_cross_repo_type_identity.py` | PASS |
| CLAIM-8 | OS composes with real math projects (property test) | V2 | `research-institution/tests/test_composed_dispatch_property.py` | PASS |

## Adversarial challenge (mutation test)

The CLAIM-3 / CLAIM-5 evidence was challenged by deliberate mutations
on 2026-09-23:

- **Mutation A** (verdict swap): swapped
  `verdict_kind=VERDICT_DISPATCH_RESEARCH` ↔
  `verdict_kind=VERDICT_DISPATCH_ARCHITECT` in the wrapper.
  → `test_no_stagnation_dispatch_research` correctly failed with
  `AssertionError: assert 'DISPATCH_ARCHITECT' == 'DISPATCH_RESEARCH'`
  → Test discriminates bug from correct implementation.

- **Mutation B** (stagnation count suppression): replaced
  `trigger.no_delta_count` with the literal `0`.
  → `test_two_no_delta_architecture_review_required` and
  `test_three_no_delta_with_architect_synthesis_dispatch_architect`
  correctly failed with `assert 0 == 3`.
  → Test discriminates bug from correct implementation.

Both mutations were reverted after capture.

## Status semantics

| Overall | Meaning |
|---------|---------|
| 8/8 PASS | GREEN-V2 — composed state matches the eight contracts above. |
| < 8/8 PASS | RED — one or more claims unverified; consult the harness output and run the individual test file with `-v` to localize. |

A bare V2 GREEN does NOT imply V3 (mutation) or V4 (release) GREEN.
This harness is one tier; full release assurance requires
`scripts/verify-institution.sh --live` (operator-only) plus the math
`make check-tests-integrated` coverage gate.

## Excluded failures (pre-existing)

The pre-existing environmental failures (tested on git stash for
identicity) are excluded from this matrix:

- `research-institution/tests/test_cold_start_hermetic.py`:
  subprocess uses pi_monitor's `.venv/bin/python3` which lacks
  `research_institution` (pip-install missing in the venv). Pre-existed
  before plan-013.
- math: `tests/integration/test_frontier_scheduler_live_wiring.py::test_receipt_binds_to_live_commit`
  (stale receipt, HEAD moved).
- math: `tests/integration/test_pi_monitor_lifecycle.py::test_lifecycle_verify_produces_documented_lines`
  (missing `mathlint.protocol` module; it's `mathlint.exchange`).
- math: `tests/contracts/test_no_call_outside_composition_root.py::test_no_call_outside_composition_root`
  (5 hits in `_deprecated_launcher/` modules; pre-existing).
- pi_monitor: 9 unrelated streaming / supervision / task-source
  tests (pre-existing on git stash diff).

The harness does not invoke any of these.

## Future enhancements (low priority)

Per `@verification` skill priority ladder:

- **Priority 4** — high-leverage generative opportunity. The math
  `consult()` wrapper is currently tested only via deterministic
  monkey-patches (V1). A Hypothesis property-based fuzzing layer
  over `verdict_kind` × `stagnation_count` × `directive_role` would
  push CLAIM-3/5 to V3 (deeper adversarial assurance) at modest cost.
- **Priority 5** — actionable structural coverage gap. The seven
  foundational tests in CLAIM-1/2/6/7 exercise the wire shape;
  adding a structural cross-repo integration test that mocks
  `pi_monitor.request("decide_next")` -> `mathlint.live_source_snapshot.consult()`
  on a real (synthetic) MathProject would close the remaining
  V2 -> V3 gap. Owner: cross-repo maintainer.
