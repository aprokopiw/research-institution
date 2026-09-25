# 05 — Quickstart

## Local verification commands

```sh
# 1. Substrate helpers exist + green.
cd ~/Documents/andrei/pi_monitor
pytest -q tests/substrate/
echo "exit=$?"   # 0

# 2. Campaign + fault tests retargeted to substrate.
pytest -q tests/mathlint_campaign.py tests/test_mathlint_faults.py
echo "exit=$?"   # 0

# 3. Static checks.
pytest -q tests/static/test_substrate_metadata.py \
       tests/static/test_substrate_inventory.py
echo "exit=$?"   # 0

# 4. Canonical prime-directive grep.
make check-prime-directive
echo "exit=$?"   # 0

# 5. Confirm manual finalize hooks are gone.
! grep -E 'finalize_attempt|finalize_record|complete_active|record_publication' \
      tests/mathlint_campaign.py
echo "exit=$?"   # 1 (none found)
```

## Expected gate statuses

| Gate | Status |
|---|---|
| VG-0 | `PASS` |
| VG-1 | `PASS` |
| VG-2 | `PASS` |
| VG-3 | `PASS` |
| VG-4 | partial `PASS` — substrate helpers contribute process-tier S2 evidence consumed by entry 06 |
| VG-5…VG-8 | `NOT_APPLICABLE` |

## Artifact locations

```
pi_monitor/
  tests/
    substrate/
      __init__.py
      fake_pi_scenario.py
      restart_at_boundary.py
      transcript_oracle.py
      process_tree_cleanup.py
      timing_seams.py
    static/
      test_substrate_metadata.py
      test_substrate_inventory.py
    mathlint_campaign.py                # manual finalize removed
    test_mathlint_faults.py             # retargeted
  AGENTS.md                             # cross-ref amended
research-institution/
  .specify/memory/transient-exemptions.toml   # rows added
  .specify/specs/05-process-fault-simulation/
```

## Cross-references

- `spec.md` cannot-claim-done list.
- Entry 06's S2 scenarios consume these helpers.
