# 04 — Tasks

## Milestones

- **M1** — typed scenario / frontier / report models + canonical-
  byte fingerprinting.
- **M2** — reducer + idempotency / monotonicity / completion
  absorbing tests.
- **M3** — env-gate + register.py dispatch + byte-preservation
  test.
- **M4** — six canonical scenarios + integration tests.
- **M5** — optional `ProgramProviders.report_sink` field (FR-7)
  + real-source adapter test + audit-close.

## M1 — Models + canonical bytes

- [ ] **T1.1** — write
      `math/src/mathlint/self_test/sample_program/_support/canonical_bytes.py`
      with `dumps(obj) -> bytes` (sorted keys, trailing newline
      fixed).
      **verify:** unit test confirms `dumps({"b":1,"a":2}) == dumps({"a":2,"b":1})`.
      **path:** `math/src/mathlint/self_test/sample_program/_support/canonical_bytes.py`

- [ ] **T1.2** — write
      `math/src/mathlint/self_test/sample_program/simulation_state.py`
      with `Scenario`, `Frontier`, `AcceptedReport`,
      `DecisionRecord` dataclasses (frozen, slots=True;
      @ADR-0014 discipline; re-exporting pi_monitor types
      TYPE_CHECKING for wire shapes).
      **verify:** import + round-trip.
      **path:** `math/src/mathlint/self_test/sample_program/simulation_state.py`

- [ ] **T1.3** — write `test_simulation_state_bytes.py` covering
      fingerprint determinism.
      **verify:** exit 0.
      **path:** `math/tests/self_test/test_simulation_state_bytes.py`

- [ ] **T1.4** — first commit. Strong-grep clean.

**M1 exit:** models + canonical bytes committed; bit-for-bit
determinism proven.

## M2 — Reducer + property tests

- [ ] **T2.1** — write
      `math/src/mathlint/self_test/sample_program/simulation_reducer.py`
      with the pure function
      `reduce(state, accepted_reports) -> (state, decision)`.
      Six scenarios covered (FR-4).
      **verify:** per-scenario unit test green.
      **path:** `math/src/mathlint/self_test/sample_program/simulation_reducer.py`

- [ ] **T2.2** — write property-style tests:
      - `test_idempotent_report.py` (FR-6).
      - `test_conflicting_report_rejected.py`.
      - `test_revision_monotonic.py`.
      - `test_completion_absorbing.py`.
      **verify:** `pytest -q tests/self_test/test_idempotent_report.py`
      and four siblings; each exits 0.
      **path:** `math/tests/self_test/`

- [ ] **T2.3** — second commit.

**M2 exit:** reducer + four property tests green; mutation
challenges caught.

## M3 — Env-gate + byte-preservation

- [ ] **T3.1** — write
      `test_readiness_bytes_unchanged.py` proving the readiness
      envelope is byte-for-byte preserved across all changes.
      **verify:** `pytest -q tests/self_test/test_readiness_bytes_unchanged.py`
      exits 0.
      **path:** `math/tests/self_test/test_readiness_bytes_unchanged.py`

- [ ] **T3.2** — add
      `simulation_register.py` registration guarded by
      `MATHLINT_SELF_TEST_MODE=simulation`; the readiness path
      in `register.py` remains unchanged.
      **verify:** `import mathlint.self_test.sample_program`
      exits 0 with no env var; with `MATHLINT_SELF_TEST_MODE=simulation`
      set, the simulation provider is registered.
      **path:** `math/src/mathlint/self_test/sample_program/simulation_register.py`,
      `math/src/mathlint/self_test/sample_program/register.py`

- [ ] **T3.3** — third commit. Strong-grep clean.

**M3 exit:** env-gated; readiness unchanged.

## M4 — Six canonical scenarios + integration

- [ ] **T4.1** — write six scenario JSONs at
      `math/src/mathlint/self_test/sample_program/scenarios/`
      (happy-three-cycle, no-delta-redirect, blocked-alternate,
      source-wait-then-work, operator-required,
      stop-completion).
      **verify:** each JSON parses; reducer unit tests
      cover each.
      **path:** `math/src/mathlint/self_test/sample_program/scenarios/*.json`

- [ ] **T4.2** — write the integration test
      `test_wait_deadline_restart.py` covering F-2 + reload
      semantics.
      **verify:** exit 0.
      **path:** `math/tests/self_test/test_wait_deadline_restart.py`

- [ ] **T4.3** — fourth commit. Strong-grep clean.

**M4 exit:** six scenarios + integration tests green.

## M5 — Optional `ProgramProviders.report_sink` (FR-7)

(Only invoked if entry 06 requires report ingestion at the
provider boundary.)

- [ ] **T5.1** — extend
      `math/src/mathlint/program_providers.py` `ProgramProviders`
      with optional `report_sink: Callable[[...], None] | None`
      defaulting to `None`.
      **verify:** import + builder syntax.
      **path:** `math/src/mathlint/program_providers.py`

- [ ] **T5.2** — entry-point compat test, real-source adapter
      test, sample registration test, generickernel-import test.
      **verify:** all four green.
      **path:** `math/tests/program_providers/`,
      `math/tests/orchestration/test_real_source_adapter.py`,
      `math/tests/self_test/test_simulation_register.py`,
      `math/tests/static/test_no_program_named_imports.py`.

- [ ] **T5.3** — fifth commit (only if FR-7 is invoked;
      otherwise skip + record `NOT_APPLICABLE` in META).

**M5 exit:** optional extension (if invoked) green; otherwise
logged as `NOT_APPLICABLE`.

## Final audit-close

- [ ] **T6.1** — emit META.md + attestation; verify all twelve
      cannot-claim-done clauses hold; emit `tests/self_test/test_*.py`
      collection deterministic inventory hash.

**M5/M6 exit:** entry closed; entry 06 unblocked.
