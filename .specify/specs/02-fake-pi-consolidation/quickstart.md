# 02 — Quickstart

## Local verification commands

```sh
# 1. Canonical commander.
cd ~/Documents/andrei/pi_monitor
make test-suite-unified
echo "exit=$?"   # 0

# 2. Tier-routed subset.
make test-tier-fast
echo "exit=$?"   # 0

# 3. Collection parity.
make test-suite-parity
echo "exit=$?"   # 0

# 4. Static checks.
pytest -q tests/static/test_closed_tier_vocabulary.py \
       tests/static/test_dependency_vocabulary.py \
       tests/static/test_skip_xfail_baseline.py \
       tests/static/test_collection_parity.py \
       tests/static/test_fake_pi_inventory.py
echo "exit=$?"   # 0

# 5. Canonical script must not regress.
make check-prime-directive
echo "exit=$?"   # 0

# 6. Fake-Pi selftest.
python -m pi_monitor.tests.support.fake_pi_rpc --selftest
echo "exit=$?"   # 0

# 7. Happy-path tests still green.
pytest -q tests/test_mathlint_campaign.py \
       tests/test_mathlint_faults.py \
       tests/test_compose_happy_path.py \
       tests/test_compose_rate_limit_trip.py \
       tests/test_compose_stop.py \
       tests/test_supervisor_dispatch_rate_limit.py \
       tests/test_state_machine_reconcile.py \
       tests/test_state_machine_execution_lifecycle.py
echo "exit=$?"   # 0
```

## Expected gate statuses

| Gate | Status |
|---|---|
| VG-0 | `PASS` |
| VG-1 | `PASS` |
| VG-2 | `PASS` |
| VG-3 | `PASS` |
| VG-4…VG-8 | `NOT_APPLICABLE` |

## Artifact locations

```
pi_monitor/
  Makefile                                    # amended
  pyproject.toml                              # amended
  AGENTS.md                                   # cross-ref amended
  README.md                                   # cross-ref amended
  tests/
    support/
      __init__.py
      fake_pi_rpc.py
      test_fake_pi_rpc.py
    static/
      test_closed_tier_vocabulary.py
      test_dependency_vocabulary.py
      test_skip_xfail_baseline.py
      skip_xfail_baseline.toml
      test_collection_parity.py
      test_fake_pi_inventory.py
    helpers.py                                # refactored (thin wrapper)
    mathlint_campaign.py                      # docstring relabel
    # many test files unchanged, all green
  docs/adr/NNNN-fake-pi-consolidation.md      # new local ADR

research-institution/
  .specify/
    memory/
      transient-exemptions.toml               # pi_monitor rows added
    specs/
      02-fake-pi-consolidation/
        spec.md plan.md tasks.md
        research.md data-model.md
        quickstart.md META.md
```

## Cleanup on failure

- A parity check fails → revert the per-commit that introduced the
  asymmetry; investigate the helper-injection source.
- A second fake-Pi generator slips in → revert; check
  `test_fake_pi_inventory.py` for the missed pattern.

## Cross-references

- `spec.md` "cannot claim done when…".
- `transient-exemptions.toml` rows seeded by this entry.
