# 09 — Tasks

## Milestones

- **M1** — `prime_directive` package skeleton.
- **M2** — attest + validate + meta_validator.
- **M3** — `--enforce` mode in canonical script + per-repo
  Makefile targets.
- **M4** — runtime extension upgrade + per-repo durable
  records + audit-close.

## M1 — Package skeleton

- [ ] **T1.1** — create
      `research-institution/research_institution/prime_directive/`
      with `__init__.py`, `attest.py`, `validate.py`,
      `meta_validator.py`, `extension_bridge.py`.
      **verify:** `python -c "from research_institution.prime_directive import attest"` exits 0.
      **path:** `research-institution/research_institution/prime_directive/`

- [ ] **T1.2** — first commit.

**M1 exit:** package skeleton in place.

## M2 — Attest / validate / meta_validator

- [ ] **T2.1** — implement `attest(spec_id, *, completion_sha) -> Attestation`
      producing
      `.pi-prime-attestations/<spec_id>.json` with the
      canonical sha256 over `completion_sha || config_fingerprint`.
      **verify:** unit test asserts the sha256 re-computes
      correctly.
      **path:** as in T1.1.

- [ ] **T2.2** — implement `validate_attestation(path, *,
      current_sha, current_fp) -> Result`.
      **verify:** unit test asserts stale SHA rejected.
      **path:** as in T1.1.

- [ ] **T2.3** — implement
      `META_validator(path) -> Result` checking the §11.2
      schema. Write `research-institution/scripts/META_validator.py`
      CLI.
      **verify:** `python -m research_institution spec_audit_close
      META_validate .specify/specs/00-…/META.md` returns
      `PASS` (template schema is valid).
      **path:** `research-institution/scripts/META_validator.py`,
      `research-institution/research_institution/prime_directive/meta_validator.py`.

- [ ] **T2.4** — second commit.

**M2 exit:** attestation + validation machine-checked.

## M3 — `--enforce` + per-repo Makefile

- [ ] **T3.1** — extend
      `research-institution/scripts/check-prime-directive.sh`
      with `--enforce` mode.
      **verify:** `--enforce --selftest` exits 0; `--enforce`
      consumes the attestations and emits `BLOCKED` for stale
      references.
      **path:** `research-institution/scripts/check-prime-directive.sh`

- [ ] **T3.2** — add
      `check-prime-directive-enforced` target to
      `research-institution/Makefile` (finalize from entry 00
      scaffold).
      **verify:** `make check-prime-directive-enforced` exits 0
      in research-institution.
      **path:** `research-institution/Makefile`

- [ ] **T3.3** — add `check-prime-directive-enforced` to
      `math/Makefile`, `pi_monitor/Makefile`, `kaplansky/Makefile`.
      **verify:** each `make check-prime-directive-enforced`
      exits 0 in its repo.
      **path:** each sibling's `Makefile`.

- [ ] **T3.4** — third commit.

**M3 exit:** `--enforce` mode + per-repo target live.

## M4 — Runtime extension + per-repo ADRs + audit-close

- [ ] **T4.1** — update
      `~/.pi/agent/extensions/prime-directive-guard.ts` to
      consume `transient-exemptions.toml` (via
      `prime_directive.extension_bridge.render_sanctioned_globs`).
      **verify:** a manual smoke write of a forbidden literal in
      an unsanctioned path is blocked; the block message cites
      the canonical registry.
      **path:** `~/.pi/agent/extensions/prime-directive-guard.ts`

- [ ] **T4.2** — write per-repo durable records:
      - `math/docs/semantic/adr/adr-NNNN-prime-directive-enforcement.md`
      - `pi_monitor/docs/adr/adr-NNNN-prime-directive-enforcement.md`
      - `kaplansky/docs/.../adr-NNNN-prime-directive-enforcement.md`
      **verify:** each file exists; each cites entry 00's three
      durable records; no ID collision across repos.
      **path:** each sibling's docs.

- [ ] **T4.3** — emit the entry 09 attestation and verify it
      re-validates. **verify:** `validate_attestation(...)` returns
      `PASS` for the freshly emitted attestation at HEAD.

- [ ] **T4.4** — fourth commit (T4.1–T4.3); verify all twelve
      cannot-claim-done clauses hold; the strengthened grep is
      clean at HEAD across the four repos.

- [ ] **T4.5** — emit META.md + attestation.

**M4 exit:** META emitted; entry 09 closed; entry 10 unblocked.
