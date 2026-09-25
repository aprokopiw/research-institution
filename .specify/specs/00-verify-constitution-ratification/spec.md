# 00 — Verify-Constitution Ratification

> **Spec-Kit** artifact. Numbering scheme is **zero-padded `00–10`**;
> lex sort = execution order. This is `00`. The program is eleven
> entries total. All spec dirs live under
> `research-institution/.specify/specs/`.

## Identity

- **spec_id:** `00-verify-constitution-ratification`
- **owner_repo:** `research-institution`
- **owner_repos:** `{research-institution}` (this touches no sibling
  code; it lays the governance foundation that 01–10 inherit).
- **status:** draft
- **depends_on:** none (entry point)
- **unblocks:** 01, 02, 03, 04, 05, 06, 07, 08, 09, 10.

## Primary actor

The maintainer / Spec-Kit harness invoking the constitution slash
command on the research-institution repo. The implicit audience is
every later entry in the eleven-entry program whose Constitution
Check section cites this file.

## Problem statement (current failure evidence)

- **research-institution/.specify/memory/constitution.md** ratifies
  only the **typing** constitution (8 principles I–VIII). The
  **verify** surface — tier vocabulary, dependency vocabulary,
  gate-status algebra, VG-0…VG-8, action matrix, prime-directive
  mechanical enforcement, audit-close-out, ownership of the canonical
  simulation CLI — has **no ratifying constitution** today.
- The four-repo `AGENTS.md` prime-directive sections are byte-identical
  but enforced by **two** mechanisms whose drift we cannot measure: a
  shell-script grep (`scripts/check-prime-directive.sh`) and a
  TypeScript pi extension
  (`~/.pi/agent/extensions/prime-directive-guard.ts`). Neither
  mechanism is anchored to a durable ADR.
- The test-and-simulation guide
  (`research-institution/.agents/transient/test_and_simulation_suite.md`)
  describes a ten-entry program **without** an opening-ratification
  step; its twelve principles of verify-policy live only in prose
  inside §7 of that guide, which is a sanctioned-exception file and
  so cannot be cited from permanent code.
- The math `AGENTS.md` enumerates twenty-two sanctioned exception
  classes for the prime-directive; each is currently deletion-coupled
  only to its own narrow artifact. There is no institution-wide
  canonical registry. New exception requests have nowhere to land
  except a single repo's `AGENTS.md`.
- No entry in the program has a machine-checked audit-close-out
  schema today. The eleven-entry program cannot begin because there
  is no upstream governance binding the eleven entries to the
  institution's long-term policy.

## Independent user stories

Each story produces a testable increment:

1. As a **maintainer**, I can run a single command that verifies the
   verify-constitution file is self-consistent (every linked durable
   anchor exists in the registry; every §N has
   Statement+Sub-Rules+Linked anchors).
2. As a **CI gate author**, I can wire `make check-prime-directive`
   in every repo to the same canonical script and verify the four
   invocations produce identical exits against identical inputs.
3. As an **agent**, when I attempt a `write` or `edit` containing
   a transient forbidden literal, the pi extension's block message
   points at the canonical durable-anchor mapping AND at a
   single-row entry in the cross-repo exemption registry; today the
   block points only at the mapping.
4. As a **future author**, my Constitution Check section has one
   canonical file to cite
   (`.specify/memory/constitution-verify.md`).
5. As an **operator**, I can list every sanctioned-transient
   exemption institution-wide, with expiry dates ratcheting towards
   zero, in one file
   (`research-institution/.specify/memory/transient-exemptions.toml`).
6. As an **adversary**, I cannot ratify a fake-tier marker, a fake
   dependency marker, a fake gate verdict, or a fake spec-id by
   editing a single file — every addition is checked at multiple
   layers (constitution, static check, gate self-test).

## Functional requirements (per spec-artifact contract)

FR-1. The file `research-institution/.specify/memory/constitution-verify.md`
is created with **§0–§12 + Governance**, each section carrying:
Statement, numbered Sub-Rules (S§N.M), and Linked durable anchors.

FR-2. `research-institution/.specify/memory/transient-exemptions.toml`
is created with the canonical initial exemption rows: the list of
files exempted by the strengthened grep (drawn from each repo's
`AGENTS.md` institution-wide prevention section) and the
math-AGENTS §22 grandfathered kaplansky list, each carrying an
`expiry_spec_id` field pointing at the entry that retires it.

FR-3. `scripts/check-prime-directive.sh` is canonical at
`research-institution/scripts/check-prime-directive.sh`. Sibling
repos (`math`, `pi_monitor`, `kaplansky`) carry a symlink (or
byte-diff-equivalent copy) at `<sibling>/scripts/check-prime-directive.sh`.
A new repo-wide helper
`scripts/check-prime-directive-enforced.sh` (initial scaffold
returning `NOT_RUN`) is created at the research-institution canonical
location; entry 09 finishes its body.

FR-4. `tests/static/test_constitution_consistency.py` is created at
`research-institution/tests/static/`. It verifies:
   - `constitution-verify.md` exists and parses;
   - for every `@ADR-NNNN` / `@INV-NNNN` / `@CTR-NNNN` / `@CON-NNNN`
     reference in §N sub-rules, a corresponding entry exists in
     `research-institution/docs/semantic/SEMANTIC_REGISTRY.md`
     (or in the repo-specific subdirectory's `*.md`);
   - the file declares a `Version` line;
   - every §N section's body carries the three parts.

FR-5. `tests/static/test_canonical_script_identity.py` is created at
`research-institution/tests/static/`. It iterates the four repos,
runs `scripts/check-prime-directive.sh --selftest` (or equivalent)
in each, and asserts byte-equivalence of exit codes and primary
output for identical inputs. Failure is gate `FAIL`.

FR-6. New durable records are authored and ratify this constitution:
   - `@ADR-0095-prime-directive-mechanical-enforcement`
     (research-institution/docs/semantic/adr/) — anchors the
     cross-repo mechanical enforcement (constitution §10).
   - `@INV-0095-prg-anchor-ownership`
     (research-institution/docs/semantic/invariants/) — anchors
     institution-wide semantic-record ownership (constitution §12).
   - `@CTR-0095-prime-directive-check-script-contract`
     (research-institution/docs/semantic/contracts/) — pins the
     strengthened regex, sanctioned-globs list, and exit-code
     behavior of `scripts/check-prime-directive.sh`.

FR-7. The cross-repo registry
(`research-institution/docs/semantic/SEMANTIC_REGISTRY.md`)
is amended to list the three new anchors above, plus a one-line
reference to `constitution-verify.md`.

FR-8. The institution-wide AGENTS.md prime-directive section
(`research-institution/AGENTS.md`, `math/AGENTS.md`,
`pi_monitor/AGENTS.md`, `kaplansky/AGENTS.md`) is amended **only in
its cross-reference portion** to point at the new files. The
canonical grep pattern is unchanged.

FR-9. The `00` directory contains a final `META.md` with the
machine-checked schema defined in constitution §11.2.

## Explicit exclusions (boundary discipline)

The following are out of scope — they live in later entries, and
citing them here overclaims:

- The eight gates (VG-0…VG-8) **implementation** — entry 00 only
  establishes the algebra and the action matrix; entry 01 adds
  VG-0/1/2/3 to math, entry 02 adds VG-0/1/2/3 to pi_monitor, entry
  03 adds VG-0/1/2/3 to kaplansky, entry 06 adds VG-4 to
  research-institution, entry 07 adds VG-5/VG-7/VG-8, entry 10 adds
  VG-6 mutation and wire-up.
- The `python -m research_institution verify-simulation` CLI — entry
  06 scaffolds it.
- The SHA-bound attestation machinery — entry 09 builds it.
- The eight subsequent entries `01` through `10` — they are not yet
  authored at the moment entry `00` ratifies.

## Measurable success criteria

- `bash research-institution/scripts/check-prime-directive.sh`
  exits 0 against the research-institution tree at completion SHA.
- The same script (called through the sibling-repo symlinks) exits
  0 against every sibling tree at the same SHA.
- `pytest -q research-institution/tests/static/test_constitution_consistency.py`
  exits 0.
- `pytest -q research-institution/tests/static/test_canonical_script_identity.py`
  exits 0.
- `python -m research_institution prime_directive attest 00…`
  produces `.pi-prime-attestations/00-verify-constitution-ratification.json`
  with a valid sha256 over (completion SHA + config fingerprint).
- The cross-repo registry lists the three new anchors
  (`@ADR-0095-prime-directive-mechanical-enforcement`,
  `@INV-0095-prg-anchor-ownership`,
  `@CTR-0095-prime-directive-check-script-contract`).

## Failure and edge cases

- **F-1.** A future entry tries to add a primary tier marker outside
  the §1 closed set. Static check
  `tests/static/test_closed_tier_vocabulary.py` (added in 01/02/03)
  raises. Pre-scaffold static check in 00 validates that no current
  repo already contains a marker outside the closed set (otherwise
  entry 00 triggers a remediation task in 01/02/03).
- **F-2.** Sibling repos disagree on the strengthened-grep output
  for the same input. Entry 00 exposes the discrepancy via
  `test_canonical_script_identity.py` and gates merge on identity.
- **F-3.** An entry's `META.md` is missing. The dependent entry's
  first task reads META.md of its predecessor; missing → `BLOCKED`.
- **F-4.** A new prime-directive exception is requested mid-program.
  Entry 00 writes the canonical addition path
  (`transient-exemptions.toml` + bump + extension reload);
  `make check-prime-directive-enforced` validates the addition is
  deletion-coupled.
- **F-5.** Constitution is amended mid-program. The amendment
  bumps the version, increments the governance log, and is itself
  subject to a META (per §11).

## Dependencies on earlier entries

- `00` has **no** earlier dep — this IS the entry point.
- `00` is the only entry whose evidence is "the constitution exists
  and is internally consistent"; later entries depend on its
  existence and on the canonical exemption registry.

## "Cannot claim done when…"

A claim that entry 00 is complete is invalid if any of the below
holds at the candidate-completion SHA:

1. `.specify/memory/constitution-verify.md` is missing or empty.
2. `constitution-verify.md` lacks any of §0–§12.
3. Any linked durable anchor in §N sub-rules is not present in
   `docs/semantic/SEMANTIC_REGISTRY.md` or in the per-repo
   `docs/semantic/{adr,invariants,contracts}/`.
4. `scripts/check-prime-directive.sh` is not canonical at
   `research-institution/scripts/`.
5. Sibling repos do not have a working invocation of the script (no
   symlink and no copy).
6. `transient-exemptions.toml` is missing or empty.
7. `tests/static/test_constitution_consistency.py` is failing or
   absent.
8. `tests/static/test_canonical_script_identity.py` is failing or
   absent.
9. `META.md` for entry 00 is missing or invalid against the §11.2
   schema.
10. `.pi-prime-attestations/00-verify-constitution-ratification.json`
    is missing or missing the sha256 over (completion SHA + config
    fingerprint).
11. The strengthened grep, run against the four repos at completion
    SHA, reports any unsanctioned hit. (Self-test.)
12. Any of the three new durable records (`@ADR-0095-…`,
    `@INV-0095-…`, `@CTR-0095-…`) is missing.

This list is mechanically enforced by `tests/static/` and the
attestation invocation; manual override is gate `FAIL` per
constitution §3.

## Non-goals

- Re-litigating the **typing** constitution (8 principles I–VIII).
- Implementing any gate body (VG-0…VG-8 implementations).
- Adding the canonical verification CLI.
- Authoring entries 01–10.

## Cross-references

- `.specify/memory/constitution.md` (typing, 8 principles I–VIII,
  unchanged).
- `.specify/memory/constitution-verify.md` (this entry's product).
- `.specify/memory/transient-exemptions.toml` (this entry's
  product).
- `research-institution/scripts/check-prime-directive.sh`
  (canonical, exists today, referenced).
- `~/.pi/agent/extensions/prime-directive-guard.ts` (existing
  enforcement extension; entry 09 does the bigger rework).
- `research-institution/.agents/transient/test_and_simulation_suite.md`
  (program-level guide; the eleven-entry program this entry
  foregrounds).
- `@ADR-0006` (research-institution scope).
- `@INV-0093` (institution green gate is canonical wiring evidence).
- pi_monitor `@ADR-0001` (source owns domain, monitor owns execution).

## Sign-off

This entry closes **only** when all `cannot claim done when…`
clauses hold at completion SHA and the META.md exists. No verbal
override (constitution §3 S3.5).
