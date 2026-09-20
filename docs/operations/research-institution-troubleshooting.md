# Research-institution troubleshooting

Symptom → cause → fix. Cross-links to `@ADR-NNNN` / `@INV-NNNN`
records in `docs/semantic/`.

## CLI surface errors

### `FATAL: missing credential env var(s): MATHLINT_MODEL_ROUTE`

Exit code **4** (CREDENTIAL_ERROR). The catalog lists `MATHLINT_MODEL_ROUTE`
as a live credential; the dispatcher's `paths.missing_credentials()` returns
non-empty.

**Fix:** export `MATHLINT_MODEL_ROUTE` in your shell:

```sh
export MATHLINT_MODEL_ROUTE="openai-codex/gpt-5.6-luna"
```

Per `@ADR-0001`, auth is OAuth-via-pi; you do NOT need `OPENAI_API_KEY`.

### `GATE NOT OPEN: mathlint roadmap reports TASK KIND=ARCHITECTURE_REVIEW_REQUIRED`

Exit code **5** (GATE_CLOSED). The dispatcher's `check_gate()` refused
because the program's roadmap task kind is closed. This is the **safety
boundary** (postmortem: the 187-attempt bug).

**Fix:** run `mathlint architect-apply --recommendation <yaml>` to flip
the roadmap task kind to `RESEARCH`. Or pass `--skip-gate` to launch
anyway (logged; only for operators who know what they're doing).

### `[Errno 2] No such file or directory: 'pi-monitor'`

The dispatcher shells out to `pi-monitor` and the operator's PATH does
not include the venv bin.

**Fix:** add `~/Documents/andrei/pi_monitor/.venv/bin` (and `~/Documents/andrei/math/.venv/bin`) to PATH in `~/.zprofile`, not just `~/.zshrc`. `.zshrc` is sourced only by interactive shells; `.zprofile` is sourced by every login shell (SSH, launchd, cron).
add `~/Documents/andrei/pi_monitor/.venv/bin` (and `~/Documents/andrei/math/.venv/bin`)
to PATH in `~/.zprofile`, not just `~/.zshrc`.

### `[Errno 2] No such file or directory: 'mathlint'`

Same as above for mathlint's venv.

### `[supervisor] not on PATH (skipped)` in green-gate output

Same as above. The green-gate script can't find `pi-monitor` so it
skips the supervisor check.

## Green-gate failures

### `SMOKE001 FAIL SMOKE004: paired-smoke verification failed: RECEIPT040: commit drifted from live HEAD`

Exit code **1** on `bash green-gate/check-institution.sh --live`. The
paired-smoke receipt's recorded commit (`~/.local/state/mathlint/receipts/paired-smoke.json`)
does not match the current HEAD of the math repo.

**Fix:** re-bootstrap the receipt with the new HEAD:

```sh
mathlint first-run --project kaplansky
```

This regenerates `paired-smoke.json` and `paired-smoke.provenance.json`
for the current commit. After this, `--live` exits 0.

### `MODEL001 FAIL` / `MODEL002 FAIL`

Either `pi` is not installed (it's at `/opt/homebrew/bin/pi` per
`pi-monitor-config-reference.md`), or the OAuth grant in
`~/.pi/agent/auth.json` has expired.

**Fix:** install pi (homebrew) and run `pi auth login` to refresh
the grant. Per `@ADR-0001`, the auth path is OAuth; no API keys.

### `POSTGRES004 FAIL migrations=...`

PostgreSQL is configured (`MATHLINT_DATABASE_URL='postgresql:///mathlint'`
in `~/.zprofile`) but migrations haven't run.

**Fix:** `mathlint postgres-cycle` (the bounded-restart helper).

## Dispatcher refusing on stale supervisor

### `research start kaplansky` spawns a duplicate pi-monitor process

`mathlint live-run` does not check whether a pi_monitor supervisor is
already running. If one is, you'll get two.

**Fix:** before running `research start kaplansky`, check whether a
supervisor is already running:

```sh
ps -ef | grep 'pi-monitor run' | grep -v grep
```

If yes, kill it (`kill <pid>` or `kill -TERM <pid>`) and let the
dispatcher start a fresh one. The supervisor's efficiency state is
in-memory only; killing it loses the context-window tracker but
nothing on disk is corrupted.

## The 187-attempt bug (B.1.2 + `@ADR-0009`)

If you see the supervisor dispatching the same task repeatedly
(hundreds of attempts in `audit.jsonl`), this is the bug that
motivated the B.1.2 gate refusal. The dispatcher now refuses to
launch while the gate is closed; the supervisor-side circuit
is `@ADR-0009` (cross-repo ask, not yet shipped).

**Immediate mitigation:** kill the supervisor, fix the underlying
roadmap TASK KIND, restart.

## Where to look for the supervisor's runtime state

```
~/.local/state/mathlint/pi-monitor/health.json      # circuit state, execution status
~/.local/state/mathlint/pi-monitor/latest.json      # last observation + efficiency
~/.local/state/mathlint/pi-monitor/audit.jsonl      # every action the supervisor took
~/.local/state/mathlint/pi-monitor/source-reports.jsonl  # structured reports from mathlint
~/.local/state/mathlint/receipts/paired-smoke.json  # smoke receipt for --live
```

For full investigation see `docs/operations/pi-monitor-debug-logging.md`.
