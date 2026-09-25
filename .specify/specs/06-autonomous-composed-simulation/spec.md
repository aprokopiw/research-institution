# 06 — Composed Autonomous Simulation

> **Spec-Kit** artifact. Zero-padded `00–10`. This is `06`. Depends on
> `04` and `05`. Unblocks `07`.

## Identity

- **spec_id:** `06-autonomous-composed-simulation`
- **owner_repo:** `research-institution`
- **owner_repos:** `{research-institution, math, pi_monitor}`
- **status:** draft
- **depends_on:** `04-stateful-sample-research`, `05-process-fault-simulation`
- **unblocks:** `07-deployment-canary-soak`

## Primary actor

The maintainer who runs the canonical verification CLI daily and
the CI system gating the merge to protected branch on the
institution VG-4 gate. Implicit audience: entry 07 (consumes the
CLI), entry 10 (wire-up).

## Problem statement

Today there is no single command that:

- Spawns the real `pi-monitor run` subprocess against a
  disposable program root.
- Configures the fake-Pi subprocess (from entry 02's
  `fake_pi_rpc.py`) via the documented scenario vocabulary.
- Provides the **sample program** in simulation mode (from entry
  04).
- Routes the math external-source subprocess against the sample.
- Reports independent transcript / audit / exactly-once / frontier /
  resource oracles.
- Runs `python -m research_institution verify-simulation --tier
  process|deployment|provider-canary|soak`.

Per the master guide §3 ("Simulation architecture") + §5
("Oracles") + §6 ("Scenario matrix"), the canonical CLI must be
**one** command and **one** implementation path; today's
ad-hoc scripts are retired.

## Independent user stories

1. As a **maintainer**, I run
   `python -m research_institution verify-simulation --tier fast`;
   it runs S0+S1 evidence via `make test-tier-fast` against the
   four repos with `<5 s` per repo budget.
2. As a **maintainer**, I run
   `--tier full`; it runs S0..S3 (`<= 5 min`).
3. As a **CI author**, I run
   `--tier process --scenario happy-three-cycle`;
   the harness spawns `pi-monitor run --config <temp>`,
   waits for the canonical scenario end-state, asserts the
   transcript / audit / frontier oracles all hold, exits 0
   in `< 90 s`.
4. As a **maintainer**, I run
   `--tier provider-canary --live`; the harness refuses to
   mutate kaplansky's production frontier and BLOCKS on missing
   credentials.

## Functional requirements

FR-1. **`research_institution/gates/verify_simulation/`** package
ships:

   - `cli.py` — Typer entry point with verbs:
     `--tier {fast|full|process|deployment|provider-canary|soak}`.
   - `runner.py` — orchestrates temp deployment root +
     pi-monitor subprocess + fake-Pi subprocess + sample program.
   - `temp_root.py` — `temp_root_factory()`; per-scenario
     uniqueness; cleanup on success, preserve-on-failure.
   - `oracle/` — `transcript.py`, `audit.py`, `exactly_once.py`,
     `frontier.py`, `resource.py` (independent oracles per
     master guide §5).
   - `scenarios.py` — registry of canonical scenarios cited by
     name from entry 04's six scenarios.
   - `__init__.py` re-exporting the public API.

FR-2. **Canonical scenarios** shipped (one per entry 04's six):

   - `happy-three-cycle`
   - `no-delta-redirect`
   - `blocked-alternate`
   - `source-wait-then-work`
   - `operator-required`
   - `stop-completion`
   - **Plus** the substrate scenarios (entry 05):
     - `rate-defer-restart`
     - `worker-very-fast`
     - `worker-slow-but-active`
     - `malformed-result`
     - `worker-crash-before-publication`
     - `source-crash-before-report-ack`
     - `execution-restart-after-publication`
     - `duplicate-conflicting-report`

FR-3. **Three independent oracles** per scenario (per master guide
§5 "Required transcript oracle"):

   - **Transcript oracle** from entry 05's
     `transcript_oracle.py` (event subsequence + forbidden
     events).
   - **Audit-chain oracle** (`audit.py`) — verifies hash chain
     using `pi_monitor.state.audit.audit_chain_verify.py`.
   - **Exactly-once oracle** (`exactly_once.py`) — for each
     `(source_identity, operation_id, revision_fingerprint)`:
     one active execution; one accepted report; no
     redispatch.
   - **Frontier oracle** (`frontier.py`) — frontier revision
     changes at expected events; restarts equivalent to
     uninterrupted reduction.
   - **Resource oracle** (`resource.py`) — subprocess count
     returns to baseline; no surviving children.

FR-4. **Public-surface enforcement**: no call to
`pi_monitor.src.pi_monitor.supervision._dispatch_loop` (private)
or `finalize_attempt` / `complete_active` (manual finalize). The
harness drives through `pi-monitor run --config <temp>`.

FR-5. **VG-4 gate** wiring: research-institution green-gate
`gates/aggregate.py` extends its `v-compose` stage (per
master guide §3) to invoke
`python -m research_institution verify-simulation --tier full`.

FR-6. **Per-scenario metadata** at registration time:

```
name
owner
minimum tier = process
maximum_runtime_seconds = 90
fault_injection_point = <scenario-specific>
expected_final_state = <scenario-specific>
required_event_subsequence = <scenario-specific>
forbidden_events = <scenario-specific>
cleanup_expectations = temp_root_cleanup_on_success,
                      preserve_on_failure
```

Stored under `research-institution/tests/simulation/scenarios/`.

FR-7. **Twenty repeated runs without flake** before merge
promotion. Randomized tests print/retain seed and shrink
counterexamples. Mutation tests kill the 15 critical mutants
named in master guide §12.

FR-8. **No second supervisor, no parallel harness**. The
canonical CLI is THE command. `scripts/verify-institution.sh`
invokes `verify-simulation --tier full` through
`gates.aggregate.check_institution()`'s `v-compose` stage.

## Explicit exclusions

- Real provider runs (entry 07).
- Multiple-cwd deployment composition (entry 07).
- Authoring the canonical verification CLI's mutation tests
  (entry 10 owns the cross-cutting VG-6 wiring).

## Measurable success criteria

- `python -m research_institution verify-simulation --tier fast`
  exits 0 in `<30 s`.
- `python -m research_institution verify-simulation --tier full`
  exits 0 in `< 5 min` (in the typical run; bounded by
  budget).
- `python -m research_institution verify-simulation --tier
   process --scenario happy-three-cycle` exits 0 in
  `< 90 s`.
- Each scenario's three oracles (transcript + audit-chain +
  exactly-once) all return their typed verdicts `PASS`.
- 20 repeated runs of `happy-three-cycle` produce zero flakes
  (with deterministic settings).
- `make check-prime-directive` exits 0 at research-institution
  HEAD.

## Failure and edge cases

- **F-1.** A scenario's temp_root survives cleanup. Process tree
  test catches.
- **F-2.** A scenario's transcript contains a forbidden event.
  Oracle rejects.
- **F-3.** A scenario's frontier is corrupted across restart.
  Frontier oracle catches.
- **F-4.** A scenario's run exceeds the budget. Scenario is
  killed and reported `OVER_BUDGET` (a sixth gate-status
  `OVER_BUDGET`, equivalent to `FAIL` for required scenarios).

## Dependencies on earlier entries

- **Entry 00** — verify-constitution §1–§12.
- **Entry 01** — math test vocabulary green.
- **Entry 02** — fake-Pi module exists.
- **Entry 03** — kaplansky domain evidence green.
- **Entry 04** — six canonical scenarios shipped.
- **Entry 05** — substrate helpers + restart-at-boundary.

## "Cannot claim done when…"

1. `research_institution/gates/verify_simulation/` does not exist.
2. `python -m research_institution verify-simulation` is not
   registered as a script (or its underlying `cli.py` is missing).
3. The canonical scenarios do not all produce the documented
   transcripts.
4. A scenario's three oracles do not all return `PASS`.
5. The harness calls a private supervisor method (private-import
   grep test fails).
6. The harness calls manual finalize helpers.
7. A scenario's run exceeds the budget without `OVER_BUDGET`.
8. The temp_root survives cleanup.
9. Twenty repeated runs of `happy-three-cycle` produce any flake.
10. Entry 00/01/02/03/04/05 cannot-claim-done clauses do NOT
    hold at HEAD.
11. `transient-exemptions.toml` mutated without version bump.
12. Mutation-test gate aggregator finds a surviving critical
    mutant (per master guide §12).

## Non-goals

- Provider_live scenarios (entry 07).
- Soak scenarios (entry 07).
- Cross-repo compatibility tests (entry 08).
- The prime-directive enforcement machinery (entry 09).

## Cross-references

- `.specify/memory/constitution-verify.md` §1–§11.
- `pi_monitor/tests/substrate/` (helpers; entry 05).
- `math/src/mathlint/self_test/sample_program/scenarios/`
  (entry 04).
- `research-institution/research_institution/gates/aggregate.py`
  (`v-compose` stage extension).
- `@ADR-0006`, `@ADR-0007`, `@ADR-0011`, `@INV-0093`,
  `@INV-0094`, `@CTR-0020`, `@CTR-0094`.
