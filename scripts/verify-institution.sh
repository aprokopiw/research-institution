#!/usr/bin/env sh
# scripts/verify-institution.sh — canonical "is the institution ready?" command.
#
# Thin shim over `scripts/verify-institution.py`. Sets the safe
# defaults operators want (RESEARCH_INSTITUTION_VWIRE_DIRECT=1)
# before forwarding. Same args as `green-gate/check-institution.sh`.
set -e
cd "$(dirname "$0")/.."
export MATHLINT_INSTITUTION_DIR="${MATHLINT_INSTITUTION_DIR:-$PWD}"
export RESEARCH_INSTITUTION_VWIRE_DIRECT="${RESEARCH_INSTITUTION_VWIRE_DIRECT:-1}"
export PYTHONPATH="${PYTHONPATH:-$PWD}"
exec python3 scripts/verify-institution.py "$@"
