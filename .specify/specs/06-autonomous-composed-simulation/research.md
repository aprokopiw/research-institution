# 06 — Research

## Existing assets reused

- `research_institution/gates/aggregate.py` `v-compose` stage.
- `pi_monitor/tests/substrate/` (entry 05).
- `math/src/mathlint/self_test/sample_program/scenarios/`
  (entry 04).
- `pi_monitor/state/audit/audit_chain_verify.py` (production).
- `research-institution/scripts/verify-institution.sh` (extended).
- `.specify/memory/constitution-verify.md`.

## Rejected parallel approaches (with reasons)

- **R1.** A new ad-hoc Bash suite runner under
  `scripts/verify-simulation.sh`. REJECTED: per §3.5.a / §9.2
  one canonical CLI; the shell script only sets env.
- **R2.** A second process runner parallel to the existing
  supervisor internals. REJECTED: §6 (no second supervisor).
- **R3.** Manual finalize helpers in any S2 scenario. REJECTED:
  §3.5.e.

## Unresolved questions resolved before implementation

| Question | Resolution |
|---|---|
| Does entry 06 own the mutation tests? | No — entry 10 wires VG-6 globally. |
| Does entry 06 ship `provider_live`? | No — entry 07. |
| What about the 15 critical mutants from §12 of guide? | Entry 06 ships the substrate that lets entry 10 verify them. |

## Open risks

- **R-A.** A scenario's temp_root path leaks across cleanup.
  Resource oracle catches.
- **R-B.** A scenario's transcript ever contains a forbidden
  event under any path. Transcript oracle catches.

## Cross-references

- Entry 04's scenarios.
- Entry 05's substrate.
- `research_institution/gates/aggregate.py` `v-compose`.
