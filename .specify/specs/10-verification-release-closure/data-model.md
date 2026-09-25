# 10 — Data Model

## `ReleaseReport`

```python
@dataclass(frozen=True, slots=True)
class ReleaseReport:
    rows: tuple["ReleaseRow", ...]

@dataclass(frozen=True, slots=True)
class ReleaseRow:
    check_name: str   # one of: every_primary_tier_has_at_least_one,
                     # every_required_claim_has_evidence,
                     # every_scenario_has_metadata,
                     # every_critical_mutant_killed,
                     # flake_audit_clean,
                     # documentation_truth_clean,
                     # prime_directive_enforcement_clean
    status: Literal["PASS", "FAIL", "BLOCKED", "NOT_RUN", "NOT_APPLICABLE"]
    detail: str
    artifact_path: Path | None
```

## `MutationKiller`

```python
@dataclass(frozen=True, slots=True)
class MutationKiller:
    mutant_id: str        # FR-NN from master guide §12
    killer_test: str      # node-id of the test that kills it
    scenario: str | None  # if killed by scenario, not unit
```

## `CLAIM_MANIFEST.toml`

```toml
[[claim]]
id = "claim-001"
name = "provider_slot_resolves"
tier = "contract"
required = true
evidence_node_ids = ["tests/contracts/test_provider_slot.py::test_xyz"]
```

## Cross-references

- `constitution-verify.md` §3 (gate-status algebra), §5
  (action matrix).
- `transient-exemptions.toml` (managed by entry 00; entry 10's
  retirement adds a row).
