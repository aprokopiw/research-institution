# Dispatcher CLI Reference

The dispatcher is the **only application code** this repo owns (see
`@ADR-0006`). Every command is a thin subprocess wrapper around
mathlint and pi_monitor; no data parsing, no persistence-boundary
crossings, no reimplementation.

This document is the canonical reference. The CLI is also discoverable
via `python -m research_institution <verb> --help`.

## Entry point

```sh
python -m research_institution <verb> [args]
```

The CLI is a Typer app; subcommands are listed below. Exit codes are
documented per verb; convention is:

- `0` — success.
- `1` — internal failure (gate verdict unparseable, subprocess error).
- `2` — usage error (unknown verb, unknown program, missing file).
- `3` — catalog-local error (program path missing, config missing).
- `4` — credential error (env var unset for a credentialed program).
- `5` — gate closed (architecture-review block; see B.1.2).

## `list`

```sh
python -m research_institution list
```

Print every program in `catalog/programs.toml` as a table.

```
NAME                 REPOSITORY                                         LOCAL_PATH
kaplansky            https://github.com/aprokopiw/math-kaplansky        $HOME/Documents/andrei/kaplansky
```

Exit `0` always; empty catalog prints `(catalog is empty)` and exits
non-zero via Typer's default (treat as success).

## `doctor [--live] [--program <name>]`

```sh
python -m research_institution doctor          # hermetic
python -m research_institution doctor --live   # operator-live (requires credentials)
python -m research_institution doctor --program kaplansky  # scope to one program
```

Delegates to `green-gate/check-institution.sh [--hermetic|--live]
[--skip-program=<name>]`. Exit code is the gate's exit code:

- `0` — `GREEN INSTITUTION READY`.
- `1` — at least one sub-check failed; stdout names which.
- `2` — unknown flag passed through to the gate.

## `start <program> [--dry-run] [--skip-gate]`

```sh
python -m research_institution start kaplansky --dry-run
python -m research_institution start kaplansky              # requires gate-open
python -m research_institution start kaplansky --skip-gate  # operator override
```

The launch verb. Per `@ADR-0006` + B.1.2, refuses to launch while
the architecture-review gate is closed.

### Behavior

1. Resolves the program's `local_path` from the catalog.
2. Exits `3` if `local_path` does not exist.
3. `--dry-run` skips both the gate check and credential check; prints
   what would happen and exits `0`.
4. Otherwise:
   - Reads the gate verdict by parsing `mathlint roadmap` output
     (`TASK KIND:` line). If the value is `ARCHITECTURE_REVIEW_REQUIRED`,
     refuses with exit `5` + actionable error.
   - `--skip-gate` overrides the gate check; logs the override and
     proceeds (use only when you have an out-of-band operator decision).
   - Validates `live_credential_env_vars` if `live_credentials_required`.
     Exits `4` if any required env var is unset.
   - Delegates to `mathlint live-run --confirm-live`. Exit code
     mirrors mathlint's exit.

### Why the gate check uses roadmap parsing

mathlint does not yet expose a programmatic gate verdict (cross-repo
ask `@ADR-0007`). `mathlint roadmap` is read-only, lock-free, runs in
~0.6s, and has a stable `TASK KIND:` line format. Once `@ADR-0007`
ships, the dispatcher switches to `mathlint architect-review --verdict
--program <name>` and the roadmap-parse path becomes a fallback.

### Exit codes

| Code | Meaning |
|---|---|
| 0 | launched (or dry-run printed) |
| 2 | unknown program |
| 3 | program `local_path` missing |
| 4 | credential env var unset |
| 5 | architecture-review gate closed (refusal) |
| other | mathlint exit code (propagated) |

## `stop <program>`

```sh
python -m research_institution stop kaplansky
```

Delegates to `mathlint research-stop`. Exit code mirrors mathlint's.

## `status <program>`

```sh
python -m research_institution status kaplansky
```

Delegates to `mathlint research-status`. Exit code mirrors mathlint's.

## `watch <program> [--interval N]`

```sh
python -m research_institution watch kaplansky              # 2s refresh
python -m research_institution watch kaplansky --interval 1 # 1s refresh
```

Delegates to `pi-monitor watch`. Requires:

- `pi-monitor` on PATH (operator's pi_monitor venv).
- `$HOME/.config/mathlint/local-pi-monitor.toml` present.
- `$PI_MONITOR_REPO/start-pi-monitor-pi-monitor.sh` present
  (defaults to `~/Documents/andrei/pi_monitor/start-pi-monitor-pi-monitor.sh`).
- A real TTY (Textual needs it).

Exit codes:

- `2` — config missing.
- `3` — start script missing.
- Other — pi-monitor's exit code (propagated).

### TUI keybindings (owned by pi_monitor)

The TUI is pi_monitor's. Keybindings and panel layout are documented
in pi_monitor's `docs/`. Research-institution does not own this surface.

## `install-skills`

```sh
python -m research_institution install-skills
```

Generates one pi skill markdown per catalog entry, symlinked into
`$PI_AGENT_SKILLS_DIR` (default `~/.pi/agent/skills/`). Idempotent:
re-running refreshes the symlinks without touching sibling skill
installs.

Each skill is a thin pointer to the dispatcher CLI:

```text
/kaplansky start
/kaplansky stop
/kaplansky status
/kaplansky watch
```

## Cross-references

- `@ADR-0006` — research-institution owns only catalog + bootstrap + green gate + dispatcher.
- `@ADR-0007` — cross-repo ask: `mathlint architect-review --program <name>` + verdict flag.
- `docs/operations/research-institution-quickstart.md` — operator one-pager.
- `docs/operations/architecture-review-gate.md` — gate semantics + how to apply.
- `docs/operations/bootstrap-and-cold-start.md` — fresh-checkout walkthrough.
