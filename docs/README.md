# research-institution docs — navigation index

> **5-minute cold-start path.** If you just landed on this
> repo, read this file first. It points you at the one doc
> for each question you probably have.

## The 5-minute navigation path

| Step | Question | Doc | Time |
|------|----------|-----|------|
| 1 | What is this repo? | [`README.md`](../README.md) | 1 min |
| 2 | How do the four repos fit together? | [`concepts/architecture.md`](concepts/architecture.md) | 2 min |
| 3 | Who decides what — supervisor vs. judge vs. source vs. worker? | [`concepts/cross-repo-decision-boundary.md`](concepts/cross-repo-decision-boundary.md) | 2 min |
| 4 | What is the durable semantic-record index? | [`semantic/SEMANTIC_REGISTRY.md`](semantic/SEMANTIC_REGISTRY.md) | 30 sec |

After step 4, you have the full picture. For deeper work:

| If you want to... | Read this |
|-------------------|-----------|
| Launch kaplansky | [`operations/launch-kaplansky-autonomously.md`](operations/launch-kaplansky-autonomously.md) |
| Quickstart (5-min tour) | [`operations/research-institution-quickstart.md`](operations/research-institution-quickstart.md) |
| Bootstrap from a fresh clone | [`operations/bootstrap-and-cold-start.md`](operations/bootstrap-and-cold-start.md) |
| Understand the architecture-review gate | [`operations/architecture-review-gate.md`](operations/architecture-review-gate.md) |
| Use the dispatcher CLI | [`operations/dispatcher-cli-reference.md`](operations/dispatcher-cli-reference.md) |
| Debug a stuck live supervisor | [`operations/pi-monitor-debug-logging.md`](operations/pi-monitor-debug-logging.md) |
| Understand the wire contracts | [`operations/wire-contracts.md`](operations/wire-contracts.md) |
| Configure `local-pi-monitor.toml` | [`operations/pi-monitor-config-reference.md`](operations/pi-monitor-config-reference.md) |
| Diagnose an operator-side failure | [`operations/research-institution-troubleshooting.md`](operations/research-institution-troubleshooting.md) |
| Run the verification gates | [`operations/verification-gates.md`](operations/verification-gates.md) |
| Fix the no-delta loop | [`operations/plan-013-live-supervisor-authority.md`](operations/plan-013-live-supervisor-authority.md) |
| Read the post-ship trace for @ADR-0011 | [`operations/plan-013-closure-audit.md`](operations/plan-013-closure-audit.md) |
| Read the kaplansky operator UX | [`operations/kaplansky-operator-ux.md`](operations/kaplansky-operator-ux.md) |
| Plan test hardening (roadmap) | [`operations/test-hardening-plan.md`](operations/test-hardening-plan.md) |
| Apply math's decisions to the roadmap | [`operations/architecture-review-gate.md`](operations/architecture-review-gate.md) (the rare `--skip-gate` escape hatch) |

## The test-locality decision tree

See [`tests/README.md`](../tests/README.md). It maps "what
am I trying to test?" to the right test file.

## The mental model in one paragraph

The institution is a four-repo machine. **math** is the
kernel (program-agnostic). **research-institution** is the
OS layer (catalog + bootstrap + green gate + dispatcher +
work-source-provider slot). **pi_monitor** is the process
driver (one worker per supervisor process). **kaplansky**
(and any future research program) is the persistent state
the OS directs the kernel to investigate.

The supervisor cycle is a loop: ask the source "what
next?" (one call per cycle, atomic) → execute the
verdict → ask the judge only on escalation → persist
the execution record. The source owns meaning; the
supervisor owns execution; the judge owns liveness. The
worker does the bounded thing it's told.

## What this repo owns vs. what it doesn't

| Owns | Does NOT own |
|------|--------------|
| Catalog (`catalog/programs.toml`) | Architecture-review gate logic (math) |
| Bootstrap (`scripts/bootstrap-institution.sh`) | Receipts / audit-chain parsing (math) |
| Green gate (`green-gate/check-institution.sh`) | WorkSource wire protocol (math + pi_monitor) |
| Dispatcher CLI (`research_institution/`) | Worker reasoning text (pi) |
| WorkSourceProvider slot per `@ADR-0007` | Supervisor lifecycle (pi_monitor) |
| Operator one-pagers + durable ADRs | Domain content (the program) |

See [`concepts/architecture.md`](concepts/architecture.md) for the full ownership table.

## Cross-repo collaboration

This repo collaborates with three siblings:

| Sibling | What lives there | Anchor for that boundary |
|---------|------------------|---------------------------|
| math | Kernel + runtime + validators + receipts + scheduler | `@ADR-0014-mathlint-does-not-import-program-named-modules` |
| pi_monitor | Supervisor + judge + recovery policy + worker runtime | `@ADR-0014-execution-authority-boundary` (pi_monitor) |
| kaplansky (or any future program) | Roadmap + work files + attempt files + content | `@ADR-0007-research-institution-owns-work-source-provider` |

If you want to teach one of these siblings about a concept
(domain-level scheduler, role-based dispatch, etc.), you
are **probably in the wrong repo**. See
[`concepts/cross-repo-decision-boundary.md`](concepts/cross-repo-decision-boundary.md)
for the four-way decision inventory that protects against
boundary violations.

## See also

- [`AGENTS.md`](../AGENTS.md) — prime directive (durable vs transient classification).
- [`README.md`](../README.md) — repo's role + sibling map.
- [`semantic/SEMANTIC_REGISTRY.md`](semantic/SEMANTIC_REGISTRY.md) — durable anchor index.
