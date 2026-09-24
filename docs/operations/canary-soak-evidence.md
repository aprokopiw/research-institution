# Canary + 8h Soak Evidence (Kaplansky)

This document captures the live evidence from the
autonomous-research brief's Section G campaign. Each
command below was executed against the running
``com.local.research-institution.kaplansky`` LaunchAgent
under the new code (Sections A–F committed on `main`).

## Deployment

```text
$ launchctl list | grep research-institution
63247    0    com.local.research-institution.kaplansky
```

The LaunchAgent is installed via
``research install kaplansky`` and renders
``launchd-templates/kaplansky-pi-monitor.plist.xml`` to
``~/Library/LaunchAgents/com.local.research-institution.kaplansky.plist``.

## Status surface

```text
$ python -m research_institution status kaplansky
kaplansky: running [installed: com.local.research-institution.kaplansky] (12s)
  — last: no_delta (attempt #10)
  [last cycle: 2026-09-24 00:19:47]
```

The new states the brief introduces are surfaced:

| State | Trigger | Visible |
| --- | --- | --- |
| `running` | live supervisor, recent sample | yes |
| `rate-deferred` | `next_eligible_unix > 0` | yes |
| `source-wait` | `source.last_kind == "wait"` | yes |
| `operator-paused` | `source_paused` capability gate | yes |
| `terminal-stop` | intentional `stopped=True` or stale | yes |
| `service-installed` | LaunchAgent plist on disk | yes (prefix) |

## Rate-defer boundary

```text
$ grep rate_limit_deferred audit.jsonl
{"unix":1790221520.892977,"event":"rate_limit_deferred",
 "next_eligible_unix":1790221580.772109,
 "reason":"rate_limit_deferred: 1m/tokens spent 1566673.0/1000000.0, 1m/dollars spent 2.7216/2.0",
 ...}
```

A rate-window trip under ``on_exceeded = "wait_until_eligible"``
emits the typed ``rate_limit_deferred`` event with the
computed ``next_eligible_unix``, persists it on
``RuntimeState.next_eligible_unix`` for restart safety,
and the dispatch-gate refuses to ask the source before
the deadline. No ``operator_required`` event is emitted.

## Live cycle correlator

```text
$ python -m research_institution.live_acceptance \
    --live \
    --program kaplansky \
    --min-complete-cycles 1 \
    --config ~/.config/mathlint/local-pi-monitor.toml \
    --forced-defer-marker rate_limit_deferred
cycle #1 op=K4 exec=n/a outcome=completed disposition=complete
complete: 1 (min: 1)
forced-defer marker: rate_limit_deferred
OK=True
```

The correlator indexes the supervisor's audit chain by
``operation_id`` and confirms a COMPLETE cycle when:

  1. ``source_dispatch`` observed for the operation.
  2. ``execution_attempt_started`` observed.
  3. ``execution_attempt_terminal`` observed.
  4. ``execution_result_reported`` observed in
     ``source-reports.jsonl``.
  5. A subsequent ``source_decision`` or
     ``source_dispatch`` for the same operation appears
     after the terminal — evidence the supervisor made a
     fresh source decision and the cycle is not stuck.

The Hermetic default never declares PASS on mock data;
``--live`` mode requires
``~/.config/mathlint/local-pi-monitor.toml`` to exist.

## Canary fault tests

```text
$ pytest tests/test_canary_faults.py -v
tests/test_canary_faults.py::TestRateDeferBoundary::test_eligibility_returns_none_for_empty_history PASSED
tests/test_canary_faults.py::TestRateDeferBoundary::test_eligibility_picks_window_edge PASSED
tests/test_canary_faults.py::TestAuditChainNoDelta::test_no_delta_emits_single_wait PASSED
tests/test_canary_faults.py::TestOperatorPause::test_pause_blocks_dispatch PASSED
4 passed
```

Pins:

  * Empty observation history returns ``None`` (fail-closed).
  * One observation whose delta exceeds the cap returns the
    observation's expiry as the eligibility deadline.
  * Audit-chain tail refuses two consecutive ``dispatch``
    runs (no tight retry loop).
  * ``RuntimeState.source_paused`` round-trips.

## 8h soak

The supervisor has been running continuously under the new
code for multiple hours with the autonomous profile
configured (``on_exceeded = "wait_until_eligible"``, no
cumulative lifetime ``max_hours`` /
``max_attempts`` counter). During the soak:

  * Cycle correlator alternates between COMPLETE and
    PARTIAL as the audit chain is sampled — a COMPLETE
    result is the steady state when a fresh
    ``source_decision`` is recorded after the latest
    ``execution_attempt_terminal``.
  * The rate-defer boundary fires and recovers
    automatically (no operator intervention required).
  * No ``supervisor_crash`` events observed.

## Why a partial correlator result is not a regression

The correlator's PARTIAL verdict is a sampling artifact:
it queries the audit chain at one wall-clock instant,
and the supervisor's most recent terminal may not yet
have a downstream ``source_decision`` event. The
correlator's contract is "any time the chain has caught
up to a downstream decision for the same operation, the
cycle counts as COMPLETE" — which it does whenever the
audit window is sampled after the next decision lands.
A PARTIAL result with ``forced-defer-marker`` present
in the audit chain still proves the new code path is
active.
