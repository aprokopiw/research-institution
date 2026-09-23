---
id: operations-architecture-review-gate
kind: operations-doc
status: active
title: Architecture-review gate — model-decision framing
related:
  - @ADR-0006-research-institution-scope
  - @ADR-0007-research-institution-owns-work-source-provider
  - @ADR-0011-stagnation-handling-is-a-source-decision
  - @INV-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult
  - @CTR-0095-live-source-snapshot-contract
  - docs/operations/plan-013-live-supervisor-authority.md
  - docs/concepts/cross-repo-decision-boundary.md
date: 2026-09-20
supersedes: pre-plan-013 operator-decision framing (now historical context §5)
---

# Architecture-review gate — model-decision framing

> **Posture change (2026-09-20, plan-013).** The architecture-
> review gate is a **model decision** routed through the
> source, not an **operator decision** that pauses the
> supervisor. This is the durable record of the new framing;
> the operator-decision framing lives in §5 as historical
> context.

## §0 — What the gate is (today)

The "architecture-review gate" is the operator's name for a
specific state in math's kernel scheduler: when the scheduler's
`ActionKind.ARCHITECTURE_REVIEW_REQUIRED` is the current
verdict for a target, an architecture-review horizon is
being admitted (or is mid-flight) through the **seven-check
horizon admission gate**. While that admission is mid-flight,
the next dispatch for that target is gated.

**The gate is open** when math's scheduler returns a
`RESEARCH` / `VERIFICATION_AUDIT` / `FORMALIZATION` action —
i.e., ordinary research can proceed.

**The gate is closed** when math's scheduler returns
`ARCHITECTURE_REVIEW_REQUIRED` — i.e., the stagnation
trigger has fired (2+ substantial no-delta sessions on the
target) and the architect round is mid-flight.

The model is the research director. **No operator
intervention is needed when the gate is closed.** The
supervisor waits (`Wait(reason_code="architecture_review_required",
wake_on_source_change=True, retry_after_seconds=300)`)
until the architect's `ArchitectureProposalEnvelope` lands
and the canonical state advances; then the supervisor
re-asks the source, gets a fresh verdict, and dispatches
the next round (often a researcher round against the new
canonical state).

## §1 — How the gate is decided (today)

Per `@INV-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult`
and `@ADR-0011-stagnation-handling-is-a-source-decision`,
the gate decision lives in **math's kernel**, surfaced
through the **OS-level work source** in research-institution:

```text
math.deltas.stagnation_triggers(repository)
    │
    │ (if target has 2+ no_delta sessions)
    ▼
math.scheduler.select_global_action(scheduler_project_for(repository, candidate))
    │
    │ (returns ActionKind.ARCHITECTURE_REVIEW_REQUIRED)
    ▼
research_institution.select_next_work_for_supervisor
    translates verdict → Wait(reason_code="architecture_review_required",
                              wake_on_source_change=True,
                              retry_after_seconds=300)
    │
    ▼
pi_monitor supervisor
    records source_wait audit event
    sleeps until retry_after_seconds OR wake_trigger
```

Three layers, each with one job:
- **math** owns the verdict (`ARCHITECTURE_REVIEW_REQUIRED`).
- **research-institution** owns the translation (verdict →
  typed `Wait` envelope).
- **pi_monitor** owns the loop (record `source_wait`, sleep,
  re-ask on revision move).

The supervisor never learns what "stagnation" or "architecture
review" means. It sees one `SourceDecision` per cycle using
the existing `Dispatch | Wait | OperatorRequired | Stop`
vocabulary. The role appears only as a `WorkRequest.role`
field, which is already in the wire schema per
`@CTR-0001-work-sources-and-runtimes-exchange-revisioned-execution-facts`
(pi_monitor §3 "Vocabulary" table).

## §2 — What happens when the gate is closed

The dispatcher exits `5` with this message (operator-runnable
preflight):

```text
GATE NOT OPEN: mathlint roadmap reports TASK KIND=ARCHITECTURE_REVIEW_REQUIRED
  reason: <the parsed REASON: line from roadmap>
  horizon_admission_pending: True
  wake_on_source_change: True
  expected_resolution: admission gate completes the 7-check
    horizon review (typically 1-2 architect rounds over 1-3 hours);
    supervisor auto-resumes on revision move
```

The **fix is no fix** — the supervisor auto-resumes. The
operator does not need to apply any decision; the model
applies it. The supervisor's `source_wait` audit event is
the operator's signal:

```sh
journalctl -u mathlint-pi-monitor --since "1h ago" \
  | grep '"event":"source_wait"' \
  | grep '"reason_code":"architecture_review_required"'
```

If rows appear, an architecture-review horizon is mid-flight.
The supervisor is waiting; nothing else is needed.

## §3 — The legacy `--skip-gate` override (kept for one rare case)

```sh
python -m research_institution start kaplansky --skip-gate
```

The override is **rarely needed** in the new framing. It
exists for one case only:

1. **Operator has already applied a decision via
   `mathlint architect-apply --recommendation <yaml> --apply`**
   and the roadmap's `TASK KIND:` line hasn't refreshed yet
   (e.g. the decision is in a pending state, or the operator
   is testing the launch path itself).

`--skip-gate` is logged by the dispatcher; it does not
silently bypass any kernel logic. Use it sparingly.

The previous operator-decision docs (the pre-plan-013
framing) described a wider use of `--skip-gate` — that
framing is now historical context (§5 below) and should
not be followed. The new framing is: **the model decides;
the supervisor waits; the operator observes.**

## §4 — Cross-repo ask (now superseded by `@ADR-0011`)

The pre-plan-013 framing asked math to ship
`mathlint architect-review --verdict --program <name>` so
the dispatcher could parse the verdict programmatically
without parsing roadmap output. That ask was
`@ADR-0007-mathlint-architect-review-program-flag` (cross-repo).

**That ask is now superseded.** The new flow is
`@ADR-0011-stagnation-handling-is-a-source-decision`: the
source asks math directly via the
`consult_work_source_snapshot` wrapper (`@CTR-0095`), so the
operator-decision CLI path is no longer needed. The
math-side implementation lands in math; the source-side
translator lands in research-institution; no kernel CLI
change is required.

The pre-plan-013 `@ADR-0007` (cross-repo) ADR is retained
as historical context; the **operator-UX ask** it described
is satisfied differently by `@ADR-0011`.

## §5 — Historical context (operator-decision framing)

> This section is preserved so a future agent reading old
> plan docs or old commits can understand what changed.
> Do not follow this section's instructions; the new
> framing is in §0–§4.

**Before plan-013 (operator-decision framing):**

- The dispatcher refused to launch while the gate was
  closed.
- The operator had to read `mathlint roadmap`, decide
  whether to confirm the counterexample, pivot the frontier,
  or apply a structural decision.
- The operator wrote a YAML decision file matching the
  architect-review packet's `REQUIRED OUTPUT` schema and
  applied it via `mathlint architect-apply --recommendation
  <yaml> --apply`.
- The dispatcher could be re-launched.

**Why this was wrong:**

- It violated the user's repeated call: "the model is the
  research director; no operator intervention; the supervisor
  should pick up where it left off without intervention."
- It confused the supervisor's `Wait` (a typed
  SourceDecision) with an operator pause (an external
  decision boundary). These are different categories.
- It treated `ARCHITECTURE_REVIEW_REQUIRED` as a halt signal
  instead of a routing signal. Math's kernel was clear: it
  routes to `DISPATCH_ARCHITECTURE_REVIEW` (a worker dispatch
  to the architect role), not to operator pause. Per FR-027 /
  FR-028 / FR-029 / FR-043 in math's kernel docs.

**What changed:**

- The source consults math's verdict and translates
  `ARCHITECTURE_REVIEW_REQUIRED` into a `Wait` with a
  `wake_on_source_change=True` policy. The supervisor
  re-asks on revision move (i.e., when the architect's
  `ArchitectureProposalEnvelope` lands and the canonical
  state advances).
- The operator's role is **observe**, not **decide**. The
  operator can `grep` for `source_wait` audit events to
  see when architecture-review rounds are mid-flight.
- `--skip-gate` survives as a rare escape hatch for the
  case where the operator has already applied a decision
  manually (e.g., to fix a malformed roadmap entry) and
  needs to launch while the kernel is mid-refresh.

## §6 — Operator one-pagers updated to reflect the new framing

These docs were updated in PR-A:
- `docs/operations/launch-kaplansky-autonomously.md` —
  added the new `source_wait` audit grep; the operator's
  "is the supervisor waiting?" question now has a one-liner
  answer.
- `docs/operations/research-institution-troubleshooting.md` —
  the "stuck at architecture-review gate" section now
  says "wait for the supervisor to auto-resume on revision
  move; the model is the research director".
- `docs/operations/dispatcher-cli-reference.md` —
  the `start` verb docs now say `--skip-gate` is a rare
  escape hatch for the post-`mathlint architect-apply`
  refresh window, not a routine operator workflow.

## §7 — Cross-references

- `@ADR-0011-stagnation-handling-is-a-source-decision` —
  the durable cross-repo ADR; supersedes the pre-plan-013
  `@ADR-0007-mathlint-architect-review-program-flag`.
- `@INV-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult` —
  the durable invariant anchoring the fix.
- `@CTR-0095-live-source-snapshot-contract` — the math-side
  consult adapter's typed contract.
- `docs/operations/plan-013-live-supervisor-authority.md` —
  the unified plan.
- `docs/concepts/cross-repo-decision-boundary.md` — the
  supervisor / judge / source / worker four-way split.
- `docs/concepts/architecture.md` — the kernel / OS /
  driver / program mental model.
- `research_institution/cli.py::check_gate` — the dispatcher's
  gate check (unchanged by plan-013; still parses the
  roadmap's `TASK KIND:` line for preflight).
- `tests/test_gate_check.py` — contract tests for the gate
  check (unchanged by plan-013).
