# 02 — Data Model

## `Scenario` (Python dataclass, `pi_monitor/tests/support/fake_pi_rpc.py`)

```python
@dataclass(frozen=True, slots=True)
class Scenario:
    api_version: Literal[1]
    steps: tuple[Step, ...]

@dataclass(frozen=True, slots=True)
class Step:
    on_steer: ActionName           # closed enum; see FR-1 list
    delay_seconds: float = 0.0
    usage: UsageSample | None = None
    artifact: ArtifactWrite | None = None

class ActionName(StrEnum):
    SETTLE_AFTER_ARTIFACT_WRITE = "settle_after_artifact_write"
    # … full list per FR-1 …
    NEVER_SETTLE_BOUNDED_BY_TEST_TIMEOUT = "never_settle_bounded_by_test_timeout"
```

## `ScenarioParseError`

```python
class ScenarioParseError(ValueError):
    """Closed vocabulary violation; fields expose file, line, action,
    permitted actions list, and a suggested correction."""
    file: Path
    line: int
    action: str
    permitted: tuple[str, ...]
```

## `parse_scenario(path)` semantics

- Reads JSON.
- Asserts `api_version` is the locally-supported integer.
- Walks `steps[*]`, asserting each `on_steer` is in
  `ActionName.__members__`.
- Validates `usage` (`input`/`output`/`cache_read`/`cache_write`
  are non-negative ints) when present.
- Validates `artifact.path` does not escape `cwd` (no `..`
  segments) when present.
- Returns a `Scenario`.

## `run_scenario(scenario, env, *, stdout=PIPE, stderr=PIPE)`

- Spins the in-process equivalent of the CLI subprocess.
- Honors `env` as the deterministic-tiers environment.
- Captures stdout / stderr into in-memory buffers.
- Returns exit code; on parse error, raises `ScenarioParseError`
  before any side effect.

## `cli_main()`

CLI mode:

```
python -m pi_monitor.tests.support.fake_pi_rpc SCENARIO.json [--selftest]
```

- Without `--selftest`: parses the scenario; on success, prints a
  one-line summary "scenario ready: <N steps>" and exits 0.
- With `--selftest`: ignores the scenario path; runs the
  canned happy-path scenario; asserts exits 0 in < 2 s.
- With a malformed scenario: prints the parse-error details
  (file + line + suggested correction) and exits 78
  (EX_CONFIG).

## Cross-references

- `pi_monitor/src/pi_monitor/protocol/source_wire.py` — wire
  constants (`WIRE_API_VERSION`, error codes) are the same
  numerical ones; `Scenario.api_version` mirrors this.
- `constitution-verify.md` §8 (fake-Pi ownership and
  consolidation).
