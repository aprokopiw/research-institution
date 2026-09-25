# 09 — Research

## Existing assets reused

- `~/.pi/agent/extensions/prime-directive-guard.ts` — extension;
  upgraded to consume the registry.
- `research-institution/scripts/check-prime-directive.sh` — script
  in canonical position; gains `--enforce`.
- `research-institution/.specify/memory/transient-exemptions.toml`
  — registry (entry 00).
- `research-institution/.specify/memory/constitution-verify.md`
  §10, §11 (the entry's authority).
- `research-institution/Makefile` (entry 00 scaffold).
- `math/Makefile`, `pi_monitor/Makefile`, `kaplansky/Makefile`
  each has `check-prime-directive`; this entry adds
  `check-prime-directive-enforced`.

## Rejected parallel approaches (with reasons)

- **R1.** Replace the TypeScript extension with a Python port.
  REJECTED: the extension is the runtime gate; replacing it is a
  bigger change than needed.
- **R2.** Hand-write attestation JSON. REJECTED: per §3.5 +
  §11, machine-checked emission is required.
- **R3.** Re-implement `check-prime-directive.sh` in Python.
  REJECTED: shell script is the canonical surface.

## Unresolved questions resolved before implementation

| Question | Resolution |
|---|---|
| Which per-repo ADR IDs? | Free IDs in each repo (`math` and `pi_monitor` and `kaplansky` ship their own namespace per `constitution-verify.md` §12.1). The IDs land at the same numeric slot as the entry's `00`-owned counterpart (`@ADR-0095-…`) only when free. |
| How does the extension load the registry? | At startup; refresh on every workspace open. |

## Open risks

- **R-A.** A malformed `transient-exemptions.toml` (manual edit)
  breaks the extension. Default-deny: extension falls back to
  the historical message; no row cited. Operator must fix the
  registry.

## Cross-references

- `@ADR-0095-prime-directive-mechanical-enforcement` (entry 00).
- `@INV-0095-prg-anchor-ownership`.
- `@CTR-0095-prime-directive-check-script-contract`.
