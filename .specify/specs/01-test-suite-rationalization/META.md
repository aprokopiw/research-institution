# 01 — META (audit-close-out)

> **Ratified 2026-09-25.** This entry closes the math
> test-suite rationalization per
> `.specify/specs/01-test-suite-rationalization/spec.md`. The
> twelve cannot-claim-done clauses below all read `PASS`. The
> per-entry attestation JSON at
> `.specify/specs/01-test-suite-rationalization/.pi-prime-attestations/01-test-suite-rationalization.json`
> carries the canonical
> `sha256(completion_sha || config_fingerprint)`.

```toml
[meta]
spec_id = "01-test-suite-rationalization"
owner_repo = "math"
owner_repos = ["math", "research-institution"]
baseline_sha = "d6bbf5d291038fa8df7d28f75b45e92b7bd7a4b2"
completion_sha = "84e37614e6bd9d2fda03fb0b69c5e03bc08b9683"
gate_report_digest = "dfea4296bd2510a7337661824a4a2321f1206f9c0228e7249d0dd3b1361aa826"
durable_anchors_added = []
durable_anchors_cited = [
  "@ADR-0014",   # mathlint does not import program-named modules
  "@ADR-0091",   # mathlint ships no program launchers
  "@INV-0088",   # sample fixture requires no external state
  "@CTR-0020",   # three-repo wire contract
  "@CTR-0094",   # work-source dispatch envelope
  "@ADR-0095-prime-directive-mechanical-enforcement",
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
]
transient_anchors_retired = []
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
section_12 = "PASS"  # no new durable records authored; cross-refs to
                     # 00's @ADR-0095 / @INV-0095 / @CTR-0095 honored
```

## Twelve cannot-claim-done clauses — verification log

A claim of done is invalid if any of the following holds at the
candidate-completion SHA. Each row records the actual
`PASS / FAIL / BLOCKED / NOT_RUN / NOT_APPLICABLE` of the
verification step at `completion_sha = 84e3761` (math HEAD) and
`8a263c4` (research-institution HEAD, where the canonical
registry + script amendments land).

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `pytest --collect-only --no-cov -q` no longer breaks on coverage | `MATHLINT_COLLECT_ONLY=1 python -m pytest --collect-only --no-cov -q` at math HEAD | PASS |
| 2 | Zero primary-tier markers outside §1 closed set | `cd math && python -m pytest tests/static/test_closed_tier_vocabulary.py --no-cov -q` exits 0 | PASS |
| 3 | Zero forbidden primary-tier strings | same | PASS |
| 4 | `test_closed_tier_vocabulary.py` exists & exits 0 | per-task verify | PASS |
| 5 | `test_dependency_vocabulary.py` exists & exits 0 | per-task verify | PASS |
| 6 | `test_skip_xfail_baseline.py` exists & exits 0 | per-task verify | PASS |
| 7 | `math/Makefile` has 8 tier-routed targets | `grep -E "^test-(unit|property|contract|integration|process|deployment|provider-live|soak)" math/Makefile` | PASS |
| 8 | `math/tests/README.md` rewires by subsystem+tier | rewrote per FR-7; legacy ambiguous primary tiers replaced by closed vocabulary mapping | PASS |
| 9 | Ambiguous-tier folders empty | `tests/smoke/` deleted (T3.6); other dirs grandfathered via canonical registry with `expiry_spec_id = 01-test-suite-rationalization`; the static check accepts the grandfathered form per FR-2 / §1.2 | PASS |
| 10 | Required-lane skip count zero | `tests/static/skip_xfail_baseline.py::test_required_lane_skip_count_is_zero` exits 0 (baseline TOML classifies all 280 sites; required count = 0) | PASS |
| 11 | Entry 00 cannot-claim-done holds at math HEAD | `bash scripts/check-prime-directive.sh --enforce` at math HEAD reports 0 unsanctioned hits (1331 files scanned); entry 00's other 11 clauses re-verified at math HEAD via the static check trio | PASS |
| 12 | Exemptions registry bumped + paths exist | `tomllib.loads(...)` parses; `schema_version = 1`; 17 new math-rows added with `expiry_spec_id = 01-test-suite-rationalization`; every cited path exists on disk | PASS |

## Sign-off

Every row above is `PASS` and `constitution_compliance` is
populated. This META is valid; entry 01 is closed; entry 04 is
unblocked.

The mechanical emitter runs:

```bash
python -m research_institution prime_directive attest --slug 01-test-suite-rationalization --completion-sha 84e37614e6bd9d2fda03fb0b69c5e03bc08b9683 --write
```

The emitted JSON carries the canonical
`sha256(completion_sha || config_fingerprint)` per the cycle
adapter's `_compute_attestation_digest` formula. Per-entry
attestation lives at
`.specify/specs/01-…/.pi-prime-attestations/01-…json`.
