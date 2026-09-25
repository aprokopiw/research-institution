# 10 — META (audit-close-out template)

```toml
[meta]
spec_id = "10-verification-release-closure"
owner_repo = "research-institution"
owner_repos = ["research-institution", "math", "pi_monitor", "kaplansky"]
baseline_sha = "PENDING"
completion_sha = "PENDING"
gate_report_digest = "PENDING"  # sha256 over --tier release's typed report blob
durable_anchors_added = [
  "@CTR-0101-release-gate-contract",
]
durable_anchors_cited = [
  "@ADR-0095-prime-directive-mechanical-enforcement",
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
  "@CTR-0020",
  "@CTR-0088",
  "@CTR-0094",
  "@INV-0093",
  "@INV-0094",
  "@ADR-0014",
  "@ADR-0091",
]
transient_anchors_retired = [
  # The transient guide `.agents/transient/test_and_simulation_suite.md`
  # is tombstoned at `.agents/transient/_retired/test_and_simulation_suite.retired.md`
  # with the strengthened-grep-clean filename; its retention path is
  # documented in this entry's plan §10.
]
unblocked_dependents = []  # this entry closes the program

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"
section_2  = "PASS"
section_3  = "PASS"
section_4  = "PASS"
section_5  = "PASS"
section_6  = "PASS"  # this entry IS VG-6 wire-up
section_7  = "PASS"
section_8  = "PASS"
section_9  = "PASS"
section_10 = "PASS"
section_11 = "PASS"
section_12 = "PASS"
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `--tier release` exits 0 | direct | PENDING |
| 2 | claim manifest resolvable for every required claim | `test_claim_manifest_integrity.py` | PENDING |
| 3 | mutation-test gate aggregator shows 0 surviving critical mutants | `mutation.py` | PENDING |
| 4 | 20× run flake audit clean | `test_flake_audit.py` | PENDING |
| 5 | documentation truth audit clean | `test_documentation_truth.py` | PENDING |
| 6 | transient guide tombstoned | `ls` test | PENDING |
| 7 | `make check-prime-directive-enforced` exits 0 in every repo | per-repo | PENDING |
| 8 | every entry META validated by entry 09's validator | entry 09's machinery | PENDING |
| 9 | every entry attestation resolves at current SHAs | entry 09's machinery | PENDING |
| 10 | Entry 00/03/08/09 twelve-clause holds | per-entry META | PENDING |
| 11 | `@CTR-0101-…` durable record present | `ls` | PENDING |
| 12 | random-order determinism proven | `test_random_order_determinism.py` | PENDING |

## Sign-off

> When all twelve rows are `PASS`, this META is valid; entry 10
> closes the program. No further entries planned. The eleven-spec
> durable memory is `.specify/specs/{00..10}/`; the transient
> guide that specified the program is tombstoned at
> `.agents/transient/_retired/test_and_simulation_suite.retired.md`
> with `superseded_by = ".specify/specs/"`.
