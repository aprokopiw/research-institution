#!/usr/bin/env bash
# Twenty-repeated-run flake check (entry 06 T4.3).
#
# Runs the canonical scenario command 20 times. Exits 0 only when
# every run exits 0. A single non-zero exit is a flake.
#
# Usage:
#   bash scripts/twenty-repeated-runs.sh happy-three-cycle

set -euo pipefail

SCENARIO_NAME="${1:-happy-three-cycle}"
RUNS="${RUNS:-20}"
SUFFIX="${SUFFIX:-hermetic}"

# Locate the venv python that has research-institution installed.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_EXE="${PYTHON_EXE:-${REPO_ROOT}/.venv/bin/python}"

if [[ ! -x "${PYTHON_EXE}" ]]; then
    echo "twenty-repeated-runs: ${PYTHON_EXE} not found" >&2
    exit 2
fi

FLAKES=0
for run in $(seq 1 "${RUNS}"); do
    if ! "${PYTHON_EXE}" -m research_institution verify-simulation \
            --scenario "${SCENARIO_NAME}" >/dev/null 2>&1; then
        echo "run ${run}/${RUNS}: FLAKE"
        FLAKES=$((FLAKES + 1))
    fi
done

if [[ "${FLAKES}" -gt 0 ]]; then
    echo "twenty-repeated-runs: ${FLAKES}/${RUNS} flakes"
    exit 1
fi

echo "twenty-repeated-runs: ${RUNS}/${RUNS} clean"
exit 0
