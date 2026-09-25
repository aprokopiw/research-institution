# 01 — Plan

## Technical context

This entry belongs to a three-sister cleanup family (entries 01, 02,
03 — math, pi_monitor, kaplansky). Each sister ships the same shape
of artifacts in its own repo and consumes the verify-constitution
machinery landed by entry 00. The differences are: file paths, repo-
local static-check placements, and the specific list of folders that
require migration.

## Existing implementation to extend

- `math/pyproject.toml` `[tool.pytest.ini_options]` — has `addopts`
  enabling coverage at all times, breaking plain collection.
- `math/Makefile` — has test/CI targets without tier routing.
- `math/tests/` — 30+ directories; ambiguous primary tier vocabulary;
  ~318 skip calls; ~584 modules.
- `math/tests/README.md` — references tier vocabulary ambiguously.
- `research-institution/.specify/memory/transient-exemptions.toml` —
  initial registry (from 00); math rows are added here.
- `research-institution/scripts/check-prime-directive.sh` — canonical,
  used at math HEAD by `make check-prime-directive`.

## Components changed

| Path | Change |
|---|---|
| `math/pyproject.toml` | add `[tool.pytest.collect_only]` profile and `--no-cov` default; doc the change. |
| `math/tests/static/test_closed_tier_vocabulary.py` | new. |
| `math/tests/static/test_dependency_vocabulary.py` | new. |
| `math/tests/static/test_skip_xfail_baseline.py` | new + baseline TOML. |
| `math/tests/README.md` | rewrite to route by subsystem + tier. |
| `math/Makefile` | add tier-routed targets. |
| `math/tests/{final_product_acceptance,e2e,live_readiness,smoke,chaos,...}/*` | bounded moves to owner-subsystem tests; per-folder commit. |
| `research-institution/.specify/memory/transient-exemptions.toml` | append math rows with `expiry_spec_id = "01-test-suite-rationalization"`. |

## Components explicitly NOT changed

- `math/src/mathlint/*` (production code).
- `research-institution/.specify/memory/constitution-verify.md`.
- Sibling repos' equivalent (entries 02 / 03 own those).
- The `dispatch_protocol` stub package (entry 09 owns this).

## Repository ownership boundary

```
math                 (test topology, static checks, Makefile targets,
                      folder moves, baseline TOML)
research-institution (transient-exemptions.toml math rows;
                      may receive O(1) commit per math-driven
                      cross-ref amendment)
```

## Constitution Check (entry-01-specific)

Sister entry to 02 and 03; the Constitution Check is identical:

- **§1** — tier vocabulary enforced by
  `math/tests/static/test_closed_tier_vocabulary.py` (FR-2).
- **§2** — dependency vocabulary enforced by
  `math/tests/static/test_dependency_vocabulary.py` (FR-3).
- **§3** — gate-status algebra respected by the new baseline
  registry: required-lane skips → lane `BLOCKED`, not green.
- **§10** — `make check-prime-directive` exits 0 at math HEAD at
  each commit.
- **§11** — META.md emitted at completion with the schema from 00.
- **§12** — math's existing anchor set is unchanged; no new anchors
  added by 01 (entries 04, 06, 10 own durable-record authorship).

## Data and state migration

- Baseline TOML registry `tests/static/skip_xfail_baseline.toml` is
  introduced carrying every pre-existing skip + xfail + importorskip,
  classified by reason code. The ratchet count can only decrease.
- `math/tests/README.md` rewrite re-orders navigation by subsystem.
- Folder migrations preserve `git log --follow` for files moving
  within the same math repo (use `git mv`).

## Failure atomicity and rollback

- Each milestone commits cleanly; `pytest --collect-only --no-cov`
  remains green at each commit. Rollback is per-commit.
- Folder moves happen in bounded batches by subsystem; a batch
  fails closed if its tier-marker coverage drops below the prior
  baseline (a `make test-tier-fast` smoke is in the batch).
- The static check `test_closed_tier_vocabulary.py` is the
  canonical rollback assertion: it MUST pass at each commit.

## Security / credential impact

- The new baseline TOML is checked-in (not under
  `.pi-prime-attestations/`). No secrets.
- No new subprocess invocations require real credentials; the
  `provider_live` tier is wired but no math test in this entry is
  expected to be `provider_live` (those are in entry 04's
  stateful sample program).

## Performance / runtime budgets

- `pytest --collect-only --no-cov -q` ≤ 30 s (today the broken
  command exits at coverage 33% in < 1 s; target = a clean
  collection in ≤ 30 s).
- `pytest -q tests/static/test_closed_tier_vocabulary.py` ≤ 5 s.
- `pytest -q tests/static/test_dependency_vocabulary.py` ≤ 5 s.
- `pytest -q tests/static/test_skip_xfail_baseline.py` ≤ 5 s.
- `make test-tier-fast` ≤ 5 min (today's math V1 suite at this
  scope is ≤ 2 min; budget headroom for the relocation).

## Test / evidence tier map (entry 01)

| Artifact | Tier | Evidence |
|---|---|---|
| `test_closed_tier_vocabulary.py` | contract | dry-run static analysis; deterministic |
| `test_dependency_vocabulary.py` | contract | dry-run static analysis; deterministic |
| `test_skip_xfail_baseline.py` | contract | reads TOML + AST; deterministic |
| `Makefile` tier targets | integration | subprocess to `pytest -m <tier>`; deterministic where `-m unit` etc. are runnable |
| folder migrations | integration | each migrated test's existing tier remains green |

This entry contributes NO `process` / `deployment` / `provider_live`
/ `soak` evidence. Those tiers land in entries 04 / 05 / 06 / 07 /
10.

## Gate integration

- VG-0: deterministic inventory hash emitted by the
  `--collect-only` command (caller-side check) is the entry's
  META evidence.
- VG-1: `test_closed_tier_vocabulary.py` passes with zero
  forbidden markers in math at completion SHA.
- VG-2: required-lane skip count is zero; baseline TOML
  documented.
- VG-3: `make test-tier-fast` green (deterministic unit +
  property + contract subset of math).
- VG-4…VG-8: `NOT_APPLICABLE` for this entry; rationale in META.

## Documentation and durable-record changes

- New: `math/tests/static/*.py`, `math/tests/static/skip_xfail_baseline.toml`.
- Amended: `math/pyproject.toml`, `math/Makefile`,
  `math/tests/README.md`,
  `research-institution/.specify/memory/transient-exemptions.toml`.
- No new durable ADR/INV/CTR/CON records (this entry does
  not change verify policy itself; entries 04 / 06 / 10 own those).

## Cross-repository compatibility

None. Math's local change; institution-wide behavior unchanged.

## Retirement / cleanup

- `transient-exemptions.toml` rows seeded by 01 expire on this
  entry's id; once forbidden-tier usage is fully migrated, the
  entry's META names the rows it retires.
- A `make test-tier-fast-cleanup` target (added by this entry)
  removes any orphan tier directory at completion SHA.
