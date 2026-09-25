# 10 — Quickstart

## Local verification commands

```sh
# 1. Release tier (the closing command).
cd ~/Documents/andrei/research-institution
python -m research_institution verify-simulation --tier release
echo "exit=$?"   # 0

# 2. Claim manifest integrity.
pytest -q tests/static/test_claim_manifest_integrity.py
echo "exit=$?"   # 0

# 3. Documentation truth audit.
pytest -q tests/static/test_documentation_truth.py
echo "exit=$?"   # 0

# 4. Flake audit (20× repeated).
pytest -q tests/simulation/test_flake_audit.py
echo "exit=$?"   # 0

# 5. Random-order determinism.
pytest -q tests/static/test_random_order_determinism.py
echo "exit=$?"   # 0

# 6. Prime-directive enforcement across repos.
cd ../math            && make check-prime-directive-enforced && cd -
cd ../pi_monitor      && make check-prime-directive-enforced && cd -
cd ../kaplansky       && make check-prime-directive-enforced && cd -
echo "exit=$?"   # 0

# 7. Strict-grep clean.
make check-prime-directive
echo "exit=$?"   # 0

# 8. Confirm transient guide is tombstoned.
! test -f .agents/transient/test_and_simulation_suite.md
test -f .agents/transient/_retired/test_and_simulation_suite.retired.md
echo "exit=$?"   # 0
```

## Expected gate statuses

| Gate | Status |
|---|---|
| VG-0…VG-5 | `PASS` |
| **VG-6** | **`PASS`** (mutation + flake + documentation + claim-manifest) |
| VG-7 | `PASS` or `BLOCKED` (acceptable; explicit at release) |
| VG-8 | `PASS` or `BLOCKED` (acceptable; explicit at release) |

## Artifact locations

```
research-institution/
  research_institution/gates/verify_simulation/
    release.py
    mutation.py
    cli.py                       # +--tier release
  docs/semantic/
    CLAIM_MANIFEST.toml
    contracts/ctr-0101-release-gate-contract.md
    SEMANTIC_REGISTRY.md         # amended
  tests/
    static/
      test_claim_manifest_integrity.py
      test_documentation_truth.py
      test_random_order_determinism.py
    simulation/
      test_flake_audit.py

.agents/transient/_retired/
  test_and_simulation_suite.retired.md   # tombstone

~/.pi/agent/extensions/prime-directive-guard.ts  # block message updated
```

## Cross-references

- `spec.md` cannot-claim-done list.
- All eleven spec dirs (the program memory).
