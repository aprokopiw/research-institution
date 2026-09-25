# 04 — Quickstart

## Local verification commands

```sh
# 1. Readiness mode unchanged.
cd ~/Documents/andrei/math
pytest -q tests/self_test/test_readiness_bytes_unchanged.py
echo "exit=$?"   # 0

# 2. Property tests.
MATHLINT_SELF_TEST_MODE=simulation pytest -q tests/self_test/
echo "exit=$?"   # 0

# 3. Hermetic self-test gate.
bash scripts/check-local-system-readiness.sh \
    --skip-external \
    --use-program=self_test-sample
echo "exit=$?"   # 0

# 4. Canonical script.
make check-prime-directive
echo "exit=$?"   # 0
```

## Expected decision transcripts

Six canonical scenarios produce the following ordered decisions:

### `happy-three-cycle`

```
1. Dispatch(op-1, ...)   ; revision = rev-1
2. Dispatch(op-2, ...)   ; revision = rev-2
3. Dispatch(op-3, ...)   ; revision = rev-3
4. Stop(completed)       ; revision = rev-4
```

### `no-delta-redirect`

```
1. Dispatch(op-1, ...)  no-delta accepted; revision unchanged
2. Dispatch(op-1, ...)  no-delta threshold reached → operation/role revisits
3. Dispatch(op-2, ...)  artifact written; revision = rev-2
4. Stop(completed)
```

### `blocked-alternate-route`

```
1. Blocked(op-1, evidence)  → no dispatch
2. Dispatch(op-2, ...)      → eligible alternate
3. Stop(completed)
```

### `source-wait-then-work`

```
1. Wait(deadline_unix = T+5)   no dispatch before T+5
2. Dispatch(op-1, ...)         dispatched at T+5
3. Stop(completed)
```

### `operator-required`

```
1. Dispatch(op-1, ...)
2. OperatorRequired(reason = ...)
3. (operator action — outside sample's authority)
4. Dispatch(op-2, ...)
```

### `stop-completion`

```
1. Dispatch(op-1, ...)
2. Dispatch(op-2, ...)
3. Dispatch(op-3, ...)
4. Stop(completed)
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
math/
  src/mathlint/self_test/sample_program/
    work_source.py                            # mode-dispatch
    register.py                               # env-gate extended
    simulation_state.py                       # new
    simulation_reducer.py                     # new
    simulation_register.py                    # new
    _support/canonical_bytes.py               # new
    scenarios/
      happy-three-cycle.json
      no-delta-redirect.json
      blocked-alternate.json
      source-wait-then-work.json
      operator-required.json
      stop-completion.json
  tests/self_test/
    test_readiness_bytes_unchanged.py         # new
    test_simulation_state_bytes.py            # new
    test_idempotent_report.py                 # new
    test_conflicting_report_rejected.py       # new
    test_revision_monotonic.py                # new
    test_completion_absorbing.py              # new
    test_wait_deadline_restart.py             # new
    test_sample_work_source.py                # preserved
    test_end_to_end_smoke.py                  # preserved
  docs/operations/run-self-test.md            # amended
```

## Cross-references

- `spec.md` cannot-claim-done list.
- Entry 06 consumes the six scenarios by name.
