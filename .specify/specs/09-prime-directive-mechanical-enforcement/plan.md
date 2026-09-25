# 09 — Plan

## Technical context

This entry wires the prime-directive enforcement surface into
production-grade machinery: the runtime extension loads the
canonical exemption registry; the canonical script gains an
`--enforce` mode; the attestation machinery is canonical.

## Existing implementation to extend

- `research-institution/scripts/check-prime-directive.sh` —
  canonical script (entry 00); extended with `--enforce`.
- `research-institution/.specify/memory/constitution-verify.md`
  §10, §11 — the verify-constitution sections this entry
  implements.
- `research-institution/.specify/memory/transient-exemptions.toml`
  — canonical registry (entry 00).
- `~/.pi/agent/extensions/prime-directive-guard.ts` — runtime
  extension; updated to consume the registry.
- `math/Makefile`, `pi_monitor/Makefile`, `kaplansky/Makefile`,
  `research-institution/Makefile` — gain
  `check-prime-directive-enforced`.

## Components changed

| Path | Change |
|---|---|
| `research-institution/research_institution/prime_directive/` | new package. |
| `research-institution/research_institution/prime_directive/{__init__,attest,validate,meta_validator,extension_bridge}.py` | new. |
| `research-institution/scripts/META_validator.py` | new CLI. |
| `research-institution/scripts/check-prime-directive.sh` | add `--enforce` mode. |
| `research-institution/pyproject.toml` | register `prime_directive` console script. |
| `~/.pi/agent/extensions/prime-directive-guard.ts` | load registry; cite row in block message. |
| `math/Makefile` | add `check-prime-directive-enforced`. |
| `pi_monitor/Makefile` | add `check-prime-directive-enforced`. |
| `kaplansky/Makefile` | add `check-prime-directive-enforced`. |
| `research-institution/Makefile` | `check-prime-directive-enforced` already added; this entry finalizes. |
| `math/docs/semantic/adr/adr-NNNN-prime-directive-enforcement.md` | new. |
| `pi_monitor/docs/adr/adr-NNNN-prime-directive-enforcement.md` | new. |
| `kaplansky/docs/.../adr-NNNN-prime-directive-enforcement.md` | new. |

## Components explicitly NOT changed

- The strengthened regex (entry 00 owns).
- The verify-constitution text (entry 00 owns).

## Repository ownership boundary

```
research-institution (prime_directive package; META_validator CLI;
                      enforce mode of canonical script; per-spec
                      attestation machinery)
math                  (Makefile target + local ADR)
pi_monitor            (Makefile target + local ADR)
kaplansky             (Makefile target + local ADR)
```

## Constitution Check (this entry specific)

- **§10** — primary content of this entry.
- **§11** — META attestation machine-checked.
- **§12** — durable record ownership (three new per-repo
  `adr-NNNN-prime-directive-enforcement` records, free IDs).
- **§3** — gate-status algebra honored in `--enforce`.

## Data and state migration

- `transient-exemptions.toml` becomes consumed live by both the
  script (via `--enforce`) and the extension.
- `.pi-prime-attestations/<spec-id>.json` files appear per spec.

## Failure atomicity and rollback

- `--enforce` mode ships as additive (does not regress
  `--selftest` mode from entry 00).
- Each per-repo commit is independently revertible.

## Security / credential impact

None. Attestation records contain only SHA + config fingerprint +
operator name.

## Performance / runtime budgets

- `make check-prime-directive-enforced` ≤ 10 s per repo.
- `attest` runtime < 1 s.
- `validate_META` runtime < 5 s per spec dir.

## Test / evidence tier map (this entry)

| Artifact | Tier |
|---|---|
| `prime_directive.attest` | unit (sha256 over canonical tuple). |
| `prime_directive.validate` | unit + property (rejects stale). |
| `meta_validator` | unit + property (round-trip). |
| `extension_bridge.render_sanctioned_globs` | unit. |
| end-to-end: blocked write → cite row | integration (manual). |

`NOT_APPLICABLE` for `process` / `deployment` / `provider_live` /
`soak`.

## Gate integration

- VG-0…VG-3: pass via prior entries; this entry's artifacts
  supplement.
- VG-4…VG-8: `NOT_APPLICABLE`.

## Documentation and durable-record changes

- New prime_directive package + META_validator.
- New per-repo ADR each.
- Amended: canonical script gains `--enforce`; per-repo Makefile
  gains target; runtime extension upgraded.

## Cross-repository compatibility

The extension loading the registry is one Python (`tomllib`) +
one TS file change; the cross-repo verification relies on the
common `transient-exemptions.toml` schema.

## Retirement / cleanup

None — this entry is permanent infrastructure.
