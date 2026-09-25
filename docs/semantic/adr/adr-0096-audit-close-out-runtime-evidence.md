---
id: ADR-0096
kind: decision
status: draft
title: Audit-close-out is runtime evidence, not witness prose
date: 2026-09-25
related:
  - AGENTS.md (research-institution)
  - @ADR-0095-prime-directive-mechanical-enforcement
  - @INV-0095-prg-anchor-ownership
  - @CTR-0095-prime-directive-check-script-contract
  - pi_monitor.work.sources.spec_kit_cycle._audit_close_out_state
  - .specify/specs/{00..10}-*/META.md
supersedes: []
---

# ADR-0096: Audit-close-out is runtime evidence, not witness prose

## Context

The Spec-Kit cycle adapter
(`pi_monitor.work.sources.spec_kit_cycle`) flips an entry's
synthetic `[audit-close-out]` tickable to `[x]` when its
`_audit_close_out_state` returns `closed=True`. Until this
ADR, that helper answered `closed=True` on **two** conditions:

1. The entry's `META.md` parses as TOML frontmatter and every
   required field is populated; AND
2. The per-entry attestation JSON at
   `.specify/specs/<slug>/.pi-prime-attestations/<slug>.json`
   carries a `digest` matching
   `sha256(completion_sha || config_fingerprint)`.

Condition (2) is a *signature* comparison: it binds the
completion_sha and the cycle's configuration surface (root +
task_globs) into a v2 fingerprint, but says nothing about
whether the cannot-claim-done clauses the META claims were
*actually* satisfied at the candidate-completion SHA.

A re-emit of the attestation JSON is sufficient to flip any
entry from `closed=False` to `closed=True`; nothing forces
the verifier commands listed in META's twelve-row table (the
"Verified by" column) to actually run.

A cycle restart in late-2025 surfaced two facts about entry
02 (`02-fake-pi-consolidation`) and entry 03
(`03-domain-verification-completeness`) on this checkout:

- The `completion_sha` recorded in META did not exist in the
  entry's `owner_repo` git history. The META claim
  ("Ratified 2026-09-25 against commit X") was unsupportable
  from the actual repo state.
- Every cannot-claim-done clause nevertheless *did* pass when
  re-run against the current `owner_repo` HEAD: the static
  checks, the prime-directive grep, the `Makefile` targets,
  and the registry row count for the entry's
  `expiry_spec_id` were all green.

The cycle reported `closed=True` for both entries before the
SHA fix; the v2 fingerprint comparator had zero way to
notice the wrong SHA, because the fingerprint only mixes the
SHA and the config, not the SHA's existence.

This is the "witness vs fact" gap: META claims a closed
state, the cycle reports a closed state, but the *underlying*
candidate-completion SHA either doesn't exist or has been
re-stamped to a different commit without re-running the
cannot-claim-done clauses.

## Decision

Audit-close-out is **runtime evidence**, not witness prose.
Three concurrent changes enforce that:

### 1. The META twelve-row table is machine-verifiable

A new verifier (`research-institution/scripts/check-audit-close-out.sh`)
walks every `META.md`, parses its twelve-row table, **dispatches**
the "Verified by" command against the **current** `owner_repo`
HEAD, and records the result in
`.specify/specs/<slug>/.pi-prime-attestations/<slug>.audit.json`:

```json
{
  "slug": "02-fake-pi-consolidation",
  "completion_sha": "<current owner_repo HEAD>",
  "row_count": 17,
  "rows": [
    {"i": 1, "result": "PASS", "verifier": "<verifier command>"},
    ...
  ],
  "all_pass": true,
  "gate_report_digest": "sha256(canonical_rows_text | config_fingerprint)",
  "evaluated_at_unix": <float>,
  "evaluated_by": "scripts/check-audit-close-out.sh"
}
```

`all_pass` is True only if every dispatched verifier exits 0
or otherwise returns the documented PASS condition. The
verifier is the **only** writer of the row `result` field;
META's prose-level `PASS` column is preserved for human
readability but is no longer consulted by the cycle.

### 2. The cycle's `_audit_close_out_state` accepts witness only with a matching runtime audit

`_audit_close_out_state` now requires **both** the v2
attestation digest match AND a current
`*.audit.json` whose `all_pass` field is True and whose
`gate_report_digest` is consistent with the entry's
`completion_sha` (no retroactive re-stamping without a fresh
audit run). The cycle's audit-close-out gate is the
*intersection* of signature + runtime evidence, not the
union.

### 3. Re-stamping requires re-running

When the entry's `completion_sha` is updated (e.g. SHA-fix
forward-port), a `completion_sha_history` list keeps the
prior SHA. The cycle refuses to flip audit-close-out `[x]`
if `completion_sha_history` carries any prior SHA whose
`git cat-file -e` answer is miss in `owner_repo`'s history
— *unless* that history SHA is annotated as
`runtime_unreachable = true` with a durable pointer to the
ADR/INV that documents the re-stamp.

### Boundary

- **research-institution** owns
  `scripts/check-audit-close-out.sh` and the audit JSON
  schema; mirror invariants in
  `@CTR-0096-audit-close-out-runtime-evidence-contract`.
- **pi_monitor** owns the cycle-adapter change
  (`_audit_close_out_state` becomes intersection-based) plus
  the new test cases in
  `tests/test_spec_kit_cycle_source.py`.
- Each entry's `owner_repo` runs `check-audit-close-out.sh`
  against its own HEAD on every CI merge and on operator
  demand; the cycle's external observation accepts the
  audit JSON as the cannot-claim-done witness.

### Consequences

- A re-emit of `.pi-prime-attestations/<slug>.json` requires
  a fresh `*.audit.json` from `check-audit-close-out.sh`.
  Stale attestations and stale audits both fail the gate.
- Re-stamping (e.g. forward-porting a SHAs across
  refactors) is supported but is auditable: every prior
  SHA in `completion_sha_history` either remains reachable
  in `owner_repo` or carries a `runtime_unreachable = true`
  annotation citing the durable record that justifies the
  re-stamp.
- The verify command list for every cannot-claim-done
  clause becomes machine-addressable. Future entries no
  longer carry the risk that a "PASS" prose row is
  unrunnable in CI.

## Boundary of acceptable change

This ADR is reversible only by adding a new ADR that names
this one in `supersedes`, AND that documents why runtime
evidence is undesirable for that specific case (e.g. a
test-as-policy clause where the verifier is itself
non-deterministic and *must* be witness-only).

## Cross-references

- `@CTR-0095-prime-directive-check-script-contract` —
  precedent for "verifier is a script, not a sentence."
- `@ADR-0095-prime-directive-mechanical-enforcement` —
  sibling ADR; the prime-directive grep is the entry-09
  precedent for runtime verification. This ADR generalizes
  the same discipline to the audit-close-out gate.
- `.specify/specs/00-verify-constitution-ratification/META.md`
  row #9 — `git cat-file -e $sha` was an early witness of
  this exact gap.
- `pi_monitor.work.sources.spec_kit_cycle._audit_close_out_state`
  — the helper this ADR constrains.
