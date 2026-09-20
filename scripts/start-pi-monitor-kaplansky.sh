#!/usr/bin/env bash
# TUI control shim for the kaplansky-launch-test supervisor.
# The TUI reads/writes via this script path; it never embeds supervisor logic.
case "${1:-}" in
    --status) /Users/erinprokopiw/Documents/andrei/math/.venv/bin/pi-monitor status --config /tmp/super.toml ;;
    --stop)   pkill -f 'pi-monitor run --config /tmp/super.toml' || true ;;
    --fresh)  rm -rf /Users/erinprokopiw/.local/state/pi-monitor/kaplansky ;;
    *)        echo "usage: $0 [--status|--stop|--fresh]"; exit 0 ;;
esac
