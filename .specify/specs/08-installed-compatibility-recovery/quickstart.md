# 08 — Quickstart

## Local verification commands

```sh
# 1. Compatibility matrix.
cd ~/Documents/andrei/research-institution
python -m research_institution verify-simulation \
    --tier compatibility-matrix
echo "exit=$?"   # 0 (or BLOCKED on missing Python)

# 2. Editable vs installed.
python -m research_institution verify-simulation \
    --tier editable-vs-installed
echo "exit=$?"   # 0

# 3. Rollback.
python -m research_institution verify-simulation \
    --tier rollback --from-version=current --to-version=prev
echo "exit=$?"   # 0

# 4. Backup-restore.
python -m research_institution verify-simulation \
    --tier backup-restore --src /tmp/state --dst /tmp/state-restored
echo "exit=$?"   # 0

# 5. Corruption.
python -m research_institution verify-simulation \
    --tier corruption --target=audit
echo "exit=$?"   # 0 (FAIL-CLOSED)

# 6. Disk pressure.
python -m research_institution verify-simulation \
    --tier disk-pressure --scenario=enospc
echo "exit=$?"   # 0 (detected)

# 7. Canonical prime-directive script.
make check-prime-directive
echo "exit=$?"   # 0
```

## Expected gate statuses

| Gate | Status |
|---|---|
| VG-0…VG-4 + VG-5 / VG-7 / VG-8 | `PASS` (via prior entries) |
| matrix per cell | `PASS` or `BLOCKED` (cleanly) |
| VG-6 | `NOT_APPLICABLE` (entry 10) |

## Artifact locations

```
research-institution/
  research_institution/gates/verify_simulation/compat/
    __init__.py
    matrix.py
    editable.py
    rollback.py
    backup.py
    corruption.py
    disk_pressure.py
  tests/simulation/test_compat_matrix.py
  python_versions.toml
```

## Cross-references

- `spec.md` cannot-claim-done list.
- Entry 10's release closure references the matrix output.
