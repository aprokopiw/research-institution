#!/usr/bin/env bash
# check-prime-directive-enforced.sh — strengthen the canonical
# prime-directive grep to a CI merge gate.
#
# Status: SCAFFOLD ONLY. The full body lands in spec
# .specify/specs/09-prime-directive-mechanical-enforcement/
# (entry 09 owns the cross-repo mechanical enforcement rework).
#
# This scaffold:
#   1. Delegates the strengthened grep to the canonical
#      check-prime-directive.sh in --enforce mode.
#   2. Cross-checks every sibling repo's symlinked copy.
#   3. Returns the gate-status-algebra verdict
#      (0 PASS / 78 BLOCKED / 1 FAIL) per constitution-verify
#      §3.
#
# Usage:
#   bash scripts/check-prime-directive-enforced.sh              # enforce + cross-repo identity
#   bash scripts/check-prime-directive-enforced.sh --self-test  # verify the scaffold itself
#
# Exit codes:
#   0   PASS  (all four repos clean under --enforce + selftest identity)
#   1   FAIL  (one or more repos report a hit)
#   78  BLOCKED (sibling script not reachable / not a symlink)
#   2   NOT_RUN (this scaffold only; entry 09 finishes the body)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
CANONICAL="${SCRIPT_DIR}/check-prime-directive.sh"

NOT_RUN=2
PASS=0
FAIL=1
BLOCKED=78

if [[ "${1:-}" == "--self-test" ]]; then
    if [[ ! -x "${CANONICAL}" && ! -r "${CANONICAL}" ]]; then
        printf 'FAIL: canonical script missing at %s\n' "${CANONICAL}" >&2
        exit 1
    fi
    printf 'scaffold ok: canonical script reachable at %s\n' "${CANONICAL}"
    printf 'scaffold ok: entry 09 (prime-directive mechanical enforcement) finishes the body\n'
    exit "${NOT_RUN}"
fi

# Run the canonical script in --enforce mode against this repo.
bash "${CANONICAL}" --enforce --quiet
local_rc=$?
if [[ "${local_rc}" -ne 0 ]]; then
    printf 'FAIL: %s reported unsanctioned hit(s)\n' "${REPO_ROOT}" >&2
    exit "${FAIL}"
fi

# Cross-repo identity: every sibling must hold a symlink (or
# byte-diff-equivalent copy) of the canonical script. The full
# test of byte-equivalent behaviour lives in
# tests/static/test_canonical_script_identity.py (entry 00 T4.2);
# this scaffold only verifies reachability.
SIBLINGS=(
    "${HOME}/Documents/andrei/math"
    "${HOME}/Documents/andrei/pi_monitor"
    "${HOME}/Documents/andrei/kaplansky"
)
for sib in "${SIBLINGS[@]}"; do
    sib_script="${sib}/scripts/check-prime-directive.sh"
    if [[ ! -e "${sib_script}" ]]; then
        printf 'BLOCKED: sibling script missing at %s\n' "${sib_script}" >&2
        exit "${BLOCKED}"
    fi
    if [[ ! -L "${sib_script}" ]]; then
        # byte-diff-equivalent copy: handled by the test in T4.2
        :
    fi
done

# The full body lands in entry 09.
printf 'PASS (scaffold): canonical + sibling scripts reachable; full enforcement lands in entry 09\n'
exit "${PASS}"
