# 06 — Data Model

## `Scenario` (re-export from entry 05's `fake_pi_rpc.Scenario`)

```python
@dataclass(frozen=True, slots=True)
class Scenario:
    api_version: Literal[1]
    name: str
    steps: tuple[Step, ...]
    minimum_tier: Literal["process", "deployment", "provider_live"]
    maximum_runtime_seconds: float
    fault_injection_point: str | None
    expected_final_state: str
    required_event_subsequence: tuple[str, ...]
    forbidden_events: tuple[str, ...]
```

## `ScenarioReport`

```python
@dataclass(frozen=True, slots=True)
class ScenarioReport:
    scenario_name: str
    runtime_seconds: float
    transcript: TranscriptReport
    audit: AuditReport
    exactly_once: ExactlyOnceReport
    frontier: FrontierReport
    resource: ResourceReport

    @property
    def ok(self) -> bool:
        return all(r.ok for r in (
            self.transcript, self.audit,
            self.exactly_once, self.frontier, self.resource,
        ))
```

## `TempRoot`

```python
@dataclass(frozen=True, slots=True)
class TempRoot:
    path: Path
    scenario: str
    cleanup_on_success: bool = True
    preserve_on_failure: bool = True
```

## Cross-references

- `pi_monitor/tests/substrate/` (entry 05 helpers).
- `math/src/mathlint/self_test/sample_program/scenarios/`
  (entry 04 scenarios; referenced by name).
- `constitution-verify.md` §3 (gate-status algebra),
  §6 (no second supervisor), §9 (one source of truth).
