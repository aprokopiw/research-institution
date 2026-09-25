# 04 — Research

## Existing assets reused

- `math/src/mathlint/self_test/sample_program/work_source.py` —
  readiness envelope body. **MUST NOT** change byte-for-byte.
- `math/src/mathlint/self_test/sample_program/register.py` —
  sentinel register behavior. **MUST NOT** change in readiness.
- `math/tests/self_test/{test_sample_work_source.py,
  test_end_to_end_smoke.py}` — preserved.
- `math/src/mathlint/program_providers.py` — slot authority;
  receiving the optional `report_sink` field.
- `math/src/mathlint/orchestration/real_source.py` —
  `configured_provider`, `decide_next`, `record_report`. The
  adapter test exercises this code path.
- `pi_monitor.work.work_source` — wire authority for
  `Dispatch`, `Wait`, `OperatorRequired`, `Stop`, `WorkRequest`.
- `math/docs/operations/run-self-test.md` — augmented.
- `@ADR-0088`, `@ADR-0089`, `@INV-0088`, `@CTR-0085`,
  `@CTR-0020`, `@ADR-0014` — durable records.

## Rejected parallel approaches (with reasons)

- **R1.** Implement the reducer outside
  `math/src/mathlint/self_test/sample_program/`. REJECTED: the
  sample lives there; one canonical owner.
- **R2.** Re-use kaplansky's `src/kaplansky/work_selection.py`
  reducer. REJECTED: `@ADR-0014` (mathlint does not import
  program-named modules).
- **R3.** Use real math source decisions in the sample. REJECTED:
  today's readiness envelope is hermetic by construction
  (`@INV-0088`); simulation mode is also hermetic.

## Unresolved questions resolved before implementation

| Question | Resolution |
|---|---|
| Does FR-7 (`report_sink`) always ship? | Invoked conditionally, depending on entry 06's need for the report-callback seam at the provider boundary. If entry 06 prefers a different seam (e.g. reusing `record_report` directly in `real_source`), FR-7 is `NOT_APPLICABLE`. |
| Is the simulation reducer pure? | Yes — `reduce(state, accepted_reports) -> (state, decision)` is a pure function; filesystem I/O happens at the boundary adapter (an in-entry thin layer). |

## Open risks

- **R-A.** A mutation of `sample_work_source` accidentally
  changes the readiness envelope bytes. `test_readiness_bytes_unchanged.py`
  catches it.
- **R-B.** A two-process write to `reports.jsonl` produces
  inconsistency. Atomic write via tempfile + os.replace
  (entry's boundary adapter).

## Cross-references

- `pi_monitor.work.work_source` (typed envelopes).
- `math/src/mathlint/program_providers.py` (slot authorities).
- `constitution-verify.md` §7 (sample-program contract).
