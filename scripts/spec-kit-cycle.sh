#!/usr/bin/env bash
# spec-kit-cycle.sh — autonomous pi-monitor harness entry point for
# the research-institution eleven-entry program.
#
# The cycle adapter (pi_monitor.work.sources.spec_kit_cycle) walks
# every spec dir under .specify/specs/ in lex order, ticks every
# Spec-Kit task, and gates each entry's audit-close-out on its
# META.md + per-entry attestation JSON. This script is the
# operator's single command for launching a supervised Pi worker
# against the program; it works on a fresh checkout.
#
# Usage:
#   bash scripts/spec-kit-cycle.sh           # launches the cycle
#   bash scripts/spec-kit-cycle.sh --dry-run # validates config + adapter
#   bash scripts/spec-kit-cycle.sh --validate <slug>  # META + adapter check
#   bash scripts/spec-kit-cycle.sh --init    # generate pi-monitor.toml
#
# Prerequisites:
#   - pi + pi-monitor installed and on $PATH
#   - this repo's working tree clean (no uncommitted changes)
#
# Exit codes (gate-status algebra, constitution-verify.md §3):
#   0   PASS    cycle ran or dry-run validated cleanly
#   78  BLOCKED prerequisites missing or working tree dirty
#   1   FAIL    adapter / META / config failure

set -euo pipefail

# Resolve the repo root from this script's location so the script
# works regardless of the operator's cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

log() { printf '[cycle] %s\n' "$*" >&2; }

# Argument parsing.
DRY_RUN=0
VALIDATE_SLUG=""
INIT_MODE=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dry-run)
            DRY_RUN=1; shift ;;
        --validate)
            VALIDATE_SLUG="${2:-}"; [[ -n "${VALIDATE_SLUG}" ]] || { log "--validate requires a slug"; exit 1; }; shift 2 ;;
        --init)
            INIT_MODE=1; shift ;;
        -h|--help)
            sed -n '3,32p' "${BASH_SOURCE[0]}"; exit 0 ;;
        *)
            log "unknown arg: $1"; exit 1 ;;
    esac
done

# Validate (sub-command).
if [[ -n "${VALIDATE_SLUG}" ]]; then
    log "validating META + attestation for ${VALIDATE_SLUG}"
    if [[ ! -d ".specify/specs/${VALIDATE_SLUG}" ]]; then
        log "spec dir .specify/specs/${VALIDATE_SLUG} does not exist"
        exit 78
    fi
    python scripts/META_validator.py --strict ".specify/specs/${VALIDATE_SLUG}/META.md"
    rc=$?
    if [[ $rc -ne 0 ]]; then
        log "META validation failed (rc=${rc})"
        exit "${rc}"
    fi
    attest=".specify/specs/${VALIDATE_SLUG}/.pi-prime-attestations/${VALIDATE_SLUG}.json"
    if [[ ! -f "${attest}" ]]; then
        log "attestation JSON missing: ${attest}"
        exit 1
    fi
    log "validation PASS for ${VALIDATE_SLUG}"
    exit 0
fi

# Init (sub-command): generate a fresh pi-monitor.toml at the
# repo root using `pi-monitor init`. This is the operator's
# "first-time setup" entry; the committed `pi-monitor.cycle.toml`
# is the cycle-specific config that `run` consumes.
if [[ "${INIT_MODE}" -eq 1 ]]; then
    log "generating pi-monitor.toml via pi-monitor init"
    if [[ -f pi-monitor.toml && "${PI_MONITOR_FORCE:-0}" != "1" ]]; then
        log "pi-monitor.toml already exists; pass PI_MONITOR_FORCE=1 to overwrite"
        exit 78
    fi
    pi-monitor init "${REPO_ROOT}" --name research-institution --force
    log "wrote pi-monitor.toml"
    log "edit it to set roadmap = \"spec-kit-cycle\" and task_globs = [\".specify/specs/*/tasks.md\"]"
    log "or use the canonical cycle config at pi-monitor.cycle.toml"
    exit 0
fi

# Pre-flight: git clean + adapter reachable.
if [[ -n "$(git status --porcelain 2>/dev/null || true)" ]]; then
    log "working tree is dirty; commit or stash before launching the cycle"
    git status --short >&2 || true
    exit 78
fi

if ! command -v pi-monitor >/dev/null 2>&1; then
    log "pi-monitor not on PATH; install with: pip install -e ../pi_monitor"
    exit 78
fi

if [[ ! -f pi-monitor.cycle.toml ]]; then
    log "pi-monitor.cycle.toml missing at ${REPO_ROOT}"
    exit 78
fi

# Adapter import sanity check.
if ! python -c "from pi_monitor.work.sources import SpecKitCycleSource; print(SpecKitCycleSource.kind)" >/dev/null 2>&1; then
    log "SpecKitCycleSource not importable; check that pi_monitor is installed"
    exit 78
fi

# Cycle the META validator against every entry so a draft template
# does not silently slip through the cycle's audit gate.
log "validating every META.md under .specify/specs/"
python scripts/META_validator.py --strict --recursive .
rc=$?
if [[ $rc -ne 0 ]]; then
    log "META validation failed (rc=${rc}); entry templates must be PENDING-free in --strict"
    log "either fill the templates in now, or re-run without --strict to allow drafts"
    exit "${rc}"
fi

if [[ "${DRY_RUN}" -eq 1 ]]; then
    log "dry-run OK; adapter reachable, META validates, config present"
    log "to launch: remove --dry-run and run again"
    exit 0
fi

# Launch.
log "launching pi-monitor against ${REPO_ROOT}"
log "config: pi-monitor.cycle.toml"
log "adapter: kind=spec-kit-cycle (entries 00..10)"
log "to stop the worker: Ctrl-C; to detach: pi-monitor status"
exec pi-monitor run --config "${REPO_ROOT}/pi-monitor.cycle.toml"
