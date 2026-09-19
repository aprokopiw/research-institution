# Bootstrap and Cold-Start

The cold-start workflow is the operator's recipe for "I just cloned
research-institution on a fresh machine; what do I do?" This document
is the operator's walkthrough; `AGENTS.md` §Cold-start is the agent's
walkthrough (same workflow, different audience).

## Fresh checkout (operator)

```sh
# 1. Clone research-institution + the two sibling repos.
cd ~/Documents/andrei/
git clone https://github.com/aprokopiw/research-institution.git
git clone https://github.com/aprokopiw/math.git math
git clone https://github.com/aprokopiw/pi_monitor.git pi_monitor

# 2. Bootstrap: clone + pip-install every catalog entry.
cd research-institution
bash scripts/bootstrap-institution.sh
# -> prints INSTITUTION BOOTSTRAPPED

# 3. Verify: hermetic green gate.
bash green-gate/check-institution.sh --hermetic
# -> prints GREEN INSTITUTION READY (engine + supervisor + each program)

# 4. (Operator-only) verify with credentials.
MATHLINT_MODEL_ROUTE=openai-codex/gpt-5.6-luna \
    bash green-gate/check-institution.sh --live
# -> prints GREEN INSTITUTION READY (with provider roundtrip)

# 5. Install per-program pi skills.
python -m research_institution install-skills
# -> /skill:kaplansky now works in any pi session

# 6. Start a program (dry-run first).
python -m research_institution start kaplansky --dry-run
python -m research_institution start kaplansky
```

## Cold-start (agent)

The agent workflow is `AGENTS.md` §Cold-start:

1. Read `AGENTS.md` (the prime directive).
2. Read `docs/operations/research-institution-quickstart.md` (this repo's role).
3. Read `catalog/programs.toml` (the in-flight programs).
4. Run `bash green-gate/check-institution.sh --hermetic`.
5. Decide what to do next from `docs/semantic/`.

A wrapper shortcut: `scripts/cold-resume.sh` does
`exec pi "Run @research_institution_orient"`.

## Bootstrap script behavior

`scripts/bootstrap-institution.sh`:

1. Reads `catalog/programs.toml`.
2. Tries `uv pip install` for mathlint + pi_monitor dev deps (warns
   if `uv` is missing or install fails; does NOT abort).
3. For each catalog entry:
   - Skips if `local_path` already exists.
   - Otherwise `git clone`s the repository at the catalog's `repository`
     URL.
4. Prints `INSTITUTION BOOTSTRAPPED` and the green-gate command.

The script is **idempotent**: re-running after partial success skips
already-cloned paths. Empty catalogs are tolerated (prints success
with no programs).

## What bootstrap does NOT do

- Does not run any LLM checks (that's `--live` on the green gate).
- Does not install Textual into pi_monitor's venv (per B.2.3, that's
  the operator's responsibility today; future: bootstrap installs it).
- Does not set up pi's auth.json (the operator's responsibility).
- Does not configure the operator's shell rc (per the original
  wiring, the operator sets `MATHLINT_MODEL_ROUTE` themselves).

## After bootstrap fails

If bootstrap prints a warning, fix the underlying cause before
proceeding:

| Symptom | Cause | Fix |
|---|---|---|
| `uv not on PATH` | uv not installed | `brew install uv` (or your platform's install command) |
| `dev-dep install failed` | git remotes unreachable, or tag `v0.1.0` retired | Update `pyproject.toml`'s dev-dep pins to current tags; the pins are operator judgment, governed by `@CTR-0088` |
| `git clone failed` for a program | repo URL wrong, or network blocked | Verify `catalog/programs.toml`'s `repository` field |
| `INSTITUTION BOOTSTRAPPED` printed but green gate RED | mathlint or pi_monitor not on PATH | Add `$HOME/Documents/andrei/math/.venv/bin` and `$HOME/Documents/andrei/pi_monitor/.venv/bin` to PATH |

## Cross-references

- `AGENTS.md` §Cold-start.
- `docs/operations/research-institution-quickstart.md` — operator one-pager.
- `scripts/bootstrap-institution.sh` — the bootstrap script.
- `green-gate/check-institution.sh` — the canonical green gate.
- `tests/test_bootstrap_dry_run.py` — contract tests for the bootstrap.
- `tests/test_cold_start_hermetic.py` — contract tests for the cold-start workflow.
