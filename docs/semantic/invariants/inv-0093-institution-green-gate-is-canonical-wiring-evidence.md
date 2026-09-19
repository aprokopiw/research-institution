---
id: INV-0093
kind: invariant
status: active
title: Institution green gate is the canonical wiring evidence
introduced: 2026-09-19
related: [INV-0091, INV-0092, CTR-0088]
scope: research_institution, green_gate
---
# INV-0093: Institution green gate is the canonical wiring evidence

## Statement

`bash research-institution/green-gate/check-institution.sh`
printing `GREEN INSTITUTION READY` is the single canonical
evidence that the full institution (math-engine + pi_monitor
+ N research programs) is wired. When this gate is red,
the institution is NOT wired.

## Why it matters

The institution spans three repos (math-engine, pi_monitor,
N research programs). Without a single canonical green gate,
every operator must independently rediscover which
combination of scripts proves the institution is wired. The
green gate is the one-line answer for fresh operators.

## Enforcement

* `research-institution/green-gate/check-institution.sh
  --hermetic` exits 0 + prints `GREEN INSTITUTION READY`
  from a clean checkout with math-engine + kaplansky
  installed.
* The aggregator iterates `catalog/programs.toml` and
  dispatches each program's `check_program_script`.
* The aggregator runs math-engine's
  `check-local-system-readiness.sh` and (if on PATH)
  pi_monitor's `doctor`.

## Boundary cases

* The gate does NOT prove the institution can do live work
  (paired-smoke receipt, live kaplansky run). For live
  evidence, run `--live` mode (operator-only).
* The gate does NOT prove model credentials are valid;
  operators with credentials use `--live` instead.

## Cross-references

* `@INV-0091` — mathlint is program-agnostic.
* `@INV-0092` — pi_monitor is program-agnostic.
* `@CTR-0088` — the catalog schema.
* `research-institution/green-gate/check-institution.sh`
  — the gate implementation.
