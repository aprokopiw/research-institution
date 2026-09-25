# 02 — pi_monitor Fake-Pi Consolidation + Verification Coherence

> **Spec-Kit** artifact. Zero-padded `00–10`. This is `02`. Depends on
> `00`. Unblocks `05`.

## Identity

- **spec_id:** `02-fake-pi-consolidation`
- **owner_repo:** `pi_monitor`
- **owner_repos:** `{pi_monitor, research-institution}`
- **status:** draft
- **depends_on:** `00-verify-constitution-ratification`
- **unblocks:** `05-process-fault-simulation`

## Primary actor

The maintainer / Spec-Kit harness running focused pi_monitor tests
daily, the CI system gating protected-branch merges on pi_monitor's
local VG-0/VG-1/VG-2 gates, and (indirectly) entry 05's process-
simulation harness that will substitute model inference with the
canonical fake-Pi executable.

## Problem statement (current failure evidence)

From the test-and-simulation guide §13 (additional inventory):

- pi_monitor ships **~100 test modules**, **1,535 AST-visible test
  functions**.
- pi_monitor `Makefile` and CI use `unittest discover` as the primary
  runner, while documentation advertises pytest selectors and the
  repo contains pytest-style free functions / async tests. This is
  a Priority-0 collection-parity risk: prove every intended test is
  collected by canonical gate, or migrate to one runner.
- pi_monitor `pyproject.toml` declares no coherent tier markers;
  README advertises a "fast" marker expression with no enforcement.
- The campaign harness (`tests/mathlint_campaign.py`) is labelled
  "end-to-end" but manually finalizes parts of lifecycle; it cannot
  count as `process` S2 evidence per §6 anti-cheat S3.5.e.
- pi_monitor keeps empty reserved test directories; they should be
  removed until real subsystem tests justify them.
- The fake-Pi implementation is inline (`tests/helpers.py::make_fake_pi`)
  and is consumed by **at least** the call sites enumerated in plan
  §1 (mathlint_campaign.py, mathlint_fixture/server.py, plus all
  `tests/test_compose_*` and `tests/test_state_machine_*` files).
  No executable module owns the protocol; no closed action
  vocabulary; no documented scenario format.

## Independent user stories

1. As a **maintainer**, I run one canonical `make test` in
   pi_monitor; it collects every intended test (unittest classes +
   pytest functions) and runs them under one commander.
2. As a **CI author**, my `unittest discover` and `pytest --collect-only`
   in pi_monitor produce identical node-ID hashes for the same tree.
3. As a **fake-Pi consumer**, I import one module:
   `pi_monitor/tests/support/fake_pi_rpc.py`. There is exactly one
   implementation; every other helper delegates.
4. As a **process-simulation author** (entry 05),
   `pi-monitor` exposes a typed Python API for `Scenario` parsing +
   a CLI-mode executable identical to the in-process default, so
   entry 06 can spawn the fake as a subprocess without importing
   pi_monitor internals.
5. As a **maintainer**, all existing
   `tests/test_mathlint_campaign.py`,
   `tests/test_mathlint_faults.py`,
   `tests/test_compose_*`,
   `tests/test_state_machine_*`,
   `tests/test_supervisor_dispatch_rate_limit.py` remain green
   **unchanged at their call sites**.

## Functional requirements (per spec-artifact contract)

FR-1. **`pi_monitor/tests/support/fake_pi_rpc.py`** is canonical and
exposes:

   - `parse_scenario(path: Path | str) -> Scenario`: validates the
     scenario JSON against the closed action vocabulary (entries in
     §8.2 below). Unknown action = immediate `ScenarioParseError`
     with actionable error.
   - `run_scenario(scenario: Scenario, env: Mapping[str, str]) -> int`:
     exec the fake as if invoked from a subprocess, returning exit
     code (process attaches to caller-provided stdout / stderr).
   - `cli_main()` (`__main__.py`-style): make the file runnable as
     a CLI (`python -m pi_monitor.tests.support.fake_pi_rpc
      <scenario.json>`) for entry 06's subprocess use.

   The closed action vocabulary (initial subset, extended in entry
   05) is:

   ```
   settle_after_artifact_write
   settle_no_repository_change
   publish_accepted_outcome
   publish_blocked_outcome
   publish_malformed_outcome
   stream_usage_slowly
   emit_usage_burst
   tool_start_tool_end_around_delay
   remain_tool_active_beyond_wedge
   silent_while_alive
   delay_first_rpc_response
   close_stdout_pipe
   exit_before_publication
   exit_after_publication
   duplicate_publication
   conflicting_duplicate_publication
   malformed_rpc_json
   unknown_rpc_event
   provider_rate_limit_diagnostic_with_retry_after
   authentication_failure_diagnostic
   ignore_abort_once_then_ack
   spawn_child_process_for_shutdown_tree
   never_settle_bounded_by_test_timeout
   ```

FR-2. **No new ad-hoc fake-Pi scripts** are introduced. Every
existing `os.system("python -c ...")` / inline script / generated
shim that feeds fake-Pi is replaced by an import of `fake_pi_rpc`.

FR-3. **`pi_monitor/tests/helpers.py::make_fake_pi`** becomes a
thin wrapper that writes or invokes `fake_pi_rpc.py` (preserving
existing call sites' signatures).

FR-4. **Tier / dependency static checks** (FR-2 / FR-3 of entry 01
re-shaped):
   - `pi_monitor/tests/static/test_closed_tier_vocabulary.py`
   - `pi_monitor/tests/static/test_dependency_vocabulary.py`
   - `pi_monitor/tests/static/test_skip_xfail_baseline.py` +
     companion `tests/static/skip_xfail_baseline.toml`.

FR-5. **`pi_monitor/Makefile`** gains the same tier-routed targets
as math (entry 01 FR-5), plus:

   - `test-suite-unified`: a single command that runs every
     intended test under the canonical runner (collected
     collection === python -m unittest discover count + pytest
     collected count, asserted by `tests/static/test_collection_parity.py`).
   - `test-suite-parity`: cross-asserts the two collectors
     produce identical node-ID sets.

FR-6. **`pi_monitor/.pi-glla` mutations** that today occur only
under `unittest discover` are ALSO produced under pytest; this
preserves existing TTY / coverage / async test compatibility. The
canonical command is the one and only.

FR-7. **Empty reserved directories** in
   `pi_monitor/tests/{e2e,smoke,acceptance,...}` (those not yet
   housing real tests) are removed; README promises about them are
   deleted.

FR-8. **Campaign harness relabel.** `tests/mathlint_campaign.py`'s
   docstring + README + AGENTS reference changes from "end-to-end
   harness" to "composed campaign fixture (manual finalization
   phase)" until entry 05 removes the manual finalize hooks.

FR-9. **Cross-repo exemption registry rows** for any legacy file
that legitimately retains one of the six forbidden strings during
the migration window, appended with
`expiry_spec_id = "02-fake-pi-consolidation"`.

## Explicit exclusions (boundary discipline)

- Removing `make_fake_pi` (it stays as a thin wrapper, per FR-3).
- Reimplementing fake-Pi from scratch (the existing
  `make_fake_pi` body is the substrate; FR-1 lifts it to a module).
- New `process`-tier scenarios (entry 05 owns them).
- Adding `process`-tier to pi_monitor's local tests (the existing
  compose tests are `integration`+ `process`; reclassification is
  bookkeeping, not new test creation).
- Cross-repo durable records (none changed by this entry; the
  fake-Pi protocol is documented in pi_monitor docs/adr/, not as
  cross-repo records).

## Measurable success criteria

- `python -m pytest --collect-only -q` and
  `python -m unittest discover` produce identical node-ID
  sets (asserted by `tests/static/test_collection_parity.py`).
- `make test-suite-unified` exits 0.
- `pytest -q tests/static/test_closed_tier_vocabulary.py
       tests/static/test_dependency_vocabulary.py
       tests/static/test_skip_xfail_baseline.py` exits 0.
- `python -m pi_monitor.tests.support.fake_pi_rpc
   /tmp/happy-settle.json --selftest` exits 0 (smoke).
- Every existing
  `tests/test_mathlint_campaign.py`,
  `tests/test_mathlint_faults.py`,
  `tests/test_compose_*`,
  `tests/test_state_machine_*`,
  `tests/test_supervisor_dispatch_rate_limit.py` remains green at
  its call site unchanged.
- `make check-prime-directive` exits 0 at pi_monitor HEAD.
- `pi_monitor/tests/test_spec_kit_cycle_source.py` exits 0
  (15 tests covering the audit-close-out gate, lex discovery,
  capabilities, and the source_for factory routing).
- `python -c "from pi_monitor.work.sources import SpecKitCycleSource; print(SpecKitCycleSource.kind)"`
  exits 0.
- `bash research-institution/scripts/spec-kit-cycle.sh --dry-run`
  exits 0 from a clean working tree at HEAD.

## Failure and edge cases

- **F-1.** A pytest test discovers a `_fakes.py` injection in
  `tests/support/` that the unittest collector misses. The
  parity check flags it; either add an `__init__.py` (preferred) or
  move the helper so both collectors see it.
- **F-2.** A scenario uses an unknown action. The fake rejects
  before publishing anything.
- **F-3.** The campaign harness still calls `finalize_attempt`
  directly. FR-8 only relabels; entry 05 removes the manual
  finalize path. Documented in META.

## Dependencies on earlier entries

- **Entry 00** — verify-constitution §1, §2, §3, §5, §8, §10, §11.

## "Cannot claim done when…"

1. `pi_monitor/tests/support/fake_pi_rpc.py` does not exist.
2. `parse_scenario` accepts an unknown action.
3. A second ad-hoc fake-Pi implementation is introduced outside
   `fake_pi_rpc.py`.
4. `tests/static/test_collection_parity.py` fails.
5. Any of the four old happy-path tests lose green status by
   virtue of this entry.
6. `mathlint_campaign.py` still bears the "end-to-end" marker
   with no follow-on to entry 05.
7. Tier-routed `Makefile` targets absent.
8. Empty reserved dirs still present.
9. Required-lane skip count is non-zero.
10. `transient-exemptions.toml` is mutated without version bump.
11. Entry 00 twelve cannot-claim-done clauses do NOT all hold at
    pi_monitor HEAD.
12. The strengthened grep is not clean at pi_monitor HEAD.
13. `pi_monitor/work/sources/spec_kit_cycle.py` is missing or
    `kind` is not `spec-kit-cycle`.
14. `RoadmapKind.SPEC_KIT_CYCLE` is missing from
    `pi_monitor/config/config.py`.
15. `research-institution/scripts/spec-kit-cycle.sh --dry-run`
    does not exit 0 from a clean working tree.
16. `pi_monitor/tests/test_spec_kit_cycle_source.py` is missing
    or fails any of its 15 tests.
17. `research-institution/pi-monitor.cycle.toml` is missing or
    `roadmap` is not `spec-kit-cycle`.

## Non-goals

- Designing new RPC verbs (the wire authority is
  `pi_monitor.protocol.source_wire`).
- Removing the campaign harness (entry 05 reshapes it).
- Re-implementing `ExternalWorkSource` (entry 05 lands any
  supervisor-side fault work).

## Cross-references

- `.specify/memory/constitution-verify.md` §1, §2, §3, §8, §10.
- `pi_monitor/AGENTS.md` PRIME DIRECTIVE + INV-022…INV-024.
- `pi_monitor/src/pi_monitor/protocol/source_wire.py` (wire
  vocabulary; immutable).
- `pi_monitor/src/pi_monitor/work/external_source.py` (consumer
  of fake-Pi behavior in fixtures).
- `@ADR-0006` (pi_monitor long-running command protection).
- `@ADR-0007` (pi_monitor deterministic context controller
  shadow mode — fake-Pi is exactly this).
- `@ADR-0009` (bounded recovery and soft circuit).
- `@ADR-0095-prime-directive-mechanical-enforcement` (entry 00).
- `@CTR-0095-prime-directive-check-script-contract` (entry 00).
