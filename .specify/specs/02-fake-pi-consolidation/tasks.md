# 02 — Tasks

## Milestones

- **M1** — canonical fake-Pi module + selftest.
- **M2** — thin-wrapper migration + commit phasing.
- **M3** — tier / dependency / skip static checks + Makefile +
  parity check.
- **M4** — empty-dir cleanup + relabel + audit-close.

## M1 — Canonical fake-Pi

- [ ] **T1.1** — create
      `pi_monitor/tests/support/fake_pi_rpc.py` exposing
      `parse_scenario`, `run_scenario`, `cli_main`, and a
      `--selftest` CLI mode that emits "self-test ok" deterministic
      text and exits 0.
      **verify:** `python -m pi_monitor.tests.support.fake_pi_rpc --selftest`
      exits 0.
      **path:** `pi_monitor/tests/support/fake_pi_rpc.py`

- [ ] **T1.2** — write unit tests
      `tests/support/test_fake_pi_rpc.py` covering: happy-path
      scenario parse; unknown action rejected;
      environment-sanitization refuses
      `OPENAI_API_KEY`-bearing env.
      **verify:** `pytest -q tests/support/test_fake_pi_rpc.py`
      exits 0.
      **path:** `pi_monitor/tests/support/test_fake_pi_rpc.py`

- [ ] **T1.3** — first commit: T1.1–T1.2; verify `make check-prime-directive`
      exits 0 in pi_monitor at HEAD.

**M1 exit:** `fake_pi_rpc.py` exists and passes its own selftest.

## M2 — Thin-wrapper migration

- [ ] **T2.1** — refactor
      `pi_monitor/tests/helpers.py::make_fake_pi` to delegate to
      `fake_pi_rpc.parse_scenario` + write the executable
      artifact (preserving the helpers' existing signature so
      call sites are untouched).
      **verify:** existing call-sites
      (`tests/test_mathlint_campaign.py`,
      `tests/test_mathlint_faults.py`,
      `tests/test_compose_*`,
      `tests/test_state_machine_*`,
      `tests/test_supervisor_dispatch_rate_limit.py`) still pass
      unchanged.
      **path:** `pi_monitor/tests/helpers.py`

- [ ] **T2.2** — search
      `pi_monitor/tests/` and `pi_monitor/src/` for any second
      fake-Pi implementation; if any exist, replace with a
      `fake_pi_rpc` invocation. Document in
      `tests/static/test_fake_pi_inventory.py` (a tracker that
      greps for `os.system("python -c ...")` or
      `subprocess.Popen([..., "fake-pi"])` patterns and asserts
      no second implementation exists).
      **verify:** `pytest -q tests/static/test_fake_pi_inventory.py`
      exits 0.
      **path:** `pi_monitor/tests/static/test_fake_pi_inventory.py`

- [ ] **T2.3** — second commit: T2.1–T2.2; verify all five happy-path
      test files remain green; `make check-prime-directive` exits 0.

**M2 exit:** zero second fake-Pi implementations; existing
call-sites unchanged.

## M3 — Tier / dependency / skip static checks + Makefile

- [ ] **T3.1** — write the three static checks
      (`test_closed_tier_vocabulary.py`,
      `test_dependency_vocabulary.py`,
      `test_skip_xfail_baseline.py`) per entry 01's FR-2/FR-3/FR-4
      (same shape, pi_monitor paths).
      **verify:** per-module `pytest -q` exits 0.
      **path:** `pi_monitor/tests/static/`

- [ ] **T3.2** — write
      `pi_monitor/tests/static/test_collection_parity.py`
      asserting pytest + unittest-discover produce identical
      collected node-ID sets.
      **verify:** `pytest -q tests/static/test_collection_parity.py`
      exits 0.
      **path:** `pi_monitor/tests/static/test_collection_parity.py`

- [ ] **T3.3** — amend `pi_monitor/Makefile` per entry 01 FR-5
      (eight tier-routed targets) + `test-suite-unified` +
      `test-suite-parity` (per plan FR-5).
      **verify:** `make test-suite-unified` exits 0; `make test-suite-parity`
      exits 0.
      **path:** `pi_monitor/Makefile`

- [ ] **T3.4** — third commit: T3.1–T3.3; verify `make test-tier-fast`,
      `make test-suite-unified`, `make test-suite-parity`,
      `make check-prime-directive` all exit 0.

**M3 exit:** tier / dependency / skip / parity checks wired into
the canonical commander; required-lane skip count zero.

## M4 — Empty-dir cleanup + relabel + audit-close

- [ ] **T4.1** — delete
      `pi_monitor/tests/{e2e,smoke,acceptance,endurance,chaos}_*`
      directories if empty per the master guide §13 cleanup list;
      migrate any non-empty folder's contents to owner subsystem.
      **verify:** `find pi_monitor/tests/` returns no empty dir.
      **path:** `pi_monitor/tests/`

- [ ] **T4.2** — relabel
      `pi_monitor/tests/mathlint_campaign.py` docstring
      ("end-to-end campaign fixture (manual finalization phase —
      refactor slated for entry 05)") + update cross-references
      in `pi_monitor/README.md`, `pi_monitor/AGENTS.md` Working
      Rules section.
      **verify:** `grep -E 'end-to-end' pi_monitor/tests/mathlint_campaign.py`
      reports the new docstring phrase; README + AGENTS.md cross-
      refs updated.
      **path:** `pi_monitor/tests/mathlint_campaign.py`,
      `pi_monitor/README.md`, `pi_monitor/AGENTS.md`

- [ ] **T4.3** — append
      `transient-exemptions.toml` pi_monitor rows with
      `expiry_spec_id = "02-fake-pi-consolidation"` for the
      legacy exempt files (e.g. the
      `tests/mathlint_fixture/` exemption, the
      `mathlint_campaign.py` exempt slot).
      **verify:** TOML parses; row count ≥ 1.
      **cross:** `research-institution/.specify/memory/transient-exemptions.toml`

- [ ] **T4.4** — fourth commit (T4.1–T4.3); verify all twelve
      cannot-claim-done clauses hold; strengthened grep clean at
      pi_monitor HEAD.

- [ ] **T4.5** — emit META.md + attestation for entry 02 via the
      local attestation emitter.

**M4 exit:** META emitted; entry 02 closed; entry 05 unblocked.

## M5 — pi-monitor spec-kit-cycle wire-up

This milestone wires the cycle adapter that drives the eleven-entry
program end-to-end. The adapter itself is implemented in
pi_monitor (M5 ships the entry); research-institution ships the
operator glue (cycle.toml + the spec-kit-cycle.sh entry point).

- [ ] **T5.1** — implement
      `pi_monitor/src/pi_monitor/work/sources/spec_kit_cycle.py`
      exposing `kind = "spec-kit-cycle"` and the
      `[audit-close-out]` tickable synthesis. The adapter
      composes the canonical `SpecKitTaskSource` scanner and
      gates every entry on its META.md + per-entry attestation
      JSON digest.
      **verify:** `pi_monitor/tests/test_spec_kit_cycle_source.py`
      passes (15 tests).
      **path:** `pi_monitor/src/pi_monitor/work/sources/spec_kit_cycle.py`

- [ ] **T5.2** — register the new roadmap value in
      `pi_monitor/src/pi_monitor/config/config.py`:
      `RoadmapKind.SPEC_KIT_CYCLE`,
      `SPEC_KIT_CYCLE_DEFAULT_GLOBS = [".specify/specs/*/tasks.md"]`,
      and the matching branch in
      `validate_semantic_config`.
      **verify:** `python -c "from pi_monitor.config.config import
      RoadmapKind; print(RoadmapKind.SPEC_KIT_CYCLE.value)"`
      exits 0.
      **path:** `pi_monitor/src/pi_monitor/config/config.py`

- [ ] **T5.3** — route `roadmap = "spec-kit-cycle"` through the
      `sources/__init__.py::source_for` factory to the new
      adapter. Existing `SpecKitSource` and `GoalsSource`
      contracts unchanged.
      **verify:** `pi_monitor/tests/test_sources_contract.py`
      still passes (37 tests, byte-for-byte).
      **path:** `pi_monitor/src/pi_monitor/work/sources/__init__.py`

- [ ] **T5.4** — author
      `research-institution/scripts/spec-kit-cycle.sh` (operator
      entry point) and `research-institution/pi-monitor.cycle.toml`
      (canonical supervisor config). Both are byte-equal in
      shape; the script does dry-run preflight + git-clean
      check + META strict validation before launching.
      **verify:** `bash scripts/spec-kit-cycle.sh --dry-run`
      exits 0; `--help` exits 0.
      **path:** `research-institution/scripts/spec-kit-cycle.sh`,
      `research-institution/pi-monitor.cycle.toml`

- [ ] **T5.5** — fifth commit (T5.1–T5.4); verify all fourteen
      cannot-claim-done clauses hold; strengthened grep clean at
      research-institution HEAD; `bash scripts/check-prime-directive.sh --enforce`
      exits 0; `make check-prime-directive-enforced` exits 0 in
      every repo at HEAD.

- [ ] **T5.6** — emit META.md + attestation for entry 02 via the
      local attestation emitter (final; supersedes T4.5).

**M5 exit:** cycle adapter wired; operator can launch
`bash scripts/spec-kit-cycle.sh` from a clean working tree and
have pi-monitor drive entries 00 through 10 autonomously.

