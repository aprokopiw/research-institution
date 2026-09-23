---
id: INV-0094
kind: invariant
status: active
title: Operator-driven no-delta loop requires ADR-0009 supervisor circuit (or budget cap)
introduced: 2026-09-22
observed-on-live-launch: 2026-09-22T21:18Z (UTC)
related: [ADR-0006, ADR-0009, INV-0093, CTR-0094]
scope: research_institution, pi_monitor, kaplansky
---

# INV-0094: Operator-driven no-delta loop requires ADR-0009 supervisor circuit (or budget cap)

## Statement

When a research program returns `no_delta` on the same
`(source_identity, operation_id)` key N consecutive times, the
supervisor MUST refuse further re-dispatch and surface
`operator_required` to the human. Until `@ADR-0009` lands in
pi_monitor, the only operator-grade enforcement is a budget
cap configured in
`~/.config/mathlint/local-pi-monitor.toml [rate_limits]`.

The default `[rate_limits]` is sized for steady progress, NOT
for repeated rejection-by-model. Operators MUST verify the
cap fits the no-delta-loop pattern, and tighten if not.

## Why it matters (the 187-attempt postmortem pattern)

Observed live on 2026-09-22 (this run, slug
`mathlint-local-readiness`, operation K4):

- Attempts 3, 4, 5, 6 on K4 all published
  `outcome=no_delta` with the **same outcome digest**
  (`aae2f6d5...`).
- Each attempt cost ~$0.20 and ~4700 tokens; the worker was
  re-reading its own attempt file and confirming the prior
  result.
- The supervisor dispatched ~6 times in ~14 min with no
  operator pause.
- No upstream signal ever reaches the supervisor that
  "this key has been attempted and bounded."
- Without `@ADR-0009`, the only stopping rule is the
  supervisor's `on_exceeded=operator_required` rate-limit
  policy. At the default Plus-plan caps, this would burn
  multi-thousand tokens before tripping.

This is the 187-attempt bug from the playbook, observed at
attempt 6. The remaining 181 attempts were reachable in the
span of an unattended shift.

## Enforcement

- **`@ADR-0009` is the durable enforcement target.** It is
  drafted in
  `docs/semantic/adr/cross-repo-requests/adr-0009-pi-monitor-supervisor-side-repeat-circuit.md`
  but not shipped. Operators should treat ADR-0009 status as
  blocking until ratification.
- **`[rate_limits]` is the interim enforcement knob.** Set
  `max_tokens_per_10m` to a value that bounds the no-delta
  pattern to a known count (e.g., at ~5k tokens per
  no_delta re-ack, `max_tokens_per_10m=20000` permits ≤4
  loops before tripping `operator_required`).
- **`attempt_outcome=partial` is the worker's stop signal
  on the artifact side.** Workers should NOT silently
  publish multiple attempts after one bounded attempt
  file. The `revisit_if` field on the attempt file is the
  canonical "what unblocks the next attempt" record.

## Boundary cases

- The supervisor's `[recovery].max_nudges_per_hour=2` and
  `[recovery].max_same_session_restarts_per_hour=2` knobs
  are NOT per-op; they do not fire on this loop pattern.
  See `pi_monitor/src/pi_monitor/policy/policy.py:373,446`.
- A worker that publishes a NEW outcome digest (a real
  attempt, even one that fails) does NOT increment the
  no-delta counter under `@ADR-0009`. Only identical
  `(outcome, digest)` strings count.
- The math-side
  `mathlint.orchestration.delegation.stagnation` ledger
  (`deltas.py:StagnationTrigger`) does fire on
  `no_delta_count≥2`, but it is reachable only via
  `mathlint architect-review` — NOT via the live
  `decide_next` path the supervisor runs.

## Live evidence anchors

- `~/.local/state/mathlint/pi-monitor/executions/750d795428...json`
  — execution file with 4 identical-outcome attempts.
- `~/.local/state/mathlint/pi-monitor/audit.jsonl` —
  records source_dispatch, worker_outcome_published,
  execution_result_reported, execution_attempt_terminal
  events on K4.
- `~/Documents/andrei/kaplansky/mathematics/attempts/K4-characteristic-two-restriction-obstruction.md`
  — the attempt artifact the worker published.
- `~/Documents/andrei/kaplansky/mathematics/work/K4.md` —
  the live work-file with the parked operator questions.

## Cross-references

- `@ADR-0006` — research-institution owns only catalog +
  bootstrap + green gate + dispatcher.
- `@ADR-0009` — drafted supervisor-side repeat circuit.
- `@INV-0093` — institution green gate is the canonical
  wiring evidence (the green gate did NOT catch this; it
  only catches wiring).
- `@CTR-0094` — WorkSourceProvider dispatch envelope.

## Operator checklist before next autonomous launch

1. Read `local-pi-monitor.toml [rate_limits]`; ensure
   `max_tokens_per_10m ≤ 200000` for the planned no-delta
   budget.
2. Confirm `@ADR-0009` status; do not launch for an
   unattended multi-hour run while it remains `drafted`.
3. Mark operation items with `needs_operator_direction` in
   the catalog when the math kernel reports a parked
   question; `next_active_work` should respect this signal.
4. Treat `attempt_outcome=partial` with `revisit_if`
   clauses as the worker's stop signal; do not dispatch
   again on the same fingerprint without operator review.
