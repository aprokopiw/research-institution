---
id: CTR-0096
kind: contract
status: draft
title: Audit-close-out runtime-evidence contract
date: 2026-09-25
related:
  - @ADR-0096-audit-close-out-runtime-evidence
  - @ADR-0095-prime-directive-mechanical-enforcement
  - @CTR-0095-prime-directive-check-script-contract
  - pi_monitor.work.sources.spec_kit_cycle._audit_close_out_state
  - research-institution/scripts/check-audit-close-out.sh
supersedes: []
---

# CTR-0096: Audit-close-out runtime-evidence contract

## Purpose

Pin the file shape + inviolable fields of the per-entry
runtime-evidence JSON produced by
`research-institution/scripts/check-audit-close-out.sh`. This
contract is the durable mirror of the helper that
`_audit_close_out_state` reads; without it, the helper's
output is unwitnessable across cycles.

## File location

For each entry slug `<slug>` belonging to the eleven-entry
program:

```
.specify/specs/<slug>/.pi-prime-attestations/<slug>.audit.json
```

The directory is created on first run; the file is
overwritten each time the verifier is run for that entry. The
file's parent directory is the same one as the existing
attestation JSON; both share the same per-entry exemption
surface.

## Schema

```jsonc
{
  "schema_version": 1,
  "slug": "<entry-slug>",
  "owner_repo": "<owner_repo-declared-in-META>",
  "completion_sha": "<current owner_repo HEAD reachable sha>",
  "completion_sha_history": [
    "<prior sha 1>",
    "<prior sha 2>"
  ],
  "row_count": 12,  // or 17 for entry 02
  "all_pass": true,
  "gate_report_digest": "sha256...",
  "evaluated_at_unix": 1234567890.0,
  "evaluated_by": "research-institution/scripts/check-audit-close-out.sh",
  "rows": [
    {
      "i": 1,
      "clause_summary": "<verbatim from META column 2>",
      "verifier": "<verbatim from META column 3>",
      "result": "PASS",
      "evidence": "exit=0 stdout=<...truncated>"
    }
  ],
  "unsanctioned_anomalies": []
}
```

### Required keys (reject if missing)

- `schema_version: int = 1`
- `slug: str` matching the directory name
- `owner_repo: str` matching `META.md [meta] owner_repo`
- `completion_sha: str (40-char hex)` reachable in
  `owner_repo`'s history via `git cat-file -e`
- `row_count: int > 0`
- `all_pass: bool` true iff every row's `result == "PASS"`
- `gate_report_digest: str (64-char hex)` equal to
  `sha256(canonical_rows_text || config_fingerprint)` where
  `config_fingerprint` matches the cycle adapter's v2 form.
- `evaluated_at_unix: float` POSIX time at the run.
- `rows: list` of length `row_count`, each row carrying
  `i`, `clause_summary`, `verifier`, `result`, `evidence`.

### Computable keys (rejected if mismatched)

- `gate_report_digest` MUST equal
  `sha256(canonical_rows_text || config_fingerprint)`
  recomputed by the cycle adapter's `_compute_attestation_digest`
  helper, where `canonical_rows_text` is the
  newline-joined triple `(i, clause_summary, verifier, result)`
  for every row.

### Optional keys

- `completion_sha_history`: list of prior SHAs no longer
  reachable in `owner_repo`. Each element carries
  `runtime_unreachable = true` annotation per
  `@ADR-0096-audit-close-out-runtime-evidence` clause 3.

## Verifier behaviour (scripts/check-audit-close-out.sh)

The verifier's job, in order:

1. Walk `META.md` from the entry directory. Parse the
   twelve-row (or seventeen-row) `| # | Clause | Verified
   by | Result |` table; tolerate Markdown table headers
   and separator rows; ignore rows that don't match the
   schema.
2. For each row whose `Verified by` column names a
   dispatchable command (`bash ...`, `python -m pytest ...`,
   `MATHLINT_COLLECT_ONLY=1 python -m pytest ...`,
   `tomllib.loads(...)`, `git cat-file -e $sha`,
   `tests/static/test_<name>.py::test_<id>`, etc.):
   a. Substitute `$sha` with the entry's
      `completion_sha`.
   b. Run the command in `owner_repo`'s worktree (the
      script walks the four-repo layout from a top-level
      repo map; the canonical installation is `~/Documents/andrei`).
   c. Capture exit code and stdout/stderr.
   d. Decide PASS/FAIL/BLOCKED per the documented clause
      semantics (e.g. `pytest ...` exit 0 = PASS;
      `tomllib.loads` parses = PASS; `git cat-file -e`
      exit 0 = PASS).
3. Write the audit JSON atomically (tmpfile + rename) to
   the canonical location.
4. Print one summary line per row, then a final
   `all_pass=True` or `all_pass=False`.

## Cycle adapter contract

`pi_monitor.work.sources.spec_kit_cycle._audit_close_out_state`
MUST:

1. Continue to require the v2 attestation digest match.
2. Additionally, **require** the audit JSON to exist with
   `all_pass = True` and a `gate_report_digest` matching
   `sha256(canonical_rows_text || config_fingerprint)`
   recomputed under the cycle's current
   `config_fingerprint`.

The intersection is reported as `closed=True`. Either
condition failing flips the audit-close-out tick back to
`[ ]` and emits a structured reason code
(`attestation_digest_mismatch`,
`audit_json_missing`,
`audit_json_all_pass_false`,
`audit_json_gate_digest_mismatch`,
`completion_sha_unreachable`).

## Tests (entry 09 owns)

- `tests/test_spec_kit_cycle_source.py::test_audit_close_out_rejects_witness_only_metas`
  — synthesize a spec dir with META + valid v2 attestation
  but no audit JSON; expect `closed=False` with reason
  `audit_json_missing`.
- `tests/test_spec_kit_cycle_source.py::test_audit_close_out_accepts_metas_with_passing_audit`
  — synthesize a spec dir with META + valid v2 attestation
  + audit JSON carrying `all_pass=True` and matching
  gate_report_digest; expect `closed=True`.
- `tests/test_spec_kit_cycle_source.py::test_audit_close_out_rejects_mismatched_gate_digest`
  — same plus tampered gate_report_digest; expect
  `closed=False` with reason
  `audit_json_gate_digest_mismatch`.
- `tests/test_spec_kit_cycle_source.py::test_audit_close_out_rejects_unreachable_completion_sha`
  — synthesize a spec dir whose META `completion_sha`
  isn't reachable; expect `closed=False` with reason
  `completion_sha_unreachable`.

## Boundary

- The audit JSON schema is strictly versioned. Any new
  required key bumps `schema_version`. Cycle adapter and
  verifier are kept in lockstep via the canonical contract
  document.
- Migration from witness-only to runtime-evidence META is
  *additive*: the META's twelve-row table is kept; only
  its `result` column is no longer authoritative at the
  cycle layer.

## Cross-references

- `@ADR-0096-audit-close-out-runtime-evidence` — rationale.
- `@CTR-0095-prime-directive-check-script-contract` —
  precedent for "verifier is the canonical script, not the
  prose."
- `@INV-0095-prg-anchor-ownership` — owns the canonical
  registry + cross-repo anchor registration.
