---
id: ADR-0095
kind: decision
status: accepted
title: Prime-directive enforcement is a single canonical script with byte-equal cross-repo invocation
date: 2026-09-25
related:
  - AGENTS.md (research-institution, math, pi_monitor, kaplansky)
  - @ADR-0006-research-institution-scope
  - @INV-0095-prg-anchor-ownership
  - @CTR-0095-prime-directive-check-script-contract
  - @INV-0093-institution-green-gate-is-canonical-wiring-evidence
supersedes: []
---

# ADR-0095: Prime-directive mechanical enforcement is a single canonical script with byte-equal cross-repo invocation

## Context

The four-repo `AGENTS.md` institution-wide prevention section
mandates that durable code must not reference transient literals
(`plan-NNN`, `Spec-NNN`, `spec NNN`, etc.). Until this entry,
the prevention was enforced by two parallel mechanisms whose
drift could not be measured:

1. **Shell-script grep** —
   `research-institution/scripts/check-prime-directive.sh`
   (and symlinks in the three sibling repos). Runs at CI merge
   time and on operator demand (`make check-prime-directive`).
2. **TypeScript pi extension** —
   `~/.pi/agent/extensions/prime-directive-guard.ts`. Blocks
   `write` / `edit` tool calls whose content carries a transient
   literal.

The two mechanisms were not anchored to a durable ADR; each
could be amended without consulting the other; and there was
no byte-equivalence test ensuring that adding a sanctioned
glob to one surface propagated to the other.

## Decision

Prime-directive enforcement is **one** canonical artifact
(`scripts/check-prime-directive.sh`) with **byte-equal**
cross-repo invocation. Sibling repos hold a symlink (or a
byte-diff-equivalent copy) at
`<sibling>/scripts/check-prime-directive.sh`; the canonical
text lives only in `research-institution/scripts/`.

The strengthened regex is pinned at
`@CTR-0095-prime-directive-check-script-contract` and is the
single source of truth. Any change to the regex requires
updating both this ADR and the contract in the same commit.

The script exposes three modes:

- **default** — print hits, exit 0 always.
- **`--enforce`** — exit 1 on any hit; CI merge gate.
- **`--selftest`** — emit a deterministic multi-line report
  asserting the canonical pattern is present and the
  sanctioned-globs list is recognised; exit 0. Used by
  `test_canonical_script_identity.py` to assert byte-equal
  behaviour across the four repos.

## Boundary

- **research-institution** owns the canonical script and
  the canonical exemption registry
  (`.specify/memory/transient-exemptions.toml`).
- **math / pi_monitor / kaplansky** own a symlink (or
  byte-diff-equivalent copy) and a cross-reference paragraph
  in their `AGENTS.md` pointing at the canonical script +
  registry.
- **entry 09** reworks the pi extension to read the
  exemption registry (today it ships a hard-coded list) and
  to consult the strengthened regex pinned by
  `@CTR-0095-prime-directive-check-script-contract`.

## Consequences

- Adding a sanctioned transient path is a single-file edit
  (the registry) + a single-test edit (`test_canonical_script_identity.py`
  picks up the change automatically).
- Removing a sanctioned path requires bumping the
  exemption row's `expiry_spec_id` to the entry that retires
  it; the cycle adapter GC's expired rows at audit-close-out.
- The four-repo `AGENTS.md` institution-wide prevention
  block becomes a thin pointer at the canonical text
  instead of a duplicated paragraph.

## Cross-references

- `@INV-0095-prg-anchor-ownership` — who owns what durable
  record across the institution.
- `@CTR-0095-prime-directive-check-script-contract` —
  pins the regex, sanctioned-globs list, and exit-code
  behaviour.
- `.specify/memory/constitution-verify.md` §10 (verify-
  constitution's prime-directive mechanical enforcement
  section).
