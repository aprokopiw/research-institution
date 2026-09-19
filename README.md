# research-institution

**The canonical home for "which math research programs are in
flight, what the LLM credential + supervisor configurations are,
and is the whole institution wired?"**

This repository orchestrates three sibling repos:

| Sibling repo | Role | GitHub |
|---|---|---|
| `math-engine` (this is `~/Documents/andrei/math/`) | Generic typed math validation engine + provider slot + pi_monitor adapter | [`aprokopiw/kaplansky-research-program`](https://github.com/aprokopiw/kaplansky-research-program) (legacy remote name; the repo IS math-engine) |
| `pi_monitor` | Generic agentic runner that supervises long-running workers | [`aprokopiw/pi_monitor`](https://github.com/aprokopiw/pi_monitor) |
| `kaplansky` (and any future research programs) | Research program: mathematics + evidence + program-specific launcher | [`aprokopiw/math-kaplansky`](https://github.com/aprokopiw/math-kaplansky) |
| **`research-institution` (this repo)** | Aggregator that owns the catalog, the green gate, the bootstrap script, and the cross-repo contracts | [`aprokopiw/research-institution`](https://github.com/aprokopiw/research-institution) |

This repo **owns no application code**. It owns:

- **`catalog/programs.toml`** — declarative registry of every
  in-flight research program (name, repository, entry point,
  local path, mathlint pin, live-credential requirements).
- **`green-gate/check-institution.sh`** — THE canonical green
  gate. Exits 0 with `GREEN INSTITUTION READY` when math-engine,
  pi_monitor, and every installed program are wired.
- **`scripts/bootstrap-institution.sh`** — clones + installs
  every catalog entry; produces a fully-wired institution from
  a fresh checkout.
- **`docs/operations/research-institution-quickstart.md`** —
  the operator's one-pager.

## Quickstart

```bash
# 1. Clone this repo + math-engine + pi_monitor + the programs you want.
cd ~/Documents/andrei/
git clone https://github.com/aprokopiw/research-institution.git research-institution

# 2. Bootstrap the institution (clones + installs the catalog).
cd research-institution
bash scripts/bootstrap-institution.sh

# 3. Verify the institution is wired (hermetic; no LLM calls).
bash green-gate/check-institution.sh --hermetic

# 4. (Operator-only, machine-specific) Verify the institution is
# wired AND credentials are valid.
bash green-gate/check-institution.sh --live
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

## Canonical green gate

```bash
bash green-gate/check-institution.sh --hermetic
```

When this exits 0 with `GREEN INSTITUTION READY`, the institution
is fully wired and verified end-to-end without making LLM calls.

For the operator-only "is this machine actually ready" check:

```bash
bash green-gate/check-institution.sh --live
```

This adds real LLM-credential verification + real kaplansky
provider roundtrip + real pi_monitor doctor on top of the
hermetic checks.

## See also

- `docs/operations/research-institution-quickstart.md` —
  one-pager for operators.
- `docs/semantic/` — durable semantic records (`@ADR-NNNN`,
  `@INV-NNNN`, `@CTR-NNNN`).
- `catalog/programs.toml` — declarative program registry.
- `tests/` — contract tests asserting the catalog and the
  green gate.
