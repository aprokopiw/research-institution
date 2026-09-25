# 08 — Data Model

## `CompatMatrixRunner`

```python
@dataclass(frozen=True, slots=True)
class CompatMatrixCell:
    python_version: str
    math_version: str
    pi_monitor_version: str
    kaplansky_version: str
    research_institution_version: str
    status: Literal["PASS", "FAIL", "BLOCKED", "NOT_APPLICABLE"]
    runtime_seconds: float
    failure_summary: str | None
```

## `EditableVsInstalledReport`

```python
@dataclass(frozen=True, slots=True)
class EditableVsInstalledReport:
    scenario: str
    editable_envelope_bytes: bytes
    installed_envelope_bytes: bytes
    @property
    def byte_equal(self) -> bool: ...
```

## `BackupRestoreReport`

```python
@dataclass(frozen=True, slots=True)
class BackupRestoreReport:
    duplicate_executions: int  # must be 0
    duplicate_reports: int     # must be 0
    resume_pass_count: int     # must be 1
```

## Cross-references

- `constitution-verify.md` §3 (gate-status algebra).
