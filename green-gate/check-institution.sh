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
exec python3 -m research_institution.gates.aggregate "$@"
