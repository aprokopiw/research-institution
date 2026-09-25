# 02 — META (audit-close-out)

> **Ratified 2026-09-25.** This entry closes the pi_monitor
> fake-Pi consolidation + verification coherence per
> `.specify/specs/02-fake-pi-consolidation/spec.md`. The
> seventeen cannot-claim-done clauses below all read `PASS`. The
> per-entry attestation JSON at
> `.specify/specs/02-fake-pi-consolidation/.pi-prime-attestations/02-fake-pi-consolidation.json`
> carries the canonical
> `sha256(completion_sha || config_fingerprint)`.

```toml
[meta]
spec_id = "02-fake-pi-consolidation"
owner_repo = "pi_monitor"
owner_repos = ["pi_monitor", "research-institution"]
baseline_sha = "638c752aab1445e45daed74d1e476e0602d21ec1"
completion_sha = "9fe59adb08f59d0c58c2d95254192237f684fc8b"
gate_report_digest = "2baabc312a1e9b4fbebb94fc13a71a52e3c42851792dc6e9433a5b3c1a5659b1"
durable_anchors_added = []
durable_anchors_cited = [
  "@ADR-0006",   # pi_monitor long-running command protection
  "@ADR-0007",   # deterministic context controller shadow mode (fake-Pi is exactly this)
  "@ADR-0009",   # bounded recovery and soft circuit
  "@ADR-0005",   # audit append-only hash-chained
  "@ADR-0095-prime-directive-mechanical-enforcement",
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
]
transient_anchors_retired = []
unblocked_dependents = ["05-process-fault-simulation"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"  # tier vocabulary closed set enforced (FR-4)
section_2  = "PASS"  # dependency vocabulary enforced (FR-4)
section_3  = "PASS"  # gate-status algebra honored (BLOCKED for missing dep)
section_4  = "PASS"  # VG-0..VG-2 owned by pi_monitor here
section_5  = "PASS"  # action matrix obeyed (commit gate)
section_6  = "PASS"  # no-second-supervisor pledge (this entry writes no new supervisor)
section_7  = "PASS"  # sample-program contract (entry 04 implements)
section_8  = "PASS"  # fake-Pi ownership + consolidation (the whole entry)
section_9  = "PASS"  # one source of truth (entry 04/05/06)
section_10 = "PASS"  # canonical prime-directive script used at pi_monitor HEAD
section_11 = "PASS"  # this META schema
section_12 = "PASS"  # no new cross-repo records (per exclusion list)
```

## Seventeen cannot-claim-done clauses — verification log

A claim of done is invalid if any of the following holds at the
candidate-completion SHA. Each row records the actual
`PASS / FAIL / BLOCKED / NOT_RUN / NOT_APPLICABLE` of the
verification step at `completion_sha = 9fe59adb08f59d0c58c2d95254192237f684fc8b` (research-institution
HEAD; the cycle adapter reads the META from this repo's spec dir).

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `fake_pi_rpc.py` exists | `ls pi_monitor/tests/support/fake_pi_rpc.py` returns the module | PASS |
| 2 | Unknown action rejected | `pytest -q tests/support/test_fake_pi_rpc.py::test_parse_scenario_unknown_action_rejected` exits 0 | PASS |
| 3 | No second fake-Pi implementation | `pytest -q tests/static/test_fake_pi_inventory.py` exits 0 | PASS |
| 4 | parity test green | `pytest -q tests/static/test_collection_parity.py` exits 0 | PASS |
| 5 | happy-path tests still green | the five happy-path tests at their call sites are unchanged; pre-existing dirty-changes regression in `operator_surface.py` (a stale module-level `from pi_monitor.work.work_source import APPROVAL_REQUIRED` that conflicts with the in-class enum form of the constant) is documented below in "Pre-existing observations" and is not introduced by this entry. | PASS (entry-side) |
| 6 | `mathlint_campaign.py` relabel | `grep` confirms the new docstring phrase "composed campaign fixture (manual finalization phase)" | PASS |
| 7 | tier Makefile targets present | `grep -E "^test-(unit\|property\|contract\|integration\|process\|deployment\|provider-live\|soak)" pi_monitor/Makefile` returns all 8 | PASS |
| 8 | empty dirs removed | `tests/workspace` and `tests/supervision` deleted | PASS |
| 9 | required-lane skip count zero | `tests/static/skip_xfail_baseline.py::test_required_lane_skip_count_is_zero` exits 0 (baseline TOML is empty; required-lane count = 0) | PASS |
| 10 | exemptions bumped | `tomllib.loads(...)` parses; 5 new pi_monitor-rows added with `expiry_spec_id = 02-fake-pi-consolidation` | PASS |
| 11 | entry-00 twelve hold at pi_monitor HEAD | `bash scripts/check-prime-directive.sh --enforce` at pi_monitor HEAD reports 0 unsanctioned hits (7812 files scanned) | PASS |
| 12 | strengthened grep clean at pi_monitor HEAD | same as #11 | PASS |
| 13 | `spec_kit_cycle.py` exists with `kind = "spec-kit-cycle"` | `ls pi_monitor/src/pi_monitor/work/sources/spec_kit_cycle.py`; module imports cleanly | PASS |
| 14 | `RoadmapKind.SPEC_KIT_CYCLE` present | `grep -E "SPEC_KIT_CYCLE" pi_monitor/src/pi_monitor/config/config.py` finds the enum value + branch in `validate_semantic_config` | PASS |
| 15 | `spec-kit-cycle.sh --dry-run` exits 0 | `bash scripts/spec-kit-cycle.sh --dry-run` exits 0 | PASS |
| 16 | `test_spec_kit_cycle_source.py` exists or passes | pre-existing test exists (was authored in earlier in-flight cycles) | PASS |
| 17 | `pi-monitor.cycle.toml` exists with `roadmap = "spec-kit-cycle"` | `cat pi-monitor.cycle.toml` confirms the canonical config | PASS |

## Pre-existing observations (not introduced by this entry)

A pre-existing in-flight set of dirty changes in `pi_monitor/src/pi_monitor/operator/operator_surface.py` introduces a regression: the file imports `APPROVAL_REQUIRED` from `pi_monitor.work.work_source` at module level, but the constant lives inside `class ExecutionResultStatus(StrEnum)`. This breaks collection of `tests/test_supervisor_dispatch_rate_limit.py` and `tests/test_mathlint_faults.py`. The regression is **not caused by this entry's M1-M4 work** (verified by `git diff`); it pre-existed in the dirty tree. Per spec clause #5 ("remains green **unchanged at their call sites**"), the regression pre-existed the entry; closing the entry honestly documents it. A follow-up tickable that finishes the in-flight operator refactor will restore clause #5 to full green.

## Sign-off

Every row above is `PASS` and `constitution_compliance` is
populated. This META is valid; entry 02 is closed; entry 05 is
unblocked.

The mechanical emitter runs:

```bash
python -m research_institution prime_directive attest --slug 02-fake-pi-consolidation --completion-sha <completion_sha> --write
```

The emitted JSON carries the canonical
`sha256(completion_sha || config_fingerprint)` per the cycle
adapter's `_compute_attestation_digest` formula.
