---
id: CTR-0101
kind: contract
status: draft
title: Release-gate contract
date: 2026-09-25
related:
  - @CTR-0095-prime-directive-check-script-contract
  - @CTR-0096-audit-close-out-runtime-evidence-contract
  - @INV-0093-institution-green-gate-canonical
  - research_institution.gates.verify_simulation.release.ReleaseReport
  - research_institution.gates.verify_simulation.cli (--tier release)
supersedes: []
---

# CTR-0101: Release-gate contract

## Purpose

Pin the typed `ReleaseReport` shape + the seven closed
`ReleaseRow` rows that the release tier produces. The release
tier is the canonical close-out aggregator for entry 10
(`10-verification-release-closure`); every entry's META.md is
a witness to its own closed state, and the release report
aggregates every witness into a single PASS / FAIL verdict.

## File location

The release tier is invoked via:

```bash
python -m research_institution verify-simulation --tier release
```

It is the last tier the verify-simulation CLI exposes; the
output is a single `ReleaseReport` printed to stdout and a
typed verdict that the cycle adapter consumes on the entry-10
audit-close-out poll.

## Inviolable fields

The `ReleaseReport` dataclass owns exactly the following
fields; downstream code MUST NOT add new fields without
amending this contract:

```python
@dataclass(frozen=True, slots=True)
class ReleaseReport:
    verdict: str                       # "PASS" | "FAIL" | "BLOCKED"
    rows: tuple[ReleaseRow, ...]       # exactly 7 rows
    duration_seconds: float
    seed: int                          # deterministic
    artifacts_dir: Path                # written even on PASS
    gate_report_digest: str            # sha256 over the captured stdout
```

`__post_init__` rejects any report whose `rows` count is not
exactly 7; the closed set is enforced at construction time.

## Seven `ReleaseRow` names

The release tier asserts exactly seven rows, in this order:

| # | Row name | Meaning |
|---|---|---|
| 1 | `every_primary_tier_has_at_least_one` | every primary evidence tier has at least one tier-marker observed in `tests/` |
| 2 | `every_required_claim_has_evidence` | every claim in `CLAIM_MANIFEST.toml` has ≥1 current node-ID or scenario-ID |
| 3 | `every_scenario_has_metadata` | every scenario file has its metadata block |
| 4 | `every_critical_mutant_killed` | every critical mutant named in `mutation_critical_mutants.toml` is killed by a named scenario + test |
| 5 | `flake_audit_clean` | 20× repeated runs of `happy-three-cycle` produce zero flakes |
| 6 | `documentation_truth_clean` | the six forbidden primary-tier strings appear zero times in durable paths |
| 7 | `prime_directive_enforcement_clean` | `bash scripts/check-prime-directive.sh --enforce` reports 0 unsanctioned hits at the entry's HEAD |

Row 5 is hermetic today (5 inline runs, all PASS); the live
20× run is owned by entry 10's `--hours` analog when wired to
the launchd. The row accepts either hermetic (5 inline runs)
or full (20 repeated) evidence; both shapes produce a PASS.

## Verdict algebra

The report's `verdict` follows the gate-status algebra
(constitution-verify §3):

  * `PASS` — every row is `PASS` (NOT_APPLICABLE rows count
    as PASS).
  * `FAIL` — any row is `FAIL`.
  * `BLOCKED` — every row is `PASS` or `NOT_APPLICABLE` but
    one row required a runtime credential that the hermetic
    tier does not have (e.g. a live credential-gated tier).

The release tier today emits only `PASS` because all seven
rows are wired; future additions MAY introduce new
`BLOCKED` paths (e.g. the wheel-install live tier for
entry 08's compat-matrix when extended beyond the 4-cell
hermetic variant).

## Consumers

  * `pi_monitor.work.sources.spec_kit_cycle` — the cycle
    adapter reads `gate_report_digest` to gate the
    entry-10 audit-close-out tickable.
  * `scripts/spec-kit-cycle.sh --dry-run` — surfaces the
    seven rows at the operator's terminal.
  * `research_institution.gates.aggregate` — joins the
    release report with prior entry-level reports into the
    institution green gate.

## Schema_version

The `ReleaseReport` carries `schema_version = 1`. Future
amendments increment this version; v1 MUST NOT change
field names or row counts.

## Cross-references

  * `@CTR-0095-prime-directive-check-script-contract` —
    the canonical strengthened-grep contract; row 7 is a
    thin wrapper over this contract's `--enforce` mode.
  * `@CTR-0096-audit-close-out-runtime-evidence-contract` —
    the runtime-evidence contract; row 2 reads the same
    `CLAIM_MANIFEST.toml`.
  * `@INV-0093-institution-green-gate-canonical` — the
    release tier's `PASS` is the green-gate's
    canonical wiring evidence.
  * `@ADR-0095-prime-directive-mechanical-enforcement` —
    the entry 00 anchor for the canonical prime-directive
    enforcement.
