# 00 — Tasks

## Task order discipline

Each task has:

- a `path:` field (relative to the entry's owner repo, or `cross:`
  for cross-repo work);
- a `verify:` field (the command proving completion);
- a milestone tag (`M1…M5`) marking which milestone it belongs to.

A task is `[x]` only after its `verify:` command passes. The audit-
close-out at the end of the task list is a separate M5 task that
emits META.md via the attestation invocation.

## Milestones

- **M1 — canonical text and durable records** (single-file additions
  + registry amendment; no production code touched).
- **M2 — canonical script and identity assertion**.
- **M3 — sibling-repo wiring** (one commit per repo).
- **M4 — static checks**.
- **M5 — audit-close-out and attestation**.

A milestone is closed only when all tasks in it are green and the
milestone-level gate runs `PASS`.

---

## M1 — Canonical text and durable records

- [ ] **T1.1** — write `research-institution/.specify/memory/constitution-verify.md`
      per plan §FR-1; verify: `wc -l` reports ≥ 100 lines and the file
      contains the section markers `## §0` … `## §12`, plus `## Governance`,
      plus a `**Version:**` line.
      **path:** `research-institution/.specify/memory/constitution-verify.md`

- [ ] **T1.2** — write
      `research-institution/.specify/memory/transient-exemptions.toml`
      per plan §FR-2; verify: `python -c 'import tomllib; tomllib.loads(open(p).read())'`
      exits 0; the file contains `version = "0.0.0"` and at least
      three rows in `[[exemption]]` (one per repo's
      `AGENTS.md`-section carve-out, one for the math §22 kaplansky
      grandfather list).
      **path:** `research-institution/.specify/memory/transient-exemptions.toml`

- [ ] **T1.3** — write
      `research-institution/docs/semantic/adr/adr-0095-prime-directive-mechanical-enforcement.md`
      ; verify: file begins with the standard ADR header
      (`# ADR-NNNN — Title`), body cites constitution §10; SHA of file
      hashed.
      **path:** `research-institution/docs/semantic/adr/adr-0095-prime-directive-mechanical-enforcement.md`

- [ ] **T1.4** — write
      `research-institution/docs/semantic/invariants/inv-0095-prg-anchor-ownership.md`
      ; verify: standard INV header; body cites constitution §12;
      SHA of file hashed.
      **path:** `research-institution/docs/semantic/invariants/inv-0095-prg-anchor-ownership.md`

- [ ] **T1.5** — write
      `research-institution/docs/semantic/contracts/ctr-0095-prime-directive-check-script-contract.md`
      ; verify: standard CTR header; pins the strengthened regex
      `(\b[Pp][Ll][Aa][Nn]|\b[Ss][Pp][Ee][Cc])[-_ ]?[0-9]{2,}`;
      SHA of file hashed.
      **path:** `research-institution/docs/semantic/contracts/ctr-0095-prime-directive-check-script-contract.md`

- [ ] **T1.6** — amend `research-institution/docs/semantic/SEMANTIC_REGISTRY.md`
      adding three rows (one per anchor above) and one cross-reference
      to `constitution-verify.md`; verify: grep on the file finds
      `@ADR-0095-prime-directive-mechanical-enforcement`,
      `@INV-0095-prg-anchor-ownership`,
      `@CTR-0095-prime-directive-check-script-contract` in
      `Research-institution anchors` section.
      **path:** `research-institution/docs/semantic/SEMANTIC_REGISTRY.md`

- [ ] **T1.7** — first-stage commit: commit T1.1–T1.6 only; verify:
      `git -C research-institution status` is clean;
      `git -C research-institution log -1 --format=%s` references
      the entry; `make check-prime-directive` still exits 0.

**M1 exit**: all tasks complete; `make check-prime-directive` exits
0 at the post-T1.7 SHA.

---

## M2 — Canonical script and identity assertion

- [ ] **T2.1** — modify
      `research-institution/scripts/check-prime-directive.sh` to
      accept `--selftest`; emit on stdout a deterministic
      multi-line self-test report (canonical phrase: "self-test
      ok: canonical grep present, sanctioned-globs recognised:
      <list>") and exit 0. Verify:
      `bash research-institution/scripts/check-prime-directive.sh --selftest | tee /tmp/selftest.txt && grep -q 'self-test ok' /tmp/selftest.txt` passes.
      **path:** `research-institution/scripts/check-prime-directive.sh`

- [ ] **T2.2** — scaffold
      `research-institution/scripts/check-prime-directive-enforced.sh`
      (returning `NOT_RUN` for now with a message naming entry 09
      as the finisher); verify: `bash … --selftest || [ $? -eq
      2 ]` semantics honour the `NOT_RUN` status code convention
      to be ratified in entry 09 (this task only needs the script
      to exist and emit a deterministic message).
      **path:** `research-institution/scripts/check-prime-directive-enforced.sh`

- [ ] **T2.3** — second-stage commit: commit T2.1–T2.2; verify:
      `make check-prime-directive` exits 0; the new selftest mode
      is reachable; SHA logged.

**M2 exit**: T2.3 commit hashes referenced; `make check-prime-directive`
exits 0 at the post-T2.3 SHA.

---

## M3 — Sibling-repo wiring

- [ ] **T3.1** — create or update
      `math/scripts/check-prime-directive.sh` to be a symlink (or
      byte-diff-equivalent copy) of the canonical script; verify:
      `diff math/scripts/check-prime-directive.sh research-institution/scripts/check-prime-directive.sh`
      exits 0; `cd math && make check-prime-directive` exits 0.
      **cross:** `math/scripts/check-prime-directive.sh`
      ← `research-institution/scripts/check-prime-directive.sh`

- [ ] **T3.2** — amend `math/AGENTS.md` institution-wide prevention
      block cross-reference to point at the new
      `research-institution/.specify/memory/transient-exemptions.toml`
      and `constitution-verify.md` (no other prose change); verify:
      `make check-prime-directive` exits 0 in `math` against the
      amended file.
      **cross:** `math/AGENTS.md`

- [ ] **T3.3** — same as T3.1 for `pi_monitor`; verify diff + gate.
      **cross:** `pi_monitor/scripts/check-prime-directive.sh`

- [ ] **T3.4** — same as T3.2 for `pi_monitor`; verify gate.
      **cross:** `pi_monitor/AGENTS.md`

- [ ] **T3.5** — same as T3.1 for `kaplansky`; verify diff + gate.
      **cross:** `kaplansky/scripts/check-prime-directive.sh`

- [ ] **T3.6** — same as T3.2 for `kaplansky`; verify gate.
      **cross:** `kaplansky/AGENTS.md`

- [ ] **T3.7** — third-stage commit (one commit per cross-repo
      pairings above, with the research-institution repo recording
      the cross-ref SHA in this entry's `META.md` later); verify
      each repo's `make check-prime-directive` exits 0 at its HEAD.

**M3 exit**: four siblings each have a working script + AGENTS.md
cross-ref; the strengthened grep still passes everywhere.

---

## M4 — Static checks

- [ ] **T4.1** — write
      `research-institution/tests/static/test_constitution_consistency.py`
      implementing the four assertions in plan §FR-4; verify:
      `pytest -q tests/static/test_constitution_consistency.py` exits 0.
      **path:** `research-institution/tests/static/test_constitution_consistency.py`

- [ ] **T4.2** — write
      `research-institution/tests/static/test_canonical_script_identity.py`
      per plan §FR-5; verify:
      `pytest -q tests/static/test_canonical_script_identity.py`
      exits 0; output reports the four repo exit codes are equal.
      **path:** `research-institution/tests/static/test_canonical_script_identity.py`

- [ ] **T4.3** — initial commit
      `research-institution/tests/static/test_closed_tier_vocabulary.py`
      with no-op test bodies (validates the static check is
      WIRING in place); the actual tier-marker migration lands in
      entries 01/02/03. Verify: `pytest -q tests/static/test_closed_tier_vocabulary.py`
      exits 0 (no current violations → green).
      **path:** `research-institution/tests/static/test_closed_tier_vocabulary.py`

- [ ] **T4.4** — fourth-stage commit (T4.1–T4.3); verify:
      `pytest -q tests/static/` exits 0 at the post-commit SHA.

**M4 exit**: all four static checks live, exit 0 at the post-T4.4
SHA, and are wired into `make test`.

---

## M5 — Audit-close-out and attestation

- [ ] **T5.1** — emit META.md (this directory) populated per the
      §11.2 schema with the actual SHAs from T1.7 / T2.3 / T3.7 /
      T4.4 and the three new durable records; verify: the file
      parses as TOML-frontmatter + Markdown body; the schema
      fields are present and non-empty where required.

- [ ] **T5.2** — emit the attestation artifact:
      `python -m research_institution prime_directive attest 00-verify-constitution-ratification`
      ; verify:
      `cat .pi-prime-attestations/00-verify-constitution-ratification.json`
      parses as JSON; `sha256sum` over (completion SHA + config
      fingerprint) appears in the file; the spec_id field equals
      `00-verify-constitution-ratification`.

- [ ] **T5.3** — fifth-stage commit (T5.1, T5.2 file creation
      only); verify: `git status` shows META.md +
      `.pi-prime-attestations/00-…json` as new untracked;
      `make check-prime-directive` exits 0; `pytest -q tests/static/`
      exits 0; the strengthened grep is clean across all four
      repos at HEAD.

- [ ] **T5.4** — final audit-close check (the `Cannot claim done
      when…` list, twelve clauses); verify by running each clause
      and recording `PASS` in the entry's META.md
      `constitution_compliance` field.

**M5 exit**: META.md + attestation present; the twelve cannot-
claim-done clauses all `PASS`; `make check-prime-directive` exits 0
across the four repos; `pytest -q tests/static/` exits 0.

---

## Done-ness check (post-M5)

A claim that entry 00 is complete is invalid if any of the twelve
clauses in `spec.md` §"Cannot claim done when…" holds. The M5
tasks above mechanically enforce all twelve. Final QA is the
attestation invocation itself; if it does not write the JSON
artifact at the expected path with the expected sha256, the claim
is invalid by constitution §3 S3.5.

The dependent entry 01 can begin. Entry 00's META.md includes its
explicit unblock line referencing entry 01's slug.
