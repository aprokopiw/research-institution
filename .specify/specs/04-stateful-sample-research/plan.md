# 04 — Plan

## Technical context

This entry extends the existing math self-test fixture with two
explicit modes (readiness, simulation). It is the entry whose
product is consumed by entry 06 as the simulation-side research
program driving the fake-Pi supervisor.

## Existing implementation to extend

- `math/src/mathlint/self_test/sample_program/work_source.py` —
  the `_build_envelope()` + `sample_work_source()` body. **MUST
  remain byte-for-byte** when simulation mode is off.
- `math/src/mathlint/self_test/sample_program/register.py` —
  entry-point registration. **MUST** continue producing a
  sentinel `ProgramProviders` so the strict-one-winner loader
  doesn't raise.
- `math/tests/self_test/{test_sample_work_source.py,
  test_end_to_end_smoke.py}` — readiness tests; preserved.
- `math/src/mathlint/program_providers.py` —
  `WorkSourceProvider`, `register_program_providers`,
  `ProgramProviders`, `set_work_selection_slot`. The optional
  report-callback extension (FR-7) defaults to `None`.
- `math/src/mathlint/orchestration/real_source.py` —
  `configured_provider`, `decide_next`, `record_report`. The
  real-source adapter test (FR-7) lives here as a unit test.
- `math/docs/operations/run-self-test.md` — the runbook;
  amended to document simulation mode.
- `@ADR-0088`, `@ADR-0089`, `@INV-0088` — durable records. No
  new records by this entry.

## Components changed

| Path | Change |
|---|---|
| `math/src/mathlint/self_test/sample_program/simulation_state.py` | new. |
| `math/src/mathlint/self_test/sample_program/simulation_reducer.py` | new. |
| `math/src/mathlint/self_test/sample_program/simulation_register.py` | new. |
| `math/src/mathlint/self_test/sample_program/_support/canonical_bytes.py` | new. |
| `math/src/mathlint/self_test/sample_program/work_source.py` | mode-dispatch added (readiness path preserved byte-for-byte). |
| `math/src/mathlint/self_test/sample_program/register.py` | env-gate extended. |
| `math/tests/self_test/test_simulation_*` (six files) | new per FR-6. |
| `math/tests/self_test/test_readiness_bytes_unchanged.py` | new — proves S7.1 holds. |
| `math/src/mathlint/program_providers.py` | optional `report_sink` field on `ProgramProviders` (default `None`) — only if FR-7 invoked. |
| `math/docs/operations/run-self-test.md` | documents simulation env. |
| `research-institution/.specify/memory/transient-exemptions.toml` | sim-related rows for new self_test files (none required; new code uses no forbidden strings). |

## Components explicitly NOT changed

- `pi_monitor.work.work_source` (wire authority).
- `mathlint.orchestration.real_source`'s public surface (only
  adds a test that exercises the real-source adapter).
- `kaplansky/programs/*` (research content unchanged).

## Repository ownership boundary

```
math                 (sample program + reducer + tests; docs)
research-institution (transient-exemptions.toml if any new row needed)
```

(Entry 06's `tests/simulation/scenarios/*.json` cite the four
canonical scenarios from this entry by name; no copy of bodies.)

## Constitution Check (entry-04-specific)

- **§6** — no-second-supervisor (the sample program is owned by
  math; not a new supervisor).
- **§7** — sample-program contract (the whole entry).
- **§8** — fake-Pi ownership (irrelevant here; entry 02 owns).
- **§9** — one source of simulation truth (canonical scenarios
  ship here; entry 06 cites them by reference).
- **§10** — `make check-prime-directive` exits 0 at math HEAD.
- **§11** — META emitted.
- **§12** — durable-record ownership honored (no new cross-repo
  records by 04; uses existing math records).

## Data and state migration

- None. The simulation reducer is local to the disposable
  program root; the math repo adds only code, no state files.

## Failure atomicity and rollback

- Each commit:
  - preserves `sample_work_source`'s bytes (verified by
    `test_readiness_bytes_unchanged.py`);
  - keeps `tests/self_test/` green;
  - keeps canonical script exit 0.
- Rollback is per-commit.

## Security / credential impact

None. The sample does not perform model inference; it does not
reach a network. The reducer is pure.

## Performance / runtime budgets

- `MATHLINT_SELF_TEST_MODE=simulation pytest -q tests/self_test/`
  ≤ 30 s.
- `tests/self_test/test_readiness_bytes_unchanged.py` ≤ 1 s.
- `check-local-system-readiness.sh --skip-external --use-program=self_test-sample`
  ≤ 5 s.

## Test / evidence tier map (entry 04)

| Artifact | Tier |
|---|---|
| `test_readiness_bytes_unchanged.py` | contract |
| `test_simulation_state_bytes.py` | contract |
| `test_idempotent_report.py` | property |
| `test_conflicting_report_rejected.py` | property |
| `test_revision_monotonic.py` | property |
| `test_completion_absorbing.py` | property |
| `test_wait_deadline_restart.py` | integration (filesystem + reload) |
| `test_simulation_happy_three.py` and 5 more | integration |

`NOT_APPLICABLE` for `process` / `deployment` / `provider_live` /
`soak`.

## Gate integration

- VG-0 / VG-1 / VG-2: pass via entry 01's artifacts.
- VG-3: `make test-tier-fast` exit 0.
- VG-4…VG-8: `NOT_APPLICABLE`.

## Documentation and durable-record changes

- `run-self-test.md` amended (simulation env-gate documented).
- No new durable records.

## Cross-repository compatibility

- The reducer's typed envelopes (`WorkRequest`, `Dispatch`, etc.)
  re-export from `pi_monitor.work.work_source`. No runtime import
  of program-named modules.

## Retirement / cleanup

- The `MATHLINT_SELF_TEST_MODE=simulation` switch is permanent;
  the opt-in env stays. Simulation files under
  `math/src/mathlint/self_test/sample_program/` ARE the canonical
  scenarios; entry 06 cites their names.
