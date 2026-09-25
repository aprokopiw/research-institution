# 07 — Quickstart

## Local verification commands

```sh
# 1. Deployment tier.
cd ~/Documents/andrei/research-institution
python -m research_institution verify-simulation --tier deployment
echo "exit=$?"   # 0

# 2. macOS deployment (opt-in; only on macOS).
python -m research_institution verify-simulation \
    --tier deployment --macos-isolated-label=simtest-$(uuidgen)
echo "exit=$?"   # 0 (or SKIP-with-not-applicable on Linux/Windows)

# 3. Provider canary (BLOCKED without credentials).
python -m research_institution verify-simulation \
    --tier provider-canary --live \
    --scenario rate-defer-restart
echo "exit=$?"   # 78 (BLOCKED) — unless real credentials configured

# 4. Soak smoke (60 s).
python -m research_institution verify-simulation \
    --tier soak --hours 0.0166   # 60 s; release path uses --hours 8
echo "exit=$?"   # 0 (or OVER_BUDGET)

# 5. Canonical prime-directive script.
make check-prime-directive
echo "exit=$?"   # 0
```

## Expected gate statuses

| Gate | Status |
|---|---|
| VG-0…VG-4 | `PASS` (via prior entries) |
| **VG-5** | **`PASS`** (deployment composition) |
| VG-6 | `NOT_APPLICABLE` (entry 10) |
| **VG-7** | `PASS` if canary `PASS`; `BLOCKED` if credentials absent (allowed at release only if explicitly rendered BLOCKED) |
| **VG-8** | `PASS` if soak duration met + bounded evidence signed |

## Artifact locations

```
research-institution/
  research_institution/gates/verify_simulation/
    deployment.py
    canary.py
    oracle/soak.py
    cli.py                          # extended
  tests/simulation/
    test_deployment_cross_cwd.py
    test_program_arguments_match.py
    test_macos_isolated_label.py
    test_canary_credentials_required.py
    test_canary_does_not_mutate_kaplansky.py
    test_soak_short.py
  scripts/verify-institution.sh     # extended
```

## Cross-references

- `spec.md` cannot-claim-done list.
- Entry 08's compatibility matrix consumes the deployment tier.
- Entry 10's release closure references canary + soak evidence.
