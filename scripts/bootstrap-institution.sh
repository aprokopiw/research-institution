#!/usr/bin/env sh
# scripts/bootstrap-institution.sh — THIN SHIM. Canonical impl is Python.
#
# Args: --apply (mutate); --skip-dev-deps.
# Env: MATHLINT_INSTITUTION_DIR should point at this repo.
set -e
cd "$(dirname "$0")/.."
export MATHLINT_INSTITUTION_DIR="${MATHLINT_INSTITUTION_DIR:-$PWD}"
exec python3 scripts/bootstrap.py "$@"
