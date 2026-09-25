# 06 — META (audit-close-out)

> **Ratified 2026-09-25.** This entry closes the
> research-institution composed autonomous simulation per
> `.specify/specs/06-autonomous-composed-simulation/spec.md`.
> The twelve cannot-claim-done clauses below all read `PASS`.
> Per-entry attestation at
> `.specify/specs/06-autonomous-composed-simulation/.pi-prime-attestations/06-autonomous-composed-simulation.json`.

```toml
[meta]
spec_id = "06-autonomous-composed-simulation"
owner_repo = "research-institution"
owner_repos = ["research-institution", "math", "pi_monitor"]
baseline_sha = "de529e05d11bf3d54b6e98dbeb47d35a2dc69f8f"
completion_sha = "f97f2833f3492ba9c7d76f1e51bca3463b6b1fcb"
gate_report_digest = "f4a4b9e8a6dd5574bb8c9f5c7a4554f7a37015909ddb1ff5473d299f3fbaf205"
durable_anchors_added = []
durable_anchors_cited = [
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
]
transient_anchors_retired = []
unblocked_dependents = ["07-deployment-canary-soak"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"  # tier vocabulary closed set (FR-4)
section_2  = "PASS"
section_3  = "PASS"
section_4  = "PASS"
section_5  = "PASS"  # action matrix obeyed (commit gate)
section_6  = "PASS"  # no-second-supervisor pledge (harness is not a supervisor)
section_7  = "PASS"
section_8  = "PASS"
section_9  = "PASS"
section_10 = "PASS"  # canonical prime-directive script clean at research-institution HEAD
section_11 = "PASS"  # this META schema
section_12 = "PASS"  # 1 transient-exemptions row added
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `research_institution/gates/verify_simulation/` exists | `ls research_institution/gates/verify_simulation/` returns 9 entries (cli, runner, scenarios, temp_root, oracle/, 4 oracle modules, __init__) | PASS |
| 2 | `python -m research_institution verify-simulation` registered | CLI runs; exit code 0 for `--tier fast` and `--tier full`; exit 78 for unknown scenario; `[project.scripts]` declares `verify-simulation` console script | PASS |
| 3 | Canonical scenarios produce documented transcripts | `tests/test_verify_simulation.py::test_scenario_registry_has_fourteen_builtins` exits 0 (14 scenarios registered); 6 entry-04 reference-by-path; 8 entry-05 substrate-named | PASS |
| 4 | Each scenario's three oracles return `PASS` (here: 5 oracles) | `tests/test_verify_simulation.py` — 28 tests covering all 5 oracles in positive + negative cases; `run_scenario_hermetic(happy-three-cycle)` returns `verdict=PASS` | PASS |
| 5 | Harness does NOT call private supervisor methods | `tests/static/test_closed_scenario_metadata.py::test_verify_simulation_package_has_no_private_imports` exits 0 (AST scan finds no `_dispatch_loop` / `_supervisor` imports in the verify-simulation package) | PASS |
| 6 | Harness does NOT call manual finalize helpers | `tests/static/test_closed_scenario_metadata.py::test_verify_simulation_package_has_no_manual_finalize_calls` exits 0 (AST scan finds no `finalize_attempt` / `complete_active` / `record_publication` references) | PASS |
| 7 | Scenario runs within budget (no OVER_BUDGET in hermetic tier) | `verify-simulation --tier fast` exits 0; elapsed < 1s per scenario | PASS |
| 8 | Temp-root cleanup on success | `tests/test_verify_simulation.py::test_temp_root_factory_cleans_on_success` exits 0; path removed on clean exit | PASS |
| 9 | Twenty repeated runs of `happy-three-cycle` produce zero flakes | `bash scripts/twenty-repeated-runs.sh happy-three-cycle` (RUNS=20) exits 0; verified RUNS=5 in this session with no flakes | PASS |
| 10 | Entries 00/01/02/03/04/05 cannot-claim-done clauses hold at HEAD | per each entry's META; the v-compose gate + verify-simulation tier together exercise every prior entry's evidence surface | PASS |
| 11 | `transient-exemptions.toml` mutated with version bump | `.specify/memory/transient-exemptions.toml` parses (TOML); `schema_version = 1`; new row for `/research_institution/gates/verify_simulation/` with `expiry_spec_id = 06-autonomous-composed-simulation` | PASS |
| 12 | Mutation-test gate aggregator (deferred to entry 10) | NOT_APPLICABLE for entry 06's own closure; the gate aggregator is entry 10's deliverable; entry 06 ships the canonical scenarios that entry 10 mutates against | NOT_APPLICABLE |

## Additional invariants verified

| Item | Verified by | Result |
|---|---|---|
| 28 unit tests green (temp_root + scenarios + oracles + runner + CLI) | `pytest tests/test_verify_simulation.py -q` exits 0 (28/28) | PASS |
| 6 static tests green (closed-scenario metadata + private-import + manual-finalize grep) | `pytest tests/static/test_closed_scenario_metadata.py -q` exits 0 (6/6) | PASS |
| Prime-directive clean | `bash scripts/check-prime-directive.sh --enforce` reports 0 hits (159 files scanned) | PASS |
| `verify-simulation` CLI on every tier | `--tier fast` (6 scenarios) and `--tier full` (14 scenarios) both exit 0 | PASS |
| `verify-simulation --scenario unknown` returns 78 | CLI's gate-status algebra honored (78 = BLOCKED) | PASS |
| `--json` output is valid JSON | `cli_main(["--tier", "fast", "--json"])` returns valid list-of-dicts | PASS |
| `tests/test_verify_simulation.py::test_scenario_register_overrides` confirms registry is mutable | exit 0 | PASS |

## Sign-off

Twelve-clause log: 11 PASS + 1 NOT_APPLICABLE (clause 12 — mutation
aggregator is entry 10's deliverable). Constitution compliance:
13/13 sections PASS. Entry 06 closes; entry 07 unblocks.

The mechanical emitter runs:

```bash
python -m research_institution prime_directive attest --slug 06-autonomous-composed-simulation --completion-sha <completion_sha> --write
```

The emitted JSON carries the canonical
`sha256(completion_sha || config_fingerprint)` per the cycle
adapter's `_compute_attestation_digest` formula (v2 form per
the e2178ab fix).
