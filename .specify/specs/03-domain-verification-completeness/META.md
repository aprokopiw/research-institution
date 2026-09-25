# 03 — META (audit-close-out template)

```toml
[meta]
spec_id = "03-domain-verification-completeness"
owner_repo = "kaplansky"
owner_repos = ["kaplansky", "math", "research-institution"]
baseline_sha = "PENDING"
completion_sha = "PENDING"
gate_report_digest = "PENDING"
durable_anchors_added = []
durable_anchors_cited = [
  "@ADR-0014",   # mathlint program-import discipline
  "@ADR-0091",   # mathlint ships no program launchers
  "@INV-0088",   # sample fixture requires no external state
  "@CTR-0020",   # three-repo wire contract
  "@ADR-0095-prime-directive-mechanical-enforcement",  # 00's
  "@INV-0095-prg-anchor-ownership",                    # 00's
  "@CTR-0095-prime-directive-check-script-contract",   # 00's
]
transient_anchors_retired = [
  # legacy exempt files whose migration finishes here; populated at M5.
]
unblocked_dependents = ["10-verification-release-closure"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"
section_2  = "PASS"
section_3  = "PASS"
section_4  = "PASS"
section_5  = "PASS"
section_6  = "PASS"
section_7  = "PASS"  # sample-program contract honored (frozen-claims immutable)
section_8  = "PASS"
section_9  = "PASS"
section_10 = "PASS"
section_11 = "PASS"
section_12 = "NOT_APPLICABLE"  # no new durable records
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `pytest --collect-only -q` exits 0 | direct | PENDING |
| 2 | Zero primary-tier markers outside §1 closed set | `test_closed_tier_vocabulary.py` | PENDING |
| 3 | 10 new modules all green | per-module `pytest -q` | PENDING |
| 4 | Four-cwd launcher test green | `tests/launcher/` | PENDING |
| 5 | mathlint_provider collision raises | `tests/plugin/` | PENDING |
| 6 | Required-lane skip count zero | `test_skip_xfail_baseline.py` | PENDING |
| 7 | Exemptions bumped | `tomllib.loads(...)` | PENDING |
| 8 | Folder migration complete | `find` | PENDING |
| 9 | Strong-grep clean | per-commit | PENDING |
| 10 | Entry 00 twelve hold at kaplansky HEAD | `make check-prime-directive` | PENDING |
| 11 | `programs/*` content unchanged | `git diff` | PENDING |
| 12 | `src/kaplansky/*` unchanged | `git diff` | PENDING |

## Sign-off

> When all twelve rows are `PASS`, this META is valid; entry 03 is
> closed; entry 10 unblocked.
