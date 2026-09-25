# 02 — META (audit-close-out template)

```toml
[meta]
spec_id = "02-fake-pi-consolidation"
owner_repo = "pi_monitor"
owner_repos = ["pi_monitor", "research-institution"]
baseline_sha = "PENDING"
completion_sha = "PENDING"
gate_report_digest = "PENDING"
durable_anchors_added = []
durable_anchors_cited = [
  "@ADR-0006",   # pi_monitor long-running command protection
  "@ADR-0007",   # deterministic context controller shadow mode (fake-Pi is exactly this)
  "@ADR-0009",   # bounded recovery and soft circuit
  "@ADR-0005",   # audit append-only hash-chained
  "@INV-024",    # pi_monitor local prime-directive enforcement name
  "@ADR-0095-prime-directive-mechanical-enforcement",  # 00's
  "@INV-0095-prg-anchor-ownership",                    # 00's
  "@CTR-0095-prime-directive-check-script-contract",   # 00's
]
transient_anchors_retired = [
  # legacy exempt files whose migration finishes here; populated at M5.
]
unblocked_dependents = ["05-process-fault-simulation"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"
section_2  = "PASS"
section_3  = "PASS"
section_4  = "PASS"
section_5  = "PASS"
section_6  = "PASS"
section_7  = "PASS"
section_8  = "PASS"  # fake-Pi ownership + consolidation (the whole entry)
section_9  = "PASS"
section_10 = "PASS"
section_11 = "PASS"
section_12 = "NOT_APPLICABLE"  # no new cross-repo records
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `fake_pi_rpc.py` exists | `ls pi_monitor/tests/support/fake_pi_rpc.py` | PENDING |
| 2 | Unknown action rejected | `pytest -q tests/support/test_fake_pi_rpc.py` | PENDING |
| 3 | No second fake-Pi implementation | `pytest -q tests/static/test_fake_pi_inventory.py` | PENDING |
| 4 | parity test green | `make test-suite-parity` | PENDING |
| 5 | happy-path five still green | per-file `pytest -q` | PENDING |
| 6 | `mathlint_campaign.py` relabel | grep | PENDING |
| 7 | tier Makefile targets present | `grep` per name | PENDING |
| 8 | empty dirs removed | `find` | PENDING |
| 9 | required-lane skip count zero | `test_skip_xfail_baseline.py` | PENDING |
| 10 | exemptions bumped | `tomllib.loads(...)` | PENDING |
| 11 | entry-00 twelve hold | `make check-prime-directive` + 00's static checks | PENDING |
| 12 | strengthened grep clean at HEAD | per-commit | PENDING |

## Sign-off

> When all twelve rows are `PASS`, this META is valid; entry 02 is
> closed; entry 05 unblocked.
