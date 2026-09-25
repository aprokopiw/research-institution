# 03 — Quickstart

## Local verification commands

```sh
# 1. Collection works.
cd ~/Documents/andrei/kaplansky
pytest --collect-only --no-cov -q
echo "exit=$?"   # 0

# 2. Static checks.
pytest -q tests/static/test_closed_tier_vocabulary.py \
       tests/static/test_dependency_vocabulary.py \
       tests/static/test_skip_xfail_baseline.py
echo "exit=$?"   # 0

# 3. Domain / work-selection / artifacts / plugin / launcher /
#    security tests.
pytest -q tests/domain/ tests/work_selection/ tests/artifacts/ \
          tests/plugin/ tests/launcher/ tests/security/
echo "exit=$?"   # 0

# 4. Tier-routed fast suite.
make test-tier-fast
echo "exit=$?"   # 0

# 5. Prime-directive grep.
make check-prime-directive
echo "exit=$?"   # 0
```

## Expected gate statuses

| Gate | Status |
|---|---|
| VG-0 | `PASS` |
| VG-1 | `PASS` |
| VG-2 | `PASS` |
| VG-3 | `PASS` |
| VG-4…VG-8 | `NOT_APPLICABLE` |

## Artifact locations

```
kaplansky/
  pyproject.toml                               # amended
  Makefile                                     # amended
  AGENTS.md                                    # cross-ref amended
  tests/
    README.md
    static/                                    # 3 static checks + TOML
    domain/                                    # 5 modules
    work_selection/                            # 3 modules
    artifacts/                                 # 1 module
    plugin/                                    # 2 modules
    launcher/                                  # 1 module
    security/                                  # 1 module
    _support/toml_roundtrip.py                 # helper
  scripts/check-prime-directive.sh             # symlink

research-institution/
  .specify/
    memory/transient-exemptions.toml           # kaplansky rows added
    specs/03-domain-verification-completeness/ # this entry
```

## Cross-references

- `spec.md` cannot-claim-done list.
- Entry 04's stateful sample program consumes the roadmpa schema
  validated by entry 03.
