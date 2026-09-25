# 05 — Data Model

## `BoundaryName` (closed enum)

```python
class BoundaryName(StrEnum):
    BEFORE_EXECUTION_RECORD = "before_execution_record"
    AFTER_INTENT_BEFORE_WORKER_LAUNCH = "after_intent_before_worker_launch"
    # … full list per FR-2 …
    DURING_SOURCE_PROCESS_RESTART_BACKOFF = "during_source_process_restart_backoff"
```

## `RestartAtBoundaryHelper`

```python
@dataclass(frozen=True, slots=True)
class RestartAtBoundaryHelper:
    boundary: BoundaryName
    process_group_id: int | None = None

@dataclass(frozen=True, slots=True)
class ReconcileObserved:
    boundary: BoundaryName
    verdict: Literal["issue_once", "supersede", "hold", "noop", "reactivate"]
    elapsed_unix: float
```

## `TranscriptOracle`

```python
@dataclass(frozen=True, slots=True)
class TranscriptOracle:
    denied_substrings: tuple[str, ...] = (
        "OPENAI_API_KEY=", "sk-", "Bearer ",
    )

    def check(self, lines: Iterable[str]) -> tuple[str, ...]:
        """Return offending lines (raise if any)."""
```

## `FakeSubprocessClock`

```python
@dataclass
class FakeSubprocessClock:
    initial: float = 0.0
    def advance(self, *, seconds: float) -> None: ...
    def now_unix(self) -> float: float(self._initial + self._offset)
```

## Cross-references

- `pi_monitor/src/pi_monitor/state/execution_records.py`
  (reconcile verdict vocabulary authority).
- `constitution-verify.md` §3 (gate-status algebra), §5
  (anti-cheat rules).
