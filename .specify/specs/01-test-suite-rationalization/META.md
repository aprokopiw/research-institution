# 01 — META (audit-close-out template)

```toml
[meta]
spec_id = "01-test-suite-rationalization"
owner_repo = "math"
owner_repos = ["math", "research-institution"]
baseline_sha = "PENDING"
completion_sha = "PENDING"
gate_report_digest = "PENDING"
durable_anchors_added = []
durable_anchors_cited = [
  "@ADR-0014",   # mathlint does not import program-named modules
  "@ADR-0091",   # mathlint ships no program launchers
  "@INV-0088",   # sample fixture requires no external state
  "@CTR-0020",   # three-repo wire contract
  "@CTR-0094",   # work-source dispatch envelope
  "@ADR-0095-prime-directive-mechanical-enforcement",  # 00's
  "@INV-0095-prg-anchor-ownership",                    # 00's
  "@CTR-0095-prime-directive-check-script-contract",   # 00's
]
transient_anchors_retired = [
  # Every legacy exempt file that this entry reclassifies or
  # absorbs; filled at M5.
]
unblocked_dependents = ["04-stateful-sample-research"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"  # tier vocabulary closed set enforced
section_2  = "PASS"  # dependency vocabulary enforced
section_3  = "PASS"  # gate-status algebra honored (BLOCKED for missing dep)
section_4  = "PASS"  # VG-0..VG-2 owned by math here
section_5  = "PASS"  # action matrix obeyed (commit gate)
section_6  = "PASS"  # no-second-supervisor pledge (this entry writes no new
                     # supervisor; extends math's tests only)
section_7  = "PASS"  # sample-program contract (entry 04 implements)
section_8  = "PASS"  # fake-Pi consolidation (entry 02 implements)
section_9  = "PASS"  # one source of truth (entry 04/05/06)
section_10 = "PASS"  # canonical prime-directive script used at math HEAD
section_11 = "PASS"  # this META schema
section_12 = "NOT_APPLICABLE"  # no new durable records authored
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `pytest --collect-only -q` no longer breaks on coverage | `pytest --collect-only --no-cov -q` | PENDING |
| 2 | Zero primary-tier markers outside §1 closed set | `pytest -q tests/static/test_closed_tier_vocabulary.py` | PENDING |
| 3 | Zero forbidden primary-tier strings | same | PENDING |
| 4 | `test_closed_tier_vocabulary.py` exists & exits 0 | per-task verify | PENDING |
| 5 | `test_dependency_vocabulary.py` exists & exits 0 | per-task verify | PENDING |
| 6 | `test_skip_xfail_baseline.py` exists & exits 0 | per-task verify | PENDING |
| 7 | `math/Makefile` has 8 tier-routed targets | `grep` for each name | PENDING |
| 8 | `math/tests/README.md` rewires by subsystem+tier | `test_closed_tier_vocabulary.py` reference scan | PENDING |
| 9 | Ambiguous-tier folders empty | `find math/tests/{e2e,smoke,...}` returns empty | PENDING |
| 10 | Required-lane skip count zero | `test_skip_xfail_baseline.py` | PENDING |
| 11 | Entry 00 cannot-claim-done holds at math HEAD | `make check-prime-directive` + 00's static checks | PENDING |
| 12 | Exemptions registry bumped + paths exist | `tomllib.loads(...)` + `Path.exists()` | PENDING |

## Sign-off

> When all twelve rows are `PASS` and `constitution_compliance` is
> populated, this META is valid; entry 01 is closed; entry 04
> unblocked.

> Mechanical emitter (replaced by canonical entry 09 emitter):
> `python -m research_institution prime_directive attest 01-test-suite-rationalization`
