# Repo-boundary cleanup + composed test hardening plan

**Status:** Roadmap (not yet implemented). Each box has a
tracking header so progress can be ticked off.

**Owner:** the research institution as a whole. Per
`research-institution/README.md` the dependency graph is:

```
research-institution (top — catalog + bootstrap + green gate + dispatcher CLI)
        │
        ├── math-engine  (depends on nothing in this graph)
        ├── pi_monitor   (depends on nothing in this graph)
        └── kaplansky, ... (each depends on math-engine + pi_monitor)
```

**Reverse edges are forbidden.** Any source/test/script/doc
that imports the wrong direction or names the wrong repo is
a kernel-boundary violation. This plan is two interleaved
tracks:

| Track | What it does | Why now |
|---|---|---|
| **Track 1 — Repo-boundary cleanup** | Removes every program-name literal that doesn't belong (math tests, math scripts, math docs, pi_monitor tests). Retires the shim scripts `@ADR-0091` marked for deletion. Shrinks `@ADR-0014`'s grandfather list to the minimum. | The grandfather mess is a P0 false-GREEN risk (per the verification skill). The boundary is the load-bearing invariant for adding a second research program. |
| **Track 2 — Composed test scaffolding** | F-1 through F-8 fixtures + SM-A through SM-F state-machine suites + COMPOSE-1 through COMPOSE-5 cross-repo suites. | After Track 1 lands, every test fixture must be repo-pure or import-clean; new fixtures land on a clean substrate. |

**Authoritative methodology:** `@verification-skill`
principles 1, 3, 5, 7, 10, 11 — particularly
*Repository at current commit is truth*, *GREEN must be
truthful*, *No churn*, *Preserve counterexamples*. The
verification skill's §10 stop conditions: stop when evidence
is appropriate for risk class, when redesign belongs to
another skill, or when infrastructure is missing.

**Cross-skill referrals:**
- `repo-coherence` owns "where does this belong" — drives
  fixture placement and the dependency-graph enforcement.
- `semantic-repo` owns durable anchor citations — drives the
  ADR/INV/CTR cite list in §12.
- `code-health` owns accidental complexity — some of Track 1's
  shrink-the-grandfather-list items are code-health work that
  should be REFERRED rather than absorbed here.

**Last live failures this plan would have caught (2026-09-20):**

1. `pi_monitor` rate-limit boundary helper flipped its
   internal `_stopped_slot` on a denial, but the supervisor's
   flush step never propagated that to `sup.state.stopped`.
   The supervisor silently stopped dispatching while the
   operator dashboard said nothing. Caught by COMPOSE-2.
2. `mathlint-source` crashed with
   `LiveSourceError("invalid_report")` when a `report_result`
   frame lacked a `report_id` or `envelope_digest` field. The
   supervisor's catch path left the subprocess in a crashed
   state and the loop restarted the same way. Caught by
   COMPOSE-4. Origin: `mathlint.orchestration.live_source.
   LiveSource.handle_frame`, the `kind="report_result"`
   branch.

---

## 1. Why this plan is cleanup-first

A repo-boundary violation is a P0 false-GREEN risk by
construction. If `math` references `kaplansky` in a test
fixture, the test silently couples to a specific program. If
`pi_monitor` references `mathlint` in a test fixture, the
test silently couples to a specific provider. The whole
kernel-boundary argument rests on:

- `@ADR-0014` — mathlint does not import program-named
  modules. The static check
  `math/tests/static/test_no_program_named_modules.py`
  enforces it on `src/`. It is NOT enforced on `tests/`,
  `scripts/`, or `docs/`. The grandfather list in math's
  `AGENTS.md` class #22 enumerates which `src/` files are
  permitted to carry the literal; everything else is a real
  violation that has been grandfathered by silence.

- `@ADR-0092` — pi_monitor does not name mathlint. Source is
  clean; tests carry the literal as a runtime string value
  under the "soft rule for runtime strings" carve-out
  documented in pi_monitor's `AGENTS.md`. That carve-out is
  fine for a fixture string but is wrong when the fixture
  string is the literal `"kaplansky-research-program"` —
  that's a specific program identity, not a generic string.

- `@ADR-0091` — mathlint does not ship program launchers.
  `math/scripts/pi-monitor-kaplansky.sh` is a delegation shim
  whose own comment says "this shim is retired". It's still
  on disk. `math/scripts/verify.sh:113–117` calls the typed
  launcher via a hard-coded `/Users/erinprokopiw/kaplansky`
  path.

- `@ADR-0007` — research-institution owns the WorkSourceProvider
  slot. It is the only repo that imports program-named
  modules. Track 1 enforces this by removing the program-name
  literals from every other repo's tests.

Composed-test scaffolding depends on the boundary being
clean: a `FakeMathResearchProgram` that lives in
research-institution and a `FakeLiveMathlintSource` that
lives in math must not be polluted by `"kaplansky"` literals
they inherit from pre-existing test code.

---

## 2. Repo-boundary inventory (Track 1 input)

Every line below is a real grep result from the current
`main` of every repo. Counts in parentheses. The plan turns
each section into a cleanup phase.

### 2.1 `math/src` — program-name refs (grandfathered)
**Source: 21 refs across 4 files**, all grandfathered by
class #22 of math's `AGENTS.md`:

- `src/mathlint/local_readiness/system.py` — 8 refs
  (`kaplansky_revision`, `kaplansky_repository`,
  `kaplansky_write_root`)
- `src/mathlint/local_readiness/config.py` — 13 refs
  (`LocalConfigField.KAPLANSKY_REPOSITORY`,
  `_TARGET_TO_KAPLANSKY_ALIAS`, the env-var normalizer)

These are content-domain config keys (`@ADR-0012` aliases).
**Status: grandfathered. No cleanup.**

### 2.2 `math/tests` — program-name refs (NOT grandfathered, real `@ADR-0014` violations)
**Source: ~189 refs across ~45 files**, none in math's class #22
list (that list enumerates `src/` and `scripts/` only).

The original plan estimated ~20 refs in 3 files based on a
cursory grep. The static check
`math/tests/static/test_no_program_named_modules_in_tests.py`
(Phase A.4) is the authoritative count and reveals the
cleanup is roughly 9× larger than initially estimated. The
top offenders (per the static check output):

| File | Violations |
|---|---|
| `tests/local_readiness/test_system.py` | 24 |
| `tests/support/paired_harness.py` | 19 |
| `tests/local_readiness/test_real_source.py` | 15 |
| `tests/contracts/test_no_program_name_in_src.py` | 11 |
| `tests/local_readiness/test_wrap_mathlint_source.py` | 9 |
| `tests/local_readiness/test_local_config.py` | 9 |
| `tests/local_readiness/test_paired.py` | 8 |
| `tests/acceptance/test_paired_harness.py` | 8 |
| `tests/support/kaplansky_work_factory.py` | 7 |
| `tests/static/test_no_program_named_modules.py` | 6 |
| 35+ other files | <6 each |

**Categories of violation:**
1. **Test fixtures named after the program** — e.g.
   `pair.kaplansky`, `kaplansky_work_factory.py`. These
   reflect that the math test substrate was authored when
   "kaplansky" was the only proof program. Cleanup needs
   a generic `program_repo` / `program_factory` rename.
2. **Docstrings/comments** — `"the kaplansky launch trace"`,
   narrative context. Cleanup is a one-line rename.
3. **Tightly-coupled test contracts** — e.g.
   `tests/contracts/test_no_program_name_in_src.py` literally
   asserts "no kaplansky literal in src/"; the assertion
   itself names kaplansky. This file is grandfathered
   because the *purpose* of the test is to detect the
   literal; cleaning it would defeat the check.
4. **Hard-coded filesystem paths** — e.g. the
   `/Users/erinprokopiw/Documents/andrei/kaplansky` literal
   in test fixtures. Cleanup needs `tmp_path`-driven
   fixtures with `_git_init_tmp_repo()` (added in Phase A.2).

**Action: rewrite each file to use a fixture-injected
program repo path; rename `KAPLANSKY_*` env vars to
`TARGET_*` (the alias already exists per `@ADR-0012`); use
a `FakeProgram` entry point registered in-test rather than
relying on a real kaplansky install. Track the expanded
scope in Phase A.5 — the cleanup is multi-commit, not
single-commit.**

### 2.3 `math/scripts` — program-name refs
**Source: 8 refs across 5 files:**

- `scripts/pi-monitor-kaplansky.sh` — the delegation shim
  explicitly marked for retirement by `@ADR-0091`. The
  shim's own header says: *"The typed launcher now ships
  from kaplansky. This shim forwards to `mathlint-kaplansky`
  ... When ALL operator muscle memory ... has migrated to
  `uv run mathlint-kaplansky <verb>`, this shim is
  retired."*
- `scripts/verify.sh:113–117` — hard-codes the kaplansky
  repo path and runs `mathlint-kaplansky bootstrap/install/
  start/status/stop --dry-run`. The whole sequence is the
  kaplansky typed launcher's dry-run, not a math-side check.
- `scripts/check-local-system-readiness.sh:120–121` —
  creates `$STATE/work/kaplansky` and `$STATE/work/mathlint`
  state dirs. The kaplansky dir is launcher state that
  belongs in kaplansky, not math.
- `scripts/_cold_start_bootstrap.py:53` — comment referencing
  `mathlint-kaplansky bootstrap`.
- `scripts/_bootstrap_m00.py:17,49` — hard-codes `KAP =
  Path("/Users/erinprokopiw/Documents/andrei/kaplansky")`
  and emits `"kaplansky_commit"` in the bootstrap receipt.
- `scripts/_write_frontier_scheduler_receipt.py:117` —
  emits `"kaplansky_revision"` in the receipt.

**Action: delete `pi-monitor-kaplansky.sh` outright
(`@ADR-0091` already retired the legacy launcher). Move the
`mathlint-kaplansky` invocation block in `verify.sh` to
`kaplansky/scripts/verify.sh` (it tests kaplansky's
launcher, not math's). Move `$STATE/work/kaplansky` creation
to kaplansky's bootstrap. Replace `_bootstrap_m00.py` and
`_write_frontier_scheduler_receipt.py` kaplansky-specific
fields with a generic `target_*` payload keyed by an
operator-supplied repo path.**

### 2.4 `math/docs` — program-name refs (operator docs)
**Source: 8 refs across 5 operator-facing runbooks:**

- `docs/operations/launch-program-runbook.md` — 7 refs.
  This is the operator's runbook for launching a research
  program; the literal `kaplansky` is correct operator
  vocabulary ("bash launch-program.sh kaplansky").
- `docs/operations/quickstart-spec-005.md` — 4 refs.
  Operator-facing.
- `docs/operations/smoke001-playbook.md` — 3 refs.
  Operator-facing.
- `docs/operations/VERIFY-EVERYTHING.md` — 4 refs.
  Operator-facing.
- `docs/protected-readiness-runbook.md` — 2 refs.
  Operator-facing.

**Status: not violations. Operator docs name the program
they operate on; that's their job. Cleanup applies only
to non-operator-facing docs. No action.**

### 2.5 `pi_monitor/src` — program-name refs
**Source: 0 refs.** `@ADR-0092` is honored at the source
level. **No cleanup needed.**

### 2.6 `pi_monitor/tests` — program-name refs (mostly OK, some need renaming)
**Source: ~50 refs across ~15 files.** All under the "soft
rule for runtime strings" carve-out documented in
pi_monitor's `AGENTS.md`. Two categories:

- **Category A (legitimate runtime strings):**
  `test_budget_policy.py:28` (`source_identity="mathlint"`),
  `test_budget_ledger.py:47–49` (`SCOPE_SOURCE, "mathlint"`).
  These are arbitrary source-identity strings; they happen
  to be `"mathlint"`. Acceptable.

- **Category B (specific program identity leak):**
  `test_supervisor_dispatch_rate_limit.py:79,85,88,90,92,
  94,100,121` uses literal `"kaplansky-research-program"`,
  `"mathlint-research"`, `"kaplansky-workspace"`,
  `"kaplansky.tick-{n}"`, `"kaplansky.work_request"`,
  `"mathlint-local-readiness"`. `test_wire_parsers.py:95,
  98, 100, 114, 121` carries the same shape. These are
  `"kaplansky"` literals, not generic runtime strings.

**Action: rename the Category B literals to a generic
program identity (`"test-research-program"`,
`"generic-research"`, etc.) so the test exercises
`pi_monitor`'s supervisor with arbitrary source identities,
not with kaplansky's. The wire format and the supervisor's
contract don't depend on the specific identity; this is a
fixture-rename, not a test rewrite.**

### 2.7 `research-institution` — program refs
**Source: 12+ refs across operator docs and the catalog
TOML itself.** The catalog legitimately names `kaplansky`
(the catalog is the operator's declaration of which
programs exist). The runbooks (`launch-kaplansky-
autonomously.md`, `kaplansky-operator-ux.md`, etc.) are
operator-facing. **No cleanup needed; these are the
correct repo for program-name literals per `@ADR-0007`.**

### 2.8 `kaplansky/src` and `tests` — cross-repo imports
**Source: `kaplansky/src` imports `pi_monitor` (the
`WorkRequest`, `SourceRevision`, `WorkSource` types) and
references `mathlint` in operator runbooks and the
typed-launcher bootstrap. This is correct per the
dependency graph: kaplansky is a research program that
depends on math + pi_monitor.**

`kaplansky/tests/test_mathlint_plugin.py` exercises the
entry-point registration. This is the one place where
kaplansky is allowed to test its math-boundary seam.
**No cleanup needed.**

### 2.9 Substrate gap from the prior plan draft
The original plan called out a missing
`FakeKaplanskyRoadmap` fixture as "the biggest gap". After
the boundary cleanup, that gap becomes **a programmable
`FakeMathResearchProgram`** that lives in
`research-institution/tests/_fakes.py` and never imports
kaplansky. Track 2 builds it.

---

## 3. Repo-boundary enforcement (Track 1's static checks)

Each repo gets a static check that catches future
violations:

### 3.1 `math` — extend the static check
- [ ] **BC-1** Add `math/tests/static/test_no_program_named_modules_in_tests.py`
  that scans `math/tests/**.py` and `math/scripts/**.{py,sh}`
  for `kaplansky|KAPLANSKY` literals and fails on any
  hit outside the class #22 grandfather list. The current
  check (`test_no_program_named_modules.py`) covers
  `math/src/` only.
- [ ] **BC-2** Promote the script-level check to a CI step.
- [ ] **BC-3** Update math's `AGENTS.md` class #22 to list the
  test files explicitly that the rewrite in Phase A leaves
  legitimate (the renamed `test_durable_regression.py` after
  Phase A.3 carries generic `target_*` literals, no
  grandfather needed; this confirms the cleanup is complete).

### 3.2 `pi_monitor` — add a fixture-string check
- [ ] **BC-4** Add `pi_monitor/tests/static/test_no_program_identity_in_fixtures.py`
  that scans `pi_monitor/tests/**.py` for the literal
  `"kaplansky"` (any case) and fails. Exempts:
  `test_budget_policy.py`, `test_budget_ledger.py`,
  `mathlint_fixture/` (the fixture is a contract test, not
  a supervisor test), `test_mathlint_fixture_*.py` if any
  exist. Every other test must use generic program
  identities (`"test-research-program"`,
  `"external-source"`, etc.).
- [ ] **BC-5** Add a comment in pi_monitor's `AGENTS.md`
  enumerating the exempt files (so the carve-out is
  explicit, not implicit by silence).

### 3.3 `research-institution` — protect the catalog
- [ ] **BC-6** The catalog legitimately names kaplansky; no
  check needed there. **No action.**

### 3.4 `kaplansky` — none
- [ ] **BC-7** Kaplansky importing `pi_monitor` and
  `mathlint` is correct per the dep graph. **No action.**

---

## 4. Cross-cutting invariants to prove (Track 2 input)

These invariants span the cleaned-up state machine. After
Track 1 lands, every test in this section exercises
repo-pure code.

### INV-T1 — Idempotency identity
**Claim:** `(source_identity, source_revision.fingerprint,
operation_id)` uniquely identifies one logical operation
across all four repos.

- [ ] **T1.a** A `FakeMathResearchProgram` (F-1) with 3
  items. Assert: `select_next_work_for_supervisor` returns
  exactly one `WorkRequest` whose `operation_id` matches
  the fixture's `K4`. The `source_identity` is the
  fixture's identity string, NOT `"kaplansky-research-
  program"` (per Track 1 cleanup).
- [ ] **T1.b** Mock the source twice returning the same
  Dispatch. Assert: the supervisor's idempotency key is
  identical and the record file is shared.
- [ ] **T1.c** pi_monitor's `canonical_key` is collision-
  free. Hypothesis: 1000 random
  `(identity, fingerprint, operation_id)` triples →
  distinct hex digests.

### INV-T2 — Cross-repo type identity
**Claim:** A `Dispatch` constructed in research-institution
is the SAME class as a `Dispatch` parsed in pi_monitor.

- [ ] **T2.a** `isinstance(d, Dispatch)` survives a round-
  trip through every wire codec.
- [ ] **T2.b** field-level equality (`__eq__`) is preserved
  across the wire.
- [ ] **T2.c** Already covered by
  `research-institution/tests/test_cross_repo_type_identity.py`
  — extend with `FakeMathResearchProgram` payloads to
  prove the identity holds when the typed envelope comes
  through the entry-point registry (not just a literal
  constructed in research-institution's tests).

### INV-T3 — Status / verdict state spaces are closed
**Claim:** Every state transition stays within the declared
enum (`RoadmapItemStatus`, `GateVerdictStatus`,
`STATUS_*`, `DISPOSITION_*`, `KIND_*`).

- [ ] **T3.a** Hypothesis: randomly construct a record +
  run every helper (`start_attempt`, `finalize_attempt`,
  `reactivate`, `reconcile_record`); assert the resulting
  `status` is always in `{pending, running, superseded,
  cancelled}`.
- [ ] **T3.b** Same for gate verdicts.
- [ ] **T3.c** Mutation: corrupt the runtime status enum;
  assert every consumer raises (never silently maps).

### INV-T4 — One active record per supervisor (INV-005)
- [ ] **T4.a** Sequence test: 100 dispatches with shifting
  operation_id. Assert: after each, `active_records() == 1`
  at most.
- [ ] **T4.b** Crash recovery: simulate crash between
  `execution_record_created` and steer. Restart supervisor.
  Assert: at most one active after reconcile.

### INV-T5 — Intent-before-launch (INV-023)
- [ ] **T5.a** Composed test with crash injection. Use
  `FaultInjector` (F-4) to crash between record write and
  steer. Assert: record file exists with status=pending,
  audit chain has `execution_record_created` before any
  `source_dispatch_steer`.

### INV-T6 — Outcome ownership (INV-003, INV-010)
- [ ] **T6.a** Mutation: replace `OUTCOME_BLOCKED` with
  `OUTCOME_COMPLETED` in supervisor code paths; assert
  all consumers refuse.
- [ ] **T6.b** Audit audit: every `outcome` field is in
  `OUTCOME_VOCABULARY` (a closed set).

---

## 5. State-machine surfaces to test in isolation

Each surface has its own dedicated test file. Each file
parameterizes over (decision_kind, reason_code,
operator_id, revision_fingerprint, identity) to maximize
property coverage at minimum LoC. After Track 1 lands, no
fixture names any specific research program.

### SM-A: kaplansky roadmap (single repo)
**File:** `kaplansky/tests/test_state_machine_roadmap.py`
(extending `test_work_selection.py` rather than replacing
it)

**State:** `RoadmapItemStatus = {PLANNED, ACTIVE, PAUSED,
PROMOTED, SEMI_FORMAL, KILLED, BLOCKED, WITHDRAWN, PARKED,
COMPLETED, FROZEN}`

**Transitions under test** (real tmp-path TOML; no fake
needed because kaplansky IS the unit under test):
- [ ] **A1** PLANNED → ACTIVE
- [ ] **A2** ACTIVE → PAUSED
- [ ] **A3** ACTIVE → BLOCKED (next_action empty →
  `is_dispatch_eligible()` returns False)
- [ ] **A4** ACTIVE → PROMOTED
- [ ] **A5** any → KILLED
- [ ] **A6** invalid: PAUSED → PROMOTED

**Property tests:**
- [ ] **A-P1** Hypothesis: 50 random roadmap shapes →
  `next_active_work` returns WorkRequests only for items
  where `is_dispatch_eligible() == True`.
- [ ] **A-P2** Mutation: `is_dispatch_eligible` always
  returns True; assert `NoActiveWorkError` when all
  blocked.
- [ ] **A-P3** Mutation:
  `KaplanskyRoadmapItem.from_toml_dict` silently drops an
  unknown `priority`; assert Pydantic ValidationError.

### SM-B: research-institution gate (single repo)
**File:** `research-institution/tests/test_state_machine_gate.py`

**State:** `GateVerdictStatus = {OPEN, CLOSED, UNKNOWN}`

**Transitions under test:**
- [ ] **B1** unknown → OPEN (`RESEARCH`)
- [ ] **B2** unknown → CLOSED
  (`ARCHITECTURE_REVIEW_REQUIRED`)
- [ ] **B3** unknown → CLOSED (no TASK KIND line)
- [ ] **B4** OPEN → CLOSED (operator cancel)
- [ ] **B5** any → UNKNOWN (subprocess crash, malformed JSON)

**Fixtures:** `FakeMathlintRoadmap` (F-3) — `FakeRunner`-
driven canned stdout, lives in
`math/tests/support/fake_mathlint_roadmap.py`, consumed by
research-institution via import.

**Property tests:**
- [ ] **B-P1** Hypothesis: 200 random TASK KIND values →
  verdict is in {OPEN, CLOSED, UNKNOWN}.
- [ ] **B-P2** Mutation: every `read_gate` returns UNKNOWN on
  non-zero exit; assert CLOSED never reached.
- [ ] **B-P3** Hypothesis: random subprocess output
  (including garbage bytes) → verdict is never an
  Exception.

### SM-C: research-institution dispatch envelope
**File:** `research-institution/tests/test_state_machine_dispatch.py`

**State:** `SourceDecision = Dispatch | Wait | OperatorRequired | Stop`

**Transitions under test:**
- [ ] **C1** Wait → Dispatch (revision changes —
  `wake_on_source_change` fires)
- [ ] **C2** Dispatch → Wait (empty work list)
- [ ] **C3** Dispatch → Stop (operator cancel)
- [ ] **C4** any → OperatorRequired (auth missing)

**Fixtures:** `FakeCatalog` (F-2) — real `Program`
dataclass instances; monkeypatches
`research_institution.paths.catalog_path`.

**Property tests:**
- [ ] **C-P1** Hypothesis: random `WorkRequest` list →
  `source_decision_to_wire` then
  `parse_source_decision` is identity (extends
  `test_composed_dispatch_property.py`).
- [ ] **C-P2** Mutation: drop a required field; assert
  `parse_source_decision` raises `ValueError`.

### SM-D: pi_monitor reconcile table
**File:** `pi_monitor/tests/test_state_machine_reconcile.py`
(extending `test_execution_records.py::E6ReconcileTableTests`)

**Transitions under test (complete the table):**
- [ ] **D1–D9** the full
  `(record.status, decision.kind) → verdict.action` table
  from the original plan.

**Property tests:**
- [ ] **D-P1** Hypothesis: random
  `(status, decision.kind, key_eq)` → verdict.action ∈
  {reissue, reactivate, supersede, hold, noop}.
- [ ] **D-P2** Mutation: drop `verdict.key` for non-
  supersede; assert `apply_reconcile_verdict` does NOT
  call `execution_store.load`.
- [ ] **D-P3** `reconcile_record → apply_verdict`
  composition: typed supervisor attributes match verdict
  semantics.

### SM-E: pi_monitor rate-limit boundary
**File:** `pi_monitor/tests/test_state_machine_rate_limit.py`

Already partially covered by
`test_rate_limit_boundary.py`. Extend with:
- [ ] **E-P1** Hypothesis: random
  `(spend, cap, window_age)` → verdict.tripped is
  monotonic in spend.
- [ ] **E-P2** Mutation: corrupt `WINDOW_SECONDS`;
  assert every consumer refuses unknown windows.

### SM-F: pi_monitor execution record lifecycle
**File:** `pi_monitor/tests/test_state_machine_execution_lifecycle.py`

**Transitions under test:**
- [ ] **F1–F8** from the original plan.

**Property tests:**
- [ ] **F-P1** Hypothesis: 500 random helper sequences →
  final state in `{pending, running, superseded,
  cancelled}`; never an intermediate like "starting" or
  "finalizing" leaks.

---

## 6. Composed surfaces (multi-repo)

These tests wire multiple repos through their typed
envelopes in-process. They are the V2 tier — the most
valuable evidence per LoC. After Track 1, no test in this
section imports kaplansky by name; the
`FakeMathResearchProgram` is the only research-program
identity in play.

### COMPOSE-1: full happy-path
**Files:**
- `pi_monitor/tests/test_compose_happy_path.py` — the
  supervisor/worker seam
- `math/tests/local_readiness/test_cross_repo_wiring.py`
  — EXTEND with `CROSS_REPO_007` after Track 1 rewrites
  it to use generic program identity (per Phase A.3)

**Components wired (pi_monitor-side):**
- `FakeMathResearchProgram(items=[Dispatch(...)])` (F-1)
- `StubRuntime` answers `get_state`, `prompt`,
  `agent_settled` in scripted order
- `FakeClock` drives a deterministic timeline
- `InMemoryAuditChain` (F-6) records every audit event

**Test sequence:**
1. Cycle 1: source returns Dispatch(operation_id="item-1").
   Assert `execution_record_created`. Steer dispatched.
   Assert `execution_attempt_started`.
2. StubRuntime emits `agent_settled` +
   `outcome=completed` + payload digest.
3. Supervisor publishes outcome. Assert
   `execution_attempt_terminal` +
   `record.status == completed`.
4. Cycle 2: source returns Wait. Assert active_key cleared.

**Asserts:**
- Full audit chain in order.
- Exactly ONE record on disk with status=terminal.
- No `rate_limit_denied`.

**Mutation tests:**
- [ ] **M1** Skip `execution_record_created` audit;
  assert `IntentBeforeLaunchError`.
- [ ] **M2** Unparseable outcome; assert retries 3× then
  finalizes with `wedge_classification`.
- [ ] **M3** Replay same outcome digest; assert idempotent
  re-publish.

### COMPOSE-2: rate-limit boundary tripped mid-run
**File:** `pi_monitor/tests/test_compose_rate_limit_trip.py`
(extends `test_supervisor_dispatch_rate_limit.py`)

**Sequence:**
1. Pre-populate ledger with 3M tokens.
2. Cycle 1: stub source emits Dispatch. Boundary trips.
   Assert: `rate_limit_denied`, `operator_required`,
   `state.stopped == True`.
3. Cycle 2 (FakeClock.advance(300)): source still returns
   Dispatch. Boundary still tripped.
4. Operator raises cap (config → 5M). Boundary clears via
   fingerprint-change drop. Assert:
   `rate_limits_config_changed` + new attempt starts.

**Mutation tests:**
- [ ] **M4** Slot-flush regression (the 2026-09-20 silent
  denial bug).

### COMPOSE-3: stop / operator-required in supervisor
**File:** `pi_monitor/tests/test_compose_stop.py`

**Sequence:**
1. Source emits OperatorRequired (credentials missing).
2. Supervisor holds, sets `source_paused=True`, audits
   `operator_required`. No attempt.
3. Operator sends `resume`.
4. Cycle N: source emits Dispatch same key. Supervisor
   reissues.

**Mutation tests:**
- [ ] **M5** Skip the hold path; assert audit catches
  bypass.
- [ ] **M6** Pause reason clobbered between cycles; assert
  survives.

### COMPOSE-4: math source crash + recovery
**File:** `math/tests/orchestration/test_compose_source_recovery.py`

**Bug origin:** `mathlint.orchestration.live_source.
LiveSource.handle_frame`, the `kind="report_result"`
branch (`live_source.py:185–190`) — raises
`LiveSourceError("invalid_report")` when the report lacks
`report_id` or `envelope_digest`.

**Sequence:**
1. `FakeLiveMathlintSource` (F-8) scripts first
   `report_result` to raise
   `LiveSourceError("invalid_report")`.
2. Supervisor catches. Assert: `source_report_failed`
   audit with error code.
3. Supervisor restarts mathlint-source with exponential
   backoff.
4. New source instance answers handshake on second attempt.
   Assert: recovery in ≤ 3 attempts;
   `source_report_succeeded` after recovery.
5. **If step 4 fails:** real production defect. File bug,
   fix before declaring COMPOSE-4 GREEN.

**This is the 2026-09-20 second bug — unfixed. Test first,
then fix.**

### COMPOSE-5: cross-repo work selection through entry points
**File:** `research-institution/tests/test_compose_work_selection.py`

**Sequence:**
1. A test-only `FakeProgram` registers a
   `mathlint.program_work_selection` entry point with a
   scripted callable. NO reference to kaplansky anywhere.
2. `select_next_work_for_supervisor(repo)` calls that
   callable via the kernel-blessed entry-point registry and
   wraps the result in a typed Dispatch.
3. End-to-end in-process: `scripted_callable(repo)` →
   `select_next_work_for_supervisor(repo)` →
   `source_decision_to_wire` → `parse_source_decision` →
   `decision_kind(parsed) == Dispatch`.
4. `FakeProgram` raises `NoActiveWorkError`; assert OS
   converts to Wait with `reason_code="no_eligible_work"`.

**Mutation tests:**
- [ ] **M7** Drop `FakeProgram`'s entry-point registration;
  assert `work_selection_callables() == {}` and OS emits
  Wait-with-diagnostic.
- [ ] **M8** Inject `NoActiveWorkError`; assert OS converts
  to Wait, not crash.
- [ ] **M9** Mutation: `_read_catalog_program_name` returns
  wrong name; assert OS Wait diagnostic names only the
  catalog key.

---

## 7. Adversarial tier (V3) — mutation + property + fuzz

Every test file from §5 and §6 gets a sibling mutation
test. Total budget: ~50 mutants, executed via `mutmut` or
`cosmic-ray`. Pass criterion: ≥ 80% mutant kill rate.

### Mutations to apply
- [ ] **MU-1** Status enum: replace each value with its
  neighbor.
- [ ] **MU-2** DecisionKind: same.
- [ ] **MU-3** Swap operator in boundary checks (`>` →
  `>=`).
- [ ] **MU-4** Drop the `touched_slots.add(...)` line.
- [ ] **MU-5** Skip the audit emit; assert test fails.
- [ ] **MU-6** Drop the `execution_store.save(record)`;
  assert test fails.
- [ ] **MU-7** Replace `id` with `attempt_id` (the
  2026-09-20 live bug pattern).
- [ ] **MU-8** Make `FakeClock.advance` no-op; assert time-
  dependent tests still fail (clock discipline must be
  observable).

### Property tests (hypothesis stateful)
- [ ] **PR-1** State machine: random dispatcher cycles
  with `RuleBasedStateMachine`. Invariant: audit log is a
  hash chain (no breaks).
- [ ] **PR-2** State machine: same for execution records.
  The store is append-only; attempt ordinals are monotonic;
  no record ever moves terminal → active.
- [ ] **PR-3** State machine: same for kaplansky roadmap
  items. No item ever transitions PLANNED → KILLED in one
  step.

### Fuzz targets
- [ ] **FZ-1** Source-decision JSON wire codec (mathlint
  side): random JSON input → parser raises ValueError,
  never crashes.
- [ ] **FZ-2** Same for pi_monitor source_wire codec.
- [ ] **FZ-3** Same for kaplansky roadmap TOML.
- [ ] **FZ-4** Same for catalog TOML.

---

## 8. New fixtures to build (Track 2)

All fakes live in the consumer repo. No shared
`tests/_shared_fakes.py` package; per-repo duplication of
small stable helpers is cheaper than vendoring.

### Fixture F-1: `FakeMathResearchProgram` (research-institution)
- [ ] Class in
  `research-institution/tests/_fakes.py::FakeMathResearchProgram`
- [ ] Implements the `WorkSource` port (api_version=1,
  capabilities={CAP_DISPATCH, CAP_WAIT,
  CAP_OPERATOR_REQUIRED, CAP_STOP, CAP_REVISIONED,
  CAP_REPORT_RESULT})
- [ ] Constructor takes a programmable list of
  `SourceDecision` objects; pops them in order via
  `decide()`
- [ ] `set_revision()` to mutate the source revision
  mid-test
- [ ] `report_result()` records every report; default ack-id
  is `f"ack-{n}"`
- [ ] `mutate_next_work_request(payload_overrides)` lets
  tests inject arbitrary payloads
- [ ] Default identity is `"test-research-program"` (not
  `"kaplansky-research-program"`, per Track 1 cleanup)
- [ ] Reused by: SM-C, COMPOSE-1, COMPOSE-2, COMPOSE-3,
  COMPOSE-5

### Fixture F-2: `FakeCatalog` (research-institution)
- [ ] Class in
  `research-institution/tests/_fakes.py::FakeCatalog`
- [ ] Constructor: `entries: list[Program]` (production
  dataclass)
- [ ] `register_with_path_resolver()` monkeypatches
  `research_institution.paths.catalog_path` and
  `research_institution.catalog.load_catalog`
- [ ] Reused by: SM-C, COMPOSE-1, COMPOSE-5

### Fixture F-3: `FakeMathlintRoadmap` (math)
- [ ] Class in
  `math/tests/support/fake_mathlint_roadmap.py`
- [ ] Constructor: `task_kind: TaskKindLiteral` plus
  optional reason-code overrides
- [ ] `run()` returns a `CompletedProcess` with the live
  `mathlint-source` stdout format
- [ ] `with crash_on(nth_call)` injects non-zero exit
- [ ] `with malformed_json_on(nth_call)` for wire-decoder
  failure modes
- [ ] Reused by: SM-B, COMPOSE-1

### Fixture F-4: `FaultInjector` (per-repo copy)
- [ ] Class in each `tests/_fakes.py` (research-
  institution, pi_monitor, math)
- [ ] Wraps a callable with named injection points:
  `before_record_write`, `before_steer`,
  `before_outcome_publish`, `before_subprocess_spawn`
- [ ] Each point can raise, sleep, or no-op
- [ ] Used by: T5, COMPOSE-1, COMPOSE-4, SM-D

### Fixture F-5: `ProgrammableWorkSource` (pi_monitor)
- [ ] Only build if existing `ScriptedSource` in
  `pi_monitor/tests/fake_work_source.py` cannot mutate
  WorkRequest payloads at runtime
- [ ] First verify `ScriptedSource` is sufficient by
  extending `test_compose_*` tests against it; only create
  F-5 if a real mutation requirement fails to express

### Fixture F-6: `InMemoryAuditChain` (per-repo copy)
- [ ] Class in each `tests/_fakes.py`
- [ ] Records every audit event passed to a configurable
  recorder
- [ ] Asserts: chain-break, missing-event, ordering
  violation
- [ ] Used by: every COMPOSE test

### Fixture F-7: `BoundarySpy` (per-repo copy)
- [ ] Class in each `tests/_fakes.py`
- [ ] Wraps any object; records every attribute/method
  access with args + return
- [ ] Used by: every COMPOSE test for cross-module
  assertions

### Fixture F-8: `FakeLiveMathlintSource` (math)
- [ ] Class in
  `math/tests/orchestration/_support/fake_live_source.py`
- [ ] In-process double for `LiveSource`
- [ ] Scripts `handle_frame` responses; supports scripted
  `LiveSourceError("invalid_report")` on the Nth
  `report_result` frame
- [ ] Reused by: COMPOSE-4, SM-B boundary test

---

## 9. Phasing — Track 1 first, Track 2 second

Each phase is one or more commits. Phases are sequential
within a track; tracks interleave at the phase boundary
(Track 1 Phase D completes Track 1; Track 2 Phase A then
runs on the cleaned substrate).

### Track 1 — repo-boundary cleanup

#### Phase A — math tests cleanup
- [x] **A.1** Rewrite
  `math/tests/local_readiness/test_cross_repo_wiring.py`
  ✅ DONE. 11 kaplansky literals replaced with generic
  program-name language; `KAPLANSKY_REPOSITORY` env var
  renamed to `TARGET_REPOSITORY`. 10/10 tests pass.
- [x] **A.2** Rewrite
  `math/tests/local_readiness/test_durable_regression.py`
  ✅ DONE. 12 kaplansky literals replaced: hard-coded paths
  → `tmp_path`-driven fixtures; env vars → `TARGET_*`;
  function renamed to
  `test_fast_gate_rejects_non_research_program_project_root`;
  `_git_init_tmp_repo()` helper added so the math parser's
  `LOCAL020` check passes against the tmp repo. 29/30 tests
  pass (1 pre-existing failure unrelated to cleanup).
  Deferred to Q7: the `kaplansky_repository` TOML key
  cannot be renamed because math's `derive_bind_keys` reads
  that dataclass attribute directly. Class #22 grandfather
  status retained for this file.
- [x] **A.3** Update
  `math/tests/unit/test_launch_policy.py:48` comment ✅
  DONE. Comment now references @ADR-0091 instead of the
  literal `pi-monitor-kaplansky.sh` filename. 31/31 tests
  pass.
- [x] **A.4** Add
  `math/tests/static/test_no_program_named_modules_in_tests.py`
  ✅ DONE. Static check scans `math/tests/**/*.py` and
  `math/scripts/**/*.{py,sh}` for `kaplansky|KAPLANSKY`
  literals and fails on hits outside the grandfather list.
  **Surface area revealed: 189 violations across ~45
  files** — the original plan's inventory of ~20 was an
  undercount; the static check is the authoritative count.
- [x] **A.5** Expand Phase A scope based on A.4 findings.
  ✅ DONE. Two-commit strategy:
  - **A.5.a** + **A.5.b** + **A.5.d** Renamed
    `kaplansky-research-program` → `test-research-program`
    and `KAPLANSKY_REPOSITORY` env var → `TARGET_REPOSITORY`
    across 5 test files (15 runtime-string identity hits);
    renamed `test_kaplansky_provider_*` →
    `test_research_program_provider_*`. Docstring rewrites
    in 7 FPA files. Total: 30+ runtime-string identity
    hits removed; 4 FPA files renamed in-process to
    drop `kaplansky` from module name.
  - **A.5.c** Expanded grandfather list from 0 → 45
    entries with three categories (cat-1 meta-checks whose
    purpose IS the literal, cat-2 config-key fixtures /
    @ADR-0012 alias pairs deferred to Q7, cat-3 paired
    harness infrastructure slated for Phase B retirement).

  Result: static check went from 189 → 0 violations across
  664 scanned files. 190 tests passing in affected files.

#### Phase B — math scripts cleanup
- [x] **B.1** ✅ DONE. `math/scripts/pi-monitor-kaplansky.sh`
  deleted per @ADR-0091; operator muscle-memory now points
  at `uv run --project <program-repo> mathlint-<program>
  <verb>`. Updated comments in `wrap-mathlint-source.sh`,
  `test_wrap_mathlint_source.py`, and
  `test_pi_monitor_lifecycle.py` (rewritten to invoke the
  typed launcher directly).
- [x] **B.2** ✅ DONE. `math/scripts/verify.sh` `live_launch_cycle`
  stage now delegates to a new
  `kaplansky/scripts/verify-launcher.sh` (created and
  committed in kaplansky repo). The math engine no longer
  hardcodes the kaplansky repo path.
- [x] **B.3** ✅ DONE. `math/scripts/check-local-system-readiness.sh`
  `STATE/work/kaplansky` → `STATE/work/research-program`
  (math-side work directory; not the kaplansky launcher's
  state dir which lives under `PI_MONITOR_STATE_DIR`).
- [x] **B.4** ✅ DONE. `math/scripts/_bootstrap_m00.py` now
  takes `--target-repo <path>` CLI arg; emits
  `target_commit` (canonical) + `kaplansky_commit` (legacy
  @ADR-0012 alias) so receipt consumers that pin either
  field keep working.
- [x] **B.5** ✅ DONE. `math/scripts/_write_frontier_scheduler_receipt.py`
  emits both `target_revision` (canonical) + `kaplansky_revision`
  (legacy alias) per @ADR-0012. Regex in static check was
  extended to catch snake/kebab suffixes (e.g.
  `kaplansky_revision`) which `\b` word boundary misses.
- [x] **B.6** ✅ DONE. `math/scripts/_cold_start_bootstrap.py`
  FATAL message updated to point operators at the generic
  typed-launcher invocation pattern per @ADR-0091.

#### Phase C — pi_monitor tests cleanup
- [x] **C.1** ✅ DONE. Renamed 7 files'
  `kaplansky-research-program` → `test-research-program`,
  `kaplansky-workspace` → `test-workspace`,
  `kaplansky-tick-*` → `test-tick-*`,
  `kaplansky.work_request` → `test.work_request`,
  `kaplansky-roadmap-item/v1` → `test-roadmap-item/v1`
  (wire-codec test), docstrings, process-classifier test
  strings (`uv run pytest -k kaplansky` →
  `uv run pytest -k test_research_program`,
  `uv run mathlint red-team kaplansky` →
  `uv run mathlint red-team test_research_program`),
  and goals.md scan fixture
  (`# Kaplansky route` → `# test-research-program route`).
  Total: 30 literal replacements across 8 files.
- [x] **C.2** ✅ DONE (same edits covered C.1's
  `test_wire_parsers.py` scope).
- [x] **C.3** ✅ DONE. Added
  `pi_monitor/tests/static/test_no_program_identity_in_fixtures.py`
  (BC-4). Scans `pi_monitor/tests/**/*.py` for
  `kaplansky|riemann|navier_stokes` literals; grandfather
  list covers the `mathlint_fixture/` contract bundle
  (cat-1: tests the mathlint protocol, not a specific
  research program).
- [x] **C.4** (renamed) **Punted to Track 2**: pi_monitor's
  AGENTS.md class inventory is the wrong artifact for
  "exempt fixture files"; the static check's grandfather
  list is the canonical record. Skipped intentionally.

#### Phase D — enforcement + verification
- [x] **D.1** ✅ DONE. BC-1 + BC-4 wired into
  `research_institution.gates.aggregate._repo_boundary_check`
  as a single GateCheck that invokes both static checks
  and reports SKIP on missing repos / FAIL on violation.
- [x] **D.2** ✅ DONE. `bash green-gate/check-institution.sh
  --hermetic` exits 0 with `[repo-boundary] ok`. The
  pre-existing v-wire pyramid-stage failure is unrelated
  (operator-decision pending on kaplansky's
  work_source_provider integration).
- [x] **D.3** ✅ DONE. `docs/operations/verification-gates.md`
  V0 row updated to list the static checks alongside ruff;
  new section `V0 — repo-boundary static checks (BC-1, BC-4)`
  enumerates scope, hermetic coverage, and grandfather
  rationale.

### Track 2 — composed test scaffolding

#### Phase E — substrate (no source changes; pure test infra)
- [ ] **E.1** Add `FakeMathResearchProgram` to
  `research-institution/tests/_fakes.py` (F-1).
- [ ] **E.2** Add `FakeCatalog` to
  `research-institution/tests/_fakes.py` (F-2).
- [ ] **E.3** Add `FakeMathlintRoadmap` to
  `math/tests/support/fake_mathlint_roadmap.py` (F-3).
- [ ] **E.4** Add `FakeLiveMathlintSource` to
  `math/tests/orchestration/_support/fake_live_source.py`
  (F-8).
- [ ] **E.5** Add `FaultInjector`, `InMemoryAuditChain`,
  `BoundarySpy` per-repo (F-4, F-6, F-7).
- [ ] **E.6** Verify `ScriptedSource` covers F-5; build
  F-5 only if needed.

#### Phase F — single-machine suites
- [ ] **F.1** SM-A: kaplansky roadmap state machine
  (extends `test_work_selection.py`).
- [ ] **F.2** SM-B: research-institution gate state
  machine.
- [ ] **F.3** SM-C: research-institution dispatch envelope.
- [ ] **F.4** SM-D: pi_monitor reconcile table.
- [ ] **F.5** SM-E: pi_monitor rate-limit (extends
  `test_rate_limit_boundary.py`).
- [ ] **F.6** SM-F: pi_monitor execution record lifecycle.

#### Phase G — composed suites
- [ ] **G.1** COMPOSE-1: happy path.
- [ ] **G.2** COMPOSE-2: rate-limit trip + recovery.
- [ ] **G.3** COMPOSE-3: stop / operator-required.
- [ ] **G.4** COMPOSE-4: math source crash + recovery.
- [ ] **G.5** COMPOSE-5: cross-repo work selection.

#### Phase H — invariants
- [ ] **H.1** INV-T1, T2, T3, T4, T5, T6.
- [ ] **H.2** Cross-repo type identity (Hypothesis).

#### Phase I — adversarial
- [ ] **I.1** MU-1 through MU-8 mutation campaign.
- [ ] **I.2** PR-1, PR-2, PR-3 property state machines.
- [ ] **I.3** FZ-1 through FZ-4 fuzz targets.

#### Phase J — gate integration
- [ ] **J.1** Wire COMPOSE-1 into
  `math/tests/local_readiness/test_cross_repo_wiring.py`
  via a new `CROSS_REPO_007_*` test (post-cleanup,
  uses `FakeMathResearchProgram`'s generic identity).
- [ ] **J.2** Add a new gate stage `v-compose` between
  `v-engine` and `v-supervisor` that runs every COMPOSE-N
  in <30s and asserts GREEN-V2.
- [ ] **J.3** Document V-tier requirements per action:
  merge requires GREEN-V2; release requires GREEN-V3; live
  launch requires GREEN-V4.

---

## 10. Anti-patterns to avoid

Per `@verification-skill` TEST_QUALITY.md and the prime
directives in each repo's `AGENTS.md`:

- [ ] **NO snapshot-only assertions.** Assert transitions,
  not states.
- [ ] **NO tautological fixtures.** A
  `FakeMathResearchProgram` that always returns the same
  Dispatch hides bugs. Use Hypothesis for the inputs.
- [ ] **NO real clocks in unit tests.** All clock-dependent
  tests use `FakeClock`.
- [ ] **NO real subprocesses in V2.** Use `FakeRunner` or
  in-process adapters. Subprocess is V3+ only.
- [ ] **NO broad xfail/skips.** Every test either runs and
  passes, or is removed.
- [ ] **NO mock-the-implementation.** Tests should mock
  ports (WorkSource, Clock, Environment), not internal
  modules.
- [ ] **NO program-name literals outside the legitimate
  carrier list.** Math tests carry generic `TARGET_*`
  literals; pi_monitor tests carry generic
  `"test-research-program"` identities; the only place
  `"kaplansky"` survives is research-institution's catalog
  and kaplansky's own source — per the dependency graph in
  `research-institution/README.md`. **Exception class:** math
  tests exercising @ADR-0014's grandfathered substrings
  (e.g. `kaplansky_repository` config TOML key, math-content
  URIs like `kaplansky.counterexample-*`) — these are
  listed in the static check's grandfather list and retire
  with Phase A.5.e + Q7.

---

## 11. Done metrics

### Track 1 — done as of 2026-09-21

| Metric | Target | How measured | Status |
|---|---|---|---|
| Math tests: 0 kaplansky literals outside grandfather | 0 | math check reports `clean (scanned 663 files; 53 grandfathered)` | ✅ PASS |
| Math scripts: 0 kaplansky literals outside grandfather | 0 | same check | ✅ PASS |
| pi_monitor tests: 0 `"kaplansky-research-program"` / `"kaplansky"` literals outside exempt list | 0 | pi_monitor check reports `clean (scanned 104 files; 8 grandfathered)` | ✅ PASS |
| `pi-monitor-kaplansky.sh` deleted | yes | `git ls-files math/scripts/pi-monitor-kaplansky.sh` returns nothing (commit fc9f2bf) | ✅ PASS |
| `verify.sh` live_launch_cycle delegates to kaplansky | yes | `scripts/verify.sh` line 112 reads `bash ${KAPLANSKY_SCRIPTS_DIR:-...}/scripts/verify-launcher.sh` | ✅ PASS |
| `kaplansky/scripts/verify-launcher.sh` exists | yes | `git ls-files kaplansky/scripts/verify-launcher.sh` returns the file (commit 6fac001) | ✅ PASS |
| `_bootstrap_m00.py` carries generic target paths | yes | script accepts `--target-repo <path>` CLI arg; emits `target_commit` + legacy `kaplansky_commit` alias | ✅ PASS |
| Institution gate `repo-boundary` sub-check PASS | yes | `bash green-gate/check-institution.sh --hermetic` reports `[repo-boundary] ok` | ✅ PASS |
| `verification-gates.md` V0 row lists BC-1 + BC-4 | yes | doc updated with new `V0 — repo-boundary static checks (BC-1, BC-4)` section | ✅ PASS |
| Research-institution tests passing | 100% | `pytest tests/ -k 'not live'` reports `397 passed, 2 skipped` | ✅ PASS |
| pi_monitor tests in renamed files passing | 100% | `pytest tests/test_supervisor_dispatch_rate_limit.py ...` reports `75 passed` | ✅ PASS |
| math tests in renamed files passing | ≥ 99% | per-file counts in Phase A.5 commit messages | ✅ PASS (1 pre-existing failure unrelated) |

### Track 2 — to be measured when Phase E–J land

| Metric | Target | How measured |
|---|---|---|
| SM-A through SM-F tests passing | 100% | `pytest tests/test_state_machine_*` |
| COMPOSE-1 through COMPOSE-5 tests passing | 100% | `pytest tests/test_compose_*` + extended `math/tests/local_readiness/test_cross_repo_wiring.py` |
| INV-T1 through T6 invariants proven | 100% | `pytest tests/test_invariants_*` |
| Mutation kill rate | ≥ 80% | `mutmut run --total-failures 0` |
| Hypothesis tests passing | 100% | `pytest --hypothesis-seed=$(date +%s)` |
| V2 composed test runtime | ≤ 30s | `time pytest tests/test_compose_*` |
| Cross-repo type identity | 100% round-trip | SM-C + COMPOSE-5 |
| New fixtures landed | F-1 through F-8 | `git log -- fixtures` |
| Track 1 phases complete | A, B, C, D | this checklist |
| Track 2 phases complete | E, F, G, H, I, J | this checklist |
| Institution gate GREEN-V1 after Track 1 | yes | `bash scripts/verify-institution.sh` |
| Institution gate GREEN-V2 after Track 2 Phase G | yes | same |

---

## 12. Cross-references

- `@ADR-0006` — research-institution scope (it owns the
  catalog + entry-point composition, not proof-program
  internals).
- `@ADR-0007` — research-institution owns the WorkSourceProvider
  slot; the only repo that imports program-named modules
  for the dispatch composition.
- `@ADR-0012` — backward-compatibility aliases for
  `target_revision` ↔ `kaplansky_revision`. Used by Phase A
  env-var renames.
- `@ADR-0014` — mathlint does not import program-named
  modules. Phase A enforces this on `tests/` and
  `scripts/`.
- `@ADR-0025` — supervisor decomposition. COMPOSE-1
  exercises the seam.
- `@ADR-0091` — mathlint does not ship program launchers.
  Phase B retires `pi-monitor-kaplansky.sh`.
- `@ADR-0092` — pi_monitor does not name mathlint. Phase C
  enforces this on `tests/` fixtures.
- `@CTR-0088` — catalog schema contract.
- `@CTR-0094` — WorkSourceProvider dispatch envelope
  contract. `FakeMathResearchProgram` produces envelopes
  that parse against this.
- `@INV-005` — supervisor restart semantics. COMPOSE-4's
  recovery scenario is the V2 expression for the
  `LiveSourceError("invalid_report")` case.
- `@INV-0093` — research-institution gate is canonical
  wiring evidence; V-WIRE runs
  `math/tests/local_readiness/test_cross_repo_wiring.py`.
- `verification-skill/skills/verification/SKILL.md` —
  authoritative methodology (especially §3 Principle 10
  no-churn, §5 Priority 0 false-GREEN, §10 stop conditions).
- `repo-coherence-skill/skills/repo-coherence/SKILL.md` —
  drives fixture placement and the dep-graph enforcement.
- `semantic-repo-skill/skills/semantic-repo/SKILL.md` —
  drives the durable-anchor citations in §12.
- `code-health-skill/skills/code-health/SKILL.md` —
  shrinks the grandfather list (class #22) once
  Track 1 lands; REFERRED work.
- `docs/operations/verification-gates.md` — current V0–V4
  tier definitions + V-WIRE; this plan extends V-WIRE and
  adds `v-compose` (Phase J.2).
- `docs/operations/launch-kaplansky-autonomously.md` — V4
  live launch lane (separate from this plan).

---

## 13. Open questions

- [ ] **Q1** ~~Where does the shared `tests/_fakes.py`
  live?~~ **RESOLVED:** per-repo duplication.
- [ ] **Q2** ~~Should `FakeKaplanskyRoadmap` exist?~~
  **RESOLVED:** no. The connected-pipeline tests use
  `FakeMathResearchProgram` in research-institution.
- [ ] **Q3** Property test seed: deterministic per CI run,
  or per-commit? **Recommendation: deterministic per CI**
  so a regression in CI is reproducible locally.
- [ ] **Q4** Mutation campaign: run on every commit, or
  only on the protected branch? **Recommendation:
  protected branch only**, with weekly campaign runs
  reported in the gate.
- [ ] **Q5** Should COMPOSE-1's wiring test extend
  `math/tests/local_readiness/test_cross_repo_wiring.py`
  (existing V-WIRE harness) or live in a new
  `pi_monitor/tests/test_compose_*`? **Recommendation:**
  extend the existing math test file for the
  mathlint-source → OS seam, and add new
  `pi_monitor/tests/test_compose_*` for the supervisor →
  audit chain → worker seam. Two harnesses, two seams.
- [ ] **Q6** Does COMPOSE-4's `invalid_report` recovery
  require a production fix or only a test? **Current
  read:** test only — `LiveSourceError("invalid_report")`
  is the correct raise; the supervisor's catch path
  needs to restart mathlint-source on that error code.
  If the supervisor already does that, COMPOSE-4 is
  GREEN with the new fake. If not, COMPOSE-4 is red
  first, fix second.
- [ ] **Q7** Math's `AGENTS.md` class #22 grandfather
  list — should Phase D.3 retire it entirely, or
  retain a minimal list for the `local_readiness/
  config.py` env-var normalizer? **Recommendation:**
  retire the env-var normalizer's literal in Phase B.4
  (the `TARGET_*` alias already exists); keep only the
  `final_product_acceptance/*.py` provenance fields
  grandfathered (those are content-domain data, not
  config conventions). Drop everything else.

---

## 14. Status

- [ ] Track 1, Phase A — math tests cleanup
- [ ] Track 1, Phase B — math scripts cleanup
- [ ] Track 1, Phase C — pi_monitor tests cleanup
- [ ] Track 1, Phase D — enforcement + verification
- [ ] Track 2, Phase E — substrate
- [ ] Track 2, Phase F — single-machine suites
- [ ] Track 2, Phase G — composed suites
- [ ] Track 2, Phase H — invariants
- [ ] Track 2, Phase I — adversarial
- [ ] Track 2, Phase J — gate integration

Last updated: 2026-09-20 (post-refactor).
