# 06 — Quickstart

## Local verification commands

```sh
# 1. Fast tier (S0+S1).
cd ~/Documents/andrei/research-institution
python -m research_institution verify-simulation --tier fast
echo "exit=$?"   # 0

# 2. Full tier (S0..S3).
python -m research_institution verify-simulation --tier full
echo "exit=$?"   # 0

# 3. Single canonical scenario.
python -m research_institution verify-simulation \
    --tier process --scenario happy-three-cycle
echo "exit=$?"   # 0

# 4. Repeated-run flake check (20x).
bash scripts/twenty-repeated-runs.sh happy-three-cycle
echo "exit=$?"   # 0

# 5. Canonical prime-directive script.
make check-prime-directive
echo "exit=$?"   # 0

# 6. Existing green-gate still works.
bash scripts/verify-institution.sh
echo "exit=$?"   # 0
```

## Expected gate statuses

| Gate | Status |
|---|---|
| VG-0…VG-3 | `PASS` (via prior entries' artifacts) |
| **VG-4** | **`PASS`** — process simulation tier |
| VG-5 | `NOT_APPLICABLE` (entry 07) |
| VG-6 | `NOT_APPLICABLE` (entry 10) |
| VG-7 | `NOT_APPLICABLE` (entry 07) |
| VG-8 | `NOT_APPLICABLE` (entry 07) |

## Artifact locations

```
research-institution/
  research_institution/gates/verify_simulation/
    __init__.py
    cli.py
    runner.py
    temp_root.py
    scenarios.py
    oracle/
      __init__.py
      transcript.py
      audit.py
      exactly_once.py
      frontier.py
      resource.py
  tests/
    simulation/
      scenarios/
        happy_three_cycle.py
        no_delta_redirect.py
        blocked_alternate.py
        source_wait_then_work.py
        operator_required.py
        stop_completion.py
        rate_defer_restart.py
        worker_very_fast.py
        worker_slow_but_active.py
        malformed_result.py
        worker_crash_before_publication.py
        source_crash_before_report_ack.py
        execution_restart_after_publication.py
        duplicate_conflicting_report.py
      static/
        test_closed_scenario_metadata.py
    static/
      test_verify_simulation_inventory.py
  scripts/twenty-repeated-runs.sh
  pyproject.toml                              # console script registered
  research_institution/gates/aggregate.py      # v-compose extended
```

## Cross-references

- `spec.md` cannot-claim-done list.
- Entry 07 (deployment + canary + soak) consumes the CLI.
- Entry 10 wires VG-6 against this entry's substrate.
