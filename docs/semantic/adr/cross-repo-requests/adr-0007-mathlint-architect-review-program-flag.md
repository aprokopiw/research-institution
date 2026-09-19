---
id: ADR-0007
kind: request
status: drafted
target: mathlint
target-id: adr-pending-in-math
title: mathlint architect-review must accept --program <name> and expose a programmatic gate verdict
date: 2026-09-19
related:
  - AGENTS.md
  - ADR-0006
  - HARDENING-CHECKLIST.md §C.1
origin-postmortem: research-institution/HARDENING-CHECKLIST.md §A
---

# ADR-0007: mathlint `architect-review --program <name>` + programmatic gate verdict

## Status

**Drafted in research-institution; pending ratification in math-engine.**
This ADR documents the institution's request to math-engine maintainers.
It is durable in this repo (the request is an institution-owned record);
the implementation lands in math-engine via a sibling ADR that cites
this one.

## Origin (postmortem)

The 2026-09-13 hardening session root-caused the 187-attempt
`blocked/stalled` loop on `work.kaplansky.extract-minimal-rigidity-overlap`
to a missing operator-visible refusal. research-institution's dispatcher
(`research start <program>`) needed to refuse to launch while the
architecture-review gate is unresolved. Per `@ADR-0006`, the dispatcher
owns the refusal logic but reads the gate verdict from mathlint.

Today the dispatcher reads the gate verdict by parsing `mathlint roadmap`
output (`TASK KIND: ARCHITECTURE_REVIEW_REQUIRED`). This works but is
fragile: it depends on roadmap's text format, runs ~0.6s per dispatch,
and is invisible to mathlint's other gate consumers (the supervisor, the
work source). The clean fix is a first-class programmatic verdict.

## Requested behavior (in mathlint)

1. **New flag on `mathlint architect-review`: `--program <name>`**
   - Validates `<name>` against the program registry (`mathlint
     program-list`); rejects unknown programs with exit 2 + JSON
     `{ "error": "MATHLINT_PROGRAM_UNKNOWN", "program": <name> }`.
   - Scopes the architect review to one program (today the command is
     global).

2. **New machine-readable verdict mode: `--verdict` or `--json`**
   - Exits with one of:
     - `0` — gate open; `{"gate": "open", "task_kind": "<kind>",
       "reason": "<text>", "since_unix": <float>}`.
     - `1` — gate closed; same JSON with `"gate": "closed"` and
       `task_kind = "ARCHITECTURE_REVIEW_REQUIRED"`.
     - `2` — program not in registry.
   - The JSON's `gate` field is the canonical verdict. `reason` is the
     parsed `REASON:` line from the roadmap.

3. **Companion: `mathlint gate-check --program <name>`**
   - Returns only the verdict (no review body). Suitable for hot-loop
     callers like the dispatcher or the supervisor's circuit. Exit 0/1/2
     as above.

## Why this is cross-repo

- mathlint's CLI surface is math-engine-owned. research-institution
  cannot add flags to it.
- The `TASK KIND:` line format is in math-engine's roadmap output; a
  change to that format would silently break research-institution's
  current refusal. A programmatic verdict eliminates the parse
  dependency.

## Migration impact

- research-institution's current `check_gate()` (which parses
  roadmap text) becomes a fallback when `mathlint architect-review
  --verdict --program <name>` is unavailable.
- The fallback path stays in the dispatcher indefinitely; the
  primary path upgrades as mathlint ships the verdict.

## Acceptance criteria

- [ ] `mathlint architect-review --program kaplansky --verdict` exits 0
      with structured JSON when the gate is open.
- [ ] Same command exits 1 with structured JSON when the gate is
      closed (today's kaplansky roadmap state).
- [ ] `mathlint gate-check --program <name>` exists and returns the same
      verdict in less than 0.1s (hot-loop safe).
- [ ] research-institution's `tests/test_gate_check.py` switches the
      primary test path to the new verdict command; the roadmap-parse
      test path becomes `test_gate_fallback_*`.

## Cross-references

- `@ADR-0006` — research-institution owns only catalog + bootstrap + green gate + dispatcher.
- `@INV-0091` — mathlint does not ship program launchers.
- `@INV-0093` — institution green gate is the canonical wiring evidence.
- `research-institution/HARDENING-CHECKLIST.md §C.1` — original ask.
