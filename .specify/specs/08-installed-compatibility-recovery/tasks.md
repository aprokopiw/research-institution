# 08 — Tasks

## Milestones

- **M1** — compat package + Python-version matrix.
- **M2** — wheel-install + editable-vs-installed proofs.
- **M3** — rollback + backup-restore proofs.
- **M4** — corruption + disk-pressure proofs.
- **M5** — audit-close.

## M1 — Compat package + matrix

- [ ] **T1.1** — write
      `research_institution/gates/verify_simulation/compat/`
      skeleton (`__init__.py`, `matrix.py`,
      `editable.py`, `rollback.py`, `backup.py`,
      `corruption.py`, `disk_pressure.py`).
      **verify:** `python -c "from research_institution.gates.verify_simulation.compat import matrix"` exits 0.
      **path:** `research-institution/research_institution/gates/verify_simulation/compat/`

- [ ] **T1.2** — write
      `python_versions.toml` declaring supported minimum +
      current Python versions.
      **verify:** TOML parses.
      **path:** `research-institution/python_versions.toml`

- [ ] **T1.3** — extend `cli.py` with five `--tier` flags.
      **verify:** `--help` exits 0 with all five flags.
      **path:** `research-institution/research_institution/gates/verify_simulation/cli.py`

- [ ] **T1.4** — first commit.

**M1 exit:** compat package + matrix declared.

## M2 — Wheel-install + editable-vs-installed

- [ ] **T2.1** — write `CompatMatrixRunner`.
      **verify:** unit test asserts typed report; matrix
      failures are `FAIL`, missing Python is `BLOCKED`.
      **path:** as in T1.1.

- [ ] **T2.2** — write `EditableVsInstalledRunner`.
      **verify:** unit test green.
      **path:** as in T1.1.

- [ ] **T2.3** — write `tests/simulation/test_compat_matrix.py`
      exercising the four-repos × current-Python cell.
      **verify:** `pytest -q tests/simulation/test_compat_matrix.py`
      exits 0.
      **path:** `research-institution/tests/simulation/test_compat_matrix.py`

- [ ] **T2.4** — second commit.

**M2 exit:** matrix + editable-vs-installed green.

## M3 — Rollback + backup-restore

- [ ] **T3.1** — write `RollbackRunner`.
      **verify:** unit test green; rollback does not redispatch.
      **path:** as in T1.1.

- [ ] **T3.2** — write `BackupRestoreRunner`.
      **verify:** unit test green; resume is single-pass.
      **path:** as in T1.1.

- [ ] **T3.3** — third commit.

**M3 exit:** rollback + backup-restore green.

## M4 — Corruption + disk-pressure

- [ ] **T4.1** — write `CorruptionRunner` (corrupt audit +
      state + ledger individually).
      **verify:** unit test green; fail-closed + documented
      recovery asserted.
      **path:** as in T1.1.

- [ ] **T4.2** — write `DiskPressureRunner` (ENOSPC,
      truncated write, permission denial, rename failure).
      **verify:** unit test green.
      **path:** as in T1.1.

- [ ] **T4.3** — fourth commit.

**M4 exit:** corruption + disk-pressure green.

## M5 — Audit-close

- [ ] **T5.1** — append
      `transient-exemptions.toml` rows for the new
      `tests/simulation/` paths.
      **verify:** TOML parses.
      **cross:** `research-institution/.specify/memory/transient-exemptions.toml`

- [ ] **T5.2** — fifth commit; verify all twelve
      cannot-claim-done clauses hold; the strengthened grep is
      clean at HEAD.

- [ ] **T5.3** — emit META.md + attestation.

**M5 exit:** META emitted; entry 08 closed; entry 10 unblocked.
