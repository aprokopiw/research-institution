# Verification Gates

This document is the operator-facing description of the institution's
GREEN hierarchy. Per `@INV-0093`, the institution green gate is the
canonical wiring evidence for the research-institution; this doc
defines what "GREEN" means at each tier.

## Tier definitions

The repository follows the standard V0–V4 GREEN hierarchy with one
additional tier, **V-WIRE**, that catches cross-repo composition
defects that per-repo unit tests cannot reach. Each tier has a
specific purpose and a specific executable command. **GREEN at a
tier means the tier's command passed; nothing more.** Cross-tier
claims (e.g. "the dispatcher is bug-free") require cross-tier
evidence.

| Tier | Purpose | Command | Status |
|---|---|---|---|
| **V0** | structural validity (lint, type, schema, repo-boundary cleanliness) | `ruff check research_institution tests` + math-side `tests/static/test_no_program_named_modules_in_tests.py` + pi_monitor-side `tests/static/test_no_program_identity_in_fixtures.py` | PASS (CI + green-gate) |
| **V1** | fast local confidence (unit tests) | `pytest -q` | PASS (296+ tests, 2 skipped) |
| **V-WIRE** | cross-repo composition contracts | `bash $HOME/Documents/andrei/math/scripts/autonomy.sh` (mathlint G7) | PASS / FAIL (operator decision pending on kaplansky work_source_provider) |
| **V2** | hermetic repository confidence (full suite + green-gate) | `bash green-gate/check-institution.sh --hermetic` | PASS |
| **V3** | deep adversarial assurance (mutation, property, fuzz) | partial: property tests for entry-point parser; staleness-boundary oracle for status | PARTIAL |
| **V4** | system / release assurance (clean-install, live-mode wiring) | `bash green-gate/check-institution.sh --live` (operator-only) | BLOCKED without operator creds; hermetic variant under `RESEARCH_INSTITUTION_HERMETIC=1` |

### V0 — repo-boundary static checks (BC-1, BC-4)

**BC-1 (math):** `tests/static/test_no_program_named_modules_in_tests.py`
scans `math/tests/` + `math/scripts/` for program-name literals
(`kaplansky`, `riemann`, `navier_stokes`). Violations mean math's
test or script surface hardcodes a specific research program,
violating `@ADR-0014` (mathlint does not import program-named
modules) and `@ADR-0091` (mathlint does not ship program
launchers). A grandfather list documents each remaining
literal with a retirement path.

**BC-4 (pi_monitor):** `tests/static/test_no_program_identity_in_fixtures.py`
scans `pi_monitor/tests/` for the same literals. Violations
mean pi_monitor's test fixtures hardcode a specific program
identity, violating `@ADR-0092` (pi_monitor does not name
mathlint). The `mathlint_fixture/` contract bundle is
grandfathered because those tests intentionally exercise the
mathlint protocol.

**Hermetic coverage:** both checks are runnable without
network/credentials and pass under `RESEARCH_INSTITUTION_HERMETIC=1`.
The math-side check is wired into the engine sub-step of the
green-gate.

## V-WIRE — cross-repo composition contracts

**Claim:** the institution wires correctly across math-engine +
pi_monitor + kaplansky (and any future research-program package).
Unit tests in any one repo CANNOT verify this — they only verify
their own boundaries.

**Evidence:** mathlint's `scripts/autonomy.sh` G7 runs
`tests/integration/test_three_repo_autonomy_e2e.py` AND
`tests/local_readiness/test_cross_repo_wiring.py`. Each test in
the latter file is prefixed with a stable ID (`CROSS_REPO_001`
through `CROSS_REPO_006`) so audit logs and dashboards can grep
for them.

**What V-WIRE catches** (each is a real defect the institution has
hit at least once):

| ID | Defect |
|---|---|
| CROSS_REPO_001 | mathlint-source CLI doesn't call `discover_program_providers()` on startup → slot stays empty |
| CROSS_REPO_002 | installed program plugin (e.g. kaplansky) registers `ProgramProviders` without `work_source_provider` → slot stays empty |
| CROSS_REPO_003 | `mathlint-source` subprocess crashes or returns `SOURCE_NO_PROVIDER` because of #1 and/or #2 |
| CROSS_REPO_004 | `mathlint.providers` entry point not discoverable (pyproject.toml drift, broken install) |
| CROSS_REPO_005 | `local.toml.model_route` and `local-pi-monitor.toml [worker].model` disagree → silent route mismatch |
| CROSS_REPO_006 | supervisor.lock file is unreadable / in an unknown state (corruption detection) |

**Skipped when:**

- `MATHLINT_AUTONOMY_SKIP_G7=1` (cold-start escape hatch; same knob
  that autonomy.sh G7 honors).
- `RESEARCH_INSTITUTION_HERMETIC=1` (CI runners without mathlint
  installed; same pattern as the engine sub-check).
- `bash $HOME/Documents/andrei/math/scripts/autonomy.sh` not found
  (operator has not yet run `scripts/bootstrap-institution.sh`).

**How to add a V-WIRE assertion:** drop a `test_cross_repo_NNN_*`
function in
`$HOME/Documents/andrei/math/tests/local_readiness/test_cross_repo_wiring.py`.
The autonomy.sh G7 invocation picks it up automatically; the
institution green-gate picks it up via `RESEARCH_INSTITUTION_AUTONOMY_SCRIPT`
(defaults to the canonical operator path).


## V0 — structural validity

**Claim:** code in `research_institution/` and `tests/` is free of the
classes of bug that ruff's curated rule set catches (E, F, W, B, S,
UP, N, PIE, RET, SIM categories).

**Excluded by design** (silenced in `pyproject.toml`):
- `E501` — line length; `ruff format` is the formatter.
- `S101` — pytest uses `assert` semantically.
- `S603` — all subprocess callsites pass argv lists (no `shell=True`).
- `S607` — operator-PATH resolution is intentional; the institution
  assumes `mathlint`, `pi-monitor`, `bash` are on `PATH`.
- `S104` — `/tmp` and similar paths are intentional.

**Evidence:** ruff exits 0 against `research_institution` and `tests/`
as of the current commit. CI runs ruff on every push and PR
(`.github/workflows/ci.yml::v0-static`). The hermetic green-gate also
runs ruff as its first sub-check
(`green-gate/check-institution.sh::run_check "v0-ruff"`).

**Mutation oracle:** if ruff's rule set were silently relaxed (e.g.
swapping `--select E,F,W,B,S,UP,N,PIE,RET,SIM` for `--select E,F`),
78 substantive violations in production code (10 S607, 8 S108, 3
SIM115, 3 SIM105, 1 B904, 1 PIE810, ...) would silently ship. CI
enforces the curated set; loosening requires editing `pyproject.toml`
+ this doc.

## V1 — fast local confidence

**Claim:** unit tests exercise the dispatcher's typed Python API, the
catalog loader, the contracts layer, and the entry-point parser with
deterministic oracles.

**Evidence:** 192 unit tests pass; 2 skipped (live-mode tests that
require `MATHLINT_MODEL_ROUTE` and no supervisor lock — both are
BLOCKED-class by design).

**Test roots:** `tests/` (24 files). Patterns exercised:
- **Fake subprocess injection** (`tests/_fakes.py::FakeRunner`) — every
  dispatcher method is exercised with argv + env + clock injection.
- **Boundary oracles** — `test_status.py::test_headline_stopped_after_5_minutes`
  pins the staleness boundary exactly (NOW+300s → running, NOW+301s →
  stopped). Mutation-test oracle: changing `>` to `>=` flips one
  boundary case to fail.
- **Property tests** — `tests/test_entry_point_contract.py` generates
  ~500 random valid (module, callable) pairs per run, asserting
  parse-then-reserialize identity.

**Out of scope:** real subprocess execution, real network I/O, real
file-system state across runs.

## V2 — hermetic repository confidence

**Claim:** the institution is wired end-to-end on a hermetic machine
(no LLM calls, no credentials). All catalog-listed programs have
their `check_program_script` resolvable and returning exit 0.

**Evidence:** `bash green-gate/check-institution.sh --hermetic` exits
0 with the message `GREEN INSTITUTION READY`. Sub-checks:

```
[v0-ruff] ok                                # ruff passes (see V0)
[engine] ok                                 # mathlint system-readiness via $HOME/.../check-local-system-readiness.sh --skip-external --use-program=self_test-sample
[supervisor] not on PATH (skipped)          # pi-monitor absent → skip (intentional)
[program=kaplansky] ok                      # kaplansky's check_program_script exits 0
```

The aggregator is `green-gate/check-institution.sh`. It reads
`catalog/programs.toml` and iterates each program, calling its
declared `check_program_script` with the appropriate mode flag.

## V3 — deep adversarial assurance

**Claim:** the most consequential claims are challenged by independent
oracles, not just example tests.

**Implemented:**
- **Entry-point parser property tests** — ~500 synthesized inputs per
  run, asserting identity + idempotence. Catches off-by-one and
  whitespace-handling regressions.
- **Staleness-boundary oracle** — exact 300-second boundary pinned
  for `read_status_headline`.
- **Gate-parser defensive default** — `OTHER` task kinds map to OPEN,
  not CLOSED, with a parametrized test over every `TaskKind` enum
  member.
- **Architecture-review argv oracle** — `tests/test_cli.py` asserts
  the exact argv shape that `research doctor` sends to the green
  gate, including the hermetic/live flag and `--skip-program=`
  forwarding.

**Not implemented:**
- Mutation testing infrastructure (e.g. `mutmut`, `cosmic-ray`). The
  existing tests are mutation-tested manually (see the
  verification-audit report); automating this would catch
  regression-induced survivors at scale.
- Coverage-guided fuzzing. Not justified by the codebase's
  combinatorial surface; the property tests cover the meaningful
  shapes.
- Concurrency stress. The dispatcher is a thin subprocess wrapper
  with no shared state; concurrency hazards are absent by design.

## V4 — system / release assurance

**Claim:** the institution is wired on a real operator machine with
real credentials.

**Operator path:** `MATHLINT_MODEL_ROUTE=openai-codex/<route> bash
green-gate/check-institution.sh --live` exits 0 when the operator has
a valid pi auth grant.

**Hermetic path:** the gate accepts two test-mode env vars:

- `RESEARCH_INSTITUTION_HERMETIC=1` — skips the V0 ruff step (use
  in isolated CI runners where the source tree isn't checked out).
- `RESEARCH_INSTITUTION_ENGINE_SCRIPT=<path>` — overrides the
  engine script location (use in tests to substitute a fake engine
  that delegates to a fake mathlint).

**Hermetic oracles** (run automatically in CI):
- `test_green_gate_live_with_fake_mathlint` — `--live` succeeds with
  fake mathlint + fake engine script + fake program dir.
- `test_green_gate_live_fails_closed_without_credentials` — `--live`
  fails with `RED:` verdict when `MATHLINT_MODEL_ROUTE` is unset.

These cover the same regression surface as the operator-only
`test_cold_start_doctor_live_passes_when_credentials_valid` test
without requiring operator credentials, so a CI runner can exercise
the live-mode code path every commit.

## Skip / BLOCKED policy

| Status | Meaning | Example |
|---|---|---|
| PASS | executed and met its oracle | `ruff check` exits 0 |
| FAIL | executed and violated its oracle | gate returns `RED:` |
| BLOCKED | required evidence unobtainable in this run | live gate when `MATHLINT_MODEL_ROUTE` is unset |
| NOT_RUN | not executed this invocation | V3 mutation tests (manual only) |
| NOT_APPLICABLE | deliberately excluded | timezone hints (DTZ) — irrelevant to glue code |

`xfail` representing a known unmet requirement **never counts as
evidence** that the requirement passes.

## Adding new code

When you add a new code path:

1. Add V1 unit tests with a deterministic oracle (fake runner, fake
   env, fake clock — see `tests/_fakes.py`).
2. If the path is security-sensitive or destructive, add a property
   test that exercises the claim with synthesized inputs.
3. If the path is on the dispatcher's hot path, add a boundary
   oracle (off-by-one, empty input, max input).
4. If the path crosses a process boundary (subprocess, network,
   filesystem), add a hermetic end-to-end test that injects a
   fake at the boundary, mirroring the live-mode oracles.

When you change the gate semantics:

1. Update `green-gate/check-institution.sh` (the executable truth).
2. Update this doc (the operator's contract).
3. Update `tests/test_green_gate_hermetic.py` (the executable test).
4. Audit `docs/semantic/` for `@INV-NNNN` references that name the
   affected invariant.

## See also

- `AGENTS.md` — prime directive + cold-start workflow.
- `docs/operations/research-institution-quickstart.md` — operator's
  one-pager.
- `docs/operations/architecture-review-gate.md` — the gate's
  application-level semantics.
- `docs/semantic/invariants/inv-0093-*.md` — institution green gate
  is canonical wiring evidence.
