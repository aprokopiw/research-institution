# 06 — Tasks

## Milestones

- **M1** — verify-simulation package skeleton + temp_root.
- **M2** — five independent oracles.
- **M3** — scenarios registry + 14 canonical scenarios.
- **M4** — green-gate `v-compose` extension + per-scenario
  metadata + audit-close.

## M1 — Package skeleton + temp_root

- [ ] **T1.1** — create
      `research_institution/gates/verify_simulation/{__init__,cli,runner,temp_root,scenarios}.py`.
      **verify:** `python -c "from research_institution.gates.verify_simulation import cli; print(cli)"` exits 0.
      **path:** `research_institution/gates/verify_simulation/`

- [ ] **T1.2** — implement `temp_root.py`
      `temp_root_factory(*, scenario: str) -> Iterator[TempRoot]`
      (unique id; cleanup on success; preserve-on-failure).
      **verify:** unit test asserts temp_root is cleaned on success
      and preserved on failure.
      **path:** `research_institution/gates/verify_simulation/temp_root.py`

- [ ] **T1.3** — implement `runner.py` `run_scenario(scenario: Scenario, *, temp_root) -> ScenarioReport`.
      **verify:** unit test asserts the report carries three
      oracle verdicts (initially stub).
      **path:** `research_institution/gates/verify_simulation/runner.py`

- [ ] **T1.4** — first commit; verify `make check-prime-directive`
      exits 0 at research-institution HEAD.

**M1 exit:** package skeleton + temp_root + runner exist.

## M2 — Five independent oracles

- [ ] **T2.1** — `oracle/transcript.py` wraps entry 05's
      `transcript_oracle.py`; typed `TranscriptReport`.
      **verify:** unit test green.
      **path:** `research_institution/gates/verify_simulation/oracle/transcript.py`

- [ ] **T2.2** — `oracle/audit.py` runs
      `pi_monitor.state.audit.audit_chain_verify.py`; typed
      `AuditReport`.
      **verify:** unit test green.
      **path:** `research_institution/gates/verify_simulation/oracle/audit.py`

- [ ] **T2.3** — `oracle/exactly_once.py`: per
      `(source_identity, operation_id, revision_fingerprint)`
      invariants.
      **verify:** unit test green.
      **path:** `research_institution/gates/verify_simulation/oracle/exactly_once.py`

- [ ] **T2.4** — `oracle/frontier.py`: frontier revision
      changes at expected events.
      **verify:** unit test green.
      **path:** `research_institution/gates/verify_simulation/oracle/frontier.py`

- [ ] **T2.5** — `oracle/resource.py`: subprocess count
      returns to baseline; no surviving children.
      **verify:** unit test green.
      **path:** `research_institution/gates/verify_simulation/oracle/resource.py`

- [ ] **T2.6** — second commit; verify static checks for the
      new packages green.

**M2 exit:** five oracles implemented + tested.

## M3 — Scenarios registry + 14 canonical scenarios

- [ ] **T3.1** — `scenarios.py` registry: `register(name: str, **metadata)`;
      `lookup(name)` returns the scenario + its metadata.
      **verify:** unit test green.
      **path:** `research_institution/gates/verify_simulation/scenarios.py`

- [ ] **T3.2** — write 14 scenario modules under
      `research-institution/tests/simulation/scenarios/`,
      each with metadata schema per FR-6.
      **verify:** `tests/static/test_closed_scenario_metadata.py`
      parses each module; missing-key tests fail.
      **path:** `research-institution/tests/simulation/scenarios/*.py`

- [ ] **T3.3** — wire six entry-04 scenarios by reference
      (NOT copy); eight substrate scenarios from entry 05
      similarly referenced.
      **verify:** `scenarios.lookup("happy-three-cycle")`
      returns metadata pointing at entry 04's
      `math/src/mathlint/self_test/sample_program/scenarios/happy-three-cycle.json`.
      **path:** `research-institution/gates/verify_simulation/scenarios.py`

- [ ] **T3.4** — third commit; verify all checks green.

**M3 exit:** canonical scenarios registered; metadata complete.

## M4 — Green-gate extension + audit-close

- [ ] **T4.1** — extend
      `research_institution/gates/aggregate.py` `v-compose`
      stage to invoke
      `python -m research_institution verify-simulation --tier full`.
      **verify:** `bash green-gate/check-institution.sh --hermetic`
      (or the canonical `scripts/verify-institution.sh`)
      invokes the canonical CLI; full tier exits 0.
      **path:** `research_institution/gates/aggregate.py`

- [ ] **T4.2** — register the new CLI as a console script in
      `research-institution/pyproject.toml` under
      `[project.scripts]`.
      **verify:** `python -m research_institution verify-simulation --help`
      exits 0; `which verify-simulation` (after install) finds it.
      **path:** `research-institution/pyproject.toml`

- [ ] **T4.3** — twenty-repeated-run flake check
      (Bash loop invoking the canonical scenario command).
      **verify:** `bash scripts/twenty-repeated-runs.sh
       happy-three-cycle` exits 0 with zero flakes.
      **path:** `research-institution/scripts/twenty-repeated-runs.sh`

- [ ] **T4.4** — append
      `transient-exemptions.toml` rows for the new package paths.
      **verify:** TOML parses.
      **cross:** `research-institution/.specify/memory/transient-exemptions.toml`

- [ ] **T4.5** — fourth commit; verify all twelve cannot-claim-done
      clauses hold; strengthened grep clean.

- [ ] **T4.6** — emit META.md + attestation.

**M4 exit:** META emitted; entry 06 closed; entry 07 unblocked.
