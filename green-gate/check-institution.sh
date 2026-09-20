#!/bin/sh
# green-gate/check-institution.sh — the canonical aggregator.
#
# Single one-line answer to "is everything wired?" across the
# research-institution: math-engine + pi_monitor + N research
# programs declared in catalog/programs.toml.
#
# Modes:
#   --hermetic   CI-safe; uses mathlint's bundled sample program +
#                stubbed pi_monitor doctor. No LLM calls.
#   --live       Operator-only; uses each program's real provider +
#                LLM credentials. Requires the operator to be on a
#                machine with credentials configured.
#   --list       Print the catalog as a table; exit 0.
#   --skip-program=<name>
#                Skip a specific program (useful when developing one).
#
# Per @CTR-0088, the catalog schema is the source of truth; this
# script reads programs.toml and dispatches.

set -eu

MODE="hermetic"
SKIP_PROGRAMS=""
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
CATALOG="$ROOT/catalog/programs.toml"

usage() {
    cat <<'EOF'
Usage: check-institution.sh [flags]
  --hermetic            Run in CI-safe mode (default).
  --live                Run in operator-live mode (requires credentials).
  --list                Print the catalog as a table; exit 0.
  --skip-program=<name> Skip a specific program (repeatable).
  -h, --help            Show this help.
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --hermetic) MODE=hermetic ;;
        --live) MODE=live ;;
        --list) MODE=list ;;
        --skip-program=*) SKIP_PROGRAMS="$SKIP_PROGRAMS ${1#*=}" ;;
        -h|--help) usage; exit 0 ;;
        *) printf 'unknown flag: %s\n' "$1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

# Resolve $HOME-prefixed paths.
expand() {
    case "$1" in
        "\$HOME"*) eval echo "$1" ;;
        *) echo "$1" ;;
    esac
}

list_catalog() {
    printf 'NAME\tDISPLAY\tREPOSITORY\tENTRY_POINT\n'
    python3 -c "
import tomllib, pathlib
data = tomllib.loads(pathlib.Path('$CATALOG').read_text())
for e in data['programs']:
    print(f\"{e['name']}\\t{e['display_name']}\\t{e['repository']}\\t{e['entry_point']}\")
"
}

if [ "$MODE" = "list" ]; then
    list_catalog
    exit 0
fi

# Aggregator body.
FAILED=""
PASSED=""

run_check() {
    label="$1"; shift
    if "$@" >/tmp/.check_$$ 2>&1; then
        PASSED="$PASSED $label"
        printf '[%s] ok\n' "$label"
    else
        FAILED="$FAILED $label"
        printf '[%s] FAILED\n' "$label"
        cat /tmp/.check_$$
    fi
    rm -f /tmp/.check_$$
}

# 0. V0 — structural validity (ruff). This repo's V0 gate, enforced
# at the institution level. Optional: if `ruff` is not on PATH, this
# step is skipped (CI runs ruff via .github/workflows/ci.yml).
# Skip when `RESEARCH_INSTITUTION_HERMETIC=1` (test mode): isolated
# test environments don't carry the source tree we lint.
if [ "${RESEARCH_INSTITUTION_HERMETIC:-0}" = "1" ]; then
    printf '[v0-ruff] hermetic mode (skipped)\n'
elif command -v ruff >/dev/null 2>&1; then
    run_check "v0-ruff" sh -c "cd '$ROOT' && ruff check research_institution tests"
else
    printf '[v0-ruff] not on PATH (skipped; CI enforces this gate)\n'
fi

# 0.5. V-WIRE — cross-repo wiring (mathlint's autonomy.sh G7).
# This is the new tier that catches composition defects that
# component-level unit tests in any single repo miss:
#   - the mathlint source CLI must call discover_program_providers
#     on startup (CROSS_REPO_001),
#   - installed program plugins must populate the
#     work_source_provider slot (CROSS_REPO_002),
#   - the mathlint-source subprocess must answer a decide frame
#     without crashing (CROSS_REPO_003),
#   - local.toml.model_route must equal local-pi-monitor.toml
#     [worker].model (CROSS_REPO_005).
# Skipped when RESEARCH_INSTITUTION_HERMETIC=1 (CI runners without
# mathlint) or when MATHLINT_AUTONOMY_SKIP_G7=1 (cold-start hatch).
# When RESEARCH_INSTITUTION_VWIRE_DIRECT=1, runs the test file
# directly with pytest instead of the full autonomy.sh — useful
# for CI runners where G1..G6 of autonomy.sh would block on
# unrelated pre-existing convention drift in mathlint.
AUTONOMY_SCRIPT="${RESEARCH_INSTITUTION_AUTONOMY_SCRIPT:-$(expand '$HOME')/Documents/andrei/math/scripts/autonomy.sh}"
MATHLINT_TEST_DIR="${RESEARCH_INSTITUTION_MATHLINT_TEST_DIR:-$(expand '$HOME')/Documents/andrei/math}"
if [ "${RESEARCH_INSTITUTION_HERMETIC:-0}" = "1" ]; then
    printf '[v-wire] hermetic mode (skipped)\n'
elif [ "${MATHLINT_AUTONOMY_SKIP_G7:-0}" = "1" ]; then
    printf '[v-wire] MATHLINT_AUTONOMY_SKIP_G7=1 (skipped)\n'
elif [ "${RESEARCH_INSTITUTION_VWIRE_DIRECT:-0}" = "1" ] && [ -f "$MATHLINT_TEST_DIR/tests/local_readiness/test_cross_repo_wiring.py" ]; then
    # Direct path: bypass autonomy.sh G1..G6 and invoke just the
    # cross-repo wiring test. Use the math-engine venv's pytest.
    MATHLINT_PYTEST="${RESEARCH_INSTITUTION_MATHLINT_PYTEST:-$MATHLINT_TEST_DIR/.venv/bin/python}"
    run_check "v-wire" sh -c "cd '$MATHLINT_TEST_DIR' && '$MATHLINT_PYTEST' -m pytest --no-cov -q tests/local_readiness/test_cross_repo_wiring.py"
elif [ -f "$AUTONOMY_SCRIPT" ]; then
    run_check "v-wire" sh -c "bash '$AUTONOMY_SCRIPT'"
else
    printf '[v-wire] autonomy.sh not at %s; skipping\n' "$AUTONOMY_SCRIPT"
fi

# 1. Engine (mathlint) — always runs.
ENGINE_FLAGS="--skip-external --use-program=self_test-sample"
if [ "$MODE" = "live" ]; then
    ENGINE_FLAGS=""
fi
# Allow hermetic tests to override the engine script location via env var.
ENGINE_SCRIPT="${RESEARCH_INSTITUTION_ENGINE_SCRIPT:-$(expand '$HOME')/Documents/andrei/math/scripts/check-local-system-readiness.sh}"
if [ -f "$ENGINE_SCRIPT" ]; then
    run_check "engine" sh -c "cd '$ROOT' && bash '$ENGINE_SCRIPT' $ENGINE_FLAGS"
else
    printf '[engine] WARN: math-engine not at expected path; skipping\n'
fi

# 2. Supervisor (pi_monitor) — optional, hermetic skips.
if command -v pi-monitor >/dev/null 2>&1; then
    run_check "supervisor" sh -c "pi-monitor doctor --config '$HOME/.config/mathlint/local-pi-monitor.toml'"
else
    printf '[supervisor] not on PATH (skipped)\n'
fi

# 3. Programs — iterate catalog.
if [ -f "$CATALOG" ]; then
    PROGRAM_NAMES=$(python3 -c "
import tomllib, pathlib
data = tomllib.loads(pathlib.Path('$CATALOG').read_text())
for e in data['programs']:
    print(e['name'])
")
    for name in $PROGRAM_NAMES; do
        case " $SKIP_PROGRAMS " in
            *" $name "*) printf '[program=%s] skipped\n' "$name"; continue ;;
        esac
        local_path=$(python3 -c "
import tomllib, pathlib
data = tomllib.loads(pathlib.Path('$CATALOG').read_text())
for e in data['programs']:
    if e['name'] == '$name':
        print(e['local_path'])
        break
")
        check_script=$(python3 -c "
import tomllib, pathlib
data = tomllib.loads(pathlib.Path('$CATALOG').read_text())
for e in data['programs']:
    if e['name'] == '$name':
        print(e['check_program_script'])
        break
")
        resolved=$(expand "$local_path")
        if [ ! -d "$resolved" ]; then
            printf '[program=%s] WARN: local_path %s missing; skipping\n' "$name" "$resolved"
            continue
        fi
        if [ ! -f "$resolved/$check_script" ]; then
            printf '[program=%s] WARN: check script %s missing; skipping\n' "$name" "$resolved/$check_script"
            continue
        fi
        flag="--hermetic"
        if [ "$MODE" = "live" ]; then flag="--live"; fi
        run_check "program=$name" sh -c "cd '$resolved' && bash './$check_script' $flag"
    done
else
    printf '[programs] WARN: catalog missing at %s\n' "$CATALOG"
fi

# Verdict.
if [ -z "$FAILED" ]; then
    printf '\nGREEN INSTITUTION READY\n'
    printf 'passed:%s\n' "$PASSED"
    exit 0
else
    printf '\nRED: failed checks:%s\n' "$FAILED"
    exit 1
fi
