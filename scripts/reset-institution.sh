#!/usr/bin/env bash
# reset-institution.sh — thin shim over `python -m research_institution reset`.
#
# Canonical "make the box clean" entry. Default dry-run. Forward all
# flags verbatim; the Python verb owns the policy.
#
# Usage:
#   bash scripts/reset-institution.sh                 # dry-run
#   bash scripts/reset-institution.sh --apply         # remove stale locks
#   bash scripts/reset-institution.sh --apply --kill-processes
#   bash scripts/reset-institution.sh --apply --purge-state ~/.local/state/pi-monitor/kaplansky --yes
set -e
cd "$(dirname "$0")/.."
export MATHLINT_INSTITUTION_DIR="${MATHLINT_INSTITUTION_DIR:-$PWD}"
export PYTHONPATH="${PYTHONPATH:-$PWD}"
exec python3 -m research_institution reset "$@"
