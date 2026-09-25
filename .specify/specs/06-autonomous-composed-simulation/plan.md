# 06 — Plan

## Technical context

This entry scaffolds the canonical verification CLI consumed by
every later entry's VG-3+ gate. It composes entries 02 (fake-Pi) +
04 (sample program) + 05 (substrate helpers) into one Typer command
that drives real subprocesses against disposable program roots.

## Existing implementation to extend

- `research_institution/research_institution/gates/aggregate.py`
  — `v-compose` stage (canonical seam per §3 of guide).
- `research_institution/research_institution/cli.py` — existing
  Typer CLI (`list`, `doctor`, `start`, `stop`, etc.).
- `research_institution/research_institution/dispatcher.py` —
  subprocess wrappers.
- `research_institution/research_institution/paths.py` —
  catalog / green-gate / pi-monitor path resolvers.
- `research_institution/research_institution/providers/research_institution_provider.py`
  — `register` (entry 04 / 05 consume this; entry 06 doesn't
  reshape it).
- `pi_monitor/tests/substrate/` (entry 05).
- `math/src/mathlint/self_test/sample_program/scenarios/`
  (entry 04).
- `research-institution/scripts/verify-institution.sh` — extends
  to invoke `verify-simulation --tier full` through the existing
  `gates.aggregate.check_institution()` `v-compose` stage.

## Components changed

| Path | Change |
|---|---|
| `research_institution/gates/verify_simulation/` | new package. |
| `research_institution/gates/verify_simulation/cli.py` | new — Typer entry. |
| `research_institution/gates/verify_simulation/runner.py` | new — orchestration. |
| `research_institution/gates/verify_simulation/temp_root.py` | new — temp factory. |
| `research_institution/gates/verify_simulation/oracle/{transcript,audit,exactly_once,frontier,resource}.py` | new — independent oracles. |
| `research_institution/gates/verify_simulation/scenarios.py` | new — registry of canonical scenarios. |
| `research_institution/tests/simulation/scenarios/*.py` | new — per-scenario metadata. |
| `research_institution/gates/aggregate.py` | extend `v-compose` to invoke the new CLI. |
| `research-institution/pyproject.toml` | register `verify-simulation` console script. |
| `pi_monitor/src/pi_monitor/state/audit.py` (`audit_chain_verify.py`) | consumed by `oracle/audit.py`. |
| `transient-exemptions.toml` | append rows for `gates/verify_simulation/`. |

## Components explicitly NOT changed

- `pi_monitor.tests.substrate` (entry 05 unchanged).
- `math.self_test.sample_program` (entry 04 unchanged).
- `pi_monitor.src.pi_monitor.supervision._dispatch_loop`
  (private — entry 06 must NOT call).

## Repository ownership boundary

```
research-institution  (canonical CLI + verify-simulation package +
                       aggregate `v-compose` extension;
                       scenarios shipped here)
math                  (sample program; scenarios consumed by
                       reference — entry 04 owns; no edits by 06
                       unless wiring consumes)
pi_monitor            (substrate helpers; entry 05 owns; no edits)
```

## Constitution Check

- **§1–§5** — verify-constitution honored.
- **§6** — no-second-supervisor; entry 06 composes existing
  supervisors, doesn't introduce new ones.
- **§9** — one canonical CLI.
- **§10** — canonical prime-directive script at HEAD.
- **§11** — META emitted.

## Data and state migration

None.

## Failure atomicity and rollback

- Verify-simulation package lands in one PR with
  green-gate aggregate extension; the canonical CLI is
  observable from day one. Rollback is per-commit.

## Security / credential impact

- `provider-canary --live` honors the credentials gate;
  refuses to mutate kaplansky production.
- `--tier fast` and `--tier full` and `--tier process` are
  network-disabled; credential vars sanitized.

## Performance / runtime budgets

- `--tier fast` ≤ 30 s.
- `--tier full` ≤ 5 min (typical).
- `--tier process --scenario happy-three-cycle` ≤ 15 s;
  required set ≤ 90 s.

## Test / evidence tier map (entry 06)

| Artifact | Tier |
|---|---|
| `gates/verify_simulation/oracle/*.py` | contract (typed envelopes). |
| `tests/simulation/scenarios/*.py` | integration / process. |
| `--tier fast` (aggregate `v-compose` extended) | integration. |
| `--tier process` (full required set) | process. |

`NOT_APPLICABLE` for `deployment` (entry 07) and `provider_live`
(entry 07) and `soak` (entry 07).

## Gate integration

- VG-0…VG-3: pass via previous entries.
- **VG-4** — process simulation gate. Entry 06 contributes the
  canonical S2 evidence.
- VG-5…VG-8: `NOT_APPLICABLE`.

## Documentation and durable-record changes

- New canonical CLI + oracles + scenarios.
- `gates/aggregate.py` `v-compose` extended.
- New durable records: none. The CLI is documented inline +
  `docs/operations/dispatcher-cli-reference.md` amended.

## Cross-repository compatibility

- The CLI consumes entry 02 / 04 / 05 outputs unchanged.
- The four repos' venv is already used (per the aggregate's
  `sys.executable` discipline).

## Retirement / cleanup

- Any ad-hoc subprocess test script that previously ran an
  end-to-end simulation is **removed** at completion SHA. The
  canonical CLI is the only entry point.
- `transient-exemptions.toml` rows seeded by 06 expire on this
  entry's id.
