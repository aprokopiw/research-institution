#!/usr/bin/env bash
# check-prime-directive.sh — canonical strengthened grep for
# transient plan/spec/PP/CP identifiers in durable paths.
#
# This is the single source of truth for the regex that the
# pi-extension enforces at runtime and the CI gate enforces at
# merge time. The pattern is byte-equal across both layers; if
# you change it here, update the extension's PRIME_DIRECTIVE_PATTERN
# at ~/.pi/agent/extensions/prime-directive-guard.ts.
#
# The strengthened pattern catches every variant agents write
# (mixed case, optional separator between word and 2+ digits,
# dash/underscore/space). It does NOT match common English
# words like "planner", "specify", "planetary", or "spec_kit".
# See the prime-directive rule-naming document at AGENTS.md and
# the cross-repo registry at docs/semantic/SEMANTIC_REGISTRY.md
# for the canonical mapping of transient literals to durable
# anchors (@ADR-NNNN, @INV-NNNN, @CTR-NNNN, @CON-NNNN).
#
# Usage:
#   bash scripts/check-prime-directive.sh                # scan repo
#   bash scripts/check-prime-directive.sh <path>...      # scan paths
#   bash scripts/check-prime-directive.sh --enforce      # exit 1 on hit
#   bash scripts/check-prime-directive.sh --help
#
# Exit codes:
#   0   clean
#   1   hit (only meaningful in --enforce mode)
#   78  usage error

set -euo pipefail

# Canonical pattern. Keep byte-equal to the extension's.
PATTERN='(\b[Pp][Ll][Aa][Nn]|\b[Ss][Pp][Ee][Cc])[-_ ]?[0-9]{2,}'

# Paths whose content is allowed to reference transient literals.
# Substring match against absolute file path; mirrors the
# extension's SANCTIONED_PATH_PATTERNS so a hit inside any of
# these directories is silently allowed.
SANCTIONED_GLOBS=(
    "/AGENTS.md"
    "/docs/operations/"
    "-closure-audit.md"
    "-live-supervisor-authority.md"
    "/.pi-glla/"
    "/.agents/transient/"
    "/.venv/"
    "/build/"
    "/__pycache__/"
    "/.git/"
    "/.specify/specs/"
)

usage() {
    cat <<'USAGE'
check-prime-directive.sh — strengthened grep for transient
plan/spec/PP/CP identifiers in durable paths.

Usage:
  bash scripts/check-prime-directive.sh [OPTIONS] [PATH...]

Options:
  --enforce     exit 1 on any unsanctioned hit (default: print only)
  --quiet       print only the count and exit code
  --help        show this message

When invoked without explicit paths, the script scans the
current working directory recursively. Files matching any
sanctioned glob are skipped.
USAGE
}

ENFORCE=0
QUIET=0
PATHS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --enforce) ENFORCE=1; shift ;;
        --quiet) QUIET=1; shift ;;
        --help|-h) usage; exit 0 ;;
        --) shift; PATHS+=("$@"); break ;;
        -*) printf 'unknown option: %s\n' "$1" >&2; usage; exit 78 ;;
        *) PATHS+=("$1"); shift ;;
    esac
done

if [[ ${#PATHS[@]} -eq 0 ]]; then
    PATHS=(".")
fi

is_sanctioned() {
    local abs="$1"
    local g
    for g in "${SANCTIONED_GLOBS[@]}"; do
        [[ "${abs}" == *"${g}"* ]] && return 0
    done
    return 1
}

hits=0
misses=0
while IFS= read -r -d '' file; do
    abs="$(cd "$(dirname "${file}")" && pwd)/$(basename "${file}")"
    if is_sanctioned "${abs}"; then
        continue
    fi
    if grep -E -q "${PATTERN}" "${file}" 2>/dev/null; then
        hits=$((hits + 1))
        if [[ "${QUIET}" -eq 0 ]]; then
            printf 'HIT  %s\n' "${abs}" >&2
            grep -nE "${PATTERN}" "${file}" 2>/dev/null | head -5 | sed 's/^/    /' >&2 || true
        fi
    else
        misses=$((misses + 1))
    fi
done < <(find "${PATHS[@]}" -type f \
    -not -path '*/.git/*' \
    -not -path '*/.venv/*' \
    -not -path '*/__pycache__/*' \
    -not -path '*/node_modules/*' \
    -not -path '*/.pi-prime-attestations/*' \
    -not -name 'check-prime-directive.sh' \
    -print0 2>/dev/null)

if [[ "${QUIET}" -eq 0 ]]; then
    printf 'scanned %d file(s); %d sanctioned-allowed; %d hit(s)\n' \
        "$((hits + misses))" "$misses" "$hits" >&2
fi

if [[ "${ENFORCE}" -eq 1 && "${hits}" -gt 0 ]]; then
    exit 1
fi
exit 0
