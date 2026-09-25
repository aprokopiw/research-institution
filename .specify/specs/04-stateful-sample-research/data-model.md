# 04 — Data Model

## `Scenario`

```python
@dataclass(frozen=True, slots=True)
class Scenario:
    api_version: Literal[1]
    name: str
    operations: tuple[Operation, ...]
    directed_cycles: tuple[DirectedCycle, ...]
    timeouts: Timeouts
```

## `Operation`

```python
@dataclass(frozen=True, slots=True)
class Operation:
    operation_id: str
    role: RoleName        # re-export from pi_monitor.work.work_source
    workspace: WorkspaceName
    payload: Mapping[str, JsonValue]   # @ADR-0014 I.2 discipline
    preconditions: tuple[str, ...] = ()
    postconditions: tuple[str, ...] = ()
```

## `Frontier`

```python
@dataclass(frozen=True, slots=True)
class Frontier:
    revision_fingerprint: str     # sha256 of canonical frontier bytes
    observed_unix: float
    current_operation_id: str
    state: Literal["pending", "running", "completed", "blocked"]
```

## `AcceptedReport`

```python
@dataclass(frozen=True, slots=True)
class AcceptedReport:
    source_identity: SourceIdentity
    operation_id: str
    revision_fingerprint: str     # must match frontier at write
    payload: Mapping[str, JsonValue]
    received_unix: float
    outcome: Literal["completed", "blocked", "no_delta"]
```

## `DecisionRecord`

```python
@dataclass(frozen=True, slots=True)
class DecisionRecord:
    decided_unix: float
    source_revision: SourceRevision
    decision: Dispatch | Wait | OperatorRequired | Stop
    reason: str
    reason_code: Literal[...]    # closed set per pi_monitor.work
```

## `reduce(state, accepted_reports) -> (state, decision)`

Pure function. Cannot mutate inputs. Reads
`frontier.json` / appends to `reports.jsonl` /
`decisions.jsonl` are delegated to the boundary adapter
(`boundary_io.py`) outside the reducer's signature.

## Cross-references

- `pi_monitor.work.work_source` — wire authority types.
- `math/src/mathlint/program_providers.py` — slot authorities.
- `constitution-verify.md` §7 (sample-program contract).
