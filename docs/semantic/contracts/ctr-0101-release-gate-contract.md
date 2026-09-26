---
id: CTR-0101
kind: contract
status: active
title: Release-gate contract — typed ReleaseReport schema, seven canonical rows, gate-report digest
introduced: 2026-09-25
related:
  - @ADR-0096-audit-close-out-runtime-evidence
  - @CTR-0096-audit-close-out-runtime-evidence-contract
  - @CTR-0095-prime-directive-check-script-contract
  - @INV-0093-institution-green-gate-canonical
  - @INV-0094-no-delta-loop-source-stagnation-consult
  - @ADR-0014-program-agnostic-mathlint-imports
  - @ADR-0091-mathlint-ships-no-program-launchers
  - research_institution.gates.verify_simulation.release.ReleaseReport
  - research_institution.gates.verify_simulation.release.ReleaseRunner
  - research_institution.gates.verify_simulation.mutation.MutationAggregator
  - research_institution.gates.verify_simulation.mutation_critical_mutants.toml
  - research-institution/docs/semantic/CLAIM_MANIFEST.toml
  - .specify/specs/10-verification-release-closure/META.md
supersedes: []
---

# CTR-0101: Release-gate contract

## Boundary

`research-institution/research_institution/gates/verify_simulation/release.py`
is the single canonical implementation of the release-gate
aggregator. The CLI tier selector `--tier release` and the
mutation gate (`mutation.py`) consume the typed contracts
defined here. Every other release-style aggregator in the
institution is forbidden; this contract pins the schema so
the cycle adapter can gate the closing entry against a
stable wire shape.

## Producer

`research-institution/research_institution/gates/verify_simulation/release.py`
(introduced 2026-09-25 by entry `10-verification-release-closure`).
The CLI surface is `--tier release` on the canonical
`research-institution verify-simulation` Typer group.

## Required behaviour

### Typed `ReleaseReport`

```python
@dataclass(frozen=True, slots=True)
class ReleaseReport:
    rows: tuple[ReleaseRow, ...]  # exactly 7; see Closed row set
    seed: int | None = None
    elapsed_seconds: float = 0.0
    artifacts_dir: Path | None = None
```

The report's `verdict` property is `PASS` iff every row's
status is `PASS` or `NOT_APPLICABLE`. Any other row status
yields `FAIL`.

### Closed row set (exactly seven)

The seven row `check_name` values are the closed set:

| # | check_name |
|---|---|
| 1 | `every_primary_tier_has_at_least_one` |
| 2 | `every_required_claim_has_evidence` |
| 3 | `every_scenario_has_metadata` |
| 4 | `every_critical_mutant_killed` |
| 5 | `flake_audit_clean` |
| 6 | `documentation_truth_clean` |
| 7 | `prime_directive_enforcement_clean` |

`ReleaseReport.__post_init__` enforces the cardinality
exactly 7 + the names form the closed set above.

### `gate_report_digest`

```
sha256(JSON-serialize({
    rows: [...sorted by check_name...],
    verdict: ...,
    seed: ...,
    elapsed_seconds: ...,
}, sort_keys=True, separators=(",", ":")))
```

The digest is byte-stable across Python versions because
the rows are sorted by `check_name` and `sort_keys=True` +
ASCII separators are used. The digest becomes the closing
entry's `gate_report_digest` field in META.md.

### Mutation gate (`mutation.py`)

The mutation aggregator reads the canonical 15 critical
mutants from
`research_institution/gates/verify_simulation/mutation_critical_mutants.toml`
(durable production-side data file). Each `MutationKiller`
carries a `killer_test` (pytest node-id) and an optional
`scenario` (verify-simulation scenario name). The
aggregator's verdict is `PASS` iff every killer has a
non-`UNRESOLVED` killer test.

### Inline flake sample + dedicated 20× audit

The release gate's row 5 performs `INLINE_FLAKE_RUNS = 5`
inline hermetic runs (sub-second each) for the CLI invocation.
The dedicated 20× repeated random-order audit lives at
`tests/simulation/test_flake_audit.py`; it runs the canonical
`FLAKE_AUDIT_SCENARIO = "happy-three-cycle"` scenario.

### CLI integration

```
python -m research_institution verify-simulation --tier release
```

Exit codes follow the gate-status algebra (per
constitution-verify §3):

| Exit | Meaning |
|---|---|
| 0 | every release row PASS or NOT_APPLICABLE |
| 1 | at least one row FAILed |
| 78 | release prerequisites missing (BLOCKED) |

### Cross-repo claim

`docs/semantic/CLAIM_MANIFEST.toml` enumerates the seven
claims; the integrity test
`tests/static/test_claim_manifest_integrity.py` asserts every
required claim has ≥1 evidence node-id.

## Consumers

- `tests/static/test_claim_manifest_integrity.py` (the
  seven-row claim manifest integrity check)
- `tests/static/test_documentation_truth.py` (row 6)
- `tests/static/test_random_order_determinism.py` (row 5)
- `tests/simulation/test_flake_audit.py` (row 5)
- `tests/test_mutation_survival.py` + `tests/test_invariants.py` +
  `tests/test_contracts.py` (row 4 — the 15 critical mutants)
- `scripts/spec-kit-cycle.sh` (closes the program)

## Failure atomicity

A release-tier invocation is atomic: every row is computed
inside a single `ReleaseRunner.run()` call. The runner
catches no exceptions; any uncaught exception from a row
function surfaces as a Python traceback + exit code 1.

## Performance / runtime budgets

- Inline flake sample: ≤ 5 seconds.
- Full 20× flake audit (test): ≤ 30 seconds.
- Mutation aggregator: < 1 second (pure-Python TOML load).
- Documentation truth audit: < 5 seconds.
- Prime-directive enforcement: ≤ 60 seconds (per the
  subprocess timeout).
- Total release tier: ≤ 90 seconds on a clean checkout.

## Cross-references

- All eleven spec dirs (`.specify/specs/{00..10}/`).
- `@CTR-0095-prime-directive-check-script-contract`
  (canonical strengthened-grep script).
- `@CTR-0096-audit-close-out-runtime-evidence-contract`
  (per-entry attestation schema).
- `@INV-0093-institution-green-gate-canonical`.
