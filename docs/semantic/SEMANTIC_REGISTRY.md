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
- `pi_monitor/docs/semantic/{adr,invariants,contracts,conventions}/`
- `kaplansky/docs/semantic/{adr,invariants,contracts,conventions}/`

A fresh agent reading the worker prompt sees an anchor
reference (e.g. `@ADR-0091`) and has to `rg` to find where it
lives. This registry collapses that lookup into one read.

The registry is **not authoritative** — the source of truth is
always the ADR / INV / CTR / CON file itself. The registry just
says "to read `@ADR-0091`, look at `pi_monitor/docs/semantic/adr/...`".

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
| `@CTR-0095` | `research-institution/docs/semantic/contracts/` | live-source snapshot — math-side consult adapter for source-decision flow |
| `@INV-0093` | `research-institution/docs/semantic/invariants/` | institution green gate is canonical wiring evidence |
| `@INV-0094` | `research-institution/docs/semantic/invariants/` | no-delta loop is broken by source-side stagnation consult, not by supervisor-side circuit |

Cross-repo-request ADRs (subdirectory `cross-repo-requests/`):

| Anchor  | Lives in | Title (abridged) |
|---------|----------|------------------|
| `@ADR-0007` (cross-repo) | `research-institution/docs/semantic/adr/cross-repo-requests/` | mathlint architect-review must accept --program `<name>` |
| `@ADR-0008` | `research-institution/docs/semantic/adr/cross-repo-requests/` | mathlint `decide_next` source-side repeat limit |
| `@ADR-0009` | `research-institution/docs/semantic/adr/cross-repo-requests/` | pi_monitor supervisor-side repeat circuit (**superseded by `@ADR-0011`**) |
| `@ADR-0010` | `research-institution/docs/semantic/adr/cross-repo-requests/` | mathlint `decide_next` `kind` discriminator must use the canonical lowercase form |
| `@ADR-0011` | `research-institution/docs/semantic/adr/cross-repo-requests/` | stagnation handling is a source decision, not a supervisor decision |

### Math-engine anchors (most-cited)

| Anchor | Lives in | Title (abridged) |
|--------|----------|------------------|
| `@ADR-0014` | `math/docs/semantic/adr/` | mathlint does not import program-named modules |
| `@ADR-0091` | `math/docs/semantic/adr/` | mathlint does not ship program launchers |
| `@ADR-0097` | `math/docs/semantic/adr/` | live source snapshot — consult adapter exposing the kernel to the live source-decision flow (plan-013 sibling) |
| `@INV-0006` | `math/docs/semantic/invariants/` | (math) |
| `@INV-0093` | `math/docs/semantic/invariants/` | (math; superset of institution's INV-0093) |

### Pi-monitor anchors (most-cited)

| Anchor | Lives in | Title (abridged) |
|--------|----------|------------------|
| `@ADR-0021` | `pi_monitor/docs/semantic/adr/` | self-supervision: pi-monitor supervises itself |
| `@ADR-0024` | `pi_monitor/docs/semantic/adr/` | closed strict task-marker vocabulary |
| `@CON-0002` | `pi_monitor/docs/semantic/contracts/` | (paired with ADR-0024) |
| `@INV-0022` | `pi_monitor/docs/semantic/invariants/` | (audit-chain-break contract) |

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
