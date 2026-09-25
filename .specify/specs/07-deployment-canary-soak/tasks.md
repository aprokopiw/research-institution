# 07 — Tasks

## Milestones

- **M1** — deployment tier (`--tier deployment`).
- **M2** — provider canary (`--tier provider-canary --live`).
- **M3** — soak (`--tier soak --hours N`).
- **M4** — audit-close.

## M1 — Deployment tier

- [ ] **T1.1** — implement
      `research_institution/gates/verify_simulation/deployment.py`
      with the `DeploymentRunner` orchestrating the four cwds +
      rendered `ProgramArguments`.
      **verify:** unit test confirms the runner is callable in
      dry-run mode.
      **path:** `research_institution/gates/verify_simulation/deployment.py`

- [ ] **T1.2** — extend `cli.py` with `--tier deployment` and
      `--macos-isolated-label=<unique>` flags.
      **verify:** `python -m research_institution verify-simulation
      --tier deployment --help` exits 0.
      **path:** `research_institution/gates/verify_simulation/cli.py`

- [ ] **T1.3** — write
      `tests/simulation/test_deployment_cross_cwd.py` — runs the
      four cwd scenarios.
      **verify:** `pytest -q tests/simulation/test_deployment_cross_cwd.py`
      exits 0.
      **path:** `research-institution/tests/simulation/test_deployment_cross_cwd.py`

- [ ] **T1.4** — write
      `tests/simulation/test_program_arguments_match.py` — asserts
      the rendered `ProgramArguments` equals the actual subprocess
      invocation's argv (byte-equal).
      **verify:** exit 0.
      **path:** `research-institution/tests/simulation/test_program_arguments_match.py`

- [ ] **T1.5** — write
      `tests/simulation/test_macos_isolated_label.py` — opt-in;
      asserts isolated label is bootout in `finally`.
      **verify:** exit 0 on a macOS host.
      **path:** `research-institution/tests/simulation/test_macos_isolated_label.py`

- [ ] **T1.6** — first commit; verify dry-run `verify-simulation --tier deployment`
      exits 0; `make check-prime-directive` exits 0.

**M1 exit:** `--tier deployment` green.

## M2 — Provider canary

- [ ] **T2.1** — implement
      `research_institution/gates/verify_simulation/canary.py`
      with `CanaryRunner(rate-defer-restart)`.
      **verify:** unit test asserts the runner BLOCKS when
      credentials are absent; refuses to run without `--live`.
      **path:** `research_institution/gates/verify_simulation/canary.py`

- [ ] **T2.2** — extend `cli.py` with `--tier provider-canary
      --live`; require `--live`.
      **verify:** missing `--live` exits 2 with actionable error.
      **path:** `research_institution/gates/verify_simulation/cli.py`

- [ ] **T2.3** — write
      `tests/simulation/test_canary_credentials_required.py`
      asserting the runner refuses without `MATHLINT_MODEL_ROUTE`
      or `~/.pi/agent/auth.json`.
      **verify:** exit 0 (refusal-correct path).
      **path:** `research-institution/tests/simulation/test_canary_credentials_required.py`

- [ ] **T2.4** — write
      `tests/simulation/test_canary_does_not_mutate_kaplansky.py`
      asserting `kaplansky/programs/kaplansky-roadmap.toml` bytes
      are unchanged before/after the canary.
      **verify:** exit 0.
      **path:** `research-institution/tests/simulation/test_canary_does_not_mutate_kaplansky.py`

- [ ] **T2.5** — second commit; verify
      `--tier provider-canary --live --scenario rate-defer-restart`
      BLOCKED (no credentials) exits 78 in < 30 s; the canary
      runner produces no subprocess leak.

**M2 exit:** `--tier provider-canary --live` is BLOCKED-correct
under absent credentials; never mutates production.

## M3 — Soak

- [ ] **T3.1** — implement
      `research_institution/gates/verify_simulation/oracle/soak.py`
      with `SoakOracle` (memory / CPU / process count /
      state-file growth / audit verification / duplicate reports /
      cycle latency).
      **verify:** unit test green.
      **path:** `research_institution/gates/verify_simulation/oracle/soak.py`

- [ ] **T3.2** — extend `cli.py` with `--tier soak --hours N`;
      require `--hours` (else exit 2).
      **verify:** missing `--hours` exits 2.
      **path:** `research_institution/gates/verify_simulation/cli.py`

- [ ] **T3.3** — write
      `tests/simulation/test_soak_short.py` — a one-minute smoke
      soak with the canonical scenario rotation.
      **verify:** exit 0 in < 90 s.
      **path:** `research-institution/tests/simulation/test_soak_short.py`

- [ ] **T3.4** — third commit; verify smoke green; signed
      evidence archive produced.

**M3 exit:** `--tier soak --hours N` is correct-against-budget.

## M4 — Audit-close

- [ ] **T4.1** — append
      `transient-exemptions.toml` rows for the new tests.
      **verify:** TOML parses.
      **cross:** `research-institution/.specify/memory/transient-exemptions.toml`

- [ ] **T4.2** — fourth commit; verify all twelve
      cannot-claim-done clauses hold; the strengthened grep is
      clean at HEAD.

- [ ] **T4.3** — emit META.md + attestation.

**M4 exit:** META emitted; entry 07 closed; entry 08 unblocked.
