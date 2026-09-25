# 04 — META (audit-close-out template)

```toml
[meta]
spec_id = "04-stateful-sample-research"
owner_repo = "math"
owner_repos = ["math", "research-institution"]
baseline_sha = "PENDING"
completion_sha = "PENDING"
gate_report_digest = "PENDING"
durable_anchors_added = []
durable_anchors_cited = [
  "@ADR-0014",   # mathlint does not import program-named modules
  "@ADR-0088",   # sample fixture is not a proof program
  "@ADR-0089",   # sample as canonical CI fixture
  "@INV-0088",   # sample requires no external state
  "@CTR-0085",   # sample dispatch envelope shape
  "@CTR-0020",   # three-repo wire contract
  "@ADR-0095-prime-directive-mechanical-enforcement",
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
]
transient_anchors_retired = []
unblocked_dependents = ["06-autonomous-composed-simulation"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"
section_2  = "PASS"
section_3  = "PASS"
section_4  = "PASS"
section_5  = "PASS"
section_6  = "PASS"
section_7  = "PASS"  # this whole entry IS §7
section_8  = "PASS"
section_9  = "PASS"  # canonical scenarios ship here; entry 06 cites by name
section_10 = "PASS"
section_11 = "PASS"
section_12 = "NOT_APPLICABLE"  # no new cross-repo records (uses math's)
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | Readiness envelope byte-for-byte preserved | `test_readiness_bytes_unchanged.py` | PENDING |
| 2 | Simulation reducer inactive without env | `simulation_register.py` review + test | PENDING |
| 3 | Six canonical scenarios produce expected transcripts | `tests/self_test/test_simulation_happy_three.py` and 5 more | PENDING |
| 4 | No program-named import in generic mathlint | `tests/static/test_no_program_named_imports.py` | PENDING |
| 5 | `ProgramProviders.report_sink` extension shipped with 4 tests | per-test green | PENDING |
| 6 | `make check-prime-directive` clean at math HEAD | per-commit | PENDING |
| 7 | Entry 00 §7 sub-rules conform | `tests/static/test_constitution_consistency.py` (RI) | PENDING |
| 8 | Entry 01 trio green at math HEAD | per-file `pytest -q` | PENDING |
| 9 | Mutation challenges killed | `tests/self_test/test_idempotent_report.py` etc. | PENDING |
| 10 | Six canonical scenarios present | `find math/src/mathlint/self_test/sample_program/scenarios/` | PENDING |
| 11 | Simulation writes restricted to disposable root | integration tests | PENDING |
| 12 | `tests/self_test/` collection deterministic under --no-cov | `pytest --collect-only --no-cov -q` | PENDING |

## Sign-off

> When all twelve rows are `PASS`, this META is valid; entry 04 is
> closed; entry 06 unblocked.
