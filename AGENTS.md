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

- **Anchor ID namespace convention.** Each repo (`math`,
  `research-institution`, `pi_monitor`, `kaplansky`) has its
  own `adr-NNNN` / `inv-NNNN` / `ctr-NNNN` / `con-NNNN`
  numbering — the same ID in two repos is allowed and refers
  to *different records*. The cross-repo registry
  (`docs/semantic/SEMANTIC_REGISTRY.md`) disambiguates by
  listing each anchor's repo. **Exception:** two records in
  different repos with the same ID and the same kind
  (e.g. two `@CTR-0095-live-...` contracts in math and
  research-institution) is a **real RC0 contradictory
  authority** — one must be renumbered to a free ID before
  cross-repo references are written. The renumbering done
  for plan-013 (`@CTR-0095` → `@CTR-0100`) is the canonical
  example.

- **The prime-directive grep** (run before every commit that
  touches a durable path) is the canonical enforcement. The
  strengthened pattern catches every variant agents write —
  `plan-013`, `Plan-013`, `PLAN_013`, `Plan 002`, `plan013`,
  `spec-011`, `Spec-009`, `spec 011` — and rejects
  false-positives like `planner`, `specify`, `spec_kit`:

  ```bash
  # Canonical strengthened pattern (ERE; portable across grep -E / bash)
  (\b[Pp][Ll][Aa][Nn]|\b[Ss][Pp][Ee][Cc])[-_ ]?[0-9]{2,}
  ```

  Run the gate locally with `make check-prime-directive`
  (calls `scripts/check-prime-directive.sh`); it exits
  non-zero on any unsanctioned hit and prints the
  `file:line` list. The CI gate is the same script, wired
  into each repo's Makefile.

  **Prevention at the agent layer.** A pi extension
  (`~/.pi/agent/extensions/prime-directive-guard.ts`)
  hooks `tool_call` for `write` and `edit` and blocks any
  attempted write that contains a forbidden literal. The
  block message points the agent at the canonical
  durable-anchor mapping (see "Anchor ID namespace
  convention" above). The extension auto-loads; no manual
  configuration is required. Attempts are logged to
  `.pi/prime-directive-violations.log` per repo so
  operators can see which agents are still writing the
  forbidden forms.

  When the extension blocks you, rewrite the content to
  cite the durable anchor (`@ADR-NNNN`, `@INV-NNNN`,
  `@CTR-NNNN`) instead of the transient literal. If your
  file is one of the sanctioned paths (AGENTS.md,
  closure-audit.md, transient plan dirs under `.pi-glla/`
  or `.agents/transient/`, vendored `.venv/`, etc.), the
  reference is allowed through.

  Hits outside the sanctioned exception classes are
  blocking defects under the corresponding plan's
  stop-the-line conditions.

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
4. Run `bash scripts/verify-institution.sh` to confirm
   the institution is wired on this machine. (The
   `green-gate/check-institution.sh` shim still works for
   backward compat; `scripts/verify-institution.sh` is
   preferred — it sets `RESEARCH_INSTITUTION_VWIRE_DIRECT=1`
   so the operator gets a clean answer when math-engine has
   unrelated drift in pyramid-inversion. See
   `docs/operations/launch-kaplansky-autonomously.md` for
   the full operator recipe.)
5. If the gate is GREEN, decide what work to do next based
   on the durable semantic records under `docs/semantic/`.
   If RED, the gate output names the failing stage; the doc
   above lists each common failure mode and its fix.

## Cross-references

- `~/Documents/andrei/math/AGENTS.md` — math-engine's
  prime directive (the canonical reference).
- `~/Documents/andrei/math/docs/semantic/` — math-engine's
  durable semantic records.
- `docs/operations/launch-kaplansky-autonomously.md` —
  the operator's one-pager (single canonical recipe).
- `docs/operations/research-institution-quickstart.md` —
  historical operator quickstart (still valid; launches the
  same path with different entry points).
- `catalog/programs.toml` — declarative program registry.
