# 06 — META (audit-close-out template)

```toml
[meta]
spec_id = "06-autonomous-composed-simulation"
owner_repo = "research-institution"
owner_repos = ["research-institution", "math", "pi_monitor"]
baseline_sha = "PENDING"
completion_sha = "PENDING"
gate_report_digest = "PENDING"
durable_anchors_added = []
durable_anchors_cited = [
  "@ADR-0006",   # research-institution scope
  "@ADR-0007",   # work-source provider slot
  "@ADR-0011",   # stagnation is a source decision
  "@INV-0093",   # green gate
  "@INV-0094",   # no-delta loop source-side
  "@CTR-0020",   # three-repo wire
  "@CTR-0094",   # work-source dispatch envelope
  "@ADR-0095-prime-directive-mechanical-enforcement",
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
]
transient_anchors_retired = []
unblocked_dependents = ["07-deployment-canary-soak"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"
section_2  = "PASS"
section_3  = "PASS"
section_4  = "PASS"
section_5  = "PASS"  # action matrix: merge requires VG-4
section_6  = "PASS"  # no-second-supervisor (this entry composes existing supervisors)
section_7  = "PASS"
section_8  = "PASS"
section_9  = "PASS"  # this entry IS §9 — one source of simulation truth
section_10 = "PASS"
section_11 = "PASS"
section_12 = "PASS"
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `gates/verify_simulation/` exists | direct | PENDING |
| 2 | `verify-simulation` console script registered | `python -m ... --help` | PENDING |
| 3 | 14 canonical scenarios produce expected transcripts | per-scenario test | PENDING |
| 4 | 3 oracles each return `PASS` per scenario | per-scenario test | PENDING |
| 5 | No private supervisor method called | private-import grep test | PENDING |
| 6 | No manual finalize calls | grep test | PENDING |
| 7 | No scenario over budget silently | budget enforcement | PENDING |
| 8 | temp_root cleanup green | resource oracle | PENDING |
| 9 | 20 repeats of `happy-three-cycle` produce zero flake | `twenty-repeated-runs.sh` | PENDING |
| 10 | Entry 00/01/02/03/04/05 clauses hold at HEAD | per-entry META | PENDING |
| 11 | `transient-exemptions.toml` bumped | `tomllib.loads(...)` | PENDING |
| 12 | Mutation-test gate aggregator finds surviving critical mutant (entry 10 wired) | `NOT_APPLICABLE` here; entry 10 owns | PENDING |

## Sign-off

> When all twelve rows are `PASS` (with row 12's `NOT_APPLICABLE`
> resolved by entry 10), this META is valid; entry 06 is closed;
> entry 07 unblocked.
