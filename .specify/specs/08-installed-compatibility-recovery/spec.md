# 08 — Installed Compatibility, Migration, and Disaster Recovery

> **Spec-Kit** artifact. Zero-padded `00–10`. This is `08`. Depends on
> `07`. Unblocks `10`.

## Identity

- **spec_id:** `08-installed-compatibility-recovery`
- **owner_repo:** `research-institution` (coordinator)
- **owner_repos:** `{research-institution, math, pi_monitor, kaplansky}`
- **status:** draft
- **depends_on:** `07-deployment-canary-soak`
- **unblocks:** `10-verification-release-closure`

## Primary actor

The release engineer / SRE who runs a wheel-install matrix and
disaster-recovery drill. Implicit audience: release closure
(entry 10) which consumes this entry's evidence.

## Problem statement

Today there is no:

- Wheel-install matrix across the four repos in a fresh
  environment.
- Supported Python-version matrix.
- Cross-repo current/oldest-supported compatibility lane.
- Editable-versus-installed equivalence assertion.
- Upgrade / interrupted-upgrade / rollback policy.
- Backup/restore to new path (resume without duplicate
  execution/report).
- Corruption / ENOSPC / permissions / torn-write / rename-failure
  exercise.
- Dependency / security / provenance scan.

## Independent user stories

1. As a **release engineer**, I run
   `python -m research_institution verify-simulation --tier
    compatibility-matrix` and see a typed report listing
   installed-package-version × supported-Python-version
   combinations (each `PASS | FAIL | BLOCKED | NOT_APPLICABLE`).
2. As a **release engineer**, I run
   `--tier rollback` and the harness proves that a wheel
   downgrade preserves readable state and refrains from
   redispatch.
3. As a **disaster-recovery officer**, I run
   `--tier backup-restore --src /tmp/state --dst /tmp/state-restored`
   and the harness proves resume without duplicate
   execution/report.

## Functional requirements

FR-1. **`research_institution/gates/verify_simulation/compat.py`**:

   - `CompatMatrixRunner` — builds a clean venv per (Python ×
     repo) cell; installs wheel + dev dep; runs the canonical
     simulation; produces typed report.
   - `EditableVsInstalledRunner` — runs the same scenario
     twice (editable; installed), asserts the typed envelopes
     are byte-equal.
   - `RollbackRunner` — installs at version N, runs scenario;
     downgrade to version N-1, runs scenario, asserts state is
     readable and no redispatch.
   - `BackupRestoreRunner` — copies state to a fresh location;
     resumes; asserts no duplicate exec / report.
   - `CorruptionRunner` — corrupts audit / state / ledger,
     asserts startup fails closed per documented behavior.
   - `DiskPressureRunner` — simulates ENOSPC, truncated write,
     permission denial, rename failure.

FR-2. **CLI** extended with `--tier compatibility-matrix |
   rollback | backup-restore | corruption | disk-pressure`.

FR-3. **Cross-repo compatibility matrix** (per master guide
"Cross-repository compatibility matrix"):

   | Producer | Consumer | Contract |
   |---|---|---|
   | math source | pi_monitor external source | wire |
   | pi_monitor outcome | math report handler | wire |
   | RI | math provider slot | wire |
   | RI | pi_monitor CLI / config | wire |
   | kaplansky | math program interfaces | wire |
   | RI catalog | kaplansky package | wire |

   Each cell is exercised by a typed test module that runs
   against a clean venv.

FR-4. **Supported Python-version matrix** ships a single
   `python_versions.toml` declaring supported minimum + current.

FR-5. **Wheel-install verification** proves every package's wheel
   installs cleanly and the entry-point discovery works
   without editable checkout.

FR-6. **Backup / restore** preserves readable state and
   resumes without duplicate execution or report.

FR-7. **Corruption recovery** is fail-closed: corrupt audit +
   corrupt state + corrupt ledger each individually tested;
   the documented recovery is asserted.

FR-8. **Resource-exhaustion tests** assert that ENOSPC,
   truncated write, permissions denied, and rename failure are
   detected and not silently masked.

FR-9. **Dependency / security / provenance scan** runs a
   reproducibly-buildable workflow; the lockfile + hashes match
   the canonical lockfile; build provenance is recorded.

## Explicit exclusions

- Real provider canary (entry 07).
- Mutation / release-closure (entry 10).
- Cross-version math source / pi_monitor wire tests beyond the
  pinned `v0.x` versions catalogued today.

## Measurable success criteria

- `--tier compatibility-matrix` exits 0 (or BLOCKED-on-missing-
  Python-version with that status honored).
- `--tier rollback` exits 0; state is readable post-rollback; no
  redispatch.
- `--tier backup-restore` exits 0; resume is single-pass.
- `--tier corruption` exits 0; fail-closed + documented
  recovery is asserted.
- `--tier disk-pressure` exits 0; resource-exhaustion is caught.
- `make check-prime-directive` exits 0 at HEAD.

## Failure and edge cases

- **F-1.** A clean venv build fails for a pinned Python
  version. The status is `BLOCKED`, not `FAIL`.
- **F-2.** Wheel install discovers a second
  `mathlint.providers` entry point. Collision detected; logged.
- **F-3.** Backup restores but resume creates a duplicate
  execution. Detected and asserted against documented contract.

## Dependencies on earlier entries

- **Entry 00–07** — full prerequisite.

## "Cannot claim done when…"

1. `--tier compatibility-matrix` exits non-zero with a non-
   `BLOCKED` status.
2. A supported Python version breaks the canonical simulation.
3. Wheel install collision goes undetected.
4. Editable-vs-installed envelope differs in any byte.
5. Rollback redispatches.
6. Backup-restore creates a duplicate execution or report.
7. Corruption is silently masked.
8. ENOSPC / truncated write / permission denial is detected only
   by a flaky side-effect path.
9. Dependency scan misses a known high-severity advisory.
10. `make check-prime-directive` exits non-zero.
11. Entry 00–07 cannot-claim-done clauses do NOT hold.
12. The cross-repo compatibility matrix is missing any cell.

## Non-goals

- Real-provider interactions (entry 07).
- Authoring mutation tests (entry 10).
- Authoring release gate (entry 10).

## Cross-references

- `.specify/memory/constitution-verify.md` §3, §5, §10, §11.
- `@CTR-0020` (three-repo wire contract).
- `@CTR-0088` (catalog schema).
