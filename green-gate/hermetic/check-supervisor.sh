#!/bin/sh
# green-gate/hermetic/check-supervisor.sh — pi_monitor hermetic sub-check.
# Runs `pi-monitor doctor --hermetic` if pi-monitor is on PATH;
# otherwise prints a skip message and exits 0.

if ! command -v pi-monitor >/dev/null 2>&1; then
    printf '[supervisor] not on PATH (skipped)\n'
    exit 0
fi

exec pi-monitor doctor \
    --config "${PI_MONITOR_CONFIG:-$HOME/.config/mathlint/local-pi-monitor.toml}" \
    --hermetic
