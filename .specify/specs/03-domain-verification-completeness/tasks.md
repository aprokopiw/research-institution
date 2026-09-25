# 03 — Tasks

## Milestones

- **M1** — collection-without-coverage fix + static checks.
- **M2** — domain / work-selection / artifacts tests.
- **M3** — plugin / launcher / security tests.
- **M4** — folder migration + audit-close.

## M1 — Collection + static checks

- [ ] **T1.1** — `kaplansky/pyproject.toml` patch: pytest config
      profile so plain collection exits 0 without coverage
      interference. **verify:** `pytest --collect-only --no-cov -q`
      exits 0; deterministic inventory hash.
      **path:** `kaplansky/pyproject.toml`

- [ ] **T1.2** — write the three static checks (closed-tier
      vocabulary, dependency vocabulary, skip/xfail baseline +
      TOML registry). **verify:** per-module `pytest -q` exits 0.
      **path:** `kaplansky/tests/static/`

- [ ] **T1.3** — first commit; verify `make check-prime-directive`
      exits 0 at kaplansky HEAD.

**M1 exit:** collection green, static checks in place.

## M2 — Domain / work-selection / artifacts

- [ ] **T2.1** — write
      `tests/domain/test_roadmap_schema_roundtrip.py` — round-trips
      every `programs/*.toml`; mutated files rejected.
      **verify:** `pytest -q tests/domain/test_roadmap_schema_roundtrip.py`
      exits 0.
      **path:** `kaplansky/tests/domain/test_roadmap_schema_roundtrip.py`

- [ ] **T2.2** — write
      `tests/domain/test_frozen_claims.py`,
      `test_palomar_provenance.py`,
      `test_modules.py`,
      `test_compute_registry.py`.
      **verify:** per-file `pytest -q` exits 0.
      **path:** `kaplansky/tests/domain/`

- [ ] **T2.3** — write
      `tests/work_selection/test_dependency_valid_operation.py`,
      `test_blocked_completion.py`,
      `test_stale_outcomes.py`.
      **verify:** per-file `pytest -q` exits 0.
      **path:** `kaplansky/tests/work_selection/`

- [ ] **T2.4** — write
      `tests/artifacts/test_artifact_integrity.py`.
      **verify:** `pytest -q` exits 0.
      **path:** `kaplansky/tests/artifacts/`

- [ ] **T2.5** — second commit; verify all twelve above exit 0.

**M2 exit:** domain + work-selection + artifacts tests all green.

## M3 — Plugin / launcher / security

- [ ] **T3.1** — write
      `tests/plugin/test_mathlint_provider.py`,
      `test_entry_point_collision.py`.
      **verify:** per-file `pytest -q` exits 0.
      **path:** `kaplansky/tests/plugin/`

- [ ] **T3.2** — write
      `tests/launcher/test_institution_check.py` — subprocess;
      four cwds; deterministic verdict.
      **verify:** `pytest -q tests/launcher/` exits 0.
      **path:** `kaplansky/tests/launcher/`

- [ ] **T3.3** — write
      `tests/security/test_no_kaplansky_literal_in_siblings.py` —
      cross-repo structural negative; today the negative is
      green and stays green.
      **verify:** `pytest -q tests/security/` exits 0.
      **path:** `kaplansky/tests/security/`

- [ ] **T3.4** — wire `kaplansky/scripts/check-prime-directive.sh`
      as a symlink (or byte-diff copy) of the canonical
      research-institution script. **verify:** diff exits 0;
      `make check-prime-directive` exits 0 at kaplansky HEAD.
      **cross:** `kaplansky/scripts/check-prime-directive.sh`

- [ ] **T3.5** — third commit; verify all checks above green.

**M3 exit:** plugin, launcher, security tests + symlink in place.

## M4 — Folder migration + audit-close

- [ ] **T4.1** — append
      `transient-exemptions.toml` kaplansky rows with
      `expiry_spec_id = "03-domain-verification-completeness"`.
      **verify:** TOML parses.
      **cross:** `research-institution/.specify/memory/transient-exemptions.toml`

- [ ] **T4.2** — folder migration: move flat tests at kaplansky
      repo root to subsystem directories; delete empty reserved
      dirs.
      **verify:** `find kaplansky/tests/` matches the new tree;
      no orphan ambiguous-tier dirs.
      **path:** `kaplansky/tests/`

- [ ] **T4.3** — amend `kaplansky/tests/README.md` per plan
      FR-4. **verify:** `test_closed_tier_vocabulary.py` confirms
      README contains no forbidden primary-tier strings.
      **path:** `kaplansky/tests/README.md`

- [ ] **T4.4** — `kaplansky/Makefile` amendment per FR-3.
      **verify:** `make test-tier-fast` exits 0; `make test-tier-cleanup`
      empty run produces no removals.
      **path:** `kaplansky/Makefile`

- [ ] **T4.5** — `kaplansky/AGENTS.md` cross-ref amendment (no
      other prose). **verify:** `make check-prime-directive` exits 0.
      **cross:** `kaplansky/AGENTS.md`

- [ ] **T4.6** — fourth commit + final verification:
      - `pytest --collect-only --no-cov -q` exits 0;
      - static-check trio exits 0;
      - ten domain / work-selection modules exit 0;
      - `make test-tier-fast` exits 0;
      - `make check-prime-directive` exits 0;
      - all twelve entry 00 cannot-claim-done clauses hold at
        kaplansky HEAD.

- [ ] **T4.7** — emit META.md + attestation.

**M4 exit:** META emitted; entry 03 closed; entry 10 unblocked.
