#!/usr/bin/env bash
# Prime-directive grep — strengthened pattern that catches every variant.
#
# Canonical pattern (ERE):
#   (\b[Pp][Ll][Aa][Nn]|\b[Ss][Pp][Ee][Cc])[-_ ]?[0-9]{2,}
#
# Catches: plan-013, Plan-013, PLAN-013, Plan 002, plan013, plan_013,
#          spec-011, Spec-011, SPEC-011, spec 009, spec011, spec_011.
#
# Does NOT catch (correctly): planner, specify, planetary, spec_kit,
#          spec kit, planning — the negative lookbehind \b before the
#          keyword ensures we match only when 'plan'/'spec' starts a
#          token, not when it's a suffix.
#
# USAGE:
#   bash scripts/check-prime-directive.sh [<repo-dir> ...]
#   bash scripts/check-prime-directive.sh --self   # check this repo
#
# EXIT CODE:
#   0 — zero hits outside sanctioned paths.
#   1 — at least one hit. The hit list is printed to stdout.
#
# This script is intentionally portable bash + grep -E (no PCRE / no
# python) so it can run in CI, locally, and inside the pi
# prime-directive-guard extension (which spawns bash).

set -uo pipefail

# Default to checking the current directory if no args.
if [ "$#" -eq 0 ] || [ "${1:-}" = "--self" ]; then
  REPOS=( ".")
else
  REPOS=( "$@" )
fi

# Strengthened pattern: catches plan/Plan/PLAN/plan_/Plan_/spec/Spec/etc
# followed by 2+ digits, optionally separated by -/_/space/''.
PATTERN='(\b[Pp][Ll][Aa][Nn]|\b[Ss][Pp][Ee][Cc])[-_ ]?[0-9]{2,}'

# Sanctioned path globs (paths whose references are exempt; matches math
# AGENTS.md precedent of named sanctioned exception classes per file).
# Each repo may add its own; this is the institutional default.
SANCTIONED_GLOBS=(
  "*/AGENTS.md"
  "*/docs/operations/plan-*-closure-audit.md"
  "*/docs/operations/plan-*-live-supervisor-authority.md"
  "*/docs/operations/run-plan-*"
  "*/docs/operations/run-spec-*"
  "*/docs/operations/spec-*"
  "*/.pi-glla/*"
  "*/.agents/transient/*"
  "*/.venv/*"
  "*/build/*"
  "*/__pycache__/*"
  "*/.git/*"
  # Math spec-kit source-of-truth (AGENTS.md class #15)
  "*/artifacts/temp/specs/*"
  "*/specs/002-canonical-research-state/*"
  "*/specs/003-operator-status-surface/*"
  # Math @ADR-0088 durable records + Phase U verification (class #16/17)
  "*/docs/operations/@ADR-0088-durable-records*"
  "*/docs/operations/@ADR-0088-phase-u-stop-the-line*"
  "*/docs/operations/run-@ADR-0088*"
  # Math prime-directive enforcement script itself (class #7)
  "*/scripts/coherence/_metrics/d9_prime_directive_clean.py"
  # Math grandfathered drift tuple (class #7 - ADR-0013)
  "*/tests/integration/test_postgres_cutover_gates.py"
  # The prime-directive bulk-rewrite helper itself (its job is to
  # name the forbidden tokens as part of the rule definitions)
  "*/scripts/rewrite-snippets.py"
  # Math decoupling-history archives (historical extraction trace)
  "*/docs/decoupling-history/*"
  # Kaplansky RESUME.md names the active Spec Kit feature
  "*/docs/RESUME.md"
  # Kaplansky spec-kit source-of-truth
  "*/.specify/*"
)

# Convert shell globs to anchored regex (escape . + translate *).
# This is needed because `grep -F` does literal matching; globs need regex.
SANCTIONED_REGEX=()
for g in "${SANCTIONED_GLOBS[@]}"; do
  # Escape regex specials except *
  re=$(printf '%s' "$g" | sed 's/\./\\./g; s/\*/.*/g')
  SANCTIONED_REGEX+=("$re")
done

EXIT=0
for REPO in "${REPOS[@]}"; do
  echo "=== checking $REPO ==="
  cd "$REPO"

  # Collect hits, then filter out sanctioned paths via grep -v.
  HITS=$(grep -rnE "$PATTERN" \
    --include='*.py' --include='*.md' --include='*.toml' \
    --include='*.yaml' --include='*.yml' \
    --exclude-dir='.git' --exclude-dir='__pycache__' \
    --exclude-dir='.venv' --exclude-dir='build' \
    --exclude-dir='.pi-glla' --exclude-dir='.agents' \
    . 2>/dev/null)

  # Apply the additional sanctioned-glob filter on top.
  FILTERED=$(echo "$HITS" | grep -vEf <(printf '%s\n' "${SANCTIONED_REGEX[@]}") 2>/dev/null || echo "$HITS")

  if [ -z "$FILTERED" ]; then
    echo "  ✓ no unsanctioned hits"
  else
    COUNT=$(echo "$FILTERED" | wc -l | tr -d ' ')
    echo "  ✗ $COUNT unsanctioned hit(s):"
    echo "$FILTERED" | sed 's/^/    /'
    EXIT=1
  fi
done

exit $EXIT
