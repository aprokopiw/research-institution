# Launch Kaplansky Autonomously — Operator One-Pager

**Goal of this doc:** a fresh operator on a fresh machine can
get `pi-monitor` running the Kaplansky research program end-to-end
in three commands. Each command is reproducible; the verdict is
verifiable. Every step below cites the durable anchor that
records the invariant.

## The mental model (skip if you already have it)

```
research-institution       ← you are here. The OS layer.
        │
        ├── math-engine    ← The kernel. Hosts mathlint.
        ├── pi_monitor     ← The long-running supervisor.
        └── kaplansky      ← A research program (content).
```

The OS owns four things: catalog, bootstrap, green gate,
dispatcher CLI. Three durable anchors pin the contract:

- `@ADR-0006` — the OS scope is exactly the four things above.
- `@ADR-0007` — the OS owns the `WorkSourceProvider` slot in
  mathlint. Kaplansky contributes theorem views, audit reports,
  and obligation labels (content only); the OS composes both
  halves at kernel registration time.
- `@INV-0093` — `bash green-gate/check-institution.sh` printing
  `GREEN INSTITUTION READY` is the canonical evidence the
  institution is wired.

## The three commands

```sh
# 1. Clone everything (research-institution, math, pi_monitor).
git clone https://github.com/aprokopiw/research-institution.git
cd research-institution
bash scripts/bootstrap-institution.sh --apply

# 2. Verify the institution is wired.
bash scripts/verify-institution.sh         # hermetic; CI-safe
# or:
bash scripts/verify-institution.sh --live  # operator-only; needs creds

# 3. Launch the program autonomously.
PYTHONPATH="$HOME/Documents/andrei/research-institution" \
MATHLINT_INSTITUTION_DIR="$PWD" \
python3 -m research_institution start kaplansky
```

## What each step does

### `bootstrap-institution.sh`

Reads `catalog/programs.toml`, then for every entry:

  1. `git clone <repository> <local_path>` (skip if present).
  2. `pip install -e <local_path>` (skip if importable).
  3. Purges `.pi-glla/`, `build/`, `.pytest_cache/` from each
     checkout so the next run starts clean.

Also installs mathlint + pi-monitor as dev deps from local
checkouts (`~/Documents/andrei/math` and
`~/Documents/andrei/pi_monitor`) when present. Falls through
with a warning otherwise (operators may have provided the deps
another way — see `@ADR-0006`).

**Idempotent.** Re-running is safe.

### `verify-institution.sh`

Runs every gate in order and exits 0 with one of:

  - `GREEN INSTITUTION READY` — every check passed.
  - `RED: failed checks: <list>` — at least one failed.

The five canonical stages:

  1. **v0-ruff** — research-institution's lint gate.
  2. **v-wire** — math-engine's G7 cross-repo wiring tier.
     Honors `RESEARCH_INSTITUTION_VWIRE_DIRECT=1` so operators
     can bypass math-engine's unrelated pyramid-inversion drift
     when mathlint's G1..G6 fail.
  3. **engine** — mathlint's `check-local-system-readiness.sh`.
     In hermetic mode it routes through the bundled
     `self_test-sample` program (no LLM, no postgres).
  4. **supervisor** — `pi-monitor doctor`.
  5. **program=kaplansky** — the kaplansky institution-check, in
     Python (`python -m kaplansky.institution_check`). Asserts
     the OS composition wires every kaplansky contribution and
     the work-source slot; checks frozen-claims, roadmap,
     modules.

### `start kaplansky`

Default mode is **autonomous**: spawns
`pi-monitor run --config ~/.config/mathlint/local-pi-monitor.toml`
directly. The supervisor monitors the kaplansky roadmap and
dispatches workers (pi coding-agent sessions). No mathlint
preflight required for this mode. The architecture-review gate
refuses to launch if the gate is closed; override with
`--skip-gate` (logged).

For a single bounded paired run (one receipt), use
`--mode durable` instead.

Use `--dry-run` to preview without spawning.

## Common failure modes

| Symptom | First diagnostic | Durable fix |
|---|---|---|
| `[program=kaplansky] FAILED: kaplansky entry point not registered` | `python -m kaplansky.institution_check` | The check script is now Python and verifies ADR-0007. If it fails, run `pip install -e ~/Documents/andrei/kaplansky` after step 1. |
| `[engine] FAILED: repository is dirty` | `git status` in math and kaplansky | Commit working changes, then re-run verify. The engine rejects dirty state by design. |
| `[v-wire] FAILED: pyramid` | `bash scripts/verify-institution.sh` with `RESEARCH_INSTITUTION_VWIRE_DIRECT=0` | Set `RESEARCH_INSTITUTION_VWIRE_DIRECT=1` (default in `verify-institution.sh`) to bypass math-engine's G1..G6 drift. The institution only owns G7. |
| `[supervisor] WARN: external source handshake` | `pi-monitor doctor --config ~/.config/mathlint/local-pi-monitor.toml` | Run `bash scripts/pi-monitor-kaplansky.sh install` (math-engine side) to (re)install the wrapper. |
| `FATAL: openai-codex credential missing` | `pi auth check --provider openai-codex` | The kaplansky program requires the openai-codex oauth grant. `pi auth login --provider openai-codex` to refresh. |

## Architecture invariants (cite these when you reach for a refactor)

- **Durable refs only:** the durable artifacts in this repo
  (AGENTS.md, README, pyproject, catalog/, green-gate/,
  scripts/, docs/, docs/semantic/) must NEVER cite transient
  refs (`.pi-glla/`, per-plan ledgers, plan-NNN ids). When
  cross-repo state is needed, cite the durable anchor in
  math-engine: `@ADR-0014`, `@ADR-0091`, `@INV-0093`, etc.
- **The dispatcher is the only application code in this
  repo** — `cli.py` is a thin wrapper over mathlint and
  pi_monitor. No persistence or data parsing here.
- **The OS owns one slot in mathlint:** `WorkSourceProvider`
  (`@ADR-0007`). Everything else in mathlint's surface
  belongs to the kernel.

## Repo files of interest

| File | What it is |
|---|---|
| `catalog/programs.toml` | The single source of truth for what runs |
| `green-gate/check-institution.sh` | 4-line shim → Python module |
| `scripts/verify-institution.sh` | The canonical "is the institution ready?" command (sets `RESEARCH_INSTITUTION_VWIRE_DIRECT=1` by default) |
| `scripts/bootstrap-institution.sh` | 4-line shim → Python module |
| `research_institution/gates/aggregate.py` | The green-gate aggregator (canonical impl) |
| `research_institution/gates/bootstrap.py` | The bootstrap installer (canonical impl) |
| `research_institution/gates/runner.py` | Subprocess helper for stage orchestration |
| `research_institution/providers/research_institution_provider.py` | OS-level `WorkSourceProvider`; composes kaplansky contributions |
| `research_institution/tools/fix_test_tier_markers.py` | One-shot tool to stamp pytest tier markers |
| `docs/semantic/adr/adr-0007-*.md` | The architecture record for the OS↔kaplansky split |

## Tests that pin this contract

| Test file | Pins |
|---|---|
| `tests/test_os_provider_compose_proof.py` | WorkSourceProvider composition; never clobber program fields |
| `tests/test_gates_module.py` | The Python gates package surface |
| `tests/test_green_gate_hermetic.py` | Green-gate CLI contract |
| `tests/test_green_gate_cli_shape.py` | Help text, exit codes, verdict lines |
| `tests/test_bootstrap_dry_run.py` | Idempotency + bootstrap install report shape |
| `tests/test_cold_start_hermetic.py` | The cold-start recipe end-to-end |
| (kaplansky) `tests/test_institution_check.py` | The kaplansky-side Python gate |

Run them with:

```sh
PATH="$PWD/.venv/bin:$PATH" MATHLINT_INSTITUTION_DIR="$PWD" \
    python3 -m pytest -q
```

In kaplansky:

```sh
/Users/erinprokopiw/Documents/andrei/math/.venv/bin/python -m pytest --no-cov -q
```
