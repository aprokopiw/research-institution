# Architecture-Review Gate

The architecture-review gate is the operator's checkpoint for "is the
roadmap ready to start another research attempt, or does it need a
human decision first?" The dispatcher's `research start` refuses to
launch while the gate is closed.

## What the gate is

mathlint's roadmap emits a `TASK KIND:` line for every dispatch
decision. The values are:

- `RESEARCH` — gate open; safe to launch.
- `ARCHITECTURE_REVIEW_REQUIRED` — gate closed; the current outcome
  has no approved `on_failure` edge and needs an operator decision.
- Other values — treated as gate-open by the dispatcher (defensive
  default: don't refuse on unrecognized values).

The gate verdict is part of mathlint's output, not research-institution's
logic. The dispatcher reads it and refuses to launch when the verdict
is closed.

## When the gate is closed

The dispatcher exits `5` with this message:

```text
GATE NOT OPEN: mathlint roadmap reports TASK KIND=ARCHITECTURE_REVIEW_REQUIRED
  reason: <the parsed REASON: line from roadmap>
  fix: run `mathlint architect-apply --recommendation <yaml>` and retry.
  override: pass --skip-gate to launch anyway (logged).
```

The fix is `mathlint architect-apply --recommendation <yaml>`, which
commits the operator's decision (read-only by default; pass `--apply`
to commit). The YAML decision is the program decision documented in
the roadmap's `REASON:` line.

## How to apply the decision

1. Read `mathlint roadmap` (or the dispatcher's refusal message) for
   the `REASON:` line.
2. Decide: confirm the existing counterexample is the answer; or pivot
   to a different frontier; or apply a structural decision the program
   needs.
3. Write the decision to a YAML file matching the architect-review
   packet's `REQUIRED OUTPUT` schema (the packet is emitted by
   `mathlint architect-start`).
4. Apply: `mathlint architect-apply --recommendation <yaml> --apply`.
5. Re-run `python -m research_institution start <program>` (no override).

## The `--skip-gate` override

```sh
python -m research_institution start kaplansky --skip-gate
```

The override exists for two cases:

1. **Operator has already applied a decision** but the roadmap's
   `TASK KIND:` line hasn't updated yet (e.g. the decision is in
   a pending state). `--skip-gate` is the documented escape hatch.
2. **Operator is testing the launch path itself** and wants to bypass
   the gate deliberately.

Every `--skip-gate` invocation is logged by the dispatcher. Use it
sparingly.

## Cross-repo ask

The gate verdict is currently read by parsing `mathlint roadmap`
output (`TASK KIND: ARCHITECTURE_REVIEW_REQUIRED`). This is fragile
to roadmap format changes and runs ~0.6s per dispatch.

The clean fix is a first-class programmatic verdict in mathlint —
see `@ADR-0007`. Once that ships, the dispatcher switches to
`mathlint architect-review --verdict --program <name>` and the
roadmap-parse path becomes a fallback.

## Cross-references

- `@ADR-0006` — research-institution owns only catalog + bootstrap + green gate + dispatcher.
- `@ADR-0007` — cross-repo ask: programmatic gate verdict in mathlint.
- `research_institution/cli.py::check_gate` — the dispatcher's gate check.
- `tests/test_gate_check.py` — contract tests for the gate check.
- `docs/operations/dispatcher-cli-reference.md#start-program` — the `start` verb.
