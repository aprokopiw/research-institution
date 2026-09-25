# 01 — Math Test-Suite Rationalization

> **Spec-Kit** artifact. Zero-padded `00–10`; lex sort = execution
> order. This is `01`. Depends on `00`. Unblocks `04`.

## Identity

- **spec_id:** `01-test-suite-rationalization`
- **owner_repo:** `math`
- **owner_repos:** `{math, research-institution}` (the latter hosts
  the canonical vocabulary machinery from entry 00).
- **status:** draft
- **depends_on:** `00-verify-constitution-ratification`
- **unblocks:** `04-stateful-sample-research`

## Primary actor

The maintainer running focused math tests daily and the CI system
gating protected-branch merges on the math-only VG-0/VG-1/VG-2
gates. Implicit audience: agents operating on math today against
six forbidden strings (`e2e`, `smoke`, `acceptance`, `endurance`,
`live`, `chaos`) used as primary tiers.

## Problem statement (current failure evidence)

From the test-and-simulation guide §7 (Pri-0 inventory):

- math contains **584 test modules** with **~7,841 collected cases**
  after parametrization.
- ≥318 direct `skip()` calls, 36 `skipif` uses, 2 `importorskip`,
  1 `xfail` in source.
- `pytest --collect-only -q` **fails red** at ~33% coverage (because
  math's `addopts` enables coverage). The plain collection
  command recommended by docs is therefore false as written.
- Directories `acceptance`, `e2e`, `endurance`,
  `final_product_acceptance`, `live_readiness`, `local_readiness`,
  `smoke`, `integration`, `chaos` overlap in meaning.
- `tests/endurance/README.md` calls the dir T1 Unit but the file
  contents are nightly long-running recovery.
- `tests/final_product_acceptance/README.md` calls the dir T1 Unit
  but mixes T5/T6/T7 work.
- `tests/acceptance/README.md` claims T7 model-bound but contains
  deterministic fake-monitor, paired-process, static release,
  security, and live tests.
- `tests/e2e/README.md` claims E2E never calls real pi-monitor,
  while entry 05–06 here require real pi-monitor in S2 scenarios.
- `tests/smoke/` has no collected test modules but still appears as
  canonical tier surface.
- Default `unit` marker swallows subprocess, filesystem, integration,
  and environment tests when markers are missing.
- Math is the foundation tier for the entire institution's
  numerical evidence; ambiguity here cascades into every later
  entry.

## Independent user stories

1. As a **maintainer**, I run
   `pytest --collect-only --no-cov -q` and it exits 0 and reports a
   stable node-ID hash that does **not** drift between identical
   trees.
2. As a **CI gate author**, every `tests/` directory has a
   `README.md` whose tier statements match the actual markers on
   the test files in that directory.
3. As a **maintainer**, `make test-target` produces tier-routed
   runs: `make test-unit`, `make test-property`,
   `make test-contract`, `make test-integration`,
   `make test-process`, `make test-deployment`,
   `make test-provider-live`, `make test-soak`.
4. As an **operator**, no test in math uses the six forbidden
   primary-tier strings. Where they are tolerated today, each
   carries an `expiry_spec_id` in
   `research-institution/.specify/memory/transient-exemptions.toml`
   that an audit static check verifies.
5. As a **maintainer**, the math docs
   `docs/operations/verification-gates.md` and `docs/concepts/`
   match what the static checks actually verify.
6. As an **adversary**, I cannot land a PR that says "I added a
   test in `tests/e2e/` and it passed" — the static-check ratchet
   rejects unmarked and forbidden-tier markers at PR time.

## Functional requirements (per spec-artifact contract)

FR-1. Math's `pyproject.toml` `[tool.pytest.ini_options]` is amended
so that `addopts = ["--no-cov", ...]` is the default at math's
research-institution test command, OR a `tool.pytest.collect_only`
config profile is added. The plain
`pytest --collect-only -q` command exits 0 at the math HEAD with
zero coverage interference.

FR-2. `math/tests/static/test_closed_tier_vocabulary.py` is created
and authored:
   - scans `math/tests/` for any test function with a primary
     marker from the §1 closed set **or** any of the six forbidden
     strings as a primary marker;
   - asserts: every collected test has exactly one primary tier
     marker from `unit | property | contract | integration |
     process | deployment | provider_live | soak`;
   - asserts: no test uses `e2e | smoke | acceptance | endurance |
     live | chaos` as primary markers (failure cites
     `tests/static/test_closed_tier_vocabulary.py` and the
     exempted row when applicable);
   - asserts: dependencies declared via `@pytest.mark.dependencies(...)`
     match the §2 closed set when present.

FR-3. `math/tests/static/test_dependency_vocabulary.py` mirrors
the same vocabulary for dependencies (`filesystem | git | subprocess
| postgres | pi_executable | pi_monitor_executable | model_provider
| network | macos_launchd | formal_backend_flint | formal_backend_gap`).

FR-4. `math/tests/static/test_skip_xfail_baseline.py` enumerates
every existing `skip` / `skipif` / `importorskip` / `xfail` call
in math source, classifies each, and asserts the total count of
**required-lane** skips is zero. Optional-environment skips
(platform-not-applicable, missing-formal-backend) are pre-flighted
to lane `BLOCKED` rather than silently skipped; every legacy skip
bears an owner / reason-code / dependency / expiry-spec-id tuple
in a baseline TOML registry that is checked-in and ratchets down.

FR-5. `math/Makefile` is amended with tier-routed targets:
```
test-unit          -> pytest -m unit
test-property      -> pytest -m property
test-contract      -> pytest -m contract
test-integration   -> pytest -m integration
test-process       -> pytest -m process
test-deployment    -> pytest -m deployment
test-provider-live -> pytest -m provider_live --live
test-soak          -> pytest -m soak --hours N
test-tier-fast     -> test-unit + test-property + test-contract
```

FR-6. Migration of folder names per the master guide §7 directory
rationalization target:
   - `tests/final_product_acceptance/` stays only while
     `src/mathlint/final_product_acceptance/` remains a real
     package; its `README.md` describes subsystem responsibility,
     not "all-files-are-acceptance-tier".
   - `tests/live_readiness/` is folded into owner-subsystem tests
     with markers; the directory is deleted when emptied.
   - `tests/e2e/` cases move to owning subsystem or are marked
     `process`; the directory is deleted when emptied.
   - `tests/acceptance/` non-provider cases move to owner
     subsystem; provider-live cases acquire the `provider_live`
     marker; the directory is deleted when emptied.
   - `tests/chaos/` deterministic cases move to owner subsystem
     with `fault_profile` metadata; the generic `chaos` bucket is
     removed when emptied.
   - `tests/smoke/` deleted (currently empty in source).
   - Root-level tests move to owner directories unless they are
     genuine repository-wide policy / static-integrity tests.

FR-7. `math/tests/README.md` is rewritten to route by subsystem +
tier, with one Makefile command per tier. It removes any reference
to ambiguous primary tiers.

## Explicit exclusions (boundary discipline)

- Implementation work inside any test file (per-FR-6 moves are
  bounded but the assertions themselves stay).
- Updates to durable records (those land in entry 04 where they
  become consequential — e.g. `@INV-0088` amendments).
- The hermetic institution green gate (entry 06).
- Any cross-repo test that exercises pi-monitor or research-
  institution code (those land in entries 02 / 05 / 06).

## Measurable success criteria

- `pytest --collect-only --no-cov -q` exits 0 and reports a
  stable deterministic inventory hash.
- `pytest -q tests/static/test_closed_tier_vocabulary.py` exits 0.
- `pytest -q tests/static/test_dependency_vocabulary.py` exits 0.
- `pytest -q tests/static/test_skip_xfail_baseline.py` exits 0.
- `make test-tier-fast` exits 0.
- The math `tests/` directory contains zero references to the six
  forbidden primary-tier strings in active markers.
- All twelve `cannot claim done when…` clauses of entry 00 hold
  at math's HEAD (re-verified by the canonical script).

## Failure and edge cases

- **F-1.** A test currently uses `live` as a marker for a
  provider-call test. Reclassify to `provider_live` with the
  existing semantics; the marker syntax change requires no test
  rewrite beyond the marker rename.
- **F-2.** A test currently uses `e2e` as a marker AND the test
  actually exercises the supervisor subprocess end-to-end.
  Reclassify to `process` (S2 territory; entry 05-06 own it).
- **F-3.** A test currently under `tests/chaos/` is genuinely
  provider-stress. Move to entry 04's filesystem, mark with
  `integration` tier + `fault_profile` metadata.
- **F-4.** A folder move changes `path:` references in docs.
  Update docs in the same commit (CI gate enforces).

## Dependencies on earlier entries

- **Entry 00** — verify-constitution ratified; §1 tier vocabulary
  closed set is the authority.
- `math/AGENTS.md` institution-wide prevention layer section —
  unchanged.

## "Cannot claim done when…"

1. The plain `pytest --collect-only -q` command still exits red
   with coverage.
2. Any test in math uses a primary marker outside the §1 closed
   set.
3. Any test in math uses `e2e | smoke | acceptance | endurance |
   live | chaos` as primary markers and lacks a registry row
   expiring on this entry's id.
4. `tests/static/test_closed_tier_vocabulary.py` is missing or
   failing.
5. `tests/static/test_dependency_vocabulary.py` is missing or
   failing.
6. `tests/static/test_skip_xfail_baseline.py` is missing or
   failing.
7. `math/Makefile` lacks the eight tier-routed targets above.
8. `math/tests/README.md` still routes by ambiguous tier directory.
9. Any migrated folder (`tests/e2e`, `tests/live_readiness`,
   `tests/smoke`, etc.) still has files inside that violate the
   migrated state.
10. The required-lane skip count is non-zero.
11. Entry 00's twelve cannot-claim-done clauses do NOT all hold at
    math's HEAD (cross-anchor cross-check).
12. The `transient-exemptions.toml` registry was edited without
    bumping its `version` field, or its exemption rows reference
    non-existent files.

## Non-goals

- Touching math's source code under `src/mathlint/`.
- Adding new durable records (entries 04, 06, 10 own those).
- Refactoring non-test modules to satisfy the tier vocabulary
  (the vocabulary is test-side only).

## Cross-references

- `.specify/memory/constitution-verify.md` §1, §2, §3, §4, §5, §11.
- `research-institution/.specify/memory/transient-exemptions.toml`
  (initial entries seeded by 00; this entry adds math rows).
- `research-institution/scripts/check-prime-directive.sh` (the
  canonical grep; unchanged here, exercised at math HEAD).
- `math/AGENTS.md` institution-wide prevention section (unchanged).
- `research-institution/.agents/transient/test_and_simulation_suite.md`
  §7 (Pri-0 inventory and directory rationalization target).
- `@ADR-0014` (mathlint does not import program-named modules;
  per-test `process` tier does not change this).
- `@ADR-0091` (mathlint ships no program launchers; tests that
  exercise launcher code move to research-institution entry 06).
- `@INV-0088` (sample fixture requires no external state; honored
  by entry 04's stateful sample program).
- `@CTR-0020` (three-repo wire contract; honored by every
  `process`-tier test that exercises pi-monitor).
