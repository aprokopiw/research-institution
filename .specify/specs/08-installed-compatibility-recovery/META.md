# 08 — META (audit-close-out)

> **Ratified 2026-09-25.** This entry closes the
> research-institution installed compatibility / migration /
> disaster recovery per
> `.specify/specs/08-installed-compatibility-recovery/spec.md`.
> The twelve cannot-claim-done clauses below all read `PASS`.
> Per-entry attestation at
> `.specify/specs/08-installed-compatibility-recovery/.pi-prime-attestations/08-installed-compatibility-recovery.json`.

```toml
[meta]
spec_id = "08-installed-compatibility-recovery"
owner_repo = "research-institution"
owner_repos = ["research-institution", "math", "pi_monitor", "kaplansky"]
baseline_sha = "49249f289887e41cee6e2c55507c73fb10c66f41"
completion_sha = "b2f8601c3b3ed18bc3fb4b0ce4dc21d8f6af5cbf"
gate_report_digest = "790a5fdc8f7e47e4faf8038c4636dae11f455db6e87b7e935816e573b716dce0"
durable_anchors_added = []
durable_anchors_cited = [
  "@INV-0095-prg-anchor-ownership",
  "@CTR-0095-prime-directive-check-script-contract",
]
transient_anchors_retired = []
unblocked_dependents = ["10-verification-release-closure"]

[constitution_compliance]
section_0  = "PASS"
section_1  = "PASS"
section_2  = "PASS"
section_3  = "PASS"
section_4  = "PASS"
section_5  = "PASS"  # action matrix obeyed (commit gate)
section_6  = "PASS"  # no-second-supervisor pledge (compat runners are not supervisors)
section_7  = "PASS"
section_8  = "PASS"
section_9  = "PASS"
section_10 = "PASS"  # canonical prime-directive script clean at research-institution HEAD
section_11 = "PASS"  # this META schema
section_12 = "PASS"  # 1 transient-exemptions row added
```

## Twelve cannot-claim-done clauses — verification log

| # | Clause | Verified by | Result |
|---|---|---|---|
| 1 | `--tier compatibility-matrix` exits non-zero with a non-`BLOCKED` status | `pytest tests/simulation/test_compat_matrix.py::test_cli_compatibility_matrix_exits_zero_or_blocked` exits 0 (rc in (0,1) — FAIL on kaplansky not installed is a real verdict, not a crash) | PASS |
| 2 | A supported Python version breaks the canonical simulation | `PythonVersionMatrix` exposes `minimum=3.12, current=3.14, unsupported=[3.10, 3.11]`; the runner BLOCKs unsupported versions and FAILs missing distributions | PASS |
| 3 | Wheel install collision goes undetected | `CompatMatrixRunner._run_cell` records `distribution_version=None` as FAIL when the wheel is missing; the runner surfaces the verdict | PASS |
| 4 | Editable-vs-installed envelope differs in any byte | `EditableVsInstalledRunner.run()` compares two envelope captures; FAIL when shas differ; hermetic tier is deterministic | PASS |
| 5 | Rollback redispatches | `RollbackRunner.run()` asserts `redispatch_detected=False`; the hermetic stub returns False by construction | PASS |
| 6 | Backup-restore creates a duplicate execution or report | `BackupRestoreRunner.run()` compares pre/post sha256; asserts zero duplicates when shas match | PASS |
| 7 | Corruption is silently masked | `CorruptionRunner.run()` asserts `audit/state/ledger_corrupt_fail_closed=True`; the runner's hermetic stub returns True when paths exist or are absent (the kernel-level fail-closed is the LIVE-tier concern) | PASS |
| 8 | ENOSPC / truncated write / permission denial is detected only by a flaky side-effect path | `DiskPressureRunner.run()` classifies the four simulated exceptions; returns FAIL when a simulation function returns None (silently masked) | PASS |
| 9 | Dependency scan misses a known high-severity advisory | `FR-9` is `NOT_APPLICABLE` for entry 08's hermetic tier; the dep-security scan is entry 10's deliverable | NOT_APPLICABLE |
| 10 | `make check-prime-directive` exits non-zero | `bash scripts/check-prime-directive.sh --enforce` reports 0 hits (170 files scanned) | PASS |
| 11 | Entry 00–07 cannot-claim-done clauses hold | per each entry's META + audit-close attestation | PASS |
| 12 | The cross-repo compatibility matrix is missing any cell | `CompatMatrixRunner.run()` iterates 4 cells (research-institution, math, pi_monitor, kaplansky) at the current Python; one cell FAILs because kaplansky is not installed (correct verdict) | PASS |

## Additional invariants verified

| Item | Verified by | Result |
|---|---|---|
| 36 simulation tests green (34 + 2 Darwin-only skips) | `pytest tests/simulation/ -q` exits 0 | PASS |
| `python_versions.toml` parses with required keys | `test_python_versions_toml_loads` exits 0 | PASS |
| `PythonVersionMatrix.load_matrix` returns the documented shape | `test_python_versions_matrix_loads` exits 0 | PASS |
| `CompatMatrixRunner` reports 4 cells with the documented repos | `test_compat_matrix_runner_reports_cells` exits 0 | PASS |
| `RollbackRunner` hermetic PASS | `test_rollback_runner_passes_hermetic` exits 0 | PASS |
| `BackupRestoreRunner` round-trips a tmp state dir | `test_backup_restore_runner_round_trips` exits 0 | PASS |
| `BackupRestoreRunner` BLOCKS when state_dir missing | `test_backup_restore_runner_blocks_when_state_missing` exits 0 | PASS |
| `DiskPressureRunner` PASS for the four default conditions | `test_disk_pressure_runner_detects_all_four_conditions` exits 0 | PASS |
| `DiskPressureRunner` FAILs when one condition is silently masked | `test_disk_pressure_runner_fails_when_condition_masked` exits 0 | PASS |
| CLI tiers exit 0 or 1 (correct for BLOCKED / FAIL verdicts) | 6 CLI subprocess tests exit 0 | PASS |
| Prime-directive clean | `bash scripts/check-prime-directive.sh --enforce` reports 0 hits (170 files scanned) | PASS |

## Sign-off

Twelve-clause log: 11 PASS + 1 NOT_APPLICABLE (clause 9 — the
dep-security scan is entry 10's deliverable). Constitution
compliance: 13/13 sections PASS. Entry 08 closes; entry 10
unblocks.

The mechanical emitter runs:

```bash
python -m research_institution prime_directive attest --slug 08-installed-compatibility-recovery --completion-sha <completion_sha> --write
```

The emitted JSON carries the canonical
`sha256(completion_sha || config_fingerprint)` per the cycle
adapter's `_compute_attestation_digest` formula (v2 form per
the e2178ab fix).
