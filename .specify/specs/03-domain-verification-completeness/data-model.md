# 03 — Data Model

## `tests/static/skip_xfail_baseline.toml`

Same schema as entry 01 / 02, kaplansky paths.

## `programs/*.toml` schema (read-only; validated by tests)

Each file under `kaplansky/programs/*.toml` is loaded by the
schema-test utility that entry 04 may itself re-import. The
schemas:

- `kaplansky-roadmap.toml` (schema 1): `id`, `title`, `north_star`,
  `roadmap_version`, `current_phase`, `primary_item`, `strategic_notes`,
  `[[phases]]`, `[[milestones]]`, etc.
- `frozen-claims.toml`: list of frozen tuples; round-trippable.
- `palomar-provenance.toml`: provenance DAG with sha256 per row.
- `modules.toml`: module registry.
- `compute-registry.toml`: compute slot registry.
- `palomar.toml`: frontmatter-matched experiments registry.

The schema round-trip test uses a single uniform helper
`tests/domain/_support/toml_roundtrip.py` exposing:

```python
def roundtrip(path: Path) -> dict[str, Any]:
    """Parse, re-emit (sorted_keys=True, trailing newline),
    re-parse, and assert the two parsed dicts are equal."""

def rejects(path: Path, mutation: Callable[[dict], None]) -> None:
    """Apply the mutation, write, re-parse, expect a parse or
    validation error."""
```

## Cross-references

- `tests/domain/_support/toml_roundtrip.py` (helper; new).
- `constitution-verify.md` §7 (sample-program contract; frozen
  claims must remain frozen).
