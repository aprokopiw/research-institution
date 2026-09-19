---
id: ADR-0006
kind: decision
status: accepted
title: Research-institution owns only the catalog, bootstrap, green gate, and dispatcher
date: 2026-09-13
related:
  - AGENTS.md
  - README.md
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0004
  - ADR-0005 (superseded)
supersedes: []
---

# ADR-0006: Research-institution owns only the catalog, bootstrap, green gate, and dispatcher

## Context

The 2026-09-13 hardening session revealed that research-institution had
accumulated application code (a reasoning tail, an artifacts tail, a
gate-check, a roadmap-gate reader) that duplicated logic owned by
mathlint (`mathlint architect-review`, `mathlint roadmap`,
`mathlint receipts`, `mathlint observability status_views`) and by pi
(`~/.pi/agent/sessions/...`). The duplication was scope creep:
research-institution had grown beyond what its own README and AGENTS.md
allow.

Per `README.md`:

> This repo **owns no application code**. It owns:
> - `catalog/programs.toml`
> - `green-gate/check-institution.sh`
> - `scripts/bootstrap-institution.sh`
> - `docs/operations/research-institution-quickstart.md`

Per `AGENTS.md` (cold-start workflow): the only durable artifacts an
agent needs to consult are the prime directive, README, the catalog,
and the green gate. Everything else is downstream.

## Decision

**Research-institution owns exactly four concerns, plus their supporting
artifacts:**

| Concern | Artifact | Scope |
|---|---|---|
| Declarative program registry | `catalog/programs.toml`, `catalog/schema.toml` | What programs exist; how to find them; how to install them |
| Bootstrap | `scripts/bootstrap-institution.sh` | Clone + install from a fresh checkout |
| Wiring evidence | `green-gate/check-institution.sh` | Cross-repo invariant: mathlint + pi_monitor + every catalog entry is wired |
| Dispatcher CLI | `research_institution/` Python package (Typer) | Catalog-driven dispatch to mathlint and pi_monitor commands |
| Operator one-pagers + durable ADRs | `docs/operations/`, `docs/semantic/adr/` | Documentation only; not application logic |

**Research-institution does NOT own:**

- Architecture-review gate logic — that's mathlint (`mathlint architect-review`,
  `mathlint architect-apply`, `mathlint integrity`).
- Receipts / audit-chain parsing — mathlint (`mathlint receipts`,
  `mathlint audit-chain-verify`).
- WorkSource wire protocol — mathlint (`mathlint.orchestration.real_source`).
- Worker reasoning text — pi (owns session JSONL at
  `~/.pi/agent/sessions/...`) and pi_monitor (TUI activity feed).
- Worker file-write observability — the program itself (kaplansky owns
  its own repo).
- Supervisor lifecycle — pi_monitor (`pi-monitor run` / `watch` / `status`).

**The dispatcher CLI is the only application code this repo owns**, and
it is *strictly* a thin delegation layer:

```sh
research list                                  # read catalog
research doctor [--live]                       # subprocess: mathlint preflight / system-readiness
research start <program> [--dry-run]           # subprocess: mathlint live-run
research stop <program>                        # subprocess: mathlint research-stop
research status <program>                      # subprocess: mathlint research-status
research watch <program>                       # subprocess: pi-monitor watch
```

No reimplementation. No data parsing. No JSONL reading. No state-file
reading. Pure dispatch.

## What was removed

Five shell scripts deleted:
- `scripts/kaplansky-attempt-timeline.sh`
- `scripts/kaplansky-reasoning-tail.sh`
- `scripts/kaplansky-artifacts-tail.sh`
- `scripts/kaplansky-gate-check.sh`
- `scripts/kaplansky-roadmap-gate.sh`

Four skill wrappers deleted:
- `skills/kaplansky/start_kaplansky.md`
- `skills/kaplansky/end_kaplansky.md`
- `skills/kaplansky/kaplansky_status.md`
- `skills/kaplansky/reasoning_tail.md`

Two ADRs superseded:
- `ADR-0005` (reasoning tail) — superseded by this ADR.

## Rationale

- A repo that owns the catalog but also reads mathlint's persistence
  boundaries (receipts, source-reports, executions) has two sources of
  truth for the same data. Duplication invites drift.
- A repo that reads pi's session JSONL has crossed the boundary into
  pi's domain. pi is the only thing that should read its own session
  format.
- The dispatcher pattern (catalog → mathlint command) is testable with
  pytest + a fixture catalog. The duplicated pattern (catalog →
  reimplement mathlint logic) was not testable because the mathlint
  API surface was being reimplemented, not mocked.
- Each cross-repo ADRs (`@INV-0091`, `@INV-0092`, `@INV-0093`,
  `@ADR-0091`, `@ADR-0092`) explicitly forbids research-institution
  from owning program-launcher logic. The duplicated logic was
  violating those invariants.

## Alternatives considered

- **Keep the scripts as "operator UX only" with no logic.** Rejected:
  the scripts were reading mathlint's persistence and pi's session
  format. That is not operator UX; that is reimplementation.
- **Move the scripts to mathlint as new subcommands.** Rejected for
  this turn: that requires mathlint-side ADR + cross-repo PR. The
  reasoning-tail candidate belongs in pi, not mathlint. The
  artifact/gate scripts can become mathlint commands in a future ADR.
- **Move the scripts to pi_monitor as new TUI panels.** Plausible for
  the reasoning tail (TUI activity feed extension) and the gate check
  (audit-events panel). Out of scope for this ADR; tracked as cross-repo
  work in `HARDENING-CHECKLIST.md`.

## Consequences

- The dispatcher CLI is the single application-code artifact. ~150
  lines Python + ~150 lines tests. Total repo source size stays under
  ~300 lines.
- Each catalog program gets one `research <verb> <program>` invocation,
  resolved from the catalog. Adding a 100th program is a one-line
  catalog edit + zero Python changes.
- Cross-repo ADR backlog (the legitimate `HARDENING-CHECKLIST.md`
  items) is the only remaining work this repo owes.
- The skill installer script (`scripts/install-kaplansky-skills.sh`)
  becomes obsolete once the dispatcher CLI exposes
  `research install-skills`. Tracked in checklist.

## Change triggers

Revisit if:

- A new concern appears that is genuinely cross-repo (e.g. cross-program
  budget aggregation). Add it; do not let it become application logic.
- mathlint ships a CLI command that subsumes something the dispatcher
  currently does. Delegate to it; remove the dispatcher layer.
- The catalog grows past ~10 programs and the per-program shim pattern
  (e.g. `monitor-kaplansky.sh`) becomes unwieldy. Generate them from
  the catalog.
