# pi-monitor debug logging

How to enable structured stderr events from the mathlint source driver
when investigating why the supervisor made a particular decision.

## Enable source-driver DEBUG logging

The source driver (`mathlint.orchestration.real_source`) reads its
log level from the `MATHLINT_SOURCE_LOG_LEVEL` environment variable.
Set it to `DEBUG` to see every `decide_next` decision the source
emits, every dispatch envelope, and every report emission.

```sh
export MATHLINT_SOURCE_LOG_LEVEL=DEBUG
```

When set, mathlint writes one log line per call to stderr. The lines
follow Python's stdlib `logging` format:

```
2026-09-19 20:36:42,123 DEBUG real_source.decide_next -> kind=dispatch key=kaplansky.x attempt_ordinal=3
2026-09-19 20:36:42,456 DEBUG real_source.report_result outcome=blocked reason=...
```

To capture to a file for later review:

```sh
MATHLINT_SOURCE_LOG_LEVEL=DEBUG pi-monitor run --config ~/.config/mathlint/local-pi-monitor.toml 2> /tmp/pi-monitor-debug.log
```

## Reading structured stderr events

pi-monitor emits structured events to stderr as one JSON object per
line. Each event has a top-level `event` key:

```json
{"event": "dispatch_received", "ts_unix": 1789864723.4, "key": "kaplansky.x", "source_digest": "..."}
{"event": "worker_call_started", "ts_unix": 1789864724.1, "attempt": 3, "model": "openai-codex/gpt-5.6-luna"}
{"event": "worker_call_finished", "ts_unix": 1789864823.7, "attempt": 3, "outcome": "completed"}
{"event": "report_received", "ts_unix": 1789864824.1, "outcome_digest": "abc...", "kind": "dispatch"}
```

To filter for a specific event type:

```sh
grep '"event": "worker_call_started"' /tmp/pi-monitor-debug.log
```

To follow a single attempt:

```sh
jq -c 'select(.attempt == 3)' /tmp/pi-monitor-debug.log
```

(The exact event shape depends on the pi-monitor version; see
`pi-monitor status` for the schema.)

## Source-report stream

In addition to stderr events, the source driver writes one structured
report per decision to `~/.local/state/mathlint/pi-monitor/source-reports.jsonl`.
This file is the **canonical wire format** between mathlint and
pi-monitor; it is what the `@ADR-0010` drift guard tests against.

To follow it in real time:

```sh
tail -F ~/.local/state/mathlint/pi-monitor/source-reports.jsonl | jq .
```

The dispatcher's `tests/test_source_reports_schema.py` parses the same
file; if the wire format changes, that test fails before any real
supervisor is affected.

## Audit chain

`~/.local/state/mathlint/pi-monitor/audit.jsonl` is the supervisor's
tamper-evident log of every action it took. To verify chain integrity:

```sh
pi-monitor status   # reports chain_breaks
```

A non-zero `chain_breaks` value means the audit log was modified out
of band; investigate before trusting the supervisor's history.

## Combined recipe

For a complete postmortem session:

```sh
# 1. Capture stderr events
MATHLINT_SOURCE_LOG_LEVEL=DEBUG \
    bash -c '
        exec >/tmp/pi-monitor.stdout.log 2>/tmp/pi-monitor.stderr.log
        pi-monitor run --config ~/.config/mathlint/local-pi-monitor.toml
    '

# 2. Watch source reports
tail -F ~/.local/state/mathlint/pi-monitor/source-reports.jsonl | jq .

# 3. Inspect audit chain
pi-monitor status

# 4. Diff against expected behavior
diff <(jq -c '.event' /tmp/pi-monitor.stderr.log) \
     <(jq -c '.event' /path/to/expected-session.jsonl)
```

## Related

- `@INV-0093` — institution green gate is the canonical wiring evidence.
- `@CTR-0090` — source-report JSONL wire format contract.
- `@ADR-0010` — mathlint decides-next kind-case drift (caught by tests).
