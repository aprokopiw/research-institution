#!/bin/sh
# research-institution/scripts/stop-program.sh <name>
#
# Graceful stop UX (per PP-Y.3):
#   1. Resolve <name> from catalog.
#   2. Read PID from ~/.local/state/mathlint/runs/last-pid.txt
#      (or use $LAUNCHED_PID env var).
#   3. SIGTERM -> poll up to 30s -> SIGKILL fallback.
#   4. Log to ~/.local/state/mathlint/logs/stop-actions.jsonl.
#   5. Optionally re-launch via launchd if a matching plist
#      exists at ~/Library/LaunchAgents/com.local.mathlint-program-<name>.plist.
set -eu

INST="${MATHLINT_INSTITUTION_DIR:-$HOME/Documents/andrei/research-institution}"
CATALOG="$INST/catalog/programs.toml"
PID_FILE="${MATHLINT_STOP_PID_FILE:-$HOME/.local/state/mathlint/runs/last-pid.txt}"
LOG_FILE="$HOME/.local/state/mathlint/logs/stop-actions.jsonl"

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
    shift
fi
NAME="${1:-}"
[ -n "$NAME" ] || { echo "USAGE: stop-program.sh [--dry-run] <name>" >&2; exit 64; }

PROG_BLOCK=$(awk -v name="$NAME" '
    $0 == "[[programs]]" { in_block = 1; next }
    /^\[/ && $0 != "[[programs]]" { in_block = 0 }
    in_block { print }
' "$CATALOG")
echo "$PROG_BLOCK" | grep -q "^name = \"$NAME\"$" \
    || { echo "UNKNOWN PROGRAM: $NAME"; exit 2; }

PID="${LAUNCHED_PID:-}"
if [ -z "$PID" ] && [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
fi
PID=${PID:-unknown}

PLIST="$HOME/Library/LaunchAgents/com.local.mathlint-program-$NAME.plist"

if [ "$DRY_RUN" = "1" ]; then
    cat <<EOF
would send SIGTERM to PID $PID ($NAME)
would poll up to 30s for graceful exit
would send SIGKILL if still alive after 30s
would append to $LOG_FILE: {ts, program: "$NAME", pid: "$PID", signal: "SIGTERM", duration_ms: TBD}
EOF
    if [ -f "$PLIST" ]; then
        echo "would reload launchd plist: $PLIST"
    fi
    exit 0
fi

START=$(date +%s%3N 2>/dev/null || python3 -c "import time; print(int(time.time()*1000))")
SIGNAL="SIGTERM"
ACTION="graceful"

if [ -n "$PID" ] && [ "$PID" != "unknown" ] && kill -0 "$PID" 2>/dev/null; then
    kill -TERM "$PID" 2>/dev/null || true

    ELAPSED=0
    while [ "$ELAPSED" -lt 30 ]; do
        if ! kill -0 "$PID" 2>/dev/null; then
            break
        fi
        sleep 2
        ELAPSED=$((ELAPSED + 2))
    done

    if kill -0 "$PID" 2>/dev/null; then
        kill -KILL "$PID" 2>/dev/null || true
        SIGNAL="SIGKILL"
        ACTION="forced"
    fi
fi

END=$(date +%s%3N 2>/dev/null || python3 -c "import time; print(int(time.time()*1000))")
DURATION=$((END - START))

mkdir -p "$(dirname "$LOG_FILE")"
TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
printf '{"ts": "%s", "program": "%s", "pid": "%s", "signal": "%s", "duration_ms": %d, "action": "%s"}\n' \
    "$TS" "$NAME" "$PID" "$SIGNAL" "$DURATION" "$ACTION" >> "$LOG_FILE"

echo "STOPPED: program=$NAME pid=$PID action=$ACTION duration_ms=$DURATION"

if [ -f "$PLIST" ] && command -v launchctl >/dev/null 2>&1; then
    launchctl unload "$PLIST" 2>/dev/null || true
    launchctl load "$PLIST" 2>/dev/null || true
    echo "RELAUNCHED: launchd plist $PLIST"
fi
