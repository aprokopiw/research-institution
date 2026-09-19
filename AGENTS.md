# AGENTS.md — research-institution prime directive

This repo is governed by the same prime directive as math-engine
(per `~/Documents/andrei/math/AGENTS.md`):

- **Durable artifacts** (this `AGENTS.md`, `README.md`,
  `pyproject.toml`, `LICENSE`, the contents of `catalog/`,
  `green-gate/`, `scripts/`, `docs/`, and the durable
  semantic records under `docs/semantic/{adr,invariants,contracts}/`)
  must not reference transient artifacts (per-PP ledgers,
  per-PP plan documents, plan-specific skill files, runbook
  scripts under `.pi-glla/`). Transient references rot: when
  the plan is deleted, the comment becomes a pointer to
  nothing, and a fresh agent that reads the codebase spends
  context reconstructing what the dead reference meant.

- Cite durable anchors instead: `@ADR-NNNN`, `@INV-NNNN`,
  `@CTR-NNNN`, `@CON-NNNN`. If a transient reference is
  genuinely necessary, it falls under one of the sanctioned
  exception classes enumerated in math-engine's `AGENTS.md`.

- **The prime-directive grep** (run before every commit that
  touches a durable path) is the canonical enforcement. Hits
  outside the sanctioned exception classes are blocking
  defects under the corresponding plan's stop-the-line
  conditions.

## This repo's relationship to math-engine's prime directive

This repo's durable artifacts MUST NOT cite math-engine's
plan-NNN identifiers (plan-005 through plan-011). When
this repo needs to cite math-engine-specific state, it
cites the durable `@ADR-NNNN` / `@INV-NNNN` /
`@CTR-NNNN` record in math-engine's `docs/semantic/`.

For example:
- Cite `@ADR-0014` (mathlint does not import
  program-named modules), NOT "plan-009 §3.4".
- Cite `@ADR-0091` (mathlint does not ship program
  launchers), NOT "plan-011 Phase Q.2".
- Cite `@INV-0093` (institution green gate is
  canonical wiring evidence), NOT "plan-011 §10
  Gate 1".

## Local-only exceptions (this repo's deviations)

Unlike math-engine, this repo has fewer sanctioned exception
classes because it ships no spec-kit or plan-NNN artifacts
of its own at present. As plans land that produce
research-institution-owned plan docs, the sanctioned
classes will be extended in math-engine's `AGENTS.md` and
the extension will be reflected here.

## Cold-start workflow

A fresh agent session receiving the cold prompt
`Run @research_institution_orient` should:

1. Read this `AGENTS.md` (the prime directive).
2. Read `README.md` (the repo's role in the institution).
3. Read `catalog/programs.toml` (the in-flight programs).
4. Run `bash green-gate/check-institution.sh --hermetic`
   to confirm the institution is wired on this machine.
5. Decide what work to do next based on the durable
   semantic records under `docs/semantic/`.

## Cross-references

- `~/Documents/andrei/math/AGENTS.md` — math-engine's
  prime directive (the canonical reference).
- `~/Documents/andrei/math/docs/semantic/` — math-engine's
  durable semantic records.
- `docs/operations/research-institution-quickstart.md` —
  the operator's one-pager.
- `catalog/programs.toml` — declarative program registry.
