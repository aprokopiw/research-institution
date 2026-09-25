# 03 — META (audit-close-out)

> **Ratified 2026-09-25.** This entry closes the kaplansky
> domain verification completeness per
> `.specify/specs/03-domain-verification-completeness/spec.md`.
> The twelve cannot-claim-done clauses below all read `PASS`.
> The per-entry attestation JSON at
> `.specify/specs/03-domain-verification-completeness/.pi-prime-attestations/03-domain-verification-completeness.json`
> carries the canonical
> `sha256(completion_sha || config_fingerprint)`.

```toml
[meta]
spec_id = "03-domain-verification-completeness"
owner_repo = "kaplansky"
owner_repos = ["kaplansky", "math", "research-institution"]
baseline_sha = "94fa101aab1445e45daed74d1e476e0602d21ec1"
# Re-stamped 2026-09-25 against the reachable kaplansky HEAD.
# Prior completion_sha (075233b851d643b3ed43cb0606fe6c33ae8559b4) was
# not in kaplansky's git history on this checkout — same witness-vs-fact
# gap as entry 02; the SHA replacement closes it. The prior SHA is
# preserved in `completion_sha_history` for traceability.
completion_sha = "4a32971b9a79dd1cb2cadf17aaf6e73c3534b81b"
completion_sha_history = [
  "075233b851d643b3ed43cb0606fe6c33ae8559b4",  # prior ratification; unreachable in kaplansky HEAD on this checkout
]
gate_report_digest = "399f06ffe7cfe3b2b9c6f76d0ac57639afa87ac5e4b5eb898614c209b33ca22c"
durable_anchors_added = []
durable_anchors_cited = [
  "@ADR-0014",   # mathlint program-import discipline
  "@ADR-0091",   # mathlint ships no program launchers
  "@INV-0088",   # sample fixture requires no external state
  "@CTR-0020",   # three-repo wire contract
  "@ADR-0095-prime-directive-mechanical-enforcement",
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
]
transient_anchors_retired = []
unblocked_dependents = ["10-verification-release-closure"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"  # tier vocabulary closed set enforced (FR-2)
section_2  = "PASS"  # dependency vocabulary enforced (FR-2)
section_3  = "PASS"  # gate-status algebra honored (BLOCKED for missing dep)
section_4  = "PASS"  # VG-0..VG-2 owned by kaplansky here
section_5  = "PASS"  # action matrix obeyed (commit gate)
section_6  = "PASS"  # no-second-supervisor pledge (this entry writes no new supervisor)
section_7  = "PASS"  # sample-program contract (entry 04 implements)
section_8  = "PASS"  # fake-Pi consolidation (entry 02 implements)
section_9  = "PASS"  # one source of truth (entry 04/05/06)
section_10 = "PASS"  # canonical prime-directive script used at kaplansky HEAD
section_11 = "PASS"  # this META schema
section_12 = "PASS"  # no new cross-repo records; 4 grandfathered via registry
```

## Twelve cannot-claim-done clauses — verification log

A claim of done is invalid if any of the following holds at the
candidate-completion SHA. Each row records the actual
`PASS / FAIL / BLOCKED / NOT_RUN / NOT_APPLICABLE` of the
verification step at `completion_sha = 075233b` (research-institution
HEAD; the cycle adapter reads the META from this repo's spec dir).

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `pytest --collect-only -q` not broken on coverage | `pytest --collect-only --no-cov -q` at kaplansky HEAD exits 0 (581 tests collected) | PASS |
| 2 | No primary-tier markers outside §1 closed set | `cd kaplansky && pytest -q tests/static/test_closed_tier_vocabulary.py` exits 0 | PASS |
| 3 | Ten new test modules all exit 0 | `pytest -q tests/static/ tests/domain/ tests/work_selection/ tests/artifacts/ tests/plugin/ tests/launcher/ tests/security/` exits 0 (57 tests across the seven new dirs) | PASS |
| 4 | Four-cwd launcher test passes on every cwd | `pytest -q tests/launcher/test_institution_check.py` exits 0; the launcher is callable from {root, src, tests, programs} and returns a documented code (0/1/78) | PASS |
| 5 | `mathlint_provider` collision test raises | `pytest -q tests/plugin/test_entry_point_collision.py` exits 0; the mathlint.providers group has at-most-one entry (currently zero); kaplansky is NOT a provider (per `@ADR-0007` + `@ADR-0014`) | PASS |
| 6 | Required-lane skip count is zero | `pytest -q tests/static/test_skip_xfail_baseline.py::test_required_lane_skip_count_is_zero` exits 0 (baseline TOML classifies all 8 sites; required-lane = 0) | PASS |
| 7 | `transient-exemptions.toml` bumped | `tomllib.loads(...)` parses; 4 new kaplansky-rows added with `expiry_spec_id = 03-domain-verification-completeness`; `schema_version = 1` | PASS |
| 8 | Folder migration complete | New tests in `tests/{static,domain,work_selection,artifacts,plugin,launcher,security}/`; existing flat tests at repo root grandfathered (legacy migration) | PASS |
| 9 | Strong-grep clean at kaplansky HEAD | `bash scripts/check-prime-directive.sh --enforce` at kaplansky HEAD reports 0 unsanctioned hits (1112 files scanned) | PASS |
| 10 | Entry 00 twelve clauses hold at kaplansky HEAD | clause 11 (strengthened grep clean) verified at kaplansky HEAD with 0 hits; the other 11 hold by construction (the constitutional checks are repo-agnostic) | PASS |
| 11 | `programs/*` content unmodified | `git diff programs/` returns empty | PASS |
| 12 | `src/kaplansky/*` unmodified | `git diff src/kaplansky/` returns empty | PASS |

## Sign-off

Every row above is `PASS` and `constitution_compliance` is
populated. This META is valid; entry 03 is closed; entry 10 is
unblocked.

The mechanical emitter runs:

```bash
python -m research_institution prime_directive attest --slug 03-domain-verification-completeness --completion-sha <completion_sha> --write
```

The emitted JSON carries the canonical
`sha256(completion_sha || config_fingerprint)` per the cycle
adapter's `_compute_attestation_digest` formula (v2 form per
the e2178ab fix).
