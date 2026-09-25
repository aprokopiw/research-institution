# 01 — Data Model

## `tests/static/skip_xfail_baseline.toml` (TOML)

Schema (one row per existing skip / skipif / importorskip / xfail
call site, classified):

```toml
version = "0.0.0"
generated_by = "01-test-suite-rationalization"

[[entry]]
file = "tests/foo/bar.py"
line = 123
node_id_prefix = "tests/foo/bar.py::test_xyz"
reason_code = "platform_not_applicable"   # required | optional_dependency | platform_not_applicable | stale
tier = "unit"
note = "Skipped on non-macOS — pre-existing"
added_by_commit = "<commit sha>"
```

Reason codes:

| Code | Meaning | Treatment |
|---|---|---|
| `required` | The skip masks a real required-tier defect. | Forbidden; gate `FAIL`. |
| `optional_dependency` | Depends on formal-backend / postgres / model. | Preflights to lane `BLOCKED`. |
| `platform_not_applicable` | Hard-coded to one platform. | Counts toward `NOT_APPLICABLE`. |
| `stale` | Authored for a now-deleted feature. | Must be removed in same commit. |

The total `required` count must be zero. Any new skip requires a
new `[[entry]]` row with `reason_code != required` (or removal of
the skip entirely).

Self-test (`test_skip_xfail_baseline.py`) verifies:

- file parses;
- every `[[entry]]` row has all required fields;
- every row's `file:line` corresponds to an AST-detected skip /
  xfail call site in math source;
- the count of `reason_code = "required"` rows is zero;
- the ratchet: the running total decreases monotonically over
  merges.

## Cross-references

- `constitution-verify.md` §2 (dependency vocabulary) +
  §2.1 (missing dep → `BLOCKED`).
- `constitution-verify.md` §3 + §5 (anti-cheat rules + skip
  counts).
