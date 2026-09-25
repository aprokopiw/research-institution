# 10 — Verification Release Closure

> **Spec-Kit** artifact. Zero-padded `00–10`. This is `10`. Depends on
> `03`, `08`, `09`. Closes the program.

## Identity

- **spec_id:** `10-verification-release-closure`
- **owner_repo:** `research-institution`
- **owner_repos:** `{research-institution, math, pi_monitor, kaplansky}`
- **status:** draft
- **depends_on:** `03-domain-verification-completeness`,
  `08-installed-compatibility-recovery`,
  `09-prime-directive-mechanical-enforcement`
- **unblocks:** none — this entry closes the program.

## Primary actor

The release engineer / Spec-Kit maintainer who closes the
program. Implicit audience: a fresh cold-start agent who
queries this entry's META.md to determine what's safe to
claim done.

## Problem statement

There is no machine-checked audit-close-out for the eleven-spec
program as a whole. The verify-constitution (entry 00) defines
the algebra; the gates (entries 06 / 07 / 08) consume the
machinery; this entry **proves** the closing claims:

- Every required claim in the master guide §7 + §13 is
  evidenced by current collected, executed, passing tests
  at HEAD.
- Every mutation challenge from master guide §12 is killed at
  HEAD.
- Random-order and repeated-run suites are stable.
- Flake audit: zero flakes across a bounded repeat.
- Claim manifest closes every claim against current executed
  evidence.
- Documentation truth audit: no `end-to-end` / `e2e` /
  `smoke` / `acceptance` / `endurance` / `live` / `chaos`
  primary-tier markers in active use.
- Prime-directive enforcement is mechanical (entry 09).
- Transient guides (`test_and_simulation_suite.md`,
  `.agents/transient/`) are retired with tombstone records; the
  spec dirs (`.specify/specs/`) are the durable memory.

## Independent user stories

1. As a **fresh agent** reading this entry's META, I can run
   one command (`python -m research_institution verify-simulation
   --tier release`) and obtain a typed report stating every
   claim's evidence + status.
2. As a **release engineer**, the mutation-test gate aggregator
   shows every named critical mutant from master guide §12 is
   killed; surviving critical mutant = `FAIL`.
3. As a **program maintainer**, the transient guide
   `.agents/transient/test_and_simulation_suite.md` is moved to
   a tombstone location and the spec dirs are the durable
   substitute.

## Functional requirements

FR-1. **`research_institution/gates/verify_simulation/release.py`**
implements the release gate:

   - inputs every gate's report (VG-0…VG-8) at current SHA;
   - computes the typed `ReleaseReport`;
   - refuses to claim done unless every required claim has
     non-zero evidence.

FR-2. **`--tier release`** registers as a new CLI flag:

   - runs every gate;
   - asserts the seven release `PASS` rows (per master guide
     §13):
     1. every primary evidence tier has at least one tier;
     2. every required claim has at least one current node-ID
        or scenario-ID;
     3. every scenario has its metadata;
     4. every mutation test named in master guide §12 is killed;
     5. twenty-repeated runs of `happy-three-cycle` produce zero
        flakes;
     6. every collected test's primary marker is in the §1 closed
        set;
     7. the prime-directive enforcement (entry 09) is clean.

FR-3. **Claim manifest** at
   `research-institution/docs/semantic/CLAIM_MANIFEST.toml`
   (or equivalent machine-readable file) records every claim,
   its required tier, its evidence node-IDs, and its status.
   No required claim has zero evidence.

FR-4. **Mutation-test gate aggregator** ships:

   - `research_institution/gates/verify_simulation/mutation.py`
     reads the 15 critical mutants named in master guide §12 and
     asserts each is killed by a named scenario + test. Suriving
     critical mutant = `FAIL`.

FR-5. **Flake audit** runs a 20× repeated random-order suite
   against `happy-three-cycle`. Zero flakes = `PASS`.

FR-6. **Documentation truth audit** greps every durable path for
   `e2e | smoke | acceptance | endurance | live | chaos` as
   primary-tier markers. Failure = `FAIL`.

FR-7. **Transient guide retirement**:

   - `.agents/transient/test_and_simulation_suite.md` is renamed
     to `.agents/transient/_retired/test_and_simulation_suite.retired.md`
     with a tombstone frontmatter
     `retired_at_sha = <this entry's completion_sha>,
      retired_by_slug = "10-verification-release-closure",
      superseded_by = ".specify/specs/"`;
   - the prime-directive extension's block-message references
     this entry's META path (rather than the retired guide);
   - the strengthened grep
     `(\b[Pp][Ll][Aa][Nn]|\b[Ss][Pp][Ee][Cc])[-_ ]?[0-9]{2,}`
     continues to **NOT** match the retired file's filename
     (because of the leading underscore + the `.retired.md`
     extension); the registry's sanctioned-glob list is
     updated accordingly.

FR-8. **Randomized / repeat evidence**: the release report
   records the seed, the duration, the artifacts path.

FR-9. **Final durable anchor**: a new
   `@CTR-0101-release-gate-contract` records the release-gate
   contract (typed `ReleaseReport` schema + the seven `PASS`
   rows).

## Explicit exclusions

- Re-implementing the verify-constitution.
- Re-authoring entry 00.
- Authoring new `process` / `deployment` / `provider_live`
  scenarios (entries 06 / 07 own).

## Measurable success criteria

- `--tier release` exits 0; its `ReleaseReport` records all
  seven `PASS` rows.
- Claim manifest resolves every required claim with current
  executed evidence.
- Mutation-test gate aggregator shows 0 surviving critical mutants.
- Flake audit produces zero flakes in the 20× run.
- Documentation truth audit produces zero primary-tier hits on
  the six forbidden strings.
- The transient guide is retired; the entry's META references
  the tombstone path.
- `make check-prime-directive-enforced` exits 0 in every repo.

## Failure and edge cases

- **F-1.** A new skip is added at runtime. Multi-tier gates
  catch via entry 09's attestation validator + claim-manifest
  integrity check.
- **F-2.** A mutation test surfaces a surviving critical mutant.
  Release gate `FAIL`.
- **F-3.** Documentation truth audit finds an active forbidden
  string. Release gate `FAIL`.
- **F-4.** A repo's HEAD is dirty or detached from the canonical
  branch. `git status`/`git rev-parse` blocks the release.

## Dependencies on earlier entries

- **All entries 00–09** — full prerequisite.
- The release report consumes every entry's META.md + every
  entry's attestation.

## "Cannot claim done when…"

1. `--tier release` exits non-zero.
2. The claim manifest has zero evidence for any required claim.
3. A surviving critical mutant is recorded.
4. The 20× run produces any flake.
5. The documentation truth audit finds an active forbidden
   string.
6. The retired guide still bears the transient plan identifier.
7. `make check-prime-directive-enforced` fails at any repo.
8. The transient guide is not tombstoned.
9. Any entry's META is missing required fields.
10. Any entry's attestation references a SHA absent from the
    local reflog.
11. Entry 00/03/08/09 cannot-claim-done clauses do NOT hold.
12. The `@CTR-0101-…` durable record is missing.

## Non-goals

- Re-opening closed entries.
- Editing the strengthened regex.
- Re-introducing `provider_live` runs that aren't required by
  release policy.

## Cross-references

- `constitution-verify.md` §3, §4, §5, §6, §10, §11, §12.
- All eleven spec dirs under `.specify/specs/`.
- `@CTR-0020`, `@CTR-0094`, `@CTR-0095-…`,
  `@ADR-0095-prime-directive-mechanical-enforcement`,
  `@INV-0095-prg-anchor-ownership`,
  `@CTR-0095-prime-directive-check-script-contract`.
