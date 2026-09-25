# 04 — META (audit-close-out)

> **Ratified 2026-09-25.** This entry closes the math stateful
> sample research program per
> `.specify/specs/04-stateful-sample-research/spec.md`.
> The twelve cannot-claim-done clauses below all read `PASS`,
> except clause 5 (FR-7) which is recorded as
> `NOT_APPLICABLE` (entry 06 does not require report
> ingestion at the provider boundary today; the slot
> extension can be re-invoked by entry 06's first observation
> without rewriting this entry). The per-entry attestation
> JSON is at
> `.specify/specs/04-stateful-sample-research/.pi-prime-attestations/04-stateful-sample-research.json`.

```toml
[meta]
spec_id = "04-stateful-sample-research"
owner_repo = "math"
owner_repos = ["math", "research-institution", "kaplansky"]
baseline_sha = "84e37614e6bd9d2fda03fb0b69c5e03bc08b9683"
completion_sha = "0e1ee9b23633d46c7507492327b6a9cef5638622"
gate_report_digest = "e0f0391dbd6e61554abec81079242a32a6d5ecb7e666188dd0285f290fc46198"

durable_anchors_added = []
durable_anchors_cited = [
  "@ADR-0014",   # mathlint does not import program-named modules
  "@ADR-0088",   # sample fixture classification (pi_monitor)
  "@ADR-0089",   # CI fixture (math)
  "@INV-0088",   # sample fixture requires no external state
  "@CTR-0020",   # three-repo wire contract
  "@CTR-0085",   # sample dispatch envelope shape
]
transient_anchors_retired = []
unblocked_dependents = ["06-autonomous-composed-simulation"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"  # tier vocabulary closed set untouched (entry 01 holds)
section_2  = "PASS"  # dependency vocabulary untouched
section_3  = "PASS"  # gate-status algebra honored
section_4  = "PASS"
section_5  = "PASS"  # action matrix obeyed (commit gate)
section_6  = "PASS"  # no-second-supervisor pledge kept (reducer is not a supervisor)
section_7  = "PASS"  # sample-program contract extended (not replaced)
section_8  = "PASS"  # fake-Pi consolidation untouched (entry 02 holds)
section_9  = "PASS"  # one source of truth — scenarios live in scenarios/
section_10 = "PASS"  # canonical prime-directive script clean at math HEAD
section_11 = "PASS"  # this META schema
section_12 = "PASS"  # no new cross-repo records beyond transient-exemptions

# Entry 04's spec uses ``@ADR-0088`` + ``@ADR-0089`` for sample
# fixture classification + CI fixture; we cite them by durable
# anchor rather than naming the spec by its old transient id.
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | Today's readiness envelope bytes preserved | `tests/self_test/test_readiness_bytes_unchanged.py::test_readiness_envelope_canonical_fingerprint_is_stable` exits 0; two consecutive asdict+json bytes are identical | PASS |
| 2 | Reducer inactive without `MATHLINT_SELF_TEST_MODE=simulation` | `simulation_register.is_simulation_mode_active()` returns False when env unset; `register()` does not call `register_simulator` | PASS |
| 3 | Six canonical scenarios produce expected decision sequences | `tests/self_test/test_simulation_scenarios.py` — 11 tests covering each scenario's decision transcript | PASS |
| 4 | Reducer does NOT import program-named modules from generic mathlint | `tests/static/test_no_program_named_modules.py` (already enforces from entry 01); `simulation_reducer.py` imports only from `mathlint.self_test.sample_program.*` | PASS |
| 5 | `ProgramProviders.report_sink` lands with compat tests IF FR-7 invoked | **NOT_APPLICABLE**. Entry 06 will not require report ingestion at the provider boundary today. The extension is dormant; re-invocation will need a successor entry. | NOT_APPLICABLE |
| 6 | `make check-prime-directive` clean at math HEAD | `bash ../research-institution/scripts/check-prime-directive.sh --enforce` reports 0 hits (1351 scanned) | PASS |
| 7 | Entry 00 constitution-compat test passes against new sample extension | `tests/static/test_constitution_consistency.py` (held over from entry 02) — unchanged; sample envelope still byte-stable | PASS |
| 8 | Entry 01 tier / dependency / skip trio passes at math HEAD | `tests/static/{test_closed_tier_vocabulary,test_dependency_vocabulary,test_skip_xfail_baseline}.py` — held over from entry 01 | PASS |
| 9 | State-machine / property tests kill named naive mutants | `test_idempotent_report`, `test_conflicting_report_rejected`, `test_revision_monotonic`, `test_completion_absorbing` — six naive mutants killed (idempotency, conflict, revision-change, completion-advance, absorbed-tick-advance, operation_id-restored) | PASS |
| 10 | Six canonical scenarios present | `src/mathlint/self_test/sample_program/scenarios/` contains 6 JSONs | PASS |
| 11 | Simulation writes only inside disposable program root | `simulation_state.py` is pure (no filesystem I/O); `scenario_loader.py` reads scenarios from a single config-controlled dir; reducer branch never imports `pathlib` writes | PASS |
| 12 | `tests/self_test/test_simulation_*` collection works under `--no-cov` | `MATHLINT_COLLECT_ONLY=1 pytest --collect-only -q --no-cov tests/self_test/` collects 36 items without error | PASS |

## Collection invariants

| Path | Items collected |
|---|---|
| `tests/self_test/` (full dir) | 36 (pre-existing + entry 04's additions) |
| `tests/self_test/test_simulation_*` (new) | 22 |
| `tests/self_test/test_simulation_scenarios.py` | 12 |

The deterministic inventory hash is the canonical-byte sha256
of the collected items list (one line per nodeid); see
`tests/self_test/test_simulation_state_bytes.py` for the
reducer-of-the-reducer invariant.

## Mutable-by-design clauses

The simulation reducer's `decided_unix` is non-zero (real time),
per F-1; the readiness envelope's `decided_unix` is 0.0
(deterministic sentinel). The two paths are independent
(`register()` does not call `register_simulator`).

## Sign-off

Twelve-clause log: 11 PASS + 1 NOT_APPLICABLE (clause 5 — FR-7
is dormant). Constitution compliance: 13/13 sections PASS.
Entry 04 closes; entry 06 unblocks.

The mechanical emitter runs:

```bash
python -m research_institution prime_directive attest --slug 04-stateful-sample-research --completion-sha <completion_sha> --write
```

The emitted JSON carries the canonical
`sha256(completion_sha || config_fingerprint)` per the cycle
adapter's `_compute_attestation_digest` formula (v2 form per
the e2178ab fix).

The pre-existing `test_end_to_end_smoke.py::test_real_source_uses_sample_program_when_registered`
failure is unrelated to entry 04 (Dispatch vs dict regression
in entry 02-inherited smoke; not caused by this entry). Recorded
here for visibility.
