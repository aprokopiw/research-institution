---
id: INV-0095
kind: invariant
status: active
title: Prime-directive durable anchors are owned by the research-institution repo; sibling repos cite by reference
introduced: 2026-09-25
related:
  - @ADR-0095-prime-directive-mechanical-enforcement
  - @CTR-0095-prime-directive-check-script-contract
  - @ADR-0006-research-institution-scope
  - @INV-0093-institution-green-gate-is-canonical-wiring-evidence
scope: research_institution, math, pi_monitor, kaplansky
---

# INV-0095: Prime-directive durable anchors are owned by the research-institution repo; sibling repos cite by reference

## Statement

Every durable anchor that codifies a prime-directive rule
(`@ADR-0095-*`, `@INV-0095-*`, `@CTR-0095-*`) lives canonically
in `research-institution/docs/semantic/{adr,invariants,contracts}/`.
Sibling repos (math, pi_monitor, kaplansky) may **cite** these
anchors but may not **author** anchors that overlap in topic
(durable ownership of prime-directive enforcement is centralised).

When a sibling repo introduces a new prime-directive concern
that warrants a durable record, it authors the record in
research-institution via a cross-repo ADR request (under
`docs/semantic/adr/cross-repo-requests/`) that names the
sibling repo as the originating authority; the canonical
anchor still lives in research-institution.

The exemption registry
(`.specify/memory/transient-exemptions.toml`) is the single
canonical list of sanctioned-globs that the strengthened
grep and the pi extension both consult. A new row in this
registry is the only sanctioned way to add a transient
literal exception.

## Why it matters

- A fresh agent inspecting any sibling repo can find the
  prime-directive rule by following one link:
  `<sibling>/AGENTS.md` → `research-institution/scripts/check-prime-directive.sh`
  → `@ADR-0095` + `@CTR-0095`.
- Drift between sibling `AGENTS.md` paragraphs and the
  canonical script becomes impossible because only one
  paragraph exists.
- The institution-wide semantic registry
  (`docs/semantic/SEMANTIC_REGISTRY.md`) lists every prime-
  directive anchor in one place; a maintainer updating one
  rule sees all consumers.

## Enforcement

- `tests/static/test_constitution_consistency.py` greps every
  `AGENTS.md` for the canonical cross-reference phrase and
  rejects deviations.
- `tests/static/test_canonical_script_identity.py` asserts the
  four `scripts/check-prime-directive.sh` invocations produce
  byte-equal output under `--selftest`.
- The strengthened regex
  (`@CTR-0095-prime-directive-check-script-contract`) is
  byte-equal across the script and the pi extension.

## Boundary cases

- Math owns durable records for math-domain concerns
  (e.g. `@INV-0088-sample-fixture-requires-no-external-state`).
  Prime-directive anchors are the **only** kind that
  research-institution owns cross-repo.
- The pi extension's `SANCTIONED_PATH_PATTERNS` list is
  the **runtime mirror** of the canonical registry; entry
  09 finishes the bridge so a registry bump reloads the
  extension without operator intervention.

## Cross-references

- `@ADR-0095-prime-directive-mechanical-enforcement` —
  canonical script + byte-equal cross-repo invocation.
- `@CTR-0095-prime-directive-check-script-contract` —
  regex + sanctioned-globs + exit-code contract.
- `.specify/memory/constitution-verify.md` §12 (institution-
  wide semantic-record ownership).
- `.specify/memory/transient-exemptions.toml` (canonical
  exemption registry).
