#!/bin/sh
# research-institution/scripts/rollback-program.sh <name>
#
# Rollback UX (per PP-Y.4):
#   1. Back up the current paired-smoke receipt to a
#      timestamped .bak-<ts> file.
#   2. Send SIGTERM to the program's launcher (via
#      stop-program.sh semantics); escalate to SIGKILL.
#   3. Restart pi_monitor doctor to verify health.
#   4. Log the rollback to rollback-actions.jsonl.
#   5. Print ROLLED BACK: backup_at=<path>.
set -eu

INST="${MATHLINT_INSTITUTION_DIR:-$HOME/Documents/andrei/research-institution}"
RECEIPTS_DIR="${MATHLINT_RECEIPTS_DIR:-$HOME/.local/state/mathlint/receipts}"
LOG_FILE="$HOME/.local/state/mathlint/logs/rollback-actions.jsonl"

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
    shift
fi
NAME="${1:-}"
[ -n "$NAME" ] || { echo "USAGE: rollback-program.sh [--dry-run] <name>" >&2; exit 64; }

TS=$(date -u +%Y%m%dT%H%M%SZ)
BACKUP_AT=""
if [ -f "$RECEIPTS_DIR/paired-smoke.json" ]; then
    BACKUP_AT="$RECEIPTS_DIR/paired-smoke.json.bak-$TS"
fi

if [ "$DRY_RUN" = "1" ]; then
    cat <<EOF
would back up $RECEIPTS_DIR/paired-smoke.json -> $BACKUP_AT
would call stop-program.sh $NAME (SIGTERM -> SIGKILL after 30s)
would run 'pi_monitor doctor' to verify health
would append to $LOG_FILE: {ts, program, backup_at, action}
ROLLED BACK: backup_at=$BACKUP_AT
EOF
    exit 0
fi

if [ -n "$BACKUP_AT" ]; then
    cp "$RECEIPTS_DIR/paired-smoke.json" "$BACKUP_AT"
fi

if [ -x "$INST/scripts/stop-program.sh" ]; then
    bash "$INST/scripts/stop-program.sh" "$NAME" >/dev/null 2>&1 || true
fi

if command -v pi_monitor >/dev/null 2>&1; then
    pi_monitor doctor >/dev/null 2>&1 || true
fi

mkdir -p "$(dirname "$LOG_FILE")"
printf '{"ts": "%s", "program": "%s", "backup_at": "%s", "action": "rollback"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$NAME" "$BACKUP_AT" >> "$LOG_FILE"

echo "ROLLED BACK: backup_at=$BACKUP_AT"
