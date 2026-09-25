# 03 — Kaplansky Domain Verification Completeness

> **Spec-Kit** artifact. Zero-padded `00–10`. This is `03`. Depends on
> `00`. Unblocks `10` (release closure references kaplansky's
> domain evidence).

## Identity

- **spec_id:** `03-domain-verification-completeness`
- **owner_repo:** `kaplansky`
- **owner_repos:** `{kaplansky, math, research-institution}`
- **status:** draft
- **depends_on:** `00-verify-constitution-ratification`
- **unblocks:** `10-verification-release-closure`

## Primary actor

The maintainer running kaplansky's tests daily and the CI system
gating protected-branch merges on kaplansky's local VG-0…VG-3 gates.
The implicit audience is entry 04 (stateful sample research) which
relies on kaplansky's domain tests proving the **`programs/*`**
schema is closed and the math ↔ kaplansky contract holds.

## Problem statement (current failure evidence)

From the test-and-simulation guide §13 (additional inventory):

- kaplansky has **~84 test modules**, **1,104 AST-visible test
  functions**, mostly flat at the repo root.
- kaplansky's test policy is minimal; no explicit tier / dependency /
  cadence contract is enforced.
- All four repos contain absolute-path, `$HOME`, `/tmp`, platform,
  `sleep`, and ambient-environment assumptions. Each must be
  classified and isolated.
- kaplansky roadmap (`programs/kaplansky-roadmap.toml`) is the
  active domain state — schema round-trip, migration, frontier
  integrity, work-selection fairness — are not yet tested against
  the institution's verify policy.

## Independent user stories

1. As a **maintainer**, I run kaplansky's focused tests today and
   nothing relies on `unittest discover` vs pytest ambiguity; tier
   vocabulary is enforced.
2. As a **maintainer**, the kaplansky roadmap schema round-trips
   losslessly; a malformed roadmap is rejected at parse time;
   the test suite proves this without depending on real kaplansky
   data.
3. As a **maintainer**, I can run **`work-selection` fairness /
   idempotency / stale-outcome / conflicting-outcome** tests
   against today's roadmap independently of the live research
   cycle.
4. As a **maintainer**, the four evidence families enumerated in
   the master guide §13 (Domain State / Work Selection / Outcomes /
   Artifact Integrity / Plugin / Launcher / Scale / Security) all
   have at least one test per family at completion.

## Functional requirements (per spec-artifact contract)

FR-1. Kaplansky's `pyproject.toml` `[tool.pytest.ini_options]`
gains the same tier-marker conventions as math (entry 01) and
pi_monitor (entry 02). The plain `pytest --collect-only -q`
command exits 0 at kaplansky HEAD.

FR-2. `kaplansky/tests/static/test_closed_tier_vocabulary.py`,
`test_dependency_vocabulary.py`,
`test_skip_xfail_baseline.py` + companion
`skip_xfail_baseline.toml` are created per entry 01's FR-2/FR-3/
FR-4 pattern, with kaplansky paths.

FR-3. `kaplansky/Makefile` gains the eight tier-routed targets per
entry 01 FR-5.

FR-4. `kaplansky/tests/README.md` rewires by subsystem + tier.

FR-5. Domain evidence families (each as a separate test module):

   - **`tests/domain/test_roadmap_schema_roundtrip.py`** — the
     roadmap TOML schema (re-exported from
     `mathlint.orchestration.real_source` types where the schema
     originates) round-trips losslessly through write+read for
     every `programs/*.toml` in kaplansky; a deliberately mutated
     file is rejected.
   - **`tests/domain/test_frozen_claims.py`** —
     `programs/frozen-claims.toml` rejects any modification at
     runtime via the documented contract.
   - **`tests/domain/test_palomar_provenance.py`** —
     `programs/palomar-provenance.toml` round-trip + canonical
     hash.
   - **`tests/domain/test_modules.py`** — `programs/modules.toml`
     registers each module once; collisions rejected.
   - **`tests/domain/test_compute_registry.py`** —
     `programs/compute-registry.toml` registers each compute slot
     once.
   - **`tests/work_selection/test_dependency_valid_operation.py`**
     — work-selection reducer respects the
     `programs/kaplansky-roadmap.toml` dependency edges;
     deterministic tie-break; deterministic when fingerprint
     changes (no-delta redirect); chronological `decided_unix`
     monotonicity.
   - **`tests/work_selection/test_blocked_completion.py`** — a
     blocked outcome advances `next_attempts` not
     `complete_set`; idempotent completion is absorbing; repeated
     offers of the same operation are deduplicated by
     `(source_identity, operation_id, revision_fingerprint)`.
   - **`tests/work_selection/test_stale_outcomes.py`** — an
     outcome referencing an old revision is rejected; a
     duplicate report is idempotent; a conflicting report fails
     closed.
   - **`tests/artifacts/test_artifact_integrity.py`** —
     certificates, evidence manifests bind to exact inputs /
     revisions; malformed / truncated artifacts are rejected;
     artifact paths cannot escape the program repo root.
   - **`tests/plugin/test_mathlint_provider.py`** — the kaplansky
     `mathlint_plugin` entry-point registers with
     `register_program_providers` exactly once per machine; the
     `WorkSourceProvider` slot is populated; collision raises per
     `@ADR-0014` discipline.
   - **`tests/plugin/test_entry_point_collision.py`** — a second
     program registering a `mathlint.providers` entry point on
     the same machine is a `BLOCKED` lane, not a silent skip.
   - **`tests/launcher/test_institution_check.py`** — the
     kaplansky `scripts/check-program-institution.sh` is
     subprocess-invoked against a temporary HOME / state dir;
     four cwds; passes / fails per documented contract.
   - **`tests/security/test_no_kaplansky_literal_in_siblings.py`**
     — a mirror of BC-4 / BC-5: kaplansky_literals that legitimately
     live in kaplansky are NEVER present in research-institution
     / math / pi_monitor `src/`. The static check passes today; the
     check-in asserts the negative stays negative.

FR-6. **Folder migration** per the master guide §13 (additional
inventory):

   - Flat tests at repo root migrate to:
     `tests/{domain, work_selection, artifacts, plugin, launcher,
            scale, security, static, support}/`.
   - `tests/acceptance/` and `tests/program/` and `tests/scale/`
     reclassify per the §1 closed set; ambiguous-tier strings
     marked for retirement.
   - Empty reserved subdirectories removed.

FR-7. **`kaplansky/AGENTS.md`** confirms cross-repo exemption
registry references (per entry 00's cross-repo prevention
section).

FR-8. **`kaplansky/scripts/check-program-institution.sh`** is
wired with the canonical
`research-institution/scripts/check-prime-directive.sh` (per entry
00's symlink). Verify diff and gate.

FR-9. Cross-repo exemption registry rows for kaplansky legacy
exempt files.

FR-10. Kaplansky's roadmap (`programs/kaplansky-roadmap.toml`) is
**not modified** by this entry — entry 04's stateful sample
program references it but this entry only validates schema /
fingerprint.

## Explicit exclusions (boundary discipline)

- Modifying `programs/*` content (frozen by `frozen-claims.toml`
  contract).
- Modifying `src/kaplansky/*` production code (entry 04 extends the
  sample; kaplansky remains untouched at this stage).
- Adding new durable records (entries 04 / 06 / 10 own those).
- Cross-repo test wiring against the live research-program state.

## Measurable success criteria

- `pytest --collect-only --no-cov -q` exits 0 at kaplansky HEAD.
- The five static-check trio exits 0.
- The ten new domain / work-selection / artifact / plugin /
  launcher / security test modules all exit 0.
- `make test-tier-fast` exits 0.
- `make check-prime-directive` exits 0 at kaplansky HEAD.
- Entry 00's twelve cannot-claim-done clauses hold at kaplansky
  HEAD (cross-anchor cross-check via the canonical script).

## Failure and edge cases

- **F-1.** A roadmap schema is broken by accident in CI; the
  round-trip test catches it before any downstream consumer.
- **F-2.** A `mathlint.providers` collision arises from a stale
  pip install. The collision test runs cleanly today; the static
  check ensures it stays that way.
- **F-3.** A `check-program-institution.sh` invocation from the
  wrong cwd returns non-zero. The four-cwd launcher test proves
  the dispatcher tolerates each.

## Dependencies on earlier entries

- **Entry 00** — verify-constitution §1, §2, §3, §5, §7.

## "Cannot claim done when…"

1. `pytest --collect-only -q` is broken on coverage.
2. Any primary-tier marker outside the §1 closed set appears.
3. The ten new test modules don't all exit 0.
4. The four-cwd launcher test fails on any cwd.
5. `mathlint_provider` collision test is silent instead of
   raising.
6. Required-lane skip count is non-zero.
7. `transient-exemptions.toml` mutated without version bump.
8. Folder migration left ambiguous-tier directories in place.
9. Strong-grep violation at kaplansky HEAD.
10. Entry 00 twelve cannot-claim-done clauses do NOT all hold at
    kaplansky HEAD.
11. `programs/*` content modified.
12. `src/kaplansky/*` modified.

## Non-goals

- Changing kaplansky's research domain state.
- Adding new `programs/*` files (those land when a research
  change warrants, not in this verify-cleanup entry).

## Cross-references

- `kaplansky/AGENTS.md` Spec Kit software-engineering mode + cold
  start.
- `kaplansky/programs/{kaplansky,kaplansky-roadmap,frozen-claims,
  modules,compute-registry,palomar,palomar-provenance}.toml`.
- `kaplansky/scripts/check-program-institution.sh`.
- `.specify/memory/constitution-verify.md` §7 (sample program
  contract), §6 (no-second-supervisor).
- `@ADR-0014` (mathlint does not import program-named modules).
- `@INV-0088` (sample fixture requires no external state).
- `@ADR-0091` (mathlint ships no program launchers).
- `@CTR-0020` (three-repo wire contract).
