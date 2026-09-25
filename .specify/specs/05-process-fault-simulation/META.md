# 05 — META (audit-close-out template)

```toml
[meta]
spec_id = "05-process-fault-simulation"
owner_repo = "pi_monitor"
owner_repos = ["pi_monitor", "research-institution"]
baseline_sha = "PENDING"
completion_sha = "PENDING"
gate_report_digest = "PENDING"
durable_anchors_added = []
durable_anchors_cited = [
  "@ADR-0006",   # pi_monitor long-running command protection
  "@ADR-0007",   # deterministic context controller shadow mode
  "@ADR-0009",   # bounded recovery and soft circuit
  "@ADR-0005",   # audit append-only hash-chained
  "@INV-022",    # stable audit-event strings
  "@INV-023",    # execution intent before launch
  "@INV-025",    # rate-defer survives restart
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
section_7  = "PASS"
section_8  = "PASS"
section_9  = "PASS"
section_10 = "PASS"
section_11 = "PASS"
section_12 = "NOT_APPLICABLE"  # no new cross-repo records
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `tests/substrate/` exists | direct | PENDING |
| 2 | campaign no manual finalize | `grep` exit 1 | PENDING |
| 3 | substrate metadata complete | `test_substrate_metadata.py` | PENDING |
| 4 | no second fake-Pi impl | `test_substrate_inventory.py` | PENDING |
| 5 | Transcript oracle rejects secrets | unit test | PENDING |
| 6 | Process-tree cleanup reaps grandchild | unit test | PENDING |
| 7 | `test_substrate_metadata.py` exits 0 | direct | PENDING |
| 8 | `test_substrate_inventory.py` exits 0 | direct | PENDING |
| 9 | `make check-prime-directive` exits 0 | direct | PENDING |
| 10 | Entry 00/01/02 clauses hold at HEAD | per entry's META | PENDING |
| 11 | `tests/test_mathlint_faults.py` regressed? | `pytest -q` | PENDING |
| 12 | no `time.time` cross-process | `grep` + code review | PENDING |

## Sign-off

> When all twelve rows are `PASS`, this META is valid; entry 05
> is closed; entry 06 unblocked.
