# 05 — Plan

## Technical context

This entry builds the **substrate** on top of entry 02's
fake-Pi module and feeds entry 06. It introduces typed helpers at
`tests/substrate/`. The work is mechanical extension + cleanup of
the manual finalize hooks.

## Existing implementation to extend

- `pi_monitor/tests/helpers.py::make_fake_pi` (refactored by 02;
  now thin wrapper over `fake_pi_rpc.py`).
- `pi_monitor/tests/mathlint_campaign.py` — campaign harness;
  with manual finalize hooks.
- `pi_monitor/tests/test_mathlint_faults.py` — fault tests.
- `pi_monitor/tests/mathlint_fixture/{server.py,protocol.py,matrix.py}`
  — source-side fault controls (entry 02 retained frozen).
- `pi_monitor/src/pi_monitor/state/execution_records.py` —
  reconcile verdict table for restart-boundary.
- `pi_monitor/src/pi_monitor/protocol/source_wire.py` — wire
  vocabulary.
- `research-institution/.specify/memory/transient-exemptions.toml`
  — append pi_monitor-substrate rows.

## Components changed

| Path | Change |
|---|---|
| `pi_monitor/tests/substrate/__init__.py` | new. |
| `pi_monitor/tests/substrate/fake_pi_scenario.py` | new (FR-1). |
| `pi_monitor/tests/substrate/restart_at_boundary.py` | new (FR-2). |
| `pi_monitor/tests/substrate/transcript_oracle.py` | new (FR-3). |
| `pi_monitor/tests/substrate/process_tree_cleanup.py` | new (FR-4). |
| `pi_monitor/tests/substrate/timing_seams.py` | new (FR-5). |
| `pi_monitor/tests/static/test_substrate_metadata.py` | new (FR-8). |
| `pi_monitor/tests/static/test_substrate_inventory.py` | new (FR-10). |
| `pi_monitor/tests/mathlint_campaign.py` | manual finalize removed (FR-7). |
| `pi_monitor/tests/test_mathlint_faults.py` | retargeted to substrate helpers (FR-6). |
| `pi_monitor/AGENTS.md` | refresh cross-references. |
| `research-institution/.specify/memory/transient-exemptions.toml` | append pi_monitor-substrate rows. |

## Components explicitly NOT changed

- `src/pi_monitor/**/*` (production code).
- `protocol/source_wire.py` (wire authority).

## Repository ownership boundary

```
pi_monitor           (substrate helpers + retargeted fault tests +
                      meta + inventory static checks)
research-institution (transient-exemptions.toml rows for the
                      new tests/substrate/ paths)
```

## Constitution Check (entry-05-specific)

- **§3** — gate-status algebra honored (substrate reports its
  own verdicts).
- **§5** — action matrix respected (commit-gate).
- **§6** — no-second-supervisor pledge; the substrate is test-only.
- **§8** — fake-Pi ownership (entry 02 still owns; this entry
  consumes).
- **§10** — canonical prime-directive script at pi_monitor HEAD.
- **§11** — META emitted.

## Data and state migration

None.

## Failure atomicity and rollback

- Substrate helpers land one commit each; fault retargeting lands
  one commit; manual-finalize removal lands one commit; meta +
  inventory static checks land one commit.
- Each commit keeps `make test-tier-fast`, `make test-suite-unified`,
  `make check-prime-directive` exit 0.

## Security / credential impact

- `transcript_oracle.py` denies known-credential substrings; tested.

## Performance / runtime budgets

- `pytest -q tests/substrate/` ≤ 5 min.
- `pytest -q tests/mathlint_campaign.py` ≤ 2 min.
- `pytest -q tests/test_mathlint_faults.py` ≤ 2 min.

## Test / evidence tier map (entry 05)

| Artifact | Tier |
|---|---|
| substrate helpers | unit / integration / process |
| `test_substrate_metadata.py` | contract |
| `test_substrate_inventory.py` | contract |
| retargeted fault tests | process (per scenario metadata) |

`NOT_APPLICABLE` for `deployment` / `provider_live` / `soak`.

## Gate integration

- VG-0 / VG-1 / VG-2 / VG-3: pass via entry 02's artifacts.
- VG-4: this entry's substrate contributes process-tier S2
  evidence that entry 06 consumes.
- VG-5…VG-8: `NOT_APPLICABLE`.

## Documentation and durable-record changes

- New: substrate module + tests.
- Amended: campaign harness (manual finalize removed); AGENTS.md.
- No new durable records.

## Cross-repository compatibility

- Substrate helpers are pure Python; consumed by entry 06 across
  repos via subprocess (the fake-Pi executable spawned with the
  scenario JSON).

## Retirement / cleanup

- The manual finalize hooks in `mathlint_campaign.py` are
  removed; the harness's docstring loses the "manual
  finalization phase" phrasing.
- `transient-exemptions.toml` rows seeded by 05 expire on this
  entry's id.
