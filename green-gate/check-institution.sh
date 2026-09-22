#!/usr/bin/env sh
# green-gate/check-institution.sh — THIN SHIM. Canonical impl is Python.
#
# All logic lives in
# `research_institution.gates.aggregate.check_institution()` and its
# CLI wrapper `python -m research_institution.gates.aggregate`.
#
# Args: --hermetic (default), --live, --list, --skip-program=NAME.
# Env: RESEARCH_INSTITUTION_VWIRE_DIRECT=1 (set by default in the
#      verify entry point), MATHLINT_AUTONOMY_SKIP_G7=1.
# Env: MATHLINT_INSTITUTION_DIR should point at this repo.
set -e
cd "$(dirname "$0")/.."
export MATHLINT_INSTITUTION_DIR="${MATHLINT_INSTITUTION_DIR:-$PWD}"
export PYTHONPATH="${PYTHONPATH:-$PWD}"
# Prefer the repo's venv python so the v-compose tier (which
# invokes ``sys.executable`` for its in-process pytest run)
# sees the institution's mathlint, not whatever venv's
# ``python3`` happens to be on PATH (e.g. pi_monitor's
# older mathlint). Falls back to system python3 if the
# venv is missing.
if [ -x ".venv/bin/python" ]; then
    exec .venv/bin/python -m research_institution.gates.aggregate "$@"
else
    exec python3 -m research_institution.gates.aggregate "$@"
fi
