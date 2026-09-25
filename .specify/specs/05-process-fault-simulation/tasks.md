# 05 — Tasks

## Milestones

- **M1** — substrate helpers (5 files).
- **M2** — campaign harness manual finalize removal +
  fault-test retarget.
- **M3** — meta + inventory static checks + audit-close.

## M1 — Substrate helpers

- [ ] **T1.1** — write
      `pi_monitor/tests/substrate/fake_pi_scenario.py` (re-export
      from entry 02's `fake_pi_rpc.py`; closed action vocabulary
      preserved).
      **verify:** import + happy-path scenario returns
      typed `Scenario`.
      **path:** `pi_monitor/tests/substrate/fake_pi_scenario.py`

- [ ] **T1.2** — write
      `pi_monitor/tests/substrate/restart_at_boundary.py` with the
      `BoundaryName` enum + `RestartAtBoundaryHelper`.
      **verify:** unit test passes a synthetic boundary and
      records the reconcile verdict.
      **path:** `pi_monitor/tests/substrate/restart_at_boundary.py`

- [ ] **T1.3** — write
      `pi_monitor/tests/substrate/transcript_oracle.py` with
      secret-substring denial.
      **verify:** unit test injects a denied substring; oracle
      raises.
      **path:** `pi_monitor/tests/substrate/transcript_oracle.py`

- [ ] **T1.4** — write
      `pi_monitor/tests/substrate/process_tree_cleanup.py`
      verifying the detached-grandchild cleanup.
      **verify:** unit test confirms grandchild is reaped.
      **path:** `pi_monitor/tests/substrate/process_tree_cleanup.py`

- [ ] **T1.5** — write
      `pi_monitor/tests/substrate/timing_seams.py` with
      `FakeSubprocessClock` + `bounded_deadline`.
      **verify:** unit test confirms bounded deadline does not
      cross processes.
      **path:** `pi_monitor/tests/substrate/timing_seams.py`

- [ ] **T1.6** — first commit (T1.1–T1.5); verify all checks
      green at pi_monitor HEAD.

**M1 exit:** substrate helpers exist; unit tests pass.

## M2 — Retarget + manual finalize removal

- [ ] **T2.1** — retarget
      `pi_monitor/tests/test_mathlint_faults.py` to use
      substrate helpers.
      **verify:** `pytest -q tests/test_mathlint_faults.py`
      exits 0.
      **path:** `pi_monitor/tests/test_mathlint_faults.py`

- [ ] **T2.2** — remove manual finalize hooks from
      `pi_monitor/tests/mathlint_campaign.py`; harness drives
      the loop through the external-source wire only.
      **verify:**
      - `grep -E 'finalize_attempt|finalize_record|complete_active|record_publication' pi_monitor/tests/mathlint_campaign.py`
        reports no call sites;
      - `pytest -q tests/mathlint_campaign.py` exits 0;
      - the harness's docstring loses the "manual finalization
        phase" phrasing.
      **path:** `pi_monitor/tests/mathlint_campaign.py`

- [ ] **T2.3** — second commit (T2.1–T2.2); verify
      `make check-prime-directive` + `make test-tier-fast` exit 0.

**M2 exit:** retargeted fault tests + clean harness.

## M3 — Meta + inventory + audit-close

- [ ] **T3.1** — write
      `pi_monitor/tests/static/test_substrate_metadata.py`
      verifying per-scenario metadata completeness.
      **verify:** `pytest -q tests/static/test_substrate_metadata.py`
      exits 0.
      **path:** `pi_monitor/tests/static/test_substrate_metadata.py`

- [ ] **T3.2** — write
      `pi_monitor/tests/static/test_substrate_inventory.py`
      asserting no second fake-Pi implementation.
      **verify:** exit 0.
      **path:** `pi_monitor/tests/static/test_substrate_inventory.py`

- [ ] **T3.3** — append
      `transient-exemptions.toml` rows for the new
      tests/substrate/ paths.
      **verify:** TOML parses; row count ≥ 1.
      **cross:** `research-institution/.specify/memory/transient-exemptions.toml`

- [ ] **T3.4** — third commit (T3.1–T3.3); verify all twelve
      cannot-claim-done clauses hold.

- [ ] **T3.5** — emit META.md + attestation.

**M3 exit:** META emitted; entry 05 closed; entry 06 unblocked.
