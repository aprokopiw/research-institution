# 09 — Prime-Directive Mechanical Enforcement

> **Spec-Kit** artifact. Zero-padded `00–10`. This is `09`. Depends on
> `00`. Unblocks `10` and reinforces every entry.

## Identity

- **spec_id:** `09-prime-directive-mechanical-enforcement`
- **owner_repo:** `research-institution` (coordinator)
- **owner_repos:** `{research-institution, math, pi_monitor, kaplansky}`
- **status:** draft
- **depends_on:** `00-verify-constitution-ratification`
- **unblocks:** `10-verification-release-closure` (plus reinforces
  every entry's commit-by-commit enforcement)

## Primary actor

The maintainer who wants the prime-directive enforcement to be
**mechanical and cross-repo** — including the runtime extension's
block message pointing at the canonical
`transient-exemptions.toml` registry, plus the cross-repo
SHA-bound attestation machinery that every entry's META references.

## Problem statement

Today:

- The pi extension
  (`~/.pi/agent/extensions/prime-directive-guard.ts`) hard-codes
  `SANCTIONED_PATH_PATTERNS`; it does NOT consult
  `transient-exemptions.toml`.
- `make check-prime-directive` is invoked per repo but its output
  is not bound to a repo SHA + config fingerprint.
- Each entry's `META.md` is hand-written; no machine-checked
  attestation binds the entry to gate evidence at current SHA.
- `research_institution.spec_audit_close.META_validator` does not
  exist; the `META.md` schema is unenforced.
- The `make check-prime-directive-enforced` gate introduced in
  entry 00 is a `NOT_RUN` stub.

## Independent user stories

1. As an **agent writing durable code**, when the pi extension
   blocks my `write` / `edit` containing a forbidden literal, the
   block message points at the canonical exemption registry row
   that would have authorized my edit (if any), plus the durable
   anchor mapping.
2. As a **release engineer**, every entry's completion emits a
   `.pi-prime-attestations/<spec-id>.json` whose
   `sha256(completion_sha || config_fingerprint)` digest
   re-validates without manual approval.
3. As a **maintainer**, `make check-prime-directive-enforced` runs
   in every repo and exits 0 only when:
    - the strengthened grep is clean at HEAD;
    - at least one attestation exists per spec merged on the
      protected branch;
    - no attestation references a SHA that is absent from the
      local git reflog.

## Functional requirements

FR-1. **`research_institution/prime_directive/`** package:

   - `__init__.py` — re-exports public API.
   - `attest.py` — `attest(spec_id, *, completion_sha) ->
      Attestation`; computes `sha256(completion_sha ||
      config_fingerprint)`; writes the JSON artifact.
   - `validate.py` — `validate_attestation(path, *,
      current_sha, current_fp) -> Result`; rejects stale
      references.
   - `meta_validator.py` — `validate_META(path) -> Result`;
      checks the §11.2 schema.
   - `extension_bridge.py` — `render_sanctioned_globs() ->
      tuple[str, ...]`; reads `transient-exemptions.toml` and
      renders the `SANCTIONED_PATH_PATTERNS` shape the extension
      expects.

FR-2. **`pi_monitor/.../audit_chain_verify.py` — registered
attestation audit** (consumed). New helper
`prime_directive.attest_chain_verify(dir)` verifies the chained
attestation hash from past attestations.

FR-3. **`research-institution/scripts/check-prime-directive.sh`**
script is finalized:

   - emits the canonical `--selftest` mode (entry 00 FR-3) +
     `--enforce` mode (this entry):
       - reads every per-repo attestation under
         `<repo>/.pi-prime-attestations/*.json`;
       - verifies each `completion_sha` is reachable from HEAD;
       - verifies each `digest` is a valid sha256 over
         `completion_sha || config_fingerprint`;
       - emits `BLOCKED` if any referenced SHA is missing from
         the local reflog;
       - exits 0 / 78 / 1 per the gate-status algebra.

FR-4. **Per repo** `Makefile` target added: `check-prime-directive-enforced`,
calling the canonical script in `--enforce` mode. Exits 0 only
when the strengthened grep + per-repo attestation audit + stale-
rejection rules all pass.

FR-5. **Per-repo durable record**:

   - `math/docs/semantic/adr/adr-NNNN-prime-directive-enforcement.md`
     anchors the math-side enforcement. Body cites entry 00's
     `@ADR-0095-prime-directive-mechanical-enforcement` and
     `@CTR-0095-prime-directive-check-script-contract`.
   - `pi_monitor/docs/adr/adr-NNNN-prime-directive-enforcement.md`
     — analogous.
   - `kaplansky/docs/.../adr-NNNN-prime-directive-enforcement.md`
     — analogous.

   (Each repo's local IDs are picked to avoid cross-repo collisions
   per `constitution-verify.md` §12.1–§12.2.)

FR-6. **Update `~/.pi/agent/extensions/prime-directive-guard.ts`**:

   - the extension loads
     `research-institution/.specify/memory/transient-exemptions.toml`
     once at startup (or per call: a CLI hook);
   - the block message body cites the relevant row when one
     matches the rejected file path;
   - the strengthened regex remains canonical with the script.

FR-7. **`META_validator` script** lands at
   `research-institution/scripts/META_validator.py` (CLI):
   parses each spec dir's `META.md`, validates against §11.2,
   emits PASS / FAIL / NOT_APPLICABLE.

FR-8. **Per repo's `Makefile`** gains a `check-prime-directive-enforced`
   target wired to the canonical script.

FR-9. **Warn-not-block UX contract** — the pi extension's
   default behavior on a hit **inside an unsanctioned path** is:

   - emit a precise diagnostic to `ctx.ui` and `addMessage`
     (`file:line:col:match:class` + suggested durable anchor);
   - **return `undefined`** so the tool call proceeds;
   - log the event to
     `.pi/prime-directive-violations.log` with one of four
     event classes: `sanctioned-glob-allowed`,
     `anchor-under-construction-escape`, `warn-with-fix`,
     `extension-error`.

   This replaces the historical hard-block behavior. Block is
   reserved for **extension-internal errors** only — never for
   a content hit. The agent is expected to rewrite the offending
   line in a subsequent edit; the program gate
   (`make check-prime-directive`) continues to fail at merge
   time so durable-anchor discipline is preserved at commit
   boundaries.

FR-10. **Sanctioned-glob spec-kit auto-allow** — the extension's
   `SANCTIONED_PATH_PATTERNS` includes `<durable>/.specify/specs/<v>`
   plus the historical globs (`<durable>/AGENTS.md`,
   `<durable>/.pi-glla/`, `<durable>/.agents/transient/`,
   vendored `<durable>/.venv/`, `build/`, etc.). A forbidden
   literal in any of these paths is silently allowed through; the
   hit is logged for operator audit but no warning is surfaced.

FR-11. **Anchor-under-construction escape** — when the same edit
   contains BOTH a forbidden literal AND an explicit introduction
   statement of a new durable anchor
   (`introducing @ADR-NNNN-…` / `@INV-NNNN-…` /
   `@CTR-NNNN-…` / `@CON-NNNN-…` / `new durable anchor`), the
   edit is allowed once and the allowance is logged. This handles
   the legitimate case of an agent first writing a transient
   literal as rationale, then introducing the durable anchor as
   the replacement.

## Explicit exclusions

- Editing the canonical strengthened regex (unchanged; this
  entry only widens enforcement surface, not the rule itself).
- Modifying the sup-constitution (entry 00 unchanged).

## Measurable success criteria

- `python -m research_institution prime_directive attest 09-prime-directive-mechanical-enforcement`
  produces a valid `.pi-prime-attestations/09-…json` file.
- `python -m research_institution spec_audit_close META_validate
  .specify/specs/00-verify-constitution-ratification/META.md`
  exits 0 (proves the validator works on the entry 00 template).
- `make check-prime-directive-enforced` exits 0 in every repo at
  HEAD.
- The pi extension's updated block message names the
  transient-exemptions registry row when applicable.
- The pi extension does NOT hard-block on a content hit; it
  warns + allows the call to proceed; the warning is precise
  (file:line:col:match:class).
- The four code-paths of the rewritten extension are
  self-tested:
  1. sanctioned path → silent allow;
  2. unsanctioned + clean → allow;
  3. unsanctioned + hit → warn + proceed;
  4. unsanctioned + hit + introducing @ADR-NNNN → allow-once.
- Each of the four repos has a `make check-prime-directive-enforced`
  target.

## Failure and edge cases

- **F-1.** Attestation references a SHA absent from the local
  reflog. `validate_attestation` rejects; `check-prime-directive
  --enforce` emits `BLOCKED`.
- **F-2.** Extension loads a malformed TOML. Default deny — the
  block messages return to the historical mapping; no row cited.
- **F-3.** A `META.md` is missing a required field.
  `validate_META` returns `FAIL`.

## Dependencies on earlier entries

- **Entry 00** — verify-constitution §10, §11 + the
  `transient-exemptions.toml` registry.

## "Cannot claim done when…"

1. `research_institution/prime_directive/__init__.py` missing.
2. `attest.py` does not produce a valid sha256 over
   `(completion_sha || config_fingerprint)`.
3. `validate.py` accepts a stale SHA.
4. `meta_validator.py` does not validate §11.2.
5. `extension_bridge.py` does not render the canonical glob
   pattern.
6. The pi extension does not load the registry.
7. Per-repo `Makefile` lacks `check-prime-directive-enforced`.
8. Per-repo durable record missing.
9. `make check-prime-directive-enforced` exits non-zero in any
   repo at HEAD.
10. Entry 00 twelve cannot-claim-done clauses do NOT hold.
11. Stale attestation emits `PASS` (regression of F-1).
12. The strengthened regex differs from the canonical grep.
13. The extension hard-blocks on a content hit (regression of
    FR-9; the extension must `return undefined` to proceed).
14. The extension does not log `sanctioned-glob-allowed`,
    `anchor-under-construction-escape`, or `warn-with-fix`
    events to `.pi/prime-directive-violations.log`.
15. The extension's diagnostic does not include
    `file:line:col:match:class` precision.
16. `/specs/` (or `/spec-kit/`) is not present in
    `SANCTIONED_PATH_PATTERNS` after FR-10 lands.

## Non-goals

- Amending the verify-constitution.
- Replacing the extension with a Python rewrite.
- Editing the strengthened regex.

## Cross-references

- `.specify/memory/constitution-verify.md` §10, §11.
- `@ADR-0095-prime-directive-mechanical-enforcement`.
- `@INV-0095-prg-anchor-ownership`.
- `@CTR-0095-prime-directive-check-script-contract`.
- `~/.pi/agent/extensions/prime-directive-guard.ts`.
- `research-institution/scripts/check-prime-directive.sh`.
