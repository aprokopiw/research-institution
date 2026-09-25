# 02 — Plan

## Technical context

This is the second sister entry (math = 01, pi_monitor = 02,
kaplansky = 03) in the rationalization family. Its job is unique to
02: not only enforce the test vocabulary, but consolidate the fake-Pi
implementation from inline-generator into a typed executable
module. The latter feeds entry 05 + 06.

## Existing implementation to extend

- `pi_monitor/tests/helpers.py::make_fake_pi` — the inline
  generator. Becomes the thin wrapper. Body lifted to
  `fake_pi_rpc.py`.
- `pi_monitor/tests/mathlint_fixture/{server.py,protocol.py,matrix.py}`
  — scenario fixtures; FROZEN pre-cleanup wire vocabulary
  (exempted via `transient-exemptions.toml`).
- `pi_monitor/tests/mathlint_campaign.py` — campaign harness with
  manual `finalize_attempt` calls. Preserved at its call sites; the
  harness' docstring / README / AGENTS reference loses the
  "end-to-end" claim this entry.
- `pi_monitor/Makefile` — has `test` target routed through
  `unittest discover`. Extended.
- `pi_monitor/pyproject.toml` — no coherent tier markers; metadata
  exists for pytest configuration.
- `pi_monitor/tests/{compose_*,state_machine_*,supervisor_*,mathlint_campaign.py,mathlint_faults.py}`
  — happy-path tests that must remain green unchanged.
- `pi_monitor/src/pi_monitor/protocol/source_wire.py` — wire
  vocabulary, immutable.
- `research-institution/.specify/memory/transient-exemptions.toml`
  — receives pi_monitor rows appended with
  `expiry_spec_id = "02-fake-pi-consolidation"`.
- `research-institution/scripts/check-prime-directive.sh` — runs
  at pi_monitor HEAD per M0 prevention layer.

## Components changed

| Path | Change |
|---|---|
| `pi_monitor/tests/support/fake_pi_rpc.py` | new (FR-1). |
| `pi_monitor/tests/support/__init__.py` | new (sibling to existing `tests/helpers/`-like patterns). |
| `pi_monitor/tests/helpers.py::make_fake_pi` | becomes thin wrapper (FR-3). |
| `pi_monitor/tests/static/test_closed_tier_vocabulary.py` | new. |
| `pi_monitor/tests/static/test_dependency_vocabulary.py` | new. |
| `pi_monitor/tests/static/test_skip_xfail_baseline.py` + `.toml` | new. |
| `pi_monitor/tests/static/test_collection_parity.py` | new (FR-5). |
| `pi_monitor/Makefile` | tier-routed + unified targets (FR-5). |
| `pi_monitor/pyproject.toml` | add `[tool.pytest.collect_only]` profile + tier-marker conventions. |
| `pi_monitor/tests/{empty_reserved}/*` | deleted (FR-7). |
| `pi_monitor/tests/mathlint_campaign.py` | docstring + README ref relabel (FR-8). |
| `pi_monitor/AGENTS.md` | update cross-reference to `fake_pi_rpc` (cross-ref only). |
| `research-institution/.specify/memory/transient-exemptions.toml` | append pi_monitor rows (FR-9). |

## Components explicitly NOT changed

- `src/pi_monitor/**/*` (entry 05 owns any supervisor-side changes).
- `src/pi_monitor/protocol/source_wire.py` (wire vocabulary authority).
- `tests/mathlint_fixture/server.py` (frozen pre-cleanup wire
  vocab; exempt from migration).
- `tests/test_mathlint_campaign.py`,
  `tests/test_mathlint_faults.py`, `tests/test_compose_*`,
  `tests/test_state_machine_*` — body unchanged; documented
  success criterion.

## Repository ownership boundary

```
pi_monitor           (canonical fake-Pi module; tier static checks;
                      Makefile; parity check; relabel call-sites)
research-institution (transient-exemptions.toml pi_monitor rows)
```

## Constitution Check (entry-02-specific)

- **§1** — tier vocabulary enforced in pi_monitor.
- **§2** — dependency vocabulary enforced in pi_monitor.
- **§3** — gate-status algebra honored (BLOCKED for missing
  optional deps).
- **§8** — single source of fake-Pi truth: `fake_pi_rpc.py`.
- **§10** — canonical prime-directive script runs at pi_monitor
  HEAD per commit.
- **§11** — META emitted at completion.

## Data and state migration

- `pi_monitor/tests/static/skip_xfail_baseline.toml` — same
  schema as entry 01's companion, with pi_monitor-specific rows.
- `pi_monitor/pyproject.toml` — opt-in tier markers via
  `[tool.pytest.ini_options].markers`.

## Failure atomicity and rollback

- Each commit keeps the four happy-path tests green; if any
  regress, that commit is reverted.
- `fake_pi_rpc.py` introduction is staged:
   (a) module + parse_scenario + run_scenario + cli_main +
       selftest scenario;
   (b) `make_fake_pi` delegates to module;
   (c) any second fake-Pi generator removed.
   Each stage ends with the four happy-path tests green.

## Security / credential impact

- `fake_pi_rpc.py` sanitizes its environment (per FR-1's CLI
  contract): refuses to launch if `OPENAI_API_KEY` is present in
  the deterministic-tiers environment, refuses to launch if
  `~/.pi/agent/auth.json` exists in scope.
- The selftest scenario runs offline; no network, no provider.

## Performance / runtime budgets

- `make test-suite-unified` ≤ 5 min.
- `pytest -q tests/static/test_closed_tier_vocabulary.py ...`
  ≤ 10 s.
- `pytest -q tests/static/test_collection_parity.py` ≤ 5 s.
- `python -m pi_monitor.tests.support.fake_pi_rpc <smoke>.json --selftest`
  ≤ 2 s.

## Test / evidence tier map (entry 02)

| Artifact | Tier | Evidence |
|---|---|---|
| `fake_pi_rpc.parse_scenario` | unit | deterministic; AST + JSON schema |
| `fake_pi_rpc.run_scenario` | unit | dry-run; subprocess-isolated |
| `test_closed_tier_vocabulary.py` | contract | static AST |
| `test_dependency_vocabulary.py` | contract | static AST |
| `test_skip_xfail_baseline.py` | contract | static AST + TOML parse |
| `test_collection_parity.py` | integration | subprocess for both collectors; diff |

`NOT_APPLICABLE` for `process` / `deployment` / `provider_live` /
`soak` here — those land in 05 / 06 / 07 / 10.

## Gate integration

- VG-0: collection parity + grep clean.
- VG-1: tier vocabulary enforced.
- VG-2: required-lane skip count zero.
- VG-3: `make test-tier-fast` green; parity check green.
- VG-4…VG-8: `NOT_APPLICABLE`.

## Documentation and durable-record changes

- New: `fake_pi_rpc.py`, three static check modules, parity
  module, baseline TOML.
- Amended: `helpers.py`, `Makefile`, `pyproject.toml`,
  `mathlint_campaign.py` (docstring), `AGENTS.md` cross-ref.
- New durable records: none. The fake-Pi is documented inline in
  `tests/support/fake_pi_rpc.py`'s module docstring + a local
  `docs/adr/NNNN-fake-pi-consolidation.md` in pi_monitor (per
  pi_monitor AGENTS Working rules).

## Cross-repository compatibility

Entry 02's output is consumable by entry 06 as a subprocess:
`python -m pi_monitor.tests.support.fake_pi_rpc <scenario.json>`.
The wire contract on stdout is JSON-line (`source_wire.py`-shaped).

## Retirement / cleanup

- A `make fake-pi-consolidation-cleanup` target (added by 02)
  removes any orphan second implementation on completion SHA.
- `tests/mathlint_fixture/` remains exempt
  (`transient-exemptions.toml`); NOT retired by this entry.
