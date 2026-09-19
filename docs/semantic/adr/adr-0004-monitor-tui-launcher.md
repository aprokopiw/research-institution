---
id: ADR-0004
kind: decision
status: accepted
title: One-keystroke TUI launcher (monitor-<program>.sh) over pi-monitor watch
date: 2026-09-13
related:
  - ADR-0002
  - ADR-0003
supersedes: []
---

# ADR-0004: One-keystroke TUI launcher (`monitor-<program>.sh`) over pi-monitor watch

## Context

`pi-monitor watch` is a full-screen Textual TUI that surfaces the running
supervisor's AGENT panel, activity feed, spec/cost/health/events panels,
and exposes keybindings for launch/stop/restart/message/logs/tasks.
Invoking it directly requires:

- A specific `--config` path.
- A specific `--script` path.
- Textual installed in the pi_monitor venv.

The operator wants `./monitor-<program>.sh` from the research-institution
repo to open the TUI for any catalog program, with no flags remembered
and Textual installed on demand if missing.

## Decision

Each catalog program MAY have a `monitor-<name>.sh` shim at the
research-institution repo root that:

1. Resolves the pi_monitor binary (`$PI_MONITOR_REPO/.venv/bin/pi-monitor`,
   fallback to `$(command -v pi-monitor)` if PATH has it).
2. Resolves the start script (`$PI_MONITOR_REPO/start-pi-monitor-pi-monitor.sh`,
   searched in canonical locations).
3. Probes `pi-monitor watch --help`. If it fails (Textual missing),
   installs `textual` into the venv via
   `uv pip install --python <venv>/bin/python textual`.
4. Resolves the operator config
   (`$MATHLINT_PI_MONITOR_CONFIG` env var, default
   `~/.config/mathlint/local-pi-monitor.toml`).
5. `exec`s `pi-monitor watch` with `--config`, `--script`, `--interval`
   (default 2s, overridable via `--interval N`).

The script honors `MATHLINT_INSTITUTION_DIR` for cross-machine setups.

**Today only `monitor-kaplansky.sh` exists.** It is the first concrete
instance of this pattern; future programs get their own shim generated
from the catalog (`scripts/generate-monitor-shims.sh`, future ADR).

## Rationale

- One-keystroke operator UX is the goal; `pi-monitor watch` already has
  the panels and keybindings, just not a thin entry point.
- Auto-installing Textual is safe (idempotent, confined to the
  pi_monitor venv).
- `exec` replaces the shell process with the TUI, so the TUI becomes the
  foreground process and gets the TTY directly.
- Honoring `MATHLINT_INSTITUTION_DIR` keeps the script consistent with
  the other kaplansky operator scripts (`launch-program.sh`, etc.).

## Alternatives considered

- **A pi skill wrapper (`/skill:monitor_kaplansky`).** Rejected: skills
  are markdown, not shell launchers.
- **A launcher script inside the pi_monitor repo.** Rejected: pi_monitor
  is a generic agentic runner (does not name mathlint per `@INV-0092`).
- **A separate Python entry point.** Rejected: pi-monitor's TUI already
  accepts the right flags; adding a Python wrapper adds a dependency for
  no functional gain.

## Consequences

- Fresh checkouts that have never run pi_monitor's TUI will install
  Textual on first invocation; one-time ~5-second hit.
- The script assumes the standard repo layout (`pi_monitor/` at
  `~/Documents/andrei/pi_monitor`).
- Removing the script is a single `git rm`; the TUI remains accessible
  via the underlying `pi-monitor watch` command.
- Future programs get their own `monitor-<name>.sh` generated from the
  catalog (out of scope for this ADR).

## Change triggers

Revisit if:

- pi_monitor moves `start-pi-monitor-pi-monitor.sh` to a non-canonical
  path.
- Textual becomes a hard dependency of pi_monitor (shipped in the
  default install). Remove the on-demand install branch.
- The operator wants a single generic `./monitor.sh <program>` instead
  of per-program shims (likely when the catalog grows past ~5).
