# 10 — Plan

## Technical context

This entry closes the program. It is the culmination of entries
00–09; its job is to prove the close-out claims with
machine-checked evidence.

## Existing implementation to extend

- `research-institution/research_institution/gates/verify_simulation/`
  (entries 06 / 07 / 08).
- `research-institution/research_institution/prime_directive/`
  (entry 09).
- `research-institution/.specify/specs/{00..09}/*/META.md`
  (every prior META template).
- `.pi-prime-attestations/*.json` (per entry's attestation).
- `research-institution/.agents/transient/test_and_simulation_suite.md`
  — to be retired (FR-7).
- `~/.pi/agent/extensions/prime-directive-guard.ts` — block
  message updated (FR-7).

## Components changed

| Path | Change |
|---|---|
| `research-institution/research_institution/gates/verify_simulation/release.py` | new (FR-1). |
| `research-institution/research_institution/gates/verify_simulation/mutation.py` | new (FR-4). |
| `research-institution/research_institution/gates/verify_simulation/cli.py` | extended with `--tier release`. |
| `research-institution/docs/semantic/ctr-0101-release-gate-contract.md` | new durable record (FR-9). |
| `research-institution/docs/semantic/SEMANTIC_REGISTRY.md` | append row. |
| `research-institution/docs/semantic/CLAIM_MANIFEST.toml` | new (FR-3). |
| `.agents/transient/_retired/test_and_simulation_suite.retired.md` | tombstone (FR-7). |
| `~/.pi/agent/extensions/prime-directive-guard.ts` | block message updated (FR-7). |

## Components explicitly NOT changed

- Any earlier entry's contents (no rewrites).
- The strengthened regex.

## Repository ownership boundary

```
research-institution  (release.py; mutation.py; CLAIM_MANIFEST.toml;
                       ctr-0101-…; SEMANTIC_REGISTRY.md amendment;
                       retired tombstone)
~/.pi                 (extension block-message update)
```

## Constitution Check

- **§3** — gate-status algebra: 7 `PASS` rows + 0 `BLOCKED / NOT_RUN / FAIL`.
- **§4** — VG-6 (mutation) wired here.
- **§5** — action matrix: release-candidate row requires
  VG-0..VG-7; release/lifecycle-change row requires
  VG-0..VG-8.
- **§10** — prime-directive enforcement is mechanical (entry 09).
- **§11** — every entry's META machine-checked.
- **§12** — durable-record ownership honored; `@CTR-0101-…`
  added.

## Data and state migration

- `.agents/transient/test_and_simulation_suite.md` is moved to
  `_retired/test_and_simulation_suite.retired.md`.
- `research-institution/docs/semantic/CLAIM_MANIFEST.toml` is
  new.

## Failure atomicity and rollback

- The retired guide has a tombstone but the strengthened grep
  continues to not match (filename + underscore + .retired.md
  suffix). The pi extension's block message is updated in one
  commit; rollback is simple.

## Security / credential impact

- `release.py` consumes only typed reports; no subprocess should
  leak credentials.

## Performance / runtime budgets

- `--tier release` ≤ 10 min (hard cap).
- Mutation aggregation ≤ 30 min in full mode; CI offline mode
  ≤ 10 min with cached results.

## Test / evidence tier map

| Artifact | Tier |
|---|---|
| `release.py` | integration. |
| `mutation.py` | integration. |
| `CLAIM_MANIFEST.toml` static check | contract. |
| flake audit | property. |
| documentation truth audit | contract. |

## Gate integration

- VG-0…VG-5 / VG-7 / VG-8: pass via prior entries.
- **VG-6** — adversarial assurance gate. This entry wire-up.

## Documentation and durable-record changes

- New durable record: `@CTR-0101-release-gate-contract`.
- New manifest: `CLAIM_MANIFEST.toml`.
- Tombstone of the transient guide.
- Amended: `SEMANTIC_REGISTRY.md`, `prime-directive-guard.ts`.

## Cross-repository compatibility

The CLAIM_MANIFEST cross-references every entry's node-ID;
no cross-repo runtime change beyond the extension block
message.

## Retirement / cleanup

- The retired guide is final; the spec dirs are the durable
  substitute.
- No further entries planned after `10`.
