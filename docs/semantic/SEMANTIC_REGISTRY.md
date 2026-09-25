# Semantic Registry — durable anchor index

**Status:** Operator-facing single source of truth for every
durable ADR / INV / CTR / CON anchor across the research
institution. The handoff's §6.G item.

## Why this exists

Durable anchors (`@ADR-NNNN`, `@INV-NNNN`, `@CTR-NNNN`,
`@CON-NNNN`) are scattered across `docs/semantic/` directories
in three repos:

- `research-institution/docs/semantic/{adr,invariants,contracts}/`
- `math/docs/semantic/{adr,invariants,contracts,conventions}/`
- `pi_monitor/docs/semantic/{adr,invariants,contracts,constraints}/`
  (pi_monitor's primary ADRs live at `pi_monitor/docs/adr/`)
- `kaplansky/docs/semantic/{adr,invariants,contracts,conventions}/`

A fresh agent reading the worker prompt sees an anchor
reference (e.g. `@ADR-0091`) and has to `rg` to find where it
lives. This registry collapses that lookup into one read.

The registry is **not authoritative** — the source of truth is
always the ADR / INV / CTR / CON file itself. The registry just
says "to read `@ADR-0091`, look at `math/docs/semantic/adr/...`".

## Index

### Research-institution anchors

| Anchor  | Lives in | Title (abridged) |
|---------|----------|------------------|
| `@ADR-0001` | `research-institution/docs/semantic/adr/` | kaplansky uses pi oauth, not openai api key |
| `@ADR-0002` | `research-institution/docs/semantic/adr/` | kaplansky operator UX as thin skill wrapper |
| `@ADR-0003` | `research-institution/docs/semantic/adr/` | kaplansky slow-iteration safeguards |
| `@ADR-0004` | `research-institution/docs/semantic/adr/` | monitor TUI launcher |
| `@ADR-0005` | `research-institution/docs/semantic/adr/` | reasoning tail |
| `@ADR-0006` | `research-institution/docs/semantic/adr/` | research-institution scope |
| `@ADR-0007` | `research-institution/docs/semantic/adr/` | research-institution owns work-source provider |
| `@ADR-0011` | `research-institution/docs/semantic/adr/cross-repo-requests/` | stagnation handling is a source decision, not a supervisor decision (supersedes `@ADR-0009`) |
| `@CTR-0088` | `research-institution/docs/semantic/contracts/` | catalog schema contract |
| `@CTR-0094` | `research-institution/docs/semantic/contracts/` | work-source provider dispatch envelope |
| `@CTR-0100` | `research-institution/docs/semantic/contracts/` | live-source snapshot — math-side consult adapter for source-decision flow |
| `@INV-0093` | `research-institution/docs/semantic/invariants/` | institution green gate is canonical wiring evidence |
| `@INV-0094` | `research-institution/docs/semantic/invariants/` | no-delta loop is broken by source-side stagnation consult, not by supervisor-side circuit |
| `@ADR-0095` | `research-institution/docs/semantic/adr/` | prime-directive mechanical enforcement is a single canonical script with byte-equal cross-repo invocation |
| `@INV-0095` | `research-institution/docs/semantic/invariants/` | prime-directive durable anchors are owned by research-institution; siblings cite by reference |
| `@CTR-0095` | `research-institution/docs/semantic/contracts/` | prime-directive check-script contract — regex, sanctioned-globs, exit codes, selftest |
| `@ADR-0096` | `research-institution/docs/semantic/adr/` | audit-close-out is runtime evidence, not witness prose — cannot-claim-done rows are machine-verifiable |
| `@CTR-0096` | `research-institution/docs/semantic/contracts/` | audit-close-out runtime-evidence contract — schema for `.pi-prime-attestations/<slug>.audit.json` and cycle adapter intersection gate |

Cross-repo-request ADRs (subdirectory `cross-repo-requests/`):

| Anchor  | Lives in | Title (abridged) |
|---------|----------|------------------|
| `@ADR-0007` (cross-repo) | `research-institution/docs/semantic/adr/cross-repo-requests/` | mathlint architect-review must accept --program `<name>` |
| `@ADR-0008` | `research-institution/docs/semantic/adr/cross-repo-requests/` | mathlint `decide_next` source-side repeat limit |
| `@ADR-0009` | `research-institution/docs/semantic/adr/cross-repo-requests/` | pi_monitor supervisor-side repeat circuit (**superseded by `@ADR-0011`**) |
| `@ADR-0010` | `research-institution/docs/semantic/adr/cross-repo-requests/` | mathlint `decide_next` `kind` discriminator must use the canonical lowercase form (closed 2026-09-20) |
| `@ADR-0011` | `research-institution/docs/semantic/adr/cross-repo-requests/` | stagnation handling is a source decision, not a supervisor decision (shipped @ADR-0011) |

### Math-engine anchors (most-cited)

| Anchor | Lives in | Title (abridged) |
|--------|----------|------------------|
| `@ADR-0014` | `math/docs/semantic/adr/` | mathlint does not import program-named modules |
| `@ADR-0088` | `math/docs/semantic/adr/` | self-test fixture classification (sample fixture is a fixture, not a proof program) |
| `@ADR-0089` | `math/docs/semantic/adr/` | self-test fixture as canonical CI fixture |
| `@ADR-0091` | `math/docs/semantic/adr/` | mathlint does not ship program-specific launchers |
| `@ADR-0097` | `math/docs/semantic/adr/` | live source snapshot — consult adapter exposing the kernel to the live source-decision flow (@ADR-0011 sibling) |
| `@CTR-0020` | `math/docs/semantic/contracts/` | three-repo autonomy wire contract |
| `@CTR-0085` | `math/docs/semantic/contracts/` | sample-program dispatch envelope shape |
| `@INV-0006` | `math/docs/semantic/invariants/` | deterministic registry and typed effects |
| `@INV-0088` | `math/docs/semantic/invariants/` | self-test fixture requires no external state |
| `@INV-0093` | `math/docs/semantic/invariants/` | (math; superset of institution's INV-0093) |

### Pi-monitor anchors (most-cited)

| Anchor | Lives in | Title (abridged) |
|--------|----------|------------------|
| `@ADR-0019` | `pi_monitor/docs/adr/0019-live-campaign-sequencing.md` | cross-repository ownership and sequential integration (**superseded** by `@ADR-0001` + `@ADR-0013`) |
| `@ADR-0021` | `pi_monitor/docs/adr/0021-self-supervision-pi-monitor.md` | self-supervision of pi_monitor |
| `@ADR-0024` | `pi_monitor/docs/adr/0024-closed-strict-task-marker-vocabulary.md` | closed, strict task-marker vocabulary for the Spec-Kit WorkSource |
| `@CTR-0001` | `pi_monitor/docs/semantic/contracts/` | work sources and runtimes exchange revisioned execution facts |
| `@CTR-0002` | `pi_monitor/docs/semantic/contracts/` | worker outcomes are bounded and non-authoritative |
| `@CTR-0003` | `pi_monitor/docs/semantic/contracts/` | external work-source transport is bounded and fail-closed |

## Operator workflow

To look up an anchor:

1. `rg -l "@ADR-NNNN" research-institution/ math/ pi_monitor/`
   finds every place the anchor is cited (worker / supervisor / docs).
2. The line above gives the file; open it for the durable record.

To register a new anchor:

1. Create the file under `docs/semantic/{adr,invariants,contracts}/`
   in the appropriate repo (see "research-institution anchors" above
   for the rule on who owns what).
2. Add an entry to this registry's index table.
3. Update any cross-repo references to use the new anchor.

## Why not auto-generated?

A nightly build script could `walk()` the `docs/semantic/`
tree and emit this index. We deliberately do not: the registry
is small (≤ 30 entries today), the cost of a fresh agent
reading the registry is sub-second, and a generated artifact
introduces a build-step dependency the operator one-pager
already avoids. When the registry exceeds ~50 entries,
revisit.

## Cross-references

- `docs/operations/launch-kaplansky-autonomously.md` — the
  operator one-pager that cites many of these anchors.
- `math/AGENTS.md` — canonical prime-directive reference for
  durable vs transient classification.
- `pi_monitor/AGENTS.md` — pi-monitor's prime-directive
  equivalent.
- `.specify/memory/constitution-verify.md` — the canonical
  verify-constitution (introduced 2026-09-25 by spec
  `00-verify-constitution-ratification`); ratified durable
  anchors referenced from this registry.
