# Wire Contracts

Every boundary in research-institution has a typed contract pinned by
golden-file tests. This document is the operator-readable index of
those contracts; the code is the canonical source.

| Boundary | Wire format | Typed contract | Drift guard |
|---|---|---|---|
| `catalog/programs.toml` | TOML | `research_institution.catalog.Program` | `tests/test_catalog.py`, `tests/test_catalog_consistent.py` |
| `mathlint roadmap` (text) | `TASK KIND: <value>` + `REASON: <text>` | `research_institution.contracts.{TaskKind, GateVerdictStatus, GateVerdict}` (`GateVerdict.from_text`) | `tests/test_gate_check.py`, `tests/test_contracts.py`, `tests/test_package_boundary.py` |
| `mathlint live-run` (subprocess) | `[mathlint, live-run, --confirm-live, ...]` | `research_institution.dispatcher.Dispatcher.run_live` | `tests/test_dispatcher.py::test_argv_strings_are_pinned` |
| `mathlint research-stop` (subprocess) | `[mathlint, research-stop]` | `Dispatcher.stop_research` | `tests/test_dispatcher.py` |
| `mathlint research-status` (subprocess) | `[mathlint, research-status]` | `Dispatcher.read_status` | `tests/test_dispatcher.py` |
| `pi-monitor watch` (subprocess) | `[pi-monitor, watch, --config, --script, --interval]` | `Dispatcher.run_watch` | `tests/test_dispatcher.py::test_run_watch_argv_shape` |
| Source-report JSONL (read-only) | JSONL → `SourceReport` | `research_institution.contracts.source_reports.parse_source_report` | `tests/test_source_reports_schema.py` |
| Source-decision envelope (read-only) | dict `{kind, source_revision, decided_unix, ...}` | `research_institution.contracts.source_decision.{Dispatch, Wait, OperatorRequired, Stop}` | `tests/test_source_decision_contract.py` |
| `entry_point` field | `<dotted.module>:<callable>` | `research_institution.contracts.entry_point.parse_entry_point` | `tests/test_entry_point_contract.py` |
| Skill markdown (generated) | YAML frontmatter + body | `research_institution.contracts.skill_template.render_skill` | `tests/test_skill_template.py` |
| Dispatcher CLI verbs | `--help` text | `research_institution.contracts.DispatcherVerb` | `tests/test_contracts.py::test_dispatcher_verb_is_canonical_set` |
| Dispatcher exit codes | numeric | `research_institution.contracts.ExitCode` | `tests/test_contracts.py::test_exit_code_values_match_operator_convention` |
| Env-var + path resolution | env vars | `research_institution.paths.{Environment, institution_dir, ...}` | `tests/test_paths.py` |
| Subprocess policy | `SubprocessPolicy` defaults | `Dispatcher.policy` | `tests/test_dispatcher.py::test_default_policy_timeout_values` |

## Drift detection

When a sibling repo changes a wire format:

1. The contract test for that boundary fails (e.g. `mathlint` adds
   a new `TASK KIND:` value → `tests/test_contracts.py` fails the
   `task_kind_is_frozen_enum` assertion until the dispatcher adds a
   matching enum member).
2. The failure pinpoints the exact field that drifted; the operator
   reads the failure message + the cross-repo ADR (e.g.
   `adr-0007-mathlint-architect-review-program-flag.md`) to decide
   how to update the dispatcher.
3. If the new field is a strict superset of the old, the dispatcher
   extends its enum (one-line edit). If the new field is incompatible
   (e.g. rename), the cross-repo ADR is filed first; the dispatcher's
   update lands as a separate commit that cites the ADR.

### Caught drift (filed as cross-repo ADRs)

The following drifts were caught by tests in this repo and filed as
ADRs in `docs/semantic/adr/cross-repo-requests/`:

- `@ADR-0010` — mathlint emits `"Dispatch"` (capitalized) but
  pi_monitor's canonical kind is `"dispatch"` (lowercase). The
  parser rejects the literal mathlint output; tracked via
  `test_mathlint_decide_next_envelope_parses`.

## Testability infrastructure (shared)

- `tests/_fakes.py` — `FakeRunner`, `FakeClock`, `FakeEnvironment`,
  `RecordingEnvironment`, `SystemClock`, `OsEnviron`. Every test
  that touches subprocess or env vars should use these.
- The dispatcher accepts `runner=`, `environment=`, `clock=`,
  `policy=` keyword args so tests inject fakes without
  monkeypatching globals.
- The CLI's path resolution accepts an `env` argument (typed
  `Environment` protocol) for the same reason.

## Adding a new contract

1. Define a typed model in `research_institution/contracts/`.
2. Add a drift test in `tests/test_<contract>.py` (golden file +
   unknown-value-coerces-to-OTHER).
3. Add the row to this table.
4. If the contract is operator-facing, document the failure mode in
   `docs/operations/dispatcher-cli-reference.md` (or the appropriate
   ops doc).

## Why "StrEnum over `Literal[...]` over `str`"

`mathlint.orchestration.vocabulary` documents the choice:

- `Literal[...]` aliases give static exhaustiveness checks but no
  runtime guard (typos at call sites crash on KeyError).
- `str` is too permissive; every consumer has to validate.
- `StrEnum` gives both: static exhaustiveness (pyright strict) AND
  runtime constructor (`enum_cls(value)` raises ValueError on
  unknown), with JSON round-trip semantics (`member == member.value`).

## Why "Environment protocol + fake injection"

The dispatcher used to read `os.environ` directly inside its methods.
Tests had to use `monkeypatch.setenv`, which is global, sequential,
and breaks when multiple tests share a fixture. The Environment
protocol + `FakeEnvironment` injection:

- Lets every Dispatcher method be unit-tested with a deterministic
  env (no monkeypatch).
- Lets one test assert "the dispatcher read this var but not that
  one" via `RecordingEnvironment`.
- Decouples the dispatcher from `os` (a future async runtime can
  inject a different env backend without changing call sites).

## Cross-references

- `@ADR-0006` — research-institution owns only catalog + bootstrap + green gate + dispatcher.
- `research_institution/contracts/` — the typed vocabulary module.
- `research_institution/dispatcher.py` — the in-process Dispatcher API.
- `research_institution/paths.py` — env + path resolution (the
  single source of truth for env reads).
- `tests/_fakes.py` — shared testability infrastructure.
- `docs/operations/dispatcher-cli-reference.md` — CLI surface.
