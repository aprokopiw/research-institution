# 01 — Research

## Existing assets reused

- `math/pyproject.toml` `[tool.pytest.ini_options]` (the
  `addopts` enabling coverage is the collection-breaking
  artefact).
- `math/Makefile` (existing test + CI targets; extended).
- `math/tests/static/` directory precedent for static checks.
- `math/tests/README.md` (overhauled).
- `research-institution/.specify/memory/constitution-verify.md`
  §1, §2, §3, §5, §11, §12 (consumed).
- `research-institution/.specify/memory/transient-exemptions.toml`
  (initial rows from entry 00; math rows added here).
- `research-institution/scripts/check-prime-directive.sh`
  (canonical, runs at math HEAD per M0 prevention layer).

## Rejected parallel approaches (with reasons)

- **R1.** Add a separate `math-pyright` CI job. REJECTED:
  math's existing pyright pipeline is unchanged.
- **R2.** Convert math to `unittest discover` (matching pi_monitor).
  REJECTED: math already runs pytest; standardizing other way is
  a sister-spec concern (entry 02 / 03 territory).
- **R3.** Make `addopts = []` globally. REJECTED: may break
  legitimate coverage reports elsewhere; the entry confines its
  change to the `[tool.pytest.collect_only]` profile.

## Unresolved questions resolved before implementation

| Question | Resolution |
|---|---|
| Should the migration re-home files via `git mv` or copy + delete? | `git mv` (preserves history). |
| How granular are the migrations? | One subsystem per batch; per-batch commits; each batch green before the next. |
| Where does the baseline TOML go? | `math/tests/static/skip_xfail_baseline.toml` (co-located with the static check that reads it). |
| Should `tests/static/` already exist? | Yes (precedent: math's static checks for repo boundary). |

## Open risks

- **R-A.** A test was marked `unit` but actually launches a
  subprocess. Reclassifying to `process` exposes it to the S2
  budget; the test must be re-examined. Pre-emptively documented
  in F-3.
- **R-B.** Some folder moves invalidate `docs/concepts/` cross-
  references. The accompanying doc-update is bundled in each
  per-batch commit.

## Cross-references

- `research-institution/.agents/transient/test_and_simulation_suite.md`
  §7 (Pri-0 inventory).
- `math/AGENTS.md` institution-wide prevention section.
- `@ADR-0014` (mathlint does not import program-named modules).
- `@INV-0088` (sample fixture requires no external state).
