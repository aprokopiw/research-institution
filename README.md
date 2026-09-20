# research-institution

**The catalog-driven dispatcher for math research programs.** This repo
owns the catalog, the bootstrap, the green gate, and the dispatcher CLI
(see `@ADR-0006`). It owns no application code beyond the thin
delegation layer.

## Sibling repos

| Sibling repo | Role | GitHub |
|---|---|---|
| `math-engine` (this is `~/Documents/andrei/math/`) | Generic typed math validation engine + provider slot + pi_monitor adapter | [`aprokopiw/math-kaplansky-research-program`](https://github.com/aprokopiw/math-kaplansky-research-program) |
| `pi_monitor` | Generic agentic runner that supervises long-running workers | [`aprokopiw/pi_monitor`](https://github.com/aprokopiw/pi_monitor) |
| `kaplansky` (and any future research programs) | Research program: mathematics + evidence + program-specific launcher | [`aprokopiw/math-kaplansky`](https://github.com/aprokopiw/math-kaplansky) |
| **`research-institution` (this repo)** | Catalog + bootstrap + green gate + dispatcher CLI | [`aprokopiw/research-institution`](https://github.com/aprokopiw/research-institution) |

## What this repo owns

| Concern | Artifact |
|---|---|
| Declarative program registry | `catalog/programs.toml`, `catalog/schema.toml` |
| Bootstrap | `scripts/bootstrap-institution.sh` |
| Wiring evidence (canonical gate) | `green-gate/check-institution.sh` |
| Dispatcher CLI (the only application code) | `research_institution/` (Typer) |
| Operator docs | `docs/operations/`, `docs/semantic/` |
| Cold-start workflow | `scripts/cold-resume.sh` |

The dispatcher CLI exposes:

```sh
python -m research_institution list            # read catalog
python -m research_institution doctor [--live] # delegated from green-gate
python -m research_institution start <program> [--dry-run]  # delegated to mathlint
python -m research_institution stop <program>               # delegated to mathlint
python -m research_institution status <program>             # delegated to mathlint
python -m research_institution watch <program>              # delegated to pi-monitor
python -m research_institution install-skills               # per-program pi skill
```

Every command is a thin subprocess wrapper around mathlint + pi_monitor.
No data parsing. No persistence boundary crossings. No reimplementation.
See `@ADR-0006` for the full scope decision.

## Quickstart

```bash
# 1. Clone this repo + math-engine + pi_monitor.
cd ~/Documents/andrei/
git clone https://github.com/aprokopiw/research-institution.git research-institution

# 2. Bootstrap the institution (clones + installs the catalog).
cd research-institution
bash scripts/bootstrap-institution.sh

# 3. Verify the institution is wired (hermetic; no LLM calls).
bash green-gate/check-institution.sh --hermetic

# 4. (Operator-only, machine-specific) Verify the institution is
# wired AND credentials are valid.
MATHLINT_MODEL_ROUTE=openai-codex/gpt-5.6-luna \
    bash green-gate/check-institution.sh --live

# 5. Run a program.
python -m research_institution start kaplansky --dry-run   # preview
python -m research_institution start kaplansky            # launch

# 6. Install per-program pi skills.
python -m research_institution install-skills
```

## Architecture invariant

This repo sits **on top of** math-engine + pi_monitor + N
research programs. It depends on each as a pip-installable
package. None of the sibling repos depend on this one. The
dependency graph goes downward only:

```
research-institution
        │
        ├── math-engine (depends on nothing in this graph)
        ├── pi_monitor (depends on nothing in this graph)
        └── research-program-1, research-program-2, ...
            (each depends on math-engine + pi_monitor)
```

If you uninstall any sibling repo, this repo degrades gracefully
(skip-not-fail). If you uninstall this repo, every sibling repo
still works.

## Repository layout

```
research_institution/
├── __init__.py          # public surface re-export (Program, Dispatcher, GateVerdict, ...)
├── __main__.py          # python -m research_institution
├── catalog.py           # catalog loader + Program dataclass
├── cli.py               # Typer CLI: thin subprocess wrappers per DispatcherVerb
├── dispatcher.py        # in-process Dispatcher API (runner/env/clock injectable)
├── paths.py             # environment protocol + path resolution helpers
└── contracts/
    ├── __init__.py      # public surface for the contracts package
    ├── vocabulary.py    # pure-data StrEnums (TaskKind, GateVerdictStatus, ExitCode, DispatcherVerb)
    ├── gate_verdict.py  # architecture-review gate parser (GateVerdict.from_text)
    ├── entry_point.py   # entry_point: callable parser
    ├── skill_template.py# per-program skill markdown renderer
    ├── source_decision.py # source-decision envelope mirror
    └── source_reports.py  # source-reports JSONL reader
```

Public-surface entry point: `from research_institution import
Program, Dispatcher, GateVerdict, GateVerdictStatus, TaskKind,
ExitCode, DispatcherVerb, load_catalog`. Boundary invariants
(dispatcher does not depend on cli; vocabulary is a leaf module;
no import cycles) are pinned by `tests/test_package_boundary.py`.

## See also

- `AGENTS.md` — prime directive + cold-start workflow.
- `docs/concepts/architecture.md` — mental model: how the four repos fit together (kernel / orchestrator / driver / program).
- `docs/operations/research-institution-quickstart.md` — operator's one-pager.
- `docs/operations/dispatcher-cli-reference.md` — full `research <verb>` reference.
- `docs/operations/bootstrap-and-cold-start.md` — fresh-checkout walkthrough.
- `docs/operations/architecture-review-gate.md` — gate semantics + how to apply.
- `docs/semantic/` — durable semantic records (`@ADR-NNNN`, `@INV-NNNN`, `@CTR-NNNN`).
- `catalog/programs.toml` — declarative program registry.
- `tests/` — contract tests asserting the catalog, the dispatcher, and the green gate.
