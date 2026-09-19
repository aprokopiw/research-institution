#!/bin/sh
# research-institution/scripts/watch-program.sh <name>
#
# Operator watch UX (per PP-Y.2 in @INV-0098): five
# tail-style windows — status, activity, journal,
# snapshot, supervisor log.
#
# In dry-run mode (the canonical CI mode), prints
# the tmux layout plan and exits 0. In live mode,
# prefers tmux (2x2 grid + 1 wide) with xterm fallback.
set -eu

INST="${MATHLINT_INSTITUTION_DIR:-$HOME/Documents/andrei/research-institution}"
CATALOG="$INST/catalog/programs.toml"

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
    shift
fi
NAME="${1:-}"
[ -n "$NAME" ] || { echo "USAGE: watch-program.sh [--dry-run] <name>" >&2; exit 64; }

# Catalog lookup.
PROG_BLOCK=$(awk -v name="$NAME" '
    $0 == "[[programs]]" { in_block = 1; next }
    /^\[/ && $0 != "[[programs]]" { in_block = 0 }
    in_block { print }
' "$CATALOG")
echo "$PROG_BLOCK" | grep -q "^name = \"$NAME\"$" \
    || { echo "UNKNOWN PROGRAM: $NAME"; exit 2; }

STATUS_CMD=$(echo "$PROG_BLOCK" | sed -n 's/^launch_ready_command = "\(.*\)"$/\1/p')
STATUS_CMD=${STATUS_CMD:-"$NAME status"}

LOG_PATH_RAW=$(echo "$PROG_BLOCK" | sed -n 's/^launch_log_path = "\(.*\)"$/\1/p')
LOG_PATH=$(eval echo "$LOG_PATH_RAW")
LOG_PATH=${LOG_PATH:-"$HOME/.local/state/mathlint/logs/pi-monitor.log"}

if [ "$DRY_RUN" = "1" ]; then
    cat <<EOF
would open 5 tmux windows for $NAME:
  1. status:    while true; do $STATUS_CMD; sleep 10; done
  2. activity:  mathlint-kaplansky activity | tail -5
  3. journal:   mathlint-kaplansky journal --explain | tail -5
  4. snapshot:  mathlint-kaplansky snapshot --replay | head -40
  5. log tail:  tail -F $LOG_PATH
EOF
    exit 0
fi

if command -v tmux >/dev/null 2>&1; then
    SESSION="watch-$NAME"
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    tmux new-session -d -s "$SESSION" "while true; do $STATUS_CMD | head -40; sleep 10; done"
    tmux split-window -h -t "$SESSION":0 "while true; do mathlint-kaplansky activity 2>/dev/null | tail -5; sleep 10; done"
    tmux split-window -v -t "$SESSION":0 "while true; do mathlint-kaplansky journal --explain 2>/dev/null | tail -5; sleep 10; done"
    tmux select-pane -t "$SESSION":0.0
    tmux new-window -t "$SESSION" -n snapshot "while true; do mathlint-kaplansky snapshot --replay 2>/dev/null | head -40; sleep 30; done"
    tmux new-window -t "$SESSION" -n log "tail -F $LOG_PATH"
    tmux attach-session -t "$SESSION"
    exit 0
fi

# Fallback: xterm + tail.
if command -v xterm >/dev/null 2>&1; then
    xterm -e "while true; do $STATUS_CMD; sleep 10; done" &
    xterm -e "while true; do mathlint-kaplansky activity 2>/dev/null | tail -5; sleep 10; done" &
    xterm -e "while true; do mathlint-kaplansky journal --explain 2>/dev/null | tail -5; sleep 10; done" &
    xterm -e "while true; do mathlint-kaplansky snapshot --replay 2>/dev/null | head -40; sleep 30; done" &
    xterm -e "tail -F $LOG_PATH" &
    wait
    exit 0
fi

echo "WATCH-ENV-001: neither tmux nor xterm is available; cannot open watch windows"
exit 3
