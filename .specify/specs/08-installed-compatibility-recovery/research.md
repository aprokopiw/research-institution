# 08 — Research

## Existing assets reused

- `research_institution/gates/verify_simulation/` (entry 06).
- `research-institution/pyproject.toml` `[dependency-groups]`
  pin matrix.
- `math/pyproject.toml` `[tool.hatch.metadata]`.
- `pi_monitor/pyproject.toml`.
- `kaplansky/pyproject.toml`.
- `.specify/memory/constitution-verify.md` §3, §5, §10.

## Rejected parallel approaches (with reasons)

- **R1.** A separate `scripts/compat-matrix.sh` Bash suite.
  REJECTED: per §9, one canonical CLI.
- **R2.** Reimplementing the wire codecs in the matrix probe.
  REJECTED: per §6, no second supervisor / wire.

## Unresolved questions resolved before implementation

| Question | Resolution |
|---|---|
| Does `BLOCKED` ever `PASS`? | Only when the missing ingredient is supplied (Python / wheel / etc.). |
| Is backup-restore a `pass-rate` assertion? | Yes — it asserts the resume is single-pass within bounded deadline. |

## Open risks

- **R-A.** A clean venv build for a pinned Python version fails.
  The status is `BLOCKED`; the matrix runner honors this.

## Cross-references

- Entry 06's CLI substrate.
- `@CTR-0020` (three-repo wire).
