#!/bin/sh
# research-institution/scripts/launch-program.sh <name>
#
# 9-step operator launch UX (per PP-Y.1 in @INV-0098).
#
#   1. Preflight (hermetic): verify the institution gate is GREEN.
#   2. Catalog lookup: confirm <name> exists in catalog/programs.toml.
#   3. Local-path resolution: $HOME expansion + existence check.
#   4. Credential check: each live_credential_env_vars non-empty.
#   5. Live preflight: --live green-gate check (skipped with --dry-run).
#   6. Launch: invoke launch_command (or echo in --dry-run).
#   7. Wait for ready: poll launch_ready_command for up to 60s.
#   8. Trap SIGINT/SIGTERM: stop the program if interrupted.
#   9. Return: print LAUNCHED: pid=<pid> log=<log_path>.
#
# Exit codes:
#   1 INSTITUTION NOT READY   (hermetic preflight failed)
#   2 UNKNOWN PROGRAM         (catalog has no entry for <name>)
#   3 MISSING PROGRAM PATH    (local_path does not exist)
#   4 MISSING CREDENTIAL      (live_credential_env_vars empty)
#   5 LIVE PREFLIGHT FAILED   (live green-gate failed)
#   6 LAUNCH TIMEOUT          (launch_ready_command never returned ready)
#   7 LAUNCH COMMAND FAILED   (launch_command exited non-zero)
set -eu

INST="${MATHLINT_INSTITUTION_DIR:-$HOME/Documents/andrei/research-institution}"
GATE="$INST/green-gate/check-institution.sh"
CATALOG="$INST/catalog/programs.toml"

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
    shift
fi
NAME="${1:-}"
[ -n "$NAME" ] || { echo "USAGE: launch-program.sh [--dry-run] <name>" >&2; exit 64; }

# 1. Hermetic preflight.
if ! bash "$GATE" --hermetic >/tmp/launch-program-hermetic.log 2>&1; then
    echo "INSTITUTION NOT READY (hermetic preflight failed)"
    tail -40 /tmp/launch-program-hermetic.log >&2
    exit 1
fi

# 2. Catalog lookup.
PROG_BLOCK=$(awk -v name="$NAME" '
    $0 == "[[programs]]" { in_block = 1; next }
    /^\[/ && $0 != "[[programs]]" { in_block = 0 }
    in_block { print }
' "$CATALOG")
[ -n "$PROG_BLOCK" ] || { echo "UNKNOWN PROGRAM: $NAME"; exit 2; }

# Verify name = "<arg>" is in the block.
echo "$PROG_BLOCK" | grep -q "^name = \"$NAME\"$" \
    || { echo "UNKNOWN PROGRAM: $NAME"; exit 2; }

# 3. Local-path resolution.
LOCAL_PATH=$(echo "$PROG_BLOCK" | sed -n 's/^local_path = "\(.*\)"$/\1/p')
LOCAL_PATH_RESOLVED=$(eval echo "$LOCAL_PATH")
[ -e "$LOCAL_PATH_RESOLVED" ] || { echo "MISSING PROGRAM PATH: $LOCAL_PATH_RESOLVED"; exit 3; }

# 4. Credential check (only when live_credentials_required = true AND --dry-run is NOT set).
REQUIRES_CREDS=$(echo "$PROG_BLOCK" | sed -n 's/^live_credentials_required = //p' | tr -d ' ')
if [ "$REQUIRES_CREDS" = "true" ] && [ "$DRY_RUN" = "0" ]; then
    CREDS=$(echo "$PROG_BLOCK" | sed -n 's/^live_credential_env_vars = \[\(.*\)\]$/\1/p' | tr -d ' ')
    for var in $(echo "$CREDS" | tr ',' ' '); do
        var=$(echo "$var" | tr -d '"')
        eval val=\${$var:-}
        [ -n "$val" ] || { echo "MISSING CREDENTIAL: $var"; exit 4; }
    done
fi

# 5. Live preflight (skipped with --dry-run).
if [ "$DRY_RUN" = "0" ]; then
    if ! bash "$GATE" --live >/tmp/launch-program-live.log 2>&1; then
        echo "LIVE PREFLIGHT FAILED"
        tail -40 /tmp/launch-program-live.log >&2
        exit 5
    fi
fi

# 6. Launch.
LAUNCH_CMD=$(echo "$PROG_BLOCK" | sed -n 's/^launch_command = "\(.*\)"$/\1/p')
LOG_PATH_RAW=$(echo "$PROG_BLOCK" | sed -n 's/^launch_log_path = "\(.*\)"$/\1/p')
LOG_PATH=$(eval echo "$LOG_PATH_RAW")

# 8. Trap.
cleanup() {
    if [ "$LAUNCHED" = "1" ]; then return; fi
    RUNNING_LAUNCH=$(echo "$PROG_BLOCK" | sed -n 's/^launch_command = "\(.*\)"$/\1/p' | awk '{print $1}')
    command -v "$RUNNING_LAUNCH" >/dev/null 2>&1 && "$RUNNING_LAUNCH" stop >/dev/null 2>&1 || true
}
trap cleanup INT TERM
LAUNCHED=0

if [ "$DRY_RUN" = "1" ]; then
    echo "would launch: $LAUNCH_CMD"
    echo "would wait for ready via: $(echo "$PROG_BLOCK" | sed -n 's/^launch_ready_command = "\(.*\)"$/\1/p')"
    echo "would log to: $LOG_PATH"
    LAUNCHED=1
    echo "LAUNCHED: pid=dry-run log=$LOG_PATH"
    exit 0
fi

if ! eval "$LAUNCH_CMD" >/tmp/launch-program-start.log 2>&1; then
    echo "LAUNCH COMMAND FAILED: $LAUNCH_CMD"
    tail -40 /tmp/launch-program-start.log >&2
    exit 7
fi

# 7. Wait for ready.
READY_CMD=$(echo "$PROG_BLOCK" | sed -n 's/^launch_ready_command = "\(.*\)"$/\1/p')
PID_FIELD=$(echo "$PROG_BLOCK" | sed -n 's/^launch_pid_field = "\(.*\)"$/\1/p')
TIMEOUT=60
ELAPSED=0
PID=""
while [ "$ELAPSED" -lt "$TIMEOUT" ]; do
    if OUT=$(eval "$READY_CMD" 2>&1) && echo "$OUT" | grep -qi "ready"; then
        if [ -n "$PID_FIELD" ]; then
            PID=$(echo "$OUT" | grep -o "\"$PID_FIELD\": *[0-9]*" | grep -o "[0-9]*$" | head -1 || echo "")
            PID=${PID:-unknown}
        else
            PID=unknown
        fi
        LAUNCHED=1
        echo "LAUNCHED: pid=$PID log=$LOG_PATH"
        exit 0
    fi
    sleep 2
    ELAPSED=$((ELAPSED + 2))
done

echo "LAUNCH TIMEOUT: $READY_CMD never reported ready within ${TIMEOUT}s"
exit 6
