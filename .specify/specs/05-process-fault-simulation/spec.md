# 05 — Supervisor Process and Fault Simulation Substrate

> **Spec-Kit** artifact. Zero-padded `00–10`. This is `05`. Depends on
> `02`. Unblocks `06`.

## Identity

- **spec_id:** `05-process-fault-simulation`
- **owner_repo:** `pi_monitor`
- **owner_repos:** `{pi_monitor, research-institution}`
- **status:** draft
- **depends_on:** `02-fake-pi-consolidation`
- **unblocks:** `06-autonomous-composed-simulation`

## Primary actor

The maintainer / process-simulation harness that runs fake-Pi as a
real subprocess against the existing supervisor. Entry 06 is the
first consumer at the S2 boundary; this entry builds the
**substrate** (scenario runtime, transcript oracles, restart
primitives).

## Problem statement

Pi_monitor today has:

- A scenario-driven fake-Pi helper (`tests/helpers.py::make_fake_pi`,
  today inline; consolidated in entry 02).
- A campaign harness (`tests/mathlint_campaign.py`) that exercises
  the supervisor + external source + fake-Pi, but **manually
  finalizes** parts of execution via
  `complete_active` / `finalize_attempt` / `finalize_record` /
  `record_publication`.
- A source fixture with fault controls
  (`tests/mathlint_fixture/server.py`).
- Existing fault tests in `tests/test_mathlint_faults.py`.

What's missing per the master guide §1 (Pi-monitor campaign +
fault harness) and §6 (Pi RPC/transport antagonists):

- A clean **scenario vocabulary** for the fake-Pi subprocess
  (consolidated in 02; runtime wiring lives here).
- **Restart primitives** at every durable boundary; today tests
  rely on harness internals.
- **Transcript oracles** reusable by entry 06's S2 tests.
- **Process-tree cleanup** verification (no zombie grandchild).
- **Deterministic timing seams** (sub-second fake clock; no
  `time.sleep` across processes).

## Independent user stories

1. As a **process-simulation author**, I run
   `fake_pi_rpc` as a subprocess in a test, exercise one scenario,
   and use a typed transcript oracle to assert the expected event
   subsequence + forbidden events.
2. As a **restart-boundary author**, I run
   `RestartAtBoundaryHelper.at(boundary=...)` to issue a
   process kill exactly between two durable-write boundaries, then
   verify reconcile action is "issue once / supersede / hold /
   noop / reactivate" matching the table at
   `pi_monitor/src/pi_monitor/state/execution_records.py`.
3. As a **process-tree owner**, my fake-Pi subprocess spawns a
   detached grandchild; the supervisor's stop() reaches it via
   `killpg(start_new_session=True)` cleanup.
4. As a **transcript consumer**, I get a structured transcript
   that excludes secrets by construction.

## Functional requirements

FR-1. **`pi_monitor/tests/substrate/fake_pi_scenario.py`** provides:

   - re-export of `Scenario`, `parse_scenario`, `run_scenario` from
     entry 02's `fake_pi_rpc.py`;
   - extension of the closed action vocabulary to wire-up steps
     needed for **restart** scenarios (e.g. `crash_before_publication`,
     `exit_after_publication`, etc. — already in entry 02's list,
     behaviourally wired here).

FR-2. **`pi_monitor/tests/substrate/restart_at_boundary.py`** provides:

   - `RestartAtBoundaryHelper(boundary: BoundaryName)` where
     `BoundaryName` is a closed enum:
     ```
     BEFORE_EXECUTION_RECORD
     AFTER_INTENT_BEFORE_WORKER_LAUNCH
     AFTER_LAUNCH_BEFORE_FIRST_EVENT
     DURING_ACTIVE_TOOL_USE
     AFTER_ARTIFACT_BEFORE_PUBLICATION
     AFTER_PUBLICATION_BEFORE_FINALIZE
     AFTER_FINALIZE_BEFORE_REPORT_SEND
     AFTER_REPORT_SEND_BEFORE_ACK
     AFTER_ACK_BEFORE_REPORT_DELIVERED
     DURING_TIMED_SOURCE_WAIT
     DURING_TIMED_RATE_DEFER
     DURING_SOURCE_PROCESS_RESTART_BACKOFF
     ```
   - `helper.run(...)` starts the supervisor subprocess, captures
     the durable-write boundary log, kills the subprocess at the
     named boundary, restarts the supervisor, returns the
     reconcile verdict.

FR-3. **`pi_monitor/tests/substrate/transcript_oracle.py`** provides:

   - `TranscriptOracle(stream)` reads the canonical JSON transcript
     (one line per event) emitted by the fake-Pi subprocess side-
     channel; rejects any line containing a substring like
     `OPENAI_API_KEY`, `sk-`, `Bearer `, or a configurable deny-list.
   - `assert_event_sequence(oracle, expected, forbidden)`: typed.

FR-4. **`pi_monitor/tests/substrate/process_tree_cleanup.py`** verifies
that a fake-Pi subprocess spawning a detached grandchild (via
`start_new_session=True` + the existing
`FAKE_PI_CHILD_PID_FILE` knob from
`tests/helpers.py::make_fake_pi`) is fully reaped when
`supervisor.stop()` runs `killpg`. Uses
`psutil.Process(pid)` to enumerate descendants at kill time.

FR-5. **`pi_monitor/tests/substrate/timing_seams.py`** provides:

   - `FakeSubprocessClock()` — controls fake-Pi's internal monorime
     via an env var (already partly done via `FAKE_PI_*` knobs).
   - `bounded_deadline(seconds, fn)`: helper to run a coroutine
     with a bounded deadline that does NOT cross-process (no
     `time.time` monkeypatch across process boundaries).

FR-6. **Existing fault tests** (`tests/test_mathlint_faults.py` and
related) are re-targeted to **public** substrate helpers
(`substrate.process_tree_cleanup` instead of inline
`start_new_session()` and `killpg()`).

FR-7. **Campaign harness manual finalize hooks** are removed.
`tests/mathlint_campaign.py` no longer calls
`complete_active` / `finalize_attempt` / `finalize_record` /
`record_publication`. The harness drives the loop through the
external-source wire; lifecycle is the kernel's responsibility.

FR-8. **Per-scenario metadata** is added on every new substrate
helper call site:
```
name
owner
minimum_tier
maximum_runtime_seconds
fault_injection_point
expected_final_state
required_event_subsequence
forbidden_events
cleanup_expectations
real_incident_or_plausible_failure_rationale
```

The static check `tests/static/test_substrate_metadata.py`
verifies every substrate-helper call has its metadata.

FR-9. **Fake-Pi detaches grandchild** scenario verifies
cleanup-reach behavior end-to-end at the
`process-tree-cleanup.py` helper.

FR-10. **No new helper duplicates an existing one**. The static
check `tests/static/test_substrate_inventory.py` greps for
imports across the substrate helpers + existing
`tests/helpers.py::make_fake_pi` and asserts no second
implementation exists.

## Explicit exclusions

- Adding `process`-tier scenarios that exercise math
  (`tests/test_mathlint_*` already there; entry 06 owns the
  cross-repo composition).
- Changing `pi_monitor/src/pi_monitor/protocol/source_wire.py`
  (wire vocabulary).
- Replacing `state/execution_records.py`.

## Measurable success criteria

- `pytest -q tests/substrate/` exits 0.
- `pytest -q tests/test_mathlint_faults.py` exits 0 (existing)
  with no manual finalize calls.
- `pytest -q tests/mathlint_campaign.py` exits 0; the harness's
  docstring + AGENTS reference lose the "manual finalization
  phase" phrasing.
- `tests/static/test_substrate_metadata.py` exits 0.
- `tests/static/test_substrate_inventory.py` exits 0.
- `make check-prime-directive` exits 0 at pi_monitor HEAD.

## Failure and edge cases

- **F-1.** A new helper duplicates `tests/helpers.py::make_fake_pi`.
  Static check catches.
- **F-2.** A scenario's metadata set is incomplete. Static check
  catches.
- **F-3.** A detached grandchild survives killpg. Process tree
  test catches.
- **F-4.** A transcript line contains a secret. Oracle rejects.

## Dependencies on earlier entries

- **Entry 00** — `constitution-verify.md` §3, §5, §8.
- **Entry 02** — `fake_pi_rpc.py`; closed action vocabulary.

## "Cannot claim done when…"

1. `tests/substrate/` does not exist.
2. `tests/mathlint_campaign.py` still calls a manual finalize.
3. A scenario has incomplete metadata.
4. A second fake-Pi implementation exists (inventory check fails).
5. Transcript oracle contains a denied substring.
6. Process-tree cleanup leaves a surviving grandchild.
7. `tests/static/test_substrate_metadata.py` fails.
8. `tests/static/test_substrate_inventory.py` fails.
9. `make check-prime-directive` fails at pi_monitor HEAD.
10. Entry 00/01/02 cannot-claim-done clauses do NOT hold at
    pi_monitor HEAD.
11. `tests/test_mathlint_faults.py` regressed.
12. `time.time` is monkeypatched across processes in the new
    helpers.

## Non-goals

- Re-implementing the supervisor.
- Adding new math sample programs (entry 04).
- Cross-repo scenario composition (entry 06).

## Cross-references

- `pi_monitor/AGENTS.md` INV-001…INV-025; INV-022…INV-025 are
  substrate-relevant.
- `.specify/memory/constitution-verify.md` §3, §5, §8, §10, §11.
- Entry 02's `fake_pi_rpc.py` substrate.
- `@ADR-0006`, `@ADR-0007`, `@ADR-0009` (pi_monitor).
- `@ADR-0095-prime-directive-mechanical-enforcement`.
