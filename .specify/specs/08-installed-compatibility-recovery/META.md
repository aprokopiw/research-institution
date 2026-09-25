# 08 — META (audit-close-out template)

```toml
[meta]
spec_id = "08-installed-compatibility-recovery"
owner_repo = "research-institution"
owner_repos = ["research-institution", "math", "pi_monitor", "kaplansky"]
baseline_sha = "PENDING"
completion_sha = "PENDING"
gate_report_digest = "PENDING"
durable_anchors_added = []
durable_anchors_cited = [
  "@CTR-0020",   # three-repo wire contract
  "@CTR-0088",   # catalog schema
  "@ADR-0095-prime-directive-mechanical-enforcement",
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
]
transient_anchors_retired = []
unblocked_dependents = ["10-verification-release-closure"]

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
section_12 = "PASS"
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `--tier compatibility-matrix` clean | direct | PENDING |
| 2 | supported Python doesn't break | matrix | PENDING |
| 3 | wheel-install collision detected | matrix | PENDING |
| 4 | editable-vs-installed byte-equal | per-scenario | PENDING |
| 5 | rollback no redispatch | rollback runner | PENDING |
| 6 | backup-restore single-pass resume | backup runner | PENDING |
| 7 | corruption fail-closed + documented recovery | corruption runner | PENDING |
| 8 | ENOSPC / truncated / permissions detected | disk-pressure runner | PENDING |
| 9 | dep scan catches advisories | scan | PENDING |
| 10 | `make check-prime-directive` exits 0 | per-commit | PENDING |
| 11 | Entry 00–07 clauses hold at HEAD | per-entry META | PENDING |
| 12 | matrix contains every cell of "Cross-repository compatibility matrix" | matrix report | PENDING |

## Sign-off

> When all twelve rows are `PASS`, this META is valid; entry 08
> closed; entry 10 unblocked.
