#!/usr/bin/env bash
# start-pi-monitor-research-institution.sh
#
# Thin TUI-friendly launcher for the research-institution Spec-Kit
# cycle. The cycle is owned by pi-monitor's SpecKitCycleSource; this
# script is the named entry point `pi-monitor watch` auto-detects
# (next to the cycle config).
#
# TUI verbs supported:
#   --stop                 stop supervisor (worker dies with it)
#   --stop --stop-worker   stop worker only (supervisor may respawn)
#   --stop --stop-supervisor  stop supervisor only
#   --restart              stop then relaunch (resume)
#   --restart --fresh      stop then relaunch fresh (drop session)
#
# The supervisor's state lives off-tree under
# ~/.local/state/pi-monitor/research-institution/.

set -euo pipefail

REPO="/Users/erinprokopiw/Documents/andrei/research-institution"
CONFIG="${REPO}/pi-monitor.cycle.toml"
STATE_DIR="${HOME}/.local/state/pi-monitor/research-institution"
STATE_JSON="${STATE_DIR}/state.json"
SUPERVISOR_LOCK="${STATE_DIR}/supervisor.lock"
VENV_PY="${HOME}/Documents/andrei/pi_monitor/.venv/bin/pi-monitor"

[[ -f "${CONFIG}" ]] || { echo "missing config: ${CONFIG}" >&2; exit 2; }
[[ -x "${VENV_PY}" ]] || { echo "missing venv executable: ${VENV_PY}" >&2; exit 2; }

log() { printf '[cycle] %s\n' "$*"; }

stop_all() {
    rm -f "${SUPERVISOR_LOCK}"
    pkill -f "pi-monitor run --config ${CONFIG}" 2>/dev/null || true
    sleep 1
    pkill -9 -f "pi-monitor run --config ${CONFIG}" 2>/dev/null || true
    log "supervisor stopped"
}

stop_worker_only() {
    local worker_pid=""
    if [[ -f "${STATE_JSON}" ]]; then
        worker_pid=$(python3 -c "import json,sys; d=json.load(open('${STATE_JSON}')); print(d.get('worker_pid') or '')" 2>/dev/null || true)
    fi
    if [[ -n "${worker_pid}" ]]; then
        kill "${worker_pid}" 2>/dev/null || true
        log "worker pid=${worker_pid} signaled"
    else
        pkill -f "^\s*\d+\s+pi " 2>/dev/null || true
        log "worker signaled by pattern"
    fi
}

start_resume() {
    cd "${REPO}"
    nohup bash scripts/spec-kit-cycle.sh > "${STATE_DIR}/cycle-launcher.log" 2>&1 &
    disown || true
    sleep 3
    log "cycle launched"
}

# Parse args. Forward unknown verbs to pi-monitor CLI as a courtesy.
ACTION="${1:-}"
case "${ACTION}" in
    --stop)
        stop_all
        exit 0
        ;;
    --restart)
        stop_all
        start_resume
        exit 0
        ;;
    --status)
        "${VENV_PY}" status --config "${CONFIG}"
        exit $?
        ;;
    "")
        # Bare invocation: open the TUI.
        exec "${VENV_PY}" watch --config "${CONFIG}" --script "${BASH_SOURCE[0]}"
        ;;
    --watch)
        # Bare TUI; ignore extra args.
        exec "${VENV_PY}" watch --config "${CONFIG}" --script "${BASH_SOURCE[0]}"
        ;;
    *)
        log "unknown verb: ${ACTION} (supported: --stop, --restart, --status, --watch, bare)"
        exit 1
        ;;
esac
