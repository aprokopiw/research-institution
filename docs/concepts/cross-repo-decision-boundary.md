---
id: concept-cross-repo-decision-boundary
kind: concept-doc
status: active
title: Where each kind of decision lives — supervisor vs. judge vs. source vs. worker
related:
  - @ADR-0006-research-institution-scope
  - @ADR-0007-research-institution-owns-work-source-provider
  - @ADR-0014-execution-authority-boundary       (pi_monitor)
  - @ADR-0019-live-campaign-sequencing           (pi_monitor)
  - @ADR-0013-composition-model                  (pi_monitor)
  - @CTR-0001-work-sources-and-runtimes-exchange-revisioned-execution-facts  (pi_monitor)
  - @CTR-0002-worker-outcomes-are-bounded-and-non-authoritative             (pi_monitor)
  - @CTR-0003-external-work-source-transport-is-bounded-and-fail-closed     (pi_monitor)
date: 2026-09-20
---

# Where each kind of decision lives

> Companion to `docs/concepts/architecture.md`. That doc describes
> *what each repo is for*. This doc describes *which repo is allowed
> to make which kind of decision*. Reading both is required before
> writing any cross-repo change that affects the live supervisor loop.

## The four-decision inventory

The institution has four decision-makers. Each is the canonical
authority for one kind of decision and **must not** decide things
in the others' lanes.

### 1. The `pi_monitor` supervisor (the orchestrator)

**Decides:** liveness and recovery.

- Is the worker process alive? Is the RPC responsive? Is the
  context sustainable for another turn? Has the worker settled?
  Is the worker silently stuck on a long-running tool?
- Answers: `NOOP` / `NUDGE` / `ABORT_AND_CONTINUE` /
  `RESTART_SAME_SESSION` / `START_FRESH_SESSION` / `STOP`.
- Vocabulary: `@ADR-0009-bounded-recovery-and-soft-circuit`
  (pi_monitor) and `@ADR-0016-wait-and-lease-semantics`
  (pi_monitor).

**Does NOT decide:** what the worker is working on, what the next
step in any domain is, whether a mathematical proof is making
progress, whether to escalate to an architect, whether to admit a
submission, whether research is complete.

### 2. The optional `pi_monitor` semantic judge (the liveness sensor)

**Decides:** semantic ambiguity that timers cannot resolve.

- Is the worker *genuinely* active on a long test, or wedged on a
  silent RPC? Is the dirty worktree productive or stale? Is the
  agent's "I'm done" claim real or is it a confused settle?
- Answers: a `SemanticJudgeResult` (health / context_reset_value /
  worktree_value / confidence / reason / fingerprint) which
  deterministic policy maps onto an allowed `Action`.
- Vocabulary: `@ADR-0002-judge-advisory-policy-authoritative`
  (pi_monitor), `@ADR-0007-deterministic-context-controller-shadow-mode`
  (pi_monitor).

**Does NOT decide:** what comes next in the domain. The judge has no
filesystem or process tools, no persistent session, no domain
knowledge. Its output is **advisory**; the supervisor applies
deterministic `RecoveryPolicy` before any action.

### 3. The `WorkSource` (the research director)

**Decides:** what the worker should do next — and when it should
*not* dispatch at all.

- Reads the program's durable state (roadmap, work files, attempt
  files, deltas), consults the math kernel's stagnation trigger /
  scheduler verdict, and emits one of:
  - `Dispatch(WorkRequest(role, operation_id, payload, ...))` — the
    source is saying "this is the bounded thing the worker should
    do next".
  - `Wait(reason_code, reason, retry_after_seconds,
    wake_on_source_change)` — the source is saying "there is no
    legal dispatch right now; please wake on revision move".
  - `OperatorRequired(reason)` — the source is saying "I cannot
    proceed without an external decision (e.g. credentials broken,
    budget exceeded)".
  - `Stop(reason)` — the source is saying "domain work is
    complete; please terminate cleanly".
- Vocabulary: `@CTR-0001-work-sources-and-runtimes-exchange-revisioned-execution-facts`
  (pi_monitor) and `@ADR-0007-research-institution-owns-work-source-provider`
  (this repo).

**Does NOT decide:** how the worker process is supervised. The
supervisor owns reliability; the source owns meaning.

### 4. The `WorkerRuntime` (the executor)

**Decides:** how to launch and control one worker invocation.

- Picks the runtime profile, manages session identity, applies
  the `WorkerOutcomeEnvelope` drop path, finalizes the attempt's
  `ExecutionResult`.
- Vocabulary: `@ADR-0015-replaceable-worker-runtimes`
  (pi_monitor), `@ADR-0020-structured-worker-completion`
  (pi_monitor), `@CTR-0002-worker-outcomes-are-bounded-and-non-authoritative`
  (pi_monitor).

**Does NOT decide:** what the worker is working on. The runtime
receives the `WorkRequest` as opaque input; the
`WorkerOutcomeEnvelope` it returns is an execution fact, not a
domain fact.

## The loop, not the DAG (the guardrail)

`@ADR-0014-execution-authority-boundary` (pi_monitor) makes this
test explicit:

> Is this state required to execute externally defined work
> reliably, or are we starting to redefine what the work itself is?

If the latter, push it back into the source. For the institution:

| Concept | Where it belongs | Where it does NOT belong |
| --- | --- | --- |
| "Worker has been idle 12 minutes" | pi_monitor (`recovery-policy`) | research-institution, math |
| "Worker re-acked the same `operation_id` 3 times with `no_delta`" | research-institution's `select_next_work_for_supervisor` (consults math's `stagnation_triggers`) | pi_monitor, kaplansky's `WorkSourceProvider` |
| "Source says `Dispatch` for `op-42`, worker accepts it, attempt 1 launches" | pi_monitor's `ExecutionRecord` + `WorkRequest` chain | math, kaplansky |
| "Op-42 needs an architect before more researcher dispatches" | research-institution's `select_next_work_for_supervisor` returning `Wait(reason="architecture_review_required_for_op-42")` | pi_monitor (must NOT learn the role vocabulary), kaplansky (must NOT escalate — it produces content, not dispatch policy) |
| "Worker submitted a `WorkerSubmission(submission_kind=PROOF)`" | math (the intake + transition kernel + independent validator) | pi_monitor (records only `ExecutionResult` per `@CTR-0002`), kaplansky (writes only the canonical artifact file) |
| "Architect has admitted a `StrategicReviewHorizon` via the 7-check gate" | math (frontier-scheduler + engine) | pi_monitor, research-institution, kaplansky |
| "Worker spent >2% of the weekly budget on a single turn" | pi_monitor (`budget_policy` + `budget_ledger`) | math, kaplansky, research-institution (provider-shaped data, never core policy) |

## The smell test

> Architecture smell: if the generic core starts needing concepts
> like `depends_on`, `blocked_by`, `advances`, proof prerequisite,
> research branch, issue dependency, parent/child task, or critical
> path, pi_monitor is probably drifting into a generic DAG engine.
>
> — `@ADR-0014-execution-authority-boundary` (pi_monitor)

Same test for the institution:

> If research-institution starts needing concepts like
> "operation N has been blocked for K hours, escalate", "operator
> must review op N", "decision-tree on how to handle attempt
> staleness", "agent N1 vs agent N2 dispatch policy", it is
> drifting into a second DAG engine. Push the question into math's
> `select_global_action` + `stagnation_triggers` + architecture-
> review adapter, and let the source translate the verdict into
> the existing `SourceDecision` vocabulary.

## The four-line mental picture (for fresh agents)

```
math has the answer ("researcher should run next on op X" /
                     "stagnation: architecture review on op X" /
                     "no eligible work" / "domain complete")
                            │
                            ▼
research-institution's `select_next_work_for_supervisor`
  translates math's verdict into a typed SourceDecision
  using ONLY the existing Dispatch | Wait | OperatorRequired | Stop vocabulary
                            │
                            ▼
pi_monitor's supervisor executes that decision through the
  WorkerRuntime, observes liveness, asks the judge when
  suspicious, applies RecoveryPolicy, persists ExecutionRecord
                            │
                            ▼
The worker (Pi session) does the bounded thing it was told,
  drops a WorkerOutcomeEnvelope, and the loop repeats
```

## Why this doc exists

A fresh agent who reads the research-institution source sees
`select_next_work_for_supervisor` returning `Dispatch` / `Wait` and
naturally asks: "where does the role ('researcher' vs 'architect')
get set?" "where does the no-delta handling live?" "is the supervisor
the one that escalates to architecture review?". Without this doc
they will reach for the wrong layer. With this doc they know to
look at math's `select_global_action` and the existing
`SourceDecision` vocabulary.

## Companion docs

- `docs/concepts/architecture.md` — what each repo is for.
- `docs/operations/wire-contracts.md` — the cross-repo type audit.
- `docs/semantic/adr/adr-0006-research-institution-scope.md` — what
  research-institution owns and what it explicitly does NOT own.
- `docs/semantic/adr/adr-0007-research-institution-owns-work-source-provider.md` —
  the durable anchor for "OS owns the slot; math owns the verdict".
- `~/Documents/andrei/pi_monitor/docs/architecture/overview.md` —
  the canonical three-controller split on the pi_monitor side.
