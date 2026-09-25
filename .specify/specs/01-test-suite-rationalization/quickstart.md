# 01 — Quickstart

## Local verification commands

```sh
# 1. Collection works without coverage interference.
cd ~/Documents/andrei/math
pytest --collect-only --no-cov -q
echo "exit=$?"   # 0

# 2. Static-check trio passes.
pytest -q tests/static/test_closed_tier_vocabulary.py \
       tests/static/test_dependency_vocabulary.py \
       tests/static/test_skip_xfail_baseline.py
echo "exit=$?"   # 0

# 3. Tier-routed run.
make test-tier-fast
echo "exit=$?"   # 0

# 4. Canonical prime-directive grep still passes.
make check-prime-directive
echo "exit=$?"   # 0

# 5. Cleanup target.
make test-tier-cleanup
echo "exit=$?"   # 0
```

## Expected gate statuses

At entry 01's completion SHA:

| Gate | Status | Why |
|---|---|---|
| VG-0 | `PASS` | collection deterministic + static checks green |
| VG-1 | `PASS` | closed-tier vocabulary enforced; zero violations |
| VG-2 | `PASS` | baseline registry has zero required skips |
| VG-3 | `PASS` | `make test-tier-fast` green (math-unit + math-property + math-contract subset) |
| VG-4…VG-8 | `NOT_APPLICABLE` | this entry ships no S2/S3/S4/S5 evidence |

## Artifact locations

```
math/
  pyproject.toml                            # amended
  Makefile                                  # amended
  tests/
    README.md                               # rewritten
    static/
      test_closed_tier_vocabulary.py
      test_dependency_vocabulary.py
      test_skip_xfail_baseline.py
      skip_xfail_baseline.toml              # baseline registry
    final_product_acceptance/ ...           # migrated
    e2e/ ...                                # migrated
    live_readiness/ ...                     # migrated
    acceptance/ ...                         # migrated
    chaos/ ...                              # migrated
    smoke/                                  # deleted

research-institution/
  .specify/
    memory/
      transient-exemptions.toml             # math rows added
    specs/
      01-test-suite-rationalization/
        spec.md plan.md tasks.md
        research.md data-model.md
        quickstart.md META.md
```

## Cleanup on failure

- A folder migration breaks `make test-tier-fast` → revert the
  per-batch commit; the static-check trio's row in META records
  the regression's first-class name.
- A skip is reclassified by tooling → the AST scan flags it as
  `stale`; the `TNNN` task that introduces the stale row also
  removes the underlying skip call.
