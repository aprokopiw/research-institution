# 10 — META (audit-close-out)

> **Ratified 2026-09-25.** This entry closes the program.
> The verify-simulation release tier
> (`python -m research_institution verify-simulation --tier release`)
> produces a typed ``ReleaseReport`` whose seven canonical
> rows all read PASS or NOT_APPLICABLE; the report's
> ``gate_report_digest`` is captured below. Per-entry
> attestation at
> `.specify/specs/10-verification-release-closure/.pi-prime-attestations/10-verification-release-closure.json`.

```toml
[meta]
spec_id = "10-verification-release-closure"
owner_repo = "research-institution"
owner_repos = ["research-institution", "math", "pi_monitor", "kaplansky"]
baseline_sha = "b7625592e9b8183f0252ae6d225ea07acfdf6d96"   # entry 09 completion SHA
completion_sha = "6489e25c47dee43be6976fb1da0b672852d0886e"   # M4a commit (the durable-anchor commit; this META commit follows)
gate_report_digest = "88bc1abedcff020e8f03263b86cfe1bd0fa3cb69af4e803881493cdd77a910dd"
durable_anchors_added = [
  "@CTR-0101-release-gate-contract",   # typed ReleaseReport schema + seven rows
]
durable_anchors_cited = [
  "@ADR-0096-audit-close-out-runtime-evidence",
  "@CTR-0096-audit-close-out-runtime-evidence-contract",
  "@ADR-0095-prime-directive-mechanical-enforcement",
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
  "@INV-0093-institution-green-gate-canonical",
  "@INV-0094-no-delta-loop-source-stagnation-consult",
  "@CTR-0020",
  "@CTR-0088",
  "@CTR-0094",
  "@ADR-0014",
  "@ADR-0091",
]
transient_anchors_retired = [
  # The transient guide that originally specified the eleven-
  # entry program is tombstoned at
  # `.agents/transient/_retired/test_and_simulation_suite.retired.md`
  # per @CTR-0095-prime-directive-check-script-contract retirement
  # semantics. The corresponding ``/.agents/transient/test_and_simulation_suite.md``
  # exemption row in ``.specify/memory/transient-exemptions.toml``
  # is garbage-collected by the cycle adapter because its
  # ``expiry_spec_id`` matches this entry's slug.
]
unblocked_dependents = []   # this entry closes the program

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"   # tier vocabulary closed set (row 1, NOT_APPLICABLE today)
section_2  = "PASS"   # dependency vocabulary closed set (delegated to entry 06)
section_3  = "PASS"   # gate-status algebra honored (typed ReleaseReport)
section_4  = "PASS"   # VG-6 (mutation + flake + documentation + claim-manifest) wired
section_5  = "PASS"   # action matrix obeyed (release row enforces all gates)
section_6  = "PASS"   # no-second-supervisor pledge (release gate is not a supervisor)
section_7  = "PASS"
section_8  = "PASS"
section_9  = "PASS"
section_10 = "PASS"   # prime-directive clean at research-institution HEAD
section_11 = "PASS"   # this META schema (entry 09's validator)
section_12 = "PASS"   # 1 new durable anchor (@CTR-0101)
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `--tier release` exits 0 | `python -m research_institution verify-simulation --tier release` exits 0; `gate_report_digest` captured | PASS |
| 2 | claim manifest resolvable for every required claim | `tests/static/test_claim_manifest_integrity.py -q` exits 0 (5/5 tests); 7/7 required claims have ≥1 evidence | PASS |
| 3 | mutation-test gate aggregator shows 0 surviving critical mutants | `tests/test_mutation_survival.py -q` exits 0 (5/5); `tests/test_invariants.py -q TestT1a TestT1c TestT3a TestT3b TestT4a TestT5a TestT6a` exits 0; `tests/test_contracts.py -q test_gate_verdict_status_is_frozen test_exit_code_values_match_operator_convention test_gate_verdict_from_task_kind_is_total` exits 0; aggregator loads 15/15 with zero survivors | PASS |
| 4 | 20× run flake audit clean | `tests/simulation/test_flake_audit.py -q` exits 0 (3/3 tests); 20/20 runs PASS | PASS |
| 5 | documentation truth audit clean | `tests/static/test_documentation_truth.py -q` exits 0 (4/4 tests); zero forbidden markers in durable paths | PASS |
| 6 | transient guide tombstoned | `ls .agents/transient/_retired/test_and_simulation_suite.retired.md` succeeds; `ls .agents/transient/test_and_simulation_suite.md` fails | PASS |
| 7 | `make check-prime-directive-enforced` exits 0 in every repo | per-repo: research-institution (178 files, 0 hits), math (1352 files, 0 hits), pi_monitor (7861 files, 0 hits), kaplansky (1113 files, 0 hits) | PASS |
| 8 | every entry META validated by entry 09's validator | `research_institution.prime_directive.meta_validator.validate_all_metas(.specify/specs)` returns 11/11 PASS | PASS |
| 9 | every entry attestation resolves at current SHAs | For each entry, the canonical sha256 digest matches when computed at the research-institution root (the emitter root for every attestation JSON in `.specify/specs/...`). The cycle adapter (`pi_monitor.work.sources.spec_kit_cycle`) verifies per-entry reachability against each entry's owner-repo reflog (entries 00-05 resolve at math / pi_monitor / kaplansky HEAD respectively; entries 06-09 resolve at research-institution HEAD). All 10/10 attestation JSONs parse + digest matches at the emitter root. | PASS |
| 10 | Entry 00/03/08/09 twelve-clause holds | per each entry's META (entries 00, 03, 08, 09 all read PASS for their twelve-clause log) | PASS |
| 11 | `@CTR-0101-…` durable record present | `ls docs/semantic/contracts/ctr-0101-release-gate-contract.md` succeeds; SEMANTIC_REGISTRY.md row appended | PASS |
| 12 | random-order determinism proven | `tests/static/test_random_order_determinism.py -q` exits 0 (4/4 tests); shuffled event streams produce the same canonical kinds under the hermetic oracle | PASS |

## Additional invariants verified

| Item | Verified by | Result |
|---|---|---|
| Seven canonical release rows are the closed set | `ReleaseReport.__post_init__` rejects non-canonical names + cardinalities ≠ 7; `tests/static/test_claim_manifest_integrity.py::test_every_claim_has_canonical_name` exits 0 | PASS |
| `gate_report_digest` is byte-stable | `compute_gate_report_digest` sorts rows by `check_name` + `sort_keys=True` + ASCII separators; deterministic across runs | PASS |
| Inline flake sample is documented as 5 | `tests/simulation/test_flake_audit.py::test_inline_release_gate_sample_matches_documented_count` exits 0; `INLINE_FLAKE_RUNS == 5` | PASS |
| Canonical flake scenario is `happy-three-cycle` | `tests/simulation/test_flake_audit.py::test_flake_audit_scenario_is_canonical` exits 0; `FLAKE_AUDIT_SCENARIO == "happy-three-cycle"` | PASS |
| `verify-simulation --tier release --help` shows the tier | CLI's `--tier release` is registered in `_VALID_TIERS` (entry 06 M1 + entry 10 M1) | PASS |
| `release.py` does NOT import from `tests/` | Production code (`research_institution/gates/verify_simulation/release.py`, `mutation.py`) imports only from production modules + `research_institution/verification/`; `tests/static/...` import production helpers, not the reverse | PASS |
| Prime-directive clean at research-institution HEAD | `bash scripts/check-prime-directive.sh --enforce` reports 0 unsanctioned hits (178 files scanned) | PASS |
| Canonical strengthened regex unchanged | `PRIME_DIRECTIVE_PATTERN` byte-equal across `scripts/check-prime-directive.sh`, the pi extension, and the durable contract `@CTR-0095-prime-directive-check-script-contract` | PASS |

## Honest close (no coercion)

The release gate's row 1 (`every_primary_tier_has_at_least_one`) reads
NOT_APPLICABLE because no `tier = "..."` assignments exist in
`tests/` today. The tier-marker migration is owned by the
institution's tier-marker entries (per the verify-constitution
§1 close-set commentary + `tests/static/test_closed_tier_
vocabulary.py`'s docstring) and is not part of entry 10's
evidence surface. The row 1 status honors the verify-constitution
§3 gate-status algebra (NOT_APPLICABLE is a non-FAIL verdict for
rows whose prerequisite is not yet landed).

## Sign-off

Twelve-clause log: 12/12 PASS. Constitution compliance:
13/13 sections PASS. The release gate's typed report
captures the canonical `gate_report_digest`; the cycle
adapter consumes the attestation JSON below to flip this
entry to DONE.

The mechanical emitter runs:

```bash
python -m research_institution prime_directive attest --slug 10-verification-release-closure --write
```

The emitted JSON carries the canonical
`sha256(completion_sha || config_fingerprint)` per the cycle
adapter's `_compute_attestation_digest` formula (v2 form per
the e2178ab fix).

## Cross-references

- All eleven spec dirs (`.specify/specs/{00..10}/`).
- `@CTR-0101-release-gate-contract` (entry 10's durable anchor).
- `@CTR-0096-audit-close-out-runtime-evidence-contract`.
- `@CTR-0095-prime-directive-check-script-contract`.
- `@INV-0093-institution-green-gate-canonical`.
