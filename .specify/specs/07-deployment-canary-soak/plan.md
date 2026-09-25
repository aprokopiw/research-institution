# 07 — Plan

## Technical context

Entry 07 is the deployment + canary + soak tier; it composes the
canonical CLI (entry 06) with the production launcher (RI's
`research` Typer CLI + pi_monitor's LaunchAgent integration).

## Existing implementation to extend

- `research_institution/research_institution/cli.py` — existing
  research verbs; extended with `--tier deployment | provider-canary
  | soak` for `verify-simulation`.
- `research_institution/research_institution/dispatcher.py` —
  subprocess wrappers; consumed by `--tier deployment`.
- `research_institution/research_institution/paths.py` — path
  resolvers; consumed by deployment's temp HOME.
- `research-institution/launchd-templates/kaplansky-pi-monitor.plist.xml`
  — LaunchAgent template; rendered into a temp label under
  `--tier deployment --macos-isolated-label=<unique>`.
- `research-institution/config-templates/kaplansky-pi-monitor.toml`
  — supervisor config template; rendered by `research bootstrap`.
- `pi_monitor/src/pi_monitor/state/audit/audit_chain_verify.py` —
  audit verifier; consumed by entry 06.
- `~/.pi/agent/auth.json` — kaplansky's OAuth grant (kaplansky's
  auth path per `@ADR-0001`).
- `math/src/mathlint/self_test/sample_program/` (entry 04).
- `pi_monitor/tests/substrate/` (entry 05).
- `research_institution/gates/verify_simulation/` (entry 06).

## Components changed

| Path | Change |
|---|---|
| `research_institution/gates/verify_simulation/deployment.py` | new (FR-1). |
| `research_institution/gates/verify_simulation/cli.py` | extended with `--tier deployment \| provider-canary \| soak` (FR-1). |
| `research_institution/gates/verify_simulation/oracle/soak.py` | new (FR-6). |
| `research-institution/scripts/verify-institution.sh` | extended to invoke `--tier deployment` in hermetic mode. |
| `transient-exemptions.toml` | append rows. |

## Components explicitly NOT changed

- `launchd-templates/*` content (template).
- `config-templates/*` content.
- `pi_monitor` production code.
- `math` production code.

## Repository ownership boundary

```
research-institution  (deployment + canary + soak orchestration)
math                  (consumer of canary scenario; sample program)
pi_monitor            (LaunchAgent loader; orchestrator)
```

## Constitution Check

- **§3** — gate-status algebra honored.
- **§4** — VG-5 (deployment composition), VG-7 (provider canary),
  VG-8 (soak/release) wired.
- **§5** — action matrix (`merge` requires +VG-5; release
  candidate requires +VG-7; release/lifecycle change requires
  +VG-8).
- **§10** — `make check-prime-directive` exits 0.
- **§11** — META emitted.

## Data and state migration

None.

## Failure atomicity and rollback

Each tier lands in its own commit; rollback is per-commit.

## Security / credential impact

- `--tier provider-canary --live` honors kaplansky's OAuth grant
  path; never leaks the credential into subprocess output.
- macOS deployment test must bootout the isolated label in
  `finally`.

## Performance / runtime budgets

- `--tier deployment` ≤ 5 min (hard cap).
- `--tier provider-canary --live` ≤ 10 min (hard cap).
- `--tier soak --hours N` declared at invocation time.

## Test / evidence tier map (entry 07)

| Artifact | Tier |
|---|---|
| `--tier deployment` | deployment. |
| `--tier provider-canary --live` | provider_live. |
| `--tier soak --hours N` | soak. |

`NOT_APPLICABLE` for `unit` / `property` / `contract` /
`integration` / `process` here — those land in earlier entries.

## Gate integration

- VG-0…VG-4: pass via prior entries.
- **VG-5** — deployment composition gate. Entry 07 contributes.
- VG-6: `NOT_APPLICABLE` (entry 10).
- **VG-7** — external canary gate. Entry 07 contributes.
- **VG-8** — soak/release gate. Entry 07 contributes.

## Documentation and durable-record changes

- New: deployment.py, soak.py.
- Amended: cli.py, verify-institution.sh.
- No new durable records.

## Cross-repository compatibility

- `--tier deployment` consumes the canonical `research start`
  Typer CLI from each of the four cwds.
- `--tier provider-canary --live` runs the **disposable**
  simulation program; kaplansky's production is untouched.

## Retirement / cleanup

- Any ad-hoc soak script is removed at completion SHA. The
  canonical CLI is the only entry point.
- `transient-exemptions.toml` rows seeded by 07 expire on this
  entry's id.
