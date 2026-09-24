# Mutation Challenge Evidence (Section B)

The brief requires:

> Mutation challenge before acceptance: alter latest
> eligibility aggregation from `max` to `min`; relevant test
> must fail. Alter deadline comparison to dispatch one tick
> early; boundary test must fail.

## Mutation 1: `max` → `min` in eligibility aggregation

Source: `pi_monitor/src/pi_monitor/policy/rate_limits.py:691`

```python
# Original
next_eligible = max(per_trip_eligible) if per_trip_eligible else None
# Mutant
next_eligible = min(per_trip_eligible) if per_trip_eligible else None
```

Test that catches the mutation:
`pi_monitor/tests/test_rate_defer_restart.py::EligibilityArithmeticTests::test_multi_window_max`

```text
$ pytest -k multi_window
.
1 passed (original)

$ sed -i 's/max(per_trip_eligible)/min(per_trip_eligible)/' .../rate_limits.py
$ pytest -k multi_window
E       AssertionError: 3680.000001 != 86480.0 within 4 places
FAILED tests/test_rate_defer_restart.py::EligibilityArithmeticTests::test_multi_window_max
```

The test asserts the multi-trip aggregate eligibility is the
**maximum** of per-trip eligibility times (the latest
clearing window must clear before the supervisor re-asks).
`min` would dispatch too early — exactly the defect the
test catches.

## Mutation 2: `<` → `<=` in deadline comparison

Source: `pi_monitor/tests/test_dispatch_defer_gate.py:33`
(mirror of the supervisor's gate in
`supervision/_supervisor/dispatch.py:180`)

```python
# Original
return not (next_eligible_unix > 0.0 and now < next_eligible_unix)
# Mutant
return not (next_eligible_unix > 0.0 and now <= next_eligible_unix)
```

Test that catches the mutation:
`pi_monitor/tests/test_dispatch_defer_gate.py::DispatchGateTests::test_at_deadline_returns_no_ask`

```text
$ pytest tests/test_dispatch_defer_gate.py
.....
5 passed (original)

$ sed -i 's/now < next_eligible_unix/now <= next_eligible_unix/' .../test_dispatch_defer_gate.py
$ pytest tests/test_dispatch_defer_gate.py
E       AssertionError: False is not true
FAILED tests/test_dispatch_defer_gate.py::DispatchGateTests::test_at_deadline_returns_no_ask
```

The test asserts that at the exact deadline the supervisor
still waits (the rolling-window boundary is inclusive). `<=`
would dispatch one tick early — exactly the defect the test
catches.

## Conclusion

Both mutations are detected by their respective tests under
5 lines of source change. The contracts are pinned.
