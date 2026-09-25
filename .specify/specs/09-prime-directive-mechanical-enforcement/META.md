# 09 — META (audit-close-out template)

```toml
[meta]
spec_id = "09-prime-directive-mechanical-enforcement"
owner_repo = "research-institution"
owner_repos = ["research-institution", "math", "pi_monitor", "kaplansky"]
baseline_sha = "PENDING"
completion_sha = "PENDING"
gate_report_digest = "PENDING"
durable_anchors_added = [
  # Per-repo ADRs (each repo's own free ID):
  # math:   @ADR-NNNN-prime-directive-enforcement
  # pi_monitor: @ADR-NNNN-prime-directive-enforcement
  # kaplansky: @ADR-NNNN-prime-directive-enforcement
]
durable_anchors_cited = [
  "@ADR-0095-prime-directive-mechanical-enforcement",  # 00's
  "@INV-0095-prg-anchor-ownership",                    # 00's
  "@CTR-0095-prime-directive-check-script-contract",   # 00's
]
transient_anchors_retired = []
unblocked_dependents = ["10-verification-release-closure"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"
section_2  = "PASS"
section_3  = "PASS"  # gate-status algebra honored in --enforce
section_4  = "PASS"
section_5  = "PASS"  # action matrix respected
section_6  = "PASS"
section_7  = "PASS"
section_8  = "PASS"
section_9  = "PASS"
section_10 = "PASS"  # this entry IS §10's mechanical enforcement
section_11 = "PASS"  # META attestation machine-checked
section_12 = "PASS"  # per-repo durable records honor ownership rules
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `prime_directive/__init__.py` exists | direct | PENDING |
| 2 | `attest` produces valid sha256 | unit test | PENDING |
| 3 | `validate` rejects stale | unit test | PENDING |
| 4 | `meta_validator` validates §11.2 | unit + e2e | PENDING |
| 5 | `extension_bridge.render_sanctioned_globs` renders correctly | unit | PENDING |
| 6 | Extension loads registry | manual smoke | PENDING |
| 7 | Per-repo `check-prime-directive-enforced` target | per-repo `make` | PENDING |
| 8 | Per-repo durable record | `ls` | PENDING |
| 9 | `make check-prime-directive-enforced` exits 0 in each repo | per-repo | PENDING |
| 10 | Entry 00 twelve clauses hold | per-entry META | PENDING |
| 11 | Stale attestation rejected | F-1 unit test | PENDING |
| 12 | Strengthened regex canonical | grep | PENDING |

## Sign-off

> When all twelve rows are `PASS`, this META is valid; entry 09
> closed; entry 10 unblocked; prime-directive enforcement is
> mechanically cross-repo.
