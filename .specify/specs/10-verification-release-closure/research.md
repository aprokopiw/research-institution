# 10 — Research

## Existing assets reused

- All eleven spec dirs' META + attestations.
- `research-institution/gates/verify_simulation/` (06/07/08
  outputs).
- `research-institution/prime_directive/` (entry 09).
- `research-institution/.agents/transient/test_and_simulation_suite.md`
  — to be retired.
- `~/.pi/agent/extensions/prime-directive-guard.ts` — block
  message updated.

## Rejected parallel approaches (with reasons)

- **R1.** Re-running the master guide §12's fifteen critical
  mutants as actual `cosmic-ray`/`mutmut` runs on day one.
  REJECTED: the program already passes them as units; the
  release gate consumes those unit results.
- **R2.** Editing AGENTS.md / prime-directive section text.
  REJECTED: that section is sanctioned; entry 10 only retires
  the **transient** guide that originally specified the
  program, not the AGENTS.md cross-references.

## Unresolved questions resolved before implementation

| Question | Resolution |
|---|---|
| Does the retired guide still get matched by the strengthened grep? | No — filename `test_and_simulation_suite.retired.md` (underscore + .retired.md suffix) is outside the regex; the file's contents are also exempt because `transient_` is in the exempted list. |
| Will the 15 mutants be deep-mutation-tested? | They are unit-killed at the entry that owns them; the release aggregator consumes per-entry evidence. |

## Open risks

- **R-A.** A doc-truth audit finds an active forbidden string.
  Pre-emptively noted; F-3.

## Cross-references

- All eleven spec dirs.
- `@CTR-0095-prime-directive-check-script-contract` (entry 00's).
- All entry-04 / 05 / 06 / 07 / 08 / 09 META files.
