# 09 — Data Model

## `Attestation`

```python
@dataclass(frozen=True, slots=True)
class Attestation:
    schema_version: Literal["0.0.0"]
    spec_id: str
    owner_repo: str
    completion_sha: str
    config_fingerprint: str
    digest: str      # sha256:hex over completion_sha || config_fingerprint
    gate_report_blob: Path
    signed_off_by: str
```

## `ValidationResult`

```python
@dataclass(frozen=True, slots=True)
class ValidationResult:
    status: Literal["PASS", "FAIL", "BLOCKED", "NOT_RUN"]
    detail: str
```

## `METAValidationResult`

```python
@dataclass(frozen=True, slots=True)
class METAValidationResult:
    spec_id: str
    status: Literal["PASS", "FAIL"]
    missing_fields: tuple[str, ...]
```

## Cross-references

- `constitution-verify.md` §10 (prime-directive enforcement),
  §11 (META schema).
- `transient-exemptions.toml` (canonical registry).
