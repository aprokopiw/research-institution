# 01 — Tasks

## Milestones

- **M1** — collection-without-coverage fix + static checks +
  baseline registry.
- **M2** — tier-routed Makefile targets + README rewrite.
- **M3** — bounded folder migrations (one commit per
  sub-system).
- **M4** — Makefile tier-routed cleanup target + audit-close-out.

## M1 — Collection + static checks + baseline

- [ ] **T1.1** — `math/pyproject.toml` patch: introduce
      `[tool.pytest.collect_only]` profile so
      `pytest --collect-only --no-cov -q` exits 0 at HEAD.
      **verify:** exit 0; deterministic inventory hash
      reproducible (run twice; compare hashes).
      **path:** `math/pyproject.toml`

- [ ] **T1.2** — write
      `math/tests/static/test_closed_tier_vocabulary.py`
      enforcing the §1 closed set and six forbidden strings.
      **verify:** `pytest -q tests/static/test_closed_tier_vocabulary.py`
      exits 0 (current math has zero violations by construction
      after entry 01's migration; pre-migration violations are
      tolerated via the registry until T3.x completes).
      **path:** `math/tests/static/test_closed_tier_vocabulary.py`

- [ ] **T1.3** — write
      `math/tests/static/test_dependency_vocabulary.py`
      enforcing the §2 closed set.
      **verify:** same shape as T1.2.
      **path:** `math/tests/static/test_dependency_vocabulary.py`

- [ ] **T1.4** — write
      `math/tests/static/test_skip_xfail_baseline.py` and the
      companion `tests/static/skip_xfail_baseline.toml`
      enumerating every existing skip / skipif / importorskip /
      xfail call site, classified as
      `required | optional_dependency | platform_not_applicable
      | stale`. The required count MUST be zero.
      **verify:** `pytest -q tests/static/test_skip_xfail_baseline.py`
      exits 0; baseline TOML is checked-in and parseable.
      **path:** `math/tests/static/{test_skip_xfail_baseline.py,
      skip_xfail_baseline.toml}`

- [ ] **T1.5** — append math rows to
      `research-institution/.specify/memory/transient-exemptions.toml`
      for every legacy exempt file under `tests/` directories
      that may still use a forbidden string during migration
      (one row per file with `expiry_spec_id =
      "01-test-suite-rationalization"`).
      **verify:** TOML parses; row count ≥ 1.
      **cross:** `research-institution/.specify/memory/transient-exemptions.toml`

- [ ] **T1.6** — first commit: T1.1–T1.5; verify
      `make check-prime-directive` exits 0; `pytest --collect-only --no-cov -q`
      exits 0; static-check trio exits 0.

**M1 exit:** collection green, static checks in place, baseline
TOML committed, exemptions registry appended.

## M2 — Tier-routed Makefile + README

- [ ] **T2.1** — amend `math/Makefile` adding eight tier-routed
      targets (per plan FR-5) + a `test-tier-fast` aggregate +
      a `test-tier-cleanup` target (per plan Retirement).
      **verify:** `make -n test-tier-fast` prints the chain;
      `make test-unit` exits 0; `make test-tier-fast` exits 0.
      **path:** `math/Makefile`

- [ ] **T2.2** — rewrite `math/tests/README.md` routing by
      subsystem + tier; remove tier-ambiguous language. New
      sections: "Subsystem layout", "Tier routing", "Adding a
      test".
      **verify:** the static check `test_closed_tier_vocabulary.py`
      references README.md by relative path and confirms no
      forbidden string appears in the routing examples.
      **path:** `math/tests/README.md`

- [ ] **T2.3** — second commit: T2.1–T2.2; verify
      `make check-prime-directive` and `make test-tier-fast`
      exit 0.

**M2 exit:** tier-routed test commands available to humans and
CI; README reflects them.

## M3 — Bounded folder migrations

Each task here moves files from one folder to an owner-subsystem
folder using `git mv`, and updates any imports / conftest paths /
docs references. Each task is independently reviewable.

- [ ] **T3.1** — move
      `tests/final_product_acceptance/*` → owner subsystem
      (preserved where the `src/mathlint/final_product_acceptance/`
      production package exists; otherwise tests are reclassified
      and absorbed).
      **verify:** collection count unchanged; tier coverage
      unchanged; `make test-tier-fast` green.
      **path:** `math/tests/final_product_acceptance/*`

- [ ] **T3.2** — move `tests/live_readiness/*` to owner
      subsystem; mark test cases `provider_live` or `deployment`
      as appropriate.
      **verify:** same shape as T3.1.
      **path:** `math/tests/live_readiness/*`

- [ ] **T3.3** — move `tests/e2e/*` cases to owner subsystem;
      mark `process` or `integration` as appropriate. None of
      these become part of math's fast tier automatically.
      **verify:** same shape.
      **path:** `math/tests/e2e/*`

- [ ] **T3.4** — move `tests/acceptance/*` non-provider cases to
      owner subsystem; mark provider cases `provider_live`;
      delete the directory when emptied.
      **verify:** same shape + directory empty.
      **path:** `math/tests/acceptance/*`

- [ ] **T3.5** — move `tests/chaos/*` deterministic cases to
      owner subsystem with `fault_profile` metadata; delete the
      directory when emptied.
      **verify:** same shape + directory empty.
      **path:** `math/tests/chaos/*`

- [ ] **T3.6** — delete empty `tests/smoke/` (if currently empty;
      otherwise migrate).
      **verify:** `test -d math/tests/smoke` exits non-zero.
      **path:** `math/tests/smoke/`

- [ ] **T3.7** — bounded batch commit per subsystem; verify
      `make check-prime-directive`, `make test-tier-fast`,
      `--collect-only --no-cov -q` all exit 0.

**M3 exit:** no ambiguous-tier directory retains tests; the §1
closed set is realized in math; the baseline registry's expiry
dates can fire.

## M4 — Cleanup + audit-close

- [ ] **T4.1** — run `make test-tier-cleanup`; verify it removes
      any empty subdirectories that survived M3 and reports a
      deterministic list of removals.
      **path:** `math/Makefile` (target body).

- [ ] **T4.2** — final commit locking the migrations + the
      cleanup target. Verify all twelve `cannot claim done when…`
      clauses hold; the strengthened grep is clean at math HEAD;
      the static-check trio is green.

- [ ] **T4.3** — emit META.md + attestation for entry 01 via the
      local attestation emitter (entry 09 will replace this with
      the canonical one).

**M4 exit:** META emitted, entry 01 closed, entry 04 unblocked.
