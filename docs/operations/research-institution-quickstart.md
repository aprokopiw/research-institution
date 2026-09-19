# Research-Institution Quickstart

The research-institution repo is the **catalog-driven dispatcher** for math
research programs. It owns no application code (see `@ADR-0006`); every
program lifecycle verb (`start`, `stop`, `status`, `watch`, `doctor`,
`list`, `install-skills`) is a thin subprocess wrapper around mathlint
and pi_monitor. The catalog (`catalog/programs.toml`) is the only
declarative artifact.

This runbook walks an operator through:

1. Bootstrapping a fresh checkout.
2. Verifying the institution is wired (hermetic + live gates).
3. Driving one program end-to-end through the dispatcher CLI.
4. Installing the per-program pi skills (so `start kaplansky` works from
   any pi session).

## One-liner

```sh
# Bootstrap (clone + pip-install every catalog entry):
bash scripts/bootstrap-institution.sh

# Verify (hermetic; no credentials required):
bash green-gate/check-institution.sh --hermetic

# Verify (live; requires LLM credentials):
MATHLINT_MODEL_ROUTE=openai-codex/gpt-5.6-luna \
    bash green-gate/check-institution.sh --live

# List programs in the catalog:
python -m research_institution list

# Per-program smoke test:
python -m research_institution doctor [--live]

# Start one program (refused if architecture-review gate is closed):
python -m research_institution start <program> [--dry-run]

# Install per-program pi skills (one symlink per catalog entry):
python -m research_institution install-skills
```

When the green gate prints `GREEN INSTITUTION READY`, the institution is
fully wired at the slot + entry-point + config level.

## What the green gate proves

Three sub-checks run in order:

1. **Engine** (mathlint via
   `mathlint check-local-system-readiness.sh` in hermetic mode; the
   operator's real provider in live mode). Proves the mathlint slot is
   wired.
2. **Supervisor** (pi_monitor's `doctor` when on PATH). Proves the
   supervisor is configured.
3. **Programs** (each entry in `catalog/programs.toml` whose
   `local_path` resolves). For kaplansky today,
   `scripts/check-program-institution.sh --hermetic` asserts the entry
   point is registered + the kaplansky invariants parse.

Together: math-engine is wired, the supervisor is reachable, and every
catalog entry is integrated.

## What the green gate does NOT prove

- The gate does NOT prove the institution can do live work (paired-smoke
  receipt, live kaplansky run). For live evidence, run `--live` mode
  (operator-only; requires LLM credentials).
- The gate does NOT prove model credentials are valid; operators with
  credentials run `--live` separately.
- The gate does NOT prove every catalog entry's `mathlint_pin` is
  current; the catalog pins are operator judgment, governed by
  `@CTR-0088`.

## Per-program commands

The dispatcher CLI is the **only** application code in this repo. Every
command delegates to mathlint or pi_monitor.

```sh
python -m research_institution list
# kaplansky   https://github.com/aprokopiw/math-kaplansky   $HOME/Documents/andrei/kaplansky

python -m research_institution doctor
# Delegates to green-gate/check-institution.sh --hermetic

python -m research_institution doctor --live
# Delegates to green-gate/check-institution.sh --live
# Requires MATHLINT_MODEL_ROUTE for the provider sub-check.

python -m research_institution start kaplansky
# Refuses if the architecture-review gate is closed (per ADR-0006,
# pending @ADR-0007 in mathlint).

python -m research_institution start kaplansky --dry-run
# Prints what would launch; exits 0.

python -m research_institution stop kaplansky
# Delegates to mathlint research-stop.

python -m research_institution status kaplansky
# Delegates to mathlint research-status.

python -m research_institution watch kaplansky
# Delegates to pi-monitor watch (TUI; needs a real TTY).

python -m research_institution install-skills
# Generates one skill markdown per catalog entry, symlinked into
# $PI_AGENT_SKILLS_DIR (default: ~/.pi/agent/skills/). Idempotent.
```

## Pi skills

After bootstrapping, install per-program pi skills so `start kaplansky`
works from any pi session:

```sh
python -m research_institution install-skills
```

This generates one skill markdown per catalog entry, symlinked into
`~/.pi/agent/skills/`. Each skill is a thin wrapper
(`@ADR-0002` superseded by `@ADR-0006`) over `python -m research_institution
<verb> <program>`. Use them in any pi session:

- `/skill:kaplansky` — start, stop, status, watch for kaplansky.

Re-run `install-skills` after editing the catalog; it refreshes the
symlinks idempotently.

## Cold-start

A fresh agent session receiving the cold prompt `Run @research_institution_orient`
should follow the workflow in `AGENTS.md` §Cold-start:

1. Read this `docs/operations/research-institution-quickstart.md`.
2. Read `catalog/programs.toml` (the in-flight programs).
3. Run `bash green-gate/check-institution.sh --hermetic` to confirm the
   institution is wired.
4. Run `python -m research_institution list` to enumerate programs.
5. Decide what work to do next based on the durable semantic records
   under `docs/semantic/`.

A cold-start wrapper is also exposed as
`scripts/cold-resume.sh`, which `exec`s `pi "Run @research_institution_orient"`.

## Cross-references

- `@ADR-0006` — research-institution owns only catalog + bootstrap + green gate + dispatcher.
- `@INV-0091` — mathlint does not ship program launchers.
- `@INV-0092` — pi_monitor does not name mathlint.
- `@INV-0093` — institution green gate is the canonical wiring evidence.
- `@TOOL003` — math-engine invariant: live preflight requires `shadow_mode = false`.
- `docs/operations/dispatcher-cli-reference.md` — full CLI reference.
- `docs/operations/bootstrap-and-cold-start.md` — fresh-checkout walkthrough.
- `docs/operations/architecture-review-gate.md` — gate semantics + how to apply.
