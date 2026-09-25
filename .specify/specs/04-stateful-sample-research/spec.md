# 04 — Stateful Sample Research Program

> **Spec-Kit** artifact. Zero-padded `00–10`. This is `04`. Depends on
> `01`. Unblocks `06`.

## Identity

- **spec_id:** `04-stateful-sample-research`
- **owner_repo:** `math`
- **owner_repos:** `{math, research-institution, kaplansky}`
- **status:** draft
- **depends_on:** `01-test-suite-rationalization`
- **unblocks:** `06-autonomous-composed-simulation`

## Primary actor

The maintainer / process-simulation harness that needs a multi-cycle
deterministic research program available **without** touching
kaplansky. Entry 06 is the first consumer; entry 05 + 10 reference
its typed envelopes.

## Problem statement

The math self-test fixture
(`math/src/mathlint/self_test/sample_program/`) today is:

- One immutable `Dispatch` envelope (frozen `_ENVELOPE`).
- Fixed `operation_id = "self-test-op"`, fingerprint
  `self-test-fixture-v1`, `decided_unix=0.0`.
- Repository ignored.
- No report-driven progression.
- One-mode: readiness.

The test-and-simulation guide §4 ("Stateful sample research
program") requests an opt-in extension:

- Two explicit modes:
   - **readiness** (default; byte-equivalent to today's envelope).
   - **simulation** (opt-in via
     `MATHLINT_SELF_TEST_MODE=simulation`; stateful multi-cycle
     reducer driven by local files).

## Independent user stories

1. As a **maintainer**, today's readiness call
   (`sample_work_source(Path('/anywhere'))`) returns a `Dispatch`
   that is **byte-for-byte equivalent** to the prior envelope
   when `MATHLINT_SELF_TEST_MODE` is unset.
2. As a **process-simulation author**, I set
   `MATHLINT_SELF_TEST_MODE=simulation` and pass a
   `<program-root>/.simulation/scenario.json`. The sample
   implementation:
   - emits three `Dispatch` envelopes for three distinct
     operations, advancing the frontier revision at each step;
   - on the fourth cycle, emits `Stop(completed)`;
   - rejects a report whose revision is stale;
   - rejects a conflicting duplicate report;
   - absorbs duplicate identical reports idempotently;
   - emits a timed `Wait` whose deadline survives a process
     restart.
3. As an **operator**, the simulation mode never escapes its
   disposable program root; kaplansky's research state is
   untouched.

## Functional requirements

FR-1. **`math/src/mathlint/self_test/sample_program/`** gains:

   - `simulation_state.py` — typed scenario + frontier + report
     models; canonical-byte fingerprinting; append-only journals.
   - `simulation_reducer.py` — pure function:
     `reduce(state, accepted_reports) -> (state, decision)`.
   - `simulation_register.py` — registers the simulation
     `WorkSourceProvider` (env-gated).
   - `_support/canonical_bytes.py` — JSON encoder with
     `sort_keys=True`, trailing-newline fixed; used for hashing.
   - Existing `work_source.py` and `register.py` retain the
     readiness behavior byte-for-byte (verified by a dedicated
     test).

FR-2. **State schema** under
`<program-root>/.simulation/`:

   - `scenario.json` — input (immutable while the simulation
     runs).
   - `frontier.json` — current operation / revision / state.
   - `reports.jsonl` — append-only accepted reports.
   - `decisions.jsonl` — append-only source decisions.
   - `artifacts/` — fake worker outputs when scenario needs them.

FR-3. **Env-gating**: the simulation reducer is **only** active
when `MATHLINT_SELF_TEST_MODE=simulation` is set; a defensive
`register()` keeps today's sentinel `ProgramProviders` (empty
when both `MATHLINT_SELF_TEST_MODE` and
`MATHLINT_SELF_TEST_PROVIDER` are unset).

FR-4. **Six canonical scenarios** ship:

   - `happy-three-cycle` — three operations, settle, `Stop`.
   - `no-delta-redirect` — two settlings without artifact
     advance; third worker writes useful artifact; threshold
     revises directive/operation.
   - `blocked-alternate-route` — blocked outcome selects
     alternate eligible operation or timed wait.
   - `source-wait-then-work` — timed `Wait`; worker starts after
     deadline.
   - `operator-required` — explicit `OperatorRequired` once.
   - `stop-completion` — completes three cycles then
     `Stop(completed)`.

FR-5. **No program-named imports in generic mathlint code**;
the new simulation lives in `math/src/mathlint/self_test/` which
is already an explicit opt-in module. Generic mathlint modules
`mathlint.program_providers`, `mathlint.orchestration.real_source`,
etc., remain untouched.

FR-6. **State-machine / property tests**:

   - `tests/self_test/test_simulation_state_bytes.py`:
     deterministic fingerprint for canonical bytes.
   - `tests/self_test/test_idempotent_report.py`: same report
     twice → state changes once.
   - `tests/self_test/test_conflicting_report_rejected.py`:
     conflicting report fails closed.
   - `tests/self_test/test_revision_monotonic.py`: revision
     changes iff canonical source state changes; restart/
     reload equivalent to uninterrupted reduction.
   - `tests/self_test/test_completion_absorbing.py`: completion
     absorbing; no completed operation redispatches.
   - `tests/self_test/test_wait_deadline_restart.py`: timed
     `Wait` deadline stable across reload.

FR-7. **Optional report callback** extension to `ProgramProviders`
(if required for report ingestion at the provider boundary):

   - new field defaults to `None`;
   - typed `Callable[[AcceptedReport], None]` Protocol;
   - entry-point compat test;
   - real-source adapter test;
   - sample-registration test;
   - **zero import** of program-named modules by generic mathlint.

FR-8. **Mathlint self-test gate remains fast**:
`bash scripts/check-local-system-readiness.sh --skip-external --use-program=self_test-sample`
exits 0 in < 5 s. The simulation reducer is **only** constructed
in tests that set the env var.

## Explicit exclusions (boundary discipline)

- Modifying `src/mathlint/{program_providers,orchestration.real_source}`
  except for the optional `ProgramProviders` field per FR-7.
- Running a real kaplansky scenario on the simulation reducer.
- Adding `process` / `deployment` / `provider_live` tiers (those
  are entries 05 / 06 / 07).
- Re-implementing `WorkRequest`, `Dispatch`, `Wait`, `OperatorRequired`,
  `Stop` (the wire authority is `pi_monitor.work.work_source`; the
  sample re-exports).

## Measurable success criteria

- `bash scripts/check-local-system-readiness.sh --skip-external --use-program=self_test-sample`
  exits 0; **readiness envelope bytes unchanged**.
- `MATHLINT_SELF_TEST_MODE=simulation pytest -q tests/self_test/`
  exits 0.
- Six canonical scenarios produce the documented decision
  transcripts (table in `quickstart.md`).
- `tests/self_test/test_simulation_happy_three.py` and the four
  no-delta / blocked / wait / completion tests pass.
- Mutation challenges (entry 10 will own the integration; the
  unit tests already here should kill naive mutants):
   - removing the idempotency check → conflicting-report test
     catches it;
   - removing revision change → no-delta test catches it;
   - emitting completion before all ops are done → completion-
     absorbing test catches it.

## Failure and edge cases

- **F-1.** Today is `decided_unix=0.0` (determinism sentinel);
  the simulation reducer is allowed to use real time. The
  contract: reducer output is reproducible byte-for-byte given
  the same canonical frontier bytes and the same accepted-reports
  list.
- **F-2.** Two processes write `reports.jsonl` concurrently;
  the simulator uses file locking or
  `tempfile.NamedTemporaryFile + os.replace` to guarantee
  atomicity. The state-machine test proves last-writer-wins
  is acceptable (the canonical-byte hash makes the inconsistency
  detectable).
- **F-3.** A scenario references an operation_id not in
  `programs/kaplansky-roadmap.toml`; rejected at scenario parse.

## Dependencies on earlier entries

- **Entry 00** — `constitution-verify.md` §7 (sample-program
  contract).
- **Entry 01** — math's collection-without-coverage fix lands;
  the new `tests/self_test/` is collection-clean.
- The simulation reducer MUST NOT call into
  `mathlint.orchestration.real_source`'s filesystem wiring; the
  reducer is pure. Filesystem I/O happens only at the boundary
  adapter (a thin layer in this entry).

## "Cannot claim done when…"

1. Today's readiness envelope bytes are not byte-for-byte
   preserved.
2. The simulation reducer is active without `MATHLINT_SELF_TEST_MODE=simulation`.
3. A canonical scenario fails to produce its expected decision
   sequence.
4. The reducer imports a program-named module from generic
   mathlint code.
5. The `ProgramProviders` extension lands without the typed
   Protocol + compat tests (if FR-7 is invoked).
6. `make check-prime-directive` is not clean at math HEAD.
7. Entry 00's constitution-compatibility test fails against the
   new sample-program extension.
8. Entry 01's tier / dependency / skip trio fails at math HEAD.
9. The state-machine / property tests don't kill the named
   naive mutants.
10. Six canonical scenarios are missing.
11. The simulation writes outside the disposable program root.
12. `tests/self_test/test_simulation_*` collection still works
    under `--no-cov` (a regression of entry 01's M1 fix).

## Non-goals

- Re-implementing the sample from scratch (extends).
- Providing a `provider_live` test (those are entry 07).
- Authoring the cross-repo scenario composition (entry 06).

## Cross-references

- `.specify/memory/constitution-verify.md` §7 (sample-program
  contract), §6 (no-second-supervisor).
- `math/src/mathlint/self_test/{work_source,register}.py`.
- `math/src/mathlint/program_providers.py` (`WorkSourceProvider`,
  `register_program_providers`).
- `pi_monitor.work.work_source` (wire authority).
- `@ADR-0088`, `@ADR-0089` (sample fixture classification +
  CI fixture).
- `@INV-0088` (sample fixture requires no external state).
- `@CTR-0085` (sample dispatch envelope shape).
- `@CTR-0020` (three-repo wire contract).
- `@ADR-0014` (mathlint does not import program-named modules).
