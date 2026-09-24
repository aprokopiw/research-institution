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
  "*/.pi-glla/*"
  "*/.agents/transient/*"
  "*/.venv/*"
  "*/build/*"
  "*/__pycache__/*"
  "*/.git/*"
)

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
  FILTERED=$(echo "$HITS" | grep -vFf <(printf '%s\n' "${SANCTIONED_GLOBS[@]}") 2>/dev/null || echo "$HITS")

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
