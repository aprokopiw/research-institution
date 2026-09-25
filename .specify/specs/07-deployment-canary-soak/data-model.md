# 07 — Data Model

## `DeploymentRunner`

```python
@dataclass(frozen=True, slots=True)
class DeploymentRunner:
    four_cwds: tuple[Path, Path, Path, Path]
    rendered_program_arguments: tuple[str, ...]

    @property
    def dry_run_bytes(self) -> bytes: ...
    @property
    def actual_argv(self) -> tuple[str, ...]: ...
```

## `CanaryRunner`

```python
@dataclass(frozen=True, slots=True)
class CanaryRunner:
    scenario: Scenario            # rate-defer-restart
    state: Literal["BLOCKED", "PASS"] = "BLOCKED"

    def check_credentials(self) -> bool: ...
    def report(self) -> "CanaryReport": ...
```

## `CanaryReport`

```python
@dataclass(frozen=True, slots=True)
class CanaryReport:
    state: Literal["BLOCKED", "PASS"]
    runtime_seconds: float
    credential_fingerprint: str | None
    artifact_path: Path | None
    next_decision_kind: DecisionKind | None
```

## `SoakOracle`

```python
@dataclass
class SoakOracle:
    initial_rss: int
    initial_process_count: int
    initial_audit_size: int
    allowed_state_growth_factor: float = 1.5
    # ...

    def sample(self) -> "SoakSample": ...
    def assert_no_hot_loop(self, samples: Sequence["SoakSample"]) -> None: ...
```

## Cross-references

- `pi_monitor/src/pi_monitor/state/audit.py` — production audit
  verifier.
- `constitution-verify.md` §4 (VG-5/VG-7/VG-8 catalogue), §5
  (action matrix).
