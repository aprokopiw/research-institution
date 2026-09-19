---
name: kaplansky
description: Start, stop, status, and watch the Kaplansky Research Program program. Thin wrapper over `research kaplansky ...` (the catalog-driven dispatcher in research-institution). Use when the operator says "kaplansky start", "kaplansky stop", "@kaplansky", or asks to interact with this program. Thin wrapper over `research kaplansky ...` (the catalog-driven dispatcher in research-institution). Use when the operator says "kaplansky start", "kaplansky stop", "@kaplansky", or asks to interact with this program.
---

# Kaplansky Research Program

Catalog entry: `kaplansky`. Local path: `$HOME/Documents/andrei/kaplansky`. Entry point: `kaplansky.mathlint_plugin:register`.

## Invoke

```sh
# Start (refused if architecture-review gate is closed; --dry-run bypasses).
research start kaplansky [--dry-run]

# Stop
research stop kaplansky

# Status
research status kaplansky

# Watch (TUI; needs a real TTY).
research watch kaplansky
```

All commands are thin subprocess wrappers around mathlint + pi_monitor. See
`docs/operations/research-institution-quickstart.md` for the operator
one-pager.

## Cross-references

- `@ADR-0006` — research-institution owns only catalog + bootstrap + green gate + dispatcher.
- `$HOME/Documents/andrei/kaplansky/docs/ROADMAP.md` — program-specific roadmap.
