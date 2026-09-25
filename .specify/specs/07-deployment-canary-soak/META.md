# 07 — META (audit-close-out template)

```toml
[meta]
spec_id = "07-deployment-canary-soak"
owner_repo = "research-institution"
owner_repos = ["research-institution", "math", "pi_monitor"]
baseline_sha = "PENDING"
completion_sha = "PENDING"
gate_report_digest = "PENDING"
durable_anchors_added = []
durable_anchors_cited = [
  "@ADR-0001",   # kaplansky uses pi OAuth
  "@ADR-0006",   # research-institution scope
  "@CTR-0094",   # work-source dispatch envelope
  "@INV-0093",   # green gate
  "@ADR-0004",   # pi_monitor macOS background service
  "@ADR-0095-prime-directive-mechanical-enforcement",
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
]
transient_anchors_retired = []
unblocked_dependents = ["08-installed-compatibility-recovery"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"
section_2  = "PASS"
section_3  = "PASS"
section_4  = "PASS"  # VG-5/VG-7/VG-8 wired
section_5  = "PASS"  # action matrix respected
section_6  = "PASS"  # no second supervisor
section_7  = "PASS"
section_8  = "PASS"
section_9  = "PASS"  # canonical CLI is one source
section_10 = "PASS"
section_11 = "PASS"
section_12 = "PASS"
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `--tier deployment` exits 0 from each cwd | four-cwd test | PENDING |
| 2 | rendered `ProgramArguments` byte-equal to subprocess argv | `test_program_arguments_match.py` | PENDING |
| 3 | macOS deployment bootouts label in `finally` | `test_macos_isolated_label.py` | PENDING |
| 4 | canary refuses without `--live` | CLI smoke | PENDING |
| 5 | canary refuses without credentials | `test_canary_credentials_required.py` | PENDING |
| 6 | canary does not mutate kaplansky production | `test_canary_does_not_mutate_kaplansky.py` | PENDING |
| 7 | canary `PASS` is never silently rendered | guard rails | PENDING |
| 8 | `make check-prime-directive` exits 0 | per-commit | PENDING |
| 9 | Entry 00/04/05/06 clauses hold at HEAD | per-entry META | PENDING |
| 10 | Soak archive signed/hashtagged | `SoakOracle.assert_no_hot_loop` | PENDING |
| 11 | Canary hard-deadline 10 min | wall-clock oracle | PENDING |
| 12 | No hot loop detected in smoke soak | `test_soak_short.py` | PENDING |

## Sign-off

> When all twelve rows are `PASS`, this META is valid; entry 07
> closed; entry 08 unblocked.
