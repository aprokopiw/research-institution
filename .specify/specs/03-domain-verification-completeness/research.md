# 03 — Research

## Existing assets reused

- `kaplansky/programs/{kaplansky-roadmap,frozen-claims,modules,
   compute-registry,palomar,palomar-provenance}.toml` — schema
  source; RO for this entry.
- `kaplansky/src/kaplansky/work_selection.py` — work-selection
  reducer; referenced by `test_dependency_valid_operation.py`.
- `kaplansky/src/kaplansky/mathlint_plugin.py` — entry-point
  registration; referenced by `test_mathlint_provider.py`.
- `kaplansky/scripts/check-program-institution.sh` — wired to
  the canonical prime-directive script.
- `kaplansky/AGENTS.md` Spec-Kit software-engineering mode +
  cross-repo prevention section.
- `research-institution/.specify/memory/transient-exemptions.toml`
  — appends kaplansky rows.
- `research-institution/scripts/check-prime-directive.sh` —
  canonical, used at kaplansky HEAD.

## Rejected parallel approaches (with reasons)

- **R1.** Add stub test data to `programs/*`. REJECTED:
  research content is frozen; this entry only validates schema.
- **R2.** Re-implement work-selection reducer. REJECTED:
  `src/kaplansky/work_selection.py` is owned; this entry only
  asserts existing behavior.
- **R3.** Move kaplansky tests to a sibling repo. REJECTED:
  kaplansky is the canonical program repo; tests live here.

## Unresolved questions resolved before implementation

| Question | Resolution |
|---|---|
| Does this entry add new durable records? | No. |
| Does the runtime install-test (pip install + collision) belong here? | No — it is a deployment-composition concern and lives in entry 06 / 07. |
| What if `programs/*` has malformed TOML? | The schema round-trip test must catch it; that is the goal of the test. |

## Open risks

- **R-A.** The `programs/*.toml` files reference schemas
  introduced by math; if math's schema migrates, kaplansky's
  tests fail. The hand-off is documented in plan "Data and state
  migration" — kaplansky tests are capped to schema-migration
  checkpoints.
- **R-B.** A stale `frozen-claims` flag in CI history has been
  pre-decided for retirement; the test enforces deletion after
  expiry.

## Cross-references

- `kaplansky/AGENTS.md`.
- `math/src/mathlint/orchestration/roadmap.py` (roadmap types).
- `math/src/mathlint/program_providers.py` (slot authority).
- `@ADR-0014` (mathlint program-import discipline).
- `@INV-0088` (sample requires no external state).
- `@CTR-0020` (three-repo wire).
- `kaplansky/programs/kaplansky-roadmap.toml` (active phase 9,
  primary item K4, per current state).
