# 08 — Plan

## Technical context

Entry 08 closes the wheel-install + cross-repo matrix + disaster
recovery loop. The coordinator is research-institution; commits
land in each repo as needed; CI proves the matrix.

## Existing implementation to extend

- `research_institution/gates/verify_simulation/compat.py` —
  new package surface.
- `research-institution/scripts/verify-institution.sh` —
  extended to invoke `--tier compatibility-matrix` in nightly
  cron.
- `research-institution/pyproject.toml` `[dependency-groups]`
  pins (per `RI/pyproject.toml`).
- `math/pyproject.toml` `[tool.hatch.metadata]`.
- `pi_monitor/pyproject.toml`.
- `kaplansky/pyproject.toml`.

## Components changed

| Path | Change |
|---|---|
| `research_institution/gates/verify_simulation/compat.py` | new. |
| `research_institution/gates/verify_simulation/compat/{matrix,editable,rollback,backup,corruption,disk_pressure}.py` | new. |
| `research_institution/gates/verify_simulation/cli.py` | extended with five `--tier` flags. |
| `python_versions.toml` (research-institution new) | supported Python matrix. |
| `research-institution/tests/simulation/test_compat_matrix.py` | new. |

## Components explicitly NOT changed

- Sibling package source code.
- Catalog schema.
- Sample program (entry 04 unchanged).

## Repository ownership boundary

```
research-institution   (compat package; CLI; nightly cron driver)
math                   (receives compatibility matrix probes)
pi_monitor             (receives compatibility matrix probes)
kaplansky              (receives compatibility matrix probes)
```

## Constitution Check

- **§3, §4 (VG-5), §5, §10, §11** — verified.

## Data and state migration

None for the institution; each package's own lockfile pins are
unchanged at the entry's level — the entry only adds probes.

## Failure atomicity and rollback

Per-mutation; per-tester; per-vendor-clean-venv.

## Security / credential impact

- `--tier rollback` proves that an installed wheel downgrade
  cannot accidentally leak the older wheel's credentials.
- `--tier backup-restore` preserves credential fingerprints;
  no transmitted secrets.

## Performance / runtime budgets

- `--tier compatibility-matrix` ≤ 30 min (multiple venvs).
- `--tier rollback` ≤ 5 min.
- `--tier backup-restore` ≤ 5 min.
- `--tier corruption` ≤ 1 min.
- `--tier disk-pressure` ≤ 1 min.

## Test / evidence tier map (entry 08)

Each matrix cell is a real subprocess; each is `deployment`-tier
evidence.

## Gate integration

- VG-0…VG-5 + VG-7/VG-8: pass via prior entries.
- VG-6: `NOT_APPLICABLE` (entry 10).
- The matrix contributes additional `deployment`-tier
  coverage to nightly.

## Documentation and durable-record changes

- New: compat package + tests.
- Amended: cli.py.
- New durable records: none.

## Cross-repository compatibility

The matrix is the canonical answer; per-cell tests exercise
the producer-consumer pairs.

## Retirement / cleanup

None.
