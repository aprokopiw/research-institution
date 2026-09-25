# 10 — Tasks

## Milestones

- **M1** — `release.py` + `mutation.py`.
- **M2** — claim manifest + documentation truth audit.
- **M3** — flake audit + repeated random-order.
- **M4** — transient-guide retirement + durable record +
  audit-close.

## M1 — release + mutation

- [ ] **T1.1** — implement
      `research-institution/research_institution/gates/verify_simulation/release.py`
      with `ReleaseReport` (typed; seven `PASS` rows).
      **verify:** unit test asserts the schema.
      **path:** `research-institution/research_institution/gates/verify_simulation/release.py`

- [ ] **T1.2** — implement
      `mutation.py` reading the 15 critical mutants from master
      guide §12 (locally mirrored as `tests/mutation/critical_mutants.toml`);
      asserts each killed by named scenario + test.
      **verify:** unit test asserts each mutant's killer test is
      a real node-ID.
      **path:** `research-institution/research_institution/gates/verify_simulation/mutation.py`

- [ ] **T1.3** — extend `cli.py` with `--tier release`.
      **verify:** `--help` exits 0 with `--tier release`.
      **path:** `research-institution/research_institution/gates/verify_simulation/cli.py`

- [ ] **T1.4** — first commit.

**M1 exit:** release + mutation modules land.

## M2 — Claim manifest + docs audit

- [ ] **T2.1** — write
      `research-institution/docs/semantic/CLAIM_MANIFEST.toml`
      with every required claim from master guide §7 + §13.
      **verify:** TOML parses; no claim has zero evidence.
      **path:** `research-institution/docs/semantic/CLAIM_MANIFEST.toml`

- [ ] **T2.2** — write
      `tests/static/test_documentation_truth.py` asserting the
      six forbidden primary-tier strings appear zero times in
      active markers.
      **verify:** exits 0.
      **path:** `research-institution/tests/static/test_documentation_truth.py`

- [ ] **T2.3** — write `tests/static/test_claim_manifest_integrity.py`
      asserting every required claim has at least one
      current node-ID.
      **verify:** exits 0.
      **path:** `research-institution/tests/static/test_claim_manifest_integrity.py`

- [ ] **T2.4** — second commit.

**M2 exit:** manifest + documentation truth audit green.

## M3 — Flake audit + repeated random-order

- [ ] **T3.1** — write
      `tests/simulation/test_flake_audit.py` running 20× against
      `happy-three-cycle` with a deterministic seed.
      **verify:** exits 0; zero flakes.
      **path:** `research-institution/tests/simulation/test_flake_audit.py`

- [ ] **T3.2** — write `tests/static/test_random_order_determinism.py`
      asserting the canonical scenario produces the same
      transcript byte-for-byte under random ordering.
      **verify:** exits 0.
      **path:** `research-institution/tests/static/test_random_order_determinism.py`

- [ ] **T3.3** — third commit.

**M3 exit:** flake + random-order audit green.

## M4 — Transient-guide retirement + durable record + audit-close

- [ ] **T4.1** — move
      `.agents/transient/test_and_simulation_suite.md` to
      `.agents/transient/_retired/test_and_simulation_suite.retired.md`
      with tombstone frontmatter pointing at `.specify/specs/`.
      **verify:** `ls .agents/transient/test_and_simulation_suite.md`
      fails; `ls .agents/transient/_retired/test_and_simulation_suite.retired.md`
      succeeds.
      **path:** `.agents/transient/`

- [ ] **T4.2** — write durable record
      `research-institution/docs/semantic/contracts/ctr-0101-release-gate-contract.md`.
      **verify:** file exists; standard CTR header.
      **path:** `research-institution/docs/semantic/contracts/ctr-0101-release-gate-contract.md`

- [ ] **T4.3** — amend
      `research-institution/docs/semantic/SEMANTIC_REGISTRY.md`
      appending the new anchor row.
      **verify:** `grep` finds `@CTR-0101-release-gate-contract`.
      **path:** `research-institution/docs/semantic/SEMANTIC_REGISTRY.md`

- [ ] **T4.4** — update `~/.pi/agent/extensions/prime-directive-guard.ts`
      block-message body to cite the new entry's META path (not
      the retired guide).
      **verify:** manual smoke write of forbidden literal in
      unsanctioned path produces the new message.
      **path:** `~/.pi/agent/extensions/prime-directive-guard.ts`

- [ ] **T4.5** — fourth commit (T4.1–T4.4); verify all twelve
      cannot-claim-done clauses hold.

- [ ] **T4.6** — run
      `python -m research_institution verify-simulation --tier release`;
      verify typed report exits 0; gate report digest captured
      in this entry's META `gate_report_digest`.

- [ ] **T4.7** — emit META.md + attestation; entry 10 closes.

**M4 exit:** program is closed; no further entries planned.
