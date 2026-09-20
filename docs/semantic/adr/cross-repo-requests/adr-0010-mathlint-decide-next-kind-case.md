---
id: ADR-0010
kind: request
status: drafted
target: mathlint
target-id: adr-pending-in-math
title: mathlint decide_next kind discriminator must use the canonical lowercase form per pi_monitor.work.work_source
date: 2026-09-19
related:
  - AGENTS.md
  - ADR-0006
  - @INV-0093
  - ADR-0008 (sibling — decide_next repeat limit)
  - ADR-0009 (sibling — supervisor-side repeat circuit)
origin-test: research-institution/tests/test_source_decision_contract.py::test_mathlint_decide_next_envelope_parses
---

# ADR-0010: mathlint `decide_next` `kind` discriminator must use lowercase

## Status

**Drafted in research-institution; pending ratification in math-engine.**
Caught by `tests/test_source_decision_contract.py::test_mathlint_decide_next_envelope_parses`,
which fails on the literal `"Dispatch"` (capitalized) the mathlint
emitter returns today.

## Origin (caught by tests, not by operator)

The 2026-09-19 hardening pass added typed-contract tests for the
source-decision envelope (mirroring `pi_monitor.work.work_source`). One
test feeds the exact envelope shape `mathlint.orchestration.real_source.decide_next`
returns into the dispatcher's mirror parser; the parser rejects it
because:

  - mathlint emits `"kind": "Dispatch"` (capitalized D).
  - pi_monitor's canonical constants are `"dispatch"` (lowercase)
    per `pi_monitor/work_source.py:43` (`KIND_DISPATCH = "dispatch"`).
  - pi_monitor's consumer (`_decode_envelope` at line ~640) checks
    `if kind not in {KIND_DISPATCH, KIND_WAIT, KIND_OPERATOR_REQUIRED, KIND_STOP}`,
    which rejects capitalized variants.

This means the mathlint emitter's output, as written, would NOT
parse under pi_monitor's strict check. If pi_monitor's check has a
case-fold anywhere along the path, it's an undocumented tolerance
that future strictness could break. The drift is a latent defect.

## Evidence

```text
$ grep -n 'kind": "' /Users/erinprokopiw/Documents/andrei/math/src/mathlint/orchestration/real_source.py
143:            "kind": "OperatorRequired",
158:            "kind": "OperatorRequired",
171:            "kind": "Wait",
189:        "kind": "Dispatch",
```

All four decision variants are emitted capitalized. None of them
match pi_monitor's canonical lowercase constants.

```text
$ grep -n 'KIND_' /Users/erinprokopiw/Documents/andrei/pi_monitor/src/pi_monitor/work/work_source.py
43:KIND_DISPATCH = "dispatch"
(...)
```

## Requested behavior (in mathlint)

1. **`real_source.decide_next` (and any sibling emitters) MUST use
   the canonical lowercase strings**: `"dispatch"`, `"wait"`,
   `"operator_required"`, `"stop"`. The four call sites at
   `real_source.py:143`, `:158`, `:171`, `:189` are the immediate
   targets.

2. **A regression test in mathlint**: a unit test that asserts
   `parse_source_decision(envelope)` from pi_monitor (or a
   local mirror) accepts every decision `real_source` can emit.
   This catches case-drift regressions in CI.

3. **Or, equivalently: pi_monitor's `_decode_envelope` should
   case-fold** the discriminator. If we choose this path, the
   cross-repo ADRs must document the new tolerance and the
   canonical string remains lowercase.

## Why cross-repo

The discriminator string is on the wire between mathlint and
pi_monitor. Neither repo can unilaterally fix it; both sides must
agree on the canonical form. The test failure here is the canonical
signal that the agreement has rotted.

## Migration impact

- The dispatcher's mirror parser (in research-institution) was
  written to the lowercase canonical form per pi_monitor. Once
  mathlint's emitter switches, the test passes; no dispatcher
  change required.
- A `compat` shim is acceptable: mathlint can emit BOTH `kind`
  and `kind_legacy` for one release, then drop the legacy field.
  The dispatcher reads the canonical field only.

## Acceptance criteria

- [ ] mathlint's `real_source.decide_next` emits lowercase kind
      values that match `pi_monitor.work.work_source.KIND_*`.
- [ ] mathlint has a regression test asserting
      `parse_source_decision(envelope)` accepts every decision
      `real_source` can emit.
- [ ] `research-institution/tests/test_source_decision_contract.py::test_mathlint_decide_next_envelope_parses`
      passes (currently fails).
- [ ] All four decision variants are covered: dispatch, wait,
      operator_required, stop.

## Cross-references

- `@ADR-0006` — research-institution owns only catalog + bootstrap + green gate + dispatcher.
- `@ADR-0008` — sibling request: mathlint source-side repeat limit.
- `@ADR-0009` — sibling request: pi_monitor supervisor-side repeat circuit.
- `pi_monitor/work_source.py:43,640` — canonical kinds + decoder strict check.
- `mathlint/orchestration/real_source.py:143,158,171,189` — emitters to fix.
- `research-institution/contracts/source_decision.py` — the dispatcher's mirror.
- `research-institution/tests/test_source_decision_contract.py::test_mathlint_decide_next_envelope_parses`
  — the test that surfaces the drift.
