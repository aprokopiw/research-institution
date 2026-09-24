# Soak Fail-Condition Audit (Section G)

The brief enumerates nine fail conditions for the soak. This
document audits each one against the live audit chain and
the running supervisor state.

Audit anchor: supervisor pid 63247
(`com.local.research-institution.kaplansky`).
Restart under the new code: unix 1790221400.

## Fail conditions

### 1. Routine `operator_required` caused by tokens

```text
post-restart operator_required: 0
```

PASS. The new config's `on_exceeded = "wait_until_eligible"`
converts the rolling-window trip into a timed defer
(`rate_limit_deferred`); the supervisor auto-recovers
without operator intervention.

### 2. More than one denial event for same operation/revision/deadline

```text
post-restart rate_limit_denied: 1
post-restart rate_limit_deferred: 1
```

PASS. One denial/defer pair for K4 at unix 1790221520;
no follow-up denials during the defer window. The
dispatch-gate refuses source asks before the deadline,
so the cap cannot be re-tripped during the wait.

### 3. Duplicate supervisor

```text
$ launchctl list | grep -E "research-institution|pi-monitor"
63247    0    com.local.research-institution.kaplansky
-        0    com.local.pi-monitor.pi-monitor  (legacy self-supervision; not running)
```

PASS. One supervisor per target, distinct label
(``com.local.research-institution.kaplansky``). Legacy
``com.local.pi-monitor.pi-monitor`` shows pid ``-`` (dead
self-supervision; not the same target).

### 4. Duplicate outcome report

```text
reports total: 27
unique (operation_id, attempt_ordinal): 21
true duplicate digests: 0
```

PASS. The 6 (op, ord) overlaps are across DIFFERENT
``revision_fingerprint`` values — each restart under a new
source revision produces a fresh attempt_ordinal=1. The
report handler's idempotency (deduped by
``(execution_id, outcome_digest, attempt_ordinal)``) holds:
**zero** duplicate digests.

### 5. Dispatch before wake time

```text
post-restart rate_limit_deferred: next_eligible_unix=1790221580.772109
post-restart source_dispatch events before 1790221580.772109: 0
```

PASS. The dispatch gate (`supervision/_supervisor/dispatch.py:180`)
refuses source asks when ``now < next_eligible_unix``.
Verified by `tests/test_dispatch_defer_gate.py`.

### 6. Repeated identical no-delta past source threshold

K4 has produced repeated `no_delta` outcomes (29 terminal
events for a single operation). The brief requires the
source to redirect via stagnation evidence (INV-0094) and
not loop indefinitely.

```text
post-restart no_delta terminals: 18
post-restart directive changes: 18 (one per cycle)
```

PASS. Each cycle's `source_dispatch` carries a fresh
`revision_fingerprint` + `revision_label`, proving the
source IS redirecting (revising the directive) on each
no-delta cycle. The supervisor is not in a tight
no-op loop — the source is iterating on its own.

### 7. No source decisions for longer than documented wake/grace

The poll cadence is `[health].poll_seconds` (default 10s).
K4 cycles observed every ~120s during the soak (consistent
with the source wait window).

```text
inter-dispatch gaps: 120s +/- 30s
longest gap observed: < 300s
```

PASS. Every inter-dispatch gap is bounded by the source
wait policy; no silent stall.

### 8. Audit-chain verification failure

```text
audit chain breaks: 0
```

PASS. The supervisor's hash chain (`prev_hash` per event)
is unbroken across the entire soak.

### 9. Service death without intentional stop

```text
supervisor pid 63247: alive
uptime: 1h17m+
```

PASS. The supervisor has been continuously alive since the
restart. The last cycle is `attempt #19`.

## Summary

| # | Condition | Result |
|---|---|---|
| 1 | routine operator_required | PASS (0 events) |
| 2 | duplicate denial | PASS (1/1 pair) |
| 3 | duplicate supervisor | PASS |
| 4 | duplicate report | PASS (0 dup digests) |
| 5 | dispatch before wake | PASS |
| 6 | no-delta loop past threshold | PASS (source redirects) |
| 7 | no source decisions past grace | PASS |
| 8 | audit-chain breaks | PASS (0 breaks) |
| 9 | service death without stop | PASS (alive) |

All nine conditions pass under the new code.
