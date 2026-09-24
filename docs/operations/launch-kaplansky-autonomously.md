# Launch Kaplansky Autonomously — Operator One-Pager

## Model routing

The math-research worker is `openai-codex/gpt-5.6-sol` (the
only model in the field strong enough for the strict-invariant
discipline the math kernel enforces). The judge and all
non-math interactive sessions stay on the global default
`MiniMax-M3` — judge work is ops/monitoring
(wedge classification, transport health, compaction state),
not math.

Routing table:

| Role       | Model                              | Reason                                             |
| ---------- | ---------------------------------- | -------------------------------------------------- |
| worker     | `openai-codex/gpt-5.6-sol`         | Math research / proof / validation / architecture  |
| judge      | global default (`MiniMax-M3`)      | Ops/monitoring (wedge, transport, compaction)      |
| interactive chat | global default (`MiniMax-M3`) | Non-math work, orchestration, repo maintenance     |

The supervisor reads `[worker].model` from `/tmp/super.toml`
(or whatever `--config` points to). OAuth is satisfied at
`~/.pi/agent/auth.json` — no API key needed for
`openai-codex`.

**Naming convention.** The `[project].name` in `/tmp/super.toml`
is the state-dir slug under `~/.local/state/pi-monitor/`.
Use `name = "kaplansky"` (not `kaplansky-launch-test`) once
real autonomous research has begun — `*-launch-test` is
reserved for smoke-testing the dispatch boundary end-to-end
before model routing and durable record fields are
provisioned.

## Rate caps

The supervisor enforces rolling-window rate-of-burn caps on
top of the cumulative `[budgets]` block. Rate caps answer "is
the worker spending too fast right now?"; cumulative budgets
answer "have we spent enough overall?". A 1m cap catches a
runaway single turn; a 24h cap bounds an overnight run.

Operator-facing knobs live in `[rate_limits]` of the canonical
config (`~/.config/mathlint/local-pi-monitor.toml`):

| Key                          | Purpose                                  | Plus-plan ballpark |
| ---------------------------- | ---------------------------------------- | ------------------ |
| `max_tokens_per_1m`          | single-turn runaway                      | `500_000`          |
| `max_tokens_per_10m`         | stuck-in-a-loop detection                | `3_000_000`        |
| `max_tokens_per_1h`          | session-level drift                      | unset              |
| `max_tokens_per_24h`         | overnight run budget                     | `4_000_000`        |
| `max_dollars_per_*`          | parallel cost caps (same windows)        | unset              |

Plus-plan ballpark derivation: 4M tokens / 5h sustained = ~13K
tokens/min sustained. A 1m cap at 500K leaves 38× headroom for
spiky think steps; 24h at 4M = ~16% of the weekly budget.

When any window trips, the supervisor dispatches on the
operator-declared ``on_exceeded`` action. The Kaplansky
autonomous profile sets ``on_exceeded = "wait_until_eligible"``,
so a trip produces ``rate_limit_denied`` + ``rate_limit_deferred``
events with the computed ``next_eligible_unix`` and the
supervisor re-asks the source at eligibility time. No
``operator_required`` event is emitted, ``stopped`` stays
``False``, and the deadline persists on
``state.next_eligible_unix`` so a restart resumes the
same defer.

Operators who prefer the historical posture can switch to
``on_exceeded = "operator_required"`` in the operator
config (``~/.config/mathlint/local-pi-monitor.toml``).
Under that action the trip emits ``rate_limit_denied`` +
``operator_required`` audit events and stops the run.

Observability surface (read these to confirm the cap fired
correctly):

* `pi-monitor status --latest` -> `repo.math_artifacts.session`
  shows whether research is actually happening (separate from
  cap state).
* `pi-monitor journal -f` -> tail the audit log; search for
  `rate_limit_denied` to find the trip event.
* `~/.local/state/pi-monitor/.../rate_limits/observations.jsonl`
  -> raw ledger. Each line carries a `fp` (config fingerprint)
  tag so a cap raise can be replayed cleanly.

A cap raise in mid-run is safe: the supervisor tags every
observation with the active config fingerprint and drops
observations tagged with the previous fingerprint the moment
the cap changes. The worker resumes as soon as the new cap
is loaded.

## @ADR-0011 source-decision audit fields (post-merge)

The OS-level work source (`select_next_work_for_supervisor`)
emits three new structured fields on the `source_decision`
audit event after @ADR-0011 lands:

- `verdict_kind` — one of `DISPATCH_RESEARCH`,
  `DISPATCH_ARCHITECT`, `ARCHITECTURE_REVIEW_REQUIRED`,
  `NO_ELIGIBLE_WORK`. Maps to the math kernel's `ActionKind`
  translated into the OS-level envelope.
- `target` — the operation_id under consult (e.g. `K4-...`).
- `stagnation_session_count` — the number of substantial
  `NO_ROOT_RELEVANT_DELTA` sessions observed for the target
  (0..N).

Operator grep recipes (post-merge):

- `pi-monitor journal -f | grep '"event":"source_decision"'` —
  every poll cycle.
- `pi-monitor journal -f | grep '"verdict_kind":"ARCHITECTURE_REVIEW_REQUIRED"'` —
  the no-delta loop is paused for the architect horizon to
  complete admission; nothing to do until the kernel's
  admission commit lands.
- `pi-monitor journal -f | grep '"verdict_kind":"DISPATCH_ARCHITECT"'` —
  the architect round is mid-flight; the wire `role`
  becomes `maintenance`; the worker carries the
  `math_directive_content_hash` payload field as the math
  side's typed identity.
- `pi-monitor journal -f | grep '"reason_code":"architecture_review"'` —
  wait reasons emitted under stagnation.

The wire `role` values stay inside pi_monitor's existing
8-value `RoleName` Literal (`default | primary | supporting |
milestone | research | intake | review | maintenance`);
math-internal `MATHEMATICAL_RESEARCHER` /
`MATHEMATICAL_ARCHITECT` `RoleProfileName` values are NEVER
on the wire (`@ADR-0011` + `@INV-0094`).

**Goal of this doc:** a fresh operator on a fresh machine can
get `pi-monitor` running the Kaplansky research program end-to-end
in three commands. Each command is reproducible; the verdict is
verifiable. Every step below cites the durable anchor that
records the invariant.

## The mental model (skip if you already have it)

```
research-institution       ← you are here. The OS layer.
        │
        ├── math-engine    ← The kernel. Hosts mathlint.
        ├── pi_monitor     ← The long-running supervisor.
        └── kaplansky      ← A research program (content).
```

The OS owns four things: catalog, bootstrap, green gate,
dispatcher CLI. Three durable anchors pin the contract:

- `@ADR-0006` — the OS scope is exactly the four things above.
- `@ADR-0007` — the OS owns the `WorkSourceProvider` slot in
  mathlint. Kaplansky contributes theorem views, audit reports,
  and obligation labels (content only); the OS composes both
  halves at kernel registration time.
- `@INV-0093` — `bash green-gate/check-institution.sh` printing
  `GREEN INSTITUTION READY` is the canonical evidence the
  institution is wired.

## The three commands

```sh
# 1. Clone everything (research-institution, math, pi_monitor).
git clone https://github.com/aprokopiw/research-institution.git
cd research-institution
bash scripts/bootstrap-institution.sh --apply

# 2. Verify the institution is wired.
bash scripts/verify-institution.sh         # hermetic; CI-safe
# or:
bash scripts/verify-institution.sh --live  # operator-only; needs creds

# 3. Launch the program autonomously.
PYTHONPATH="$HOME/Documents/andrei/research-institution" \
MATHLINT_INSTITUTION_DIR="$PWD" \
python3 -m research_institution start kaplansky
```

## What each step does

### `bootstrap-institution.sh`

Reads `catalog/programs.toml`, then for every entry:

  1. `git clone <repository> <local_path>` (skip if present).
  2. `pip install -e <local_path>` (skip if importable).
  3. Purges `.pi-glla/`, `build/`, `.pytest_cache/` from each
     checkout so the next run starts clean.

Also installs mathlint + pi-monitor as dev deps from local
checkouts (`~/Documents/andrei/math` and
`~/Documents/andrei/pi_monitor`) when present. Falls through
with a warning otherwise (operators may have provided the deps
another way — see `@ADR-0006`).

**Idempotent.** Re-running is safe.

### `verify-institution.sh`

Runs every gate in order and exits 0 with one of:

  - `GREEN INSTITUTION READY` — every check passed.
  - `RED: failed checks: <list>` — at least one failed.

The five canonical stages:

  1. **v0-ruff** — research-institution's lint gate.
  2. **v-wire** — math-engine's G7 cross-repo wiring tier.
     Honors `RESEARCH_INSTITUTION_VWIRE_DIRECT=1` so operators
     can bypass math-engine's unrelated pyramid-inversion drift
     when mathlint's G1..G6 fail.
  3. **engine** — mathlint's `check-local-system-readiness.sh`.
     In hermetic mode it routes through the bundled
     `self_test-sample` program (no LLM, no postgres).
  4. **supervisor** — `pi-monitor doctor`.
  5. **program=kaplansky** — the kaplansky institution-check, in
     Python (`python -m kaplansky.institution_check`). Asserts
     the OS composition wires every kaplansky contribution and
     the work-source slot; checks frozen-claims, roadmap,
     modules.

### `start kaplansky`

Default mode is **autonomous**: spawns
`pi-monitor run --config ~/.config/mathlint/local-pi-monitor.toml`
directly. The supervisor monitors the kaplansky roadmap and
dispatches workers (pi coding-agent sessions). No mathlint
preflight required for this mode. The architecture-review gate
refuses to launch if the gate is closed; override with
`--skip-gate` (logged).

For a single bounded paired run (one receipt), use
`--mode durable` instead.

Use `--dry-run` to preview without spawning.

## Common failure modes

| Symptom | First diagnostic | Durable fix |
|---|---|---|
| `[program=kaplansky] FAILED: kaplansky entry point not registered` | `python -m kaplansky.institution_check` | The check script is now Python and verifies ADR-0007. If it fails, run `pip install -e ~/Documents/andrei/kaplansky` after step 1. |
| `[engine] FAILED: repository is dirty` | `git status` in math and kaplansky | Commit working changes, then re-run verify. The engine rejects dirty state by design. |
| `[v-wire] FAILED: pyramid` | `bash scripts/verify-institution.sh` with `RESEARCH_INSTITUTION_VWIRE_DIRECT=0` | Set `RESEARCH_INSTITUTION_VWIRE_DIRECT=1` (default in `verify-institution.sh`) to bypass math-engine's G1..G6 drift. The institution only owns G7. |
| `[supervisor] WARN: external source handshake` | `pi-monitor doctor --config ~/.config/mathlint/local-pi-monitor.toml` | Run `bash scripts/pi-monitor-kaplansky.sh install` (math-engine side) to (re)install the wrapper. |
| `FATAL: openai-codex credential missing` | `pi auth check --provider openai-codex` | The kaplansky program requires the openai-codex oauth grant. `pi auth login --provider openai-codex` to refresh. |

## Architecture invariants (cite these when you reach for a refactor)

- **Durable refs only:** the durable artifacts in this repo
  (AGENTS.md, README, pyproject, catalog/, green-gate/,
  scripts/, docs/, docs/semantic/) must NEVER cite transient
  refs (`.pi-glla/`, per-plan ledgers, plan-NNN ids). When
  cross-repo state is needed, cite the durable anchor in
  math-engine: `@ADR-0014`, `@ADR-0091`, `@INV-0093`, etc.
- **The dispatcher is the only application code in this
  repo** — `cli.py` is a thin wrapper over mathlint and
  pi_monitor. No persistence or data parsing here.
- **The OS owns one slot in mathlint:** `WorkSourceProvider`
  (`@ADR-0007`). Everything else in mathlint's surface
  belongs to the kernel.

## Repo files of interest

| File | What it is |
|---|---|
| `catalog/programs.toml` | The single source of truth for what runs |
| `green-gate/check-institution.sh` | 4-line shim → Python module |
| `scripts/verify-institution.sh` | The canonical "is the institution ready?" command (sets `RESEARCH_INSTITUTION_VWIRE_DIRECT=1` by default) |
| `scripts/bootstrap-institution.sh` | 4-line shim → Python module |
| `research_institution/gates/aggregate.py` | The green-gate aggregator (canonical impl) |
| `research_institution/gates/bootstrap.py` | The bootstrap installer (canonical impl) |
| `research_institution/gates/runner.py` | Subprocess helper for stage orchestration |
| `research_institution/providers/research_institution_provider.py` | OS-level `WorkSourceProvider`; composes kaplansky contributions |
| `research_institution/tools/fix_test_tier_markers.py` | One-shot tool to stamp pytest tier markers |
| `docs/semantic/adr/adr-0007-*.md` | The architecture record for the OS↔kaplansky split |

## Tests that pin this contract

| Test file | Pins |
|---|---|
| `tests/test_os_provider_compose_proof.py` | WorkSourceProvider composition; never clobber program fields |
| `tests/test_gates_module.py` | The Python gates package surface |
| `tests/test_green_gate_hermetic.py` | Green-gate CLI contract |
| `tests/test_green_gate_cli_shape.py` | Help text, exit codes, verdict lines |
| `tests/test_bootstrap_dry_run.py` | Idempotency + bootstrap install report shape |
| `tests/test_cold_start_hermetic.py` | The cold-start recipe end-to-end |
| (kaplansky) `tests/test_institution_check.py` | The kaplansky-side Python gate |

Run them with:

```sh
PATH="$PWD/.venv/bin:$PATH" MATHLINT_INSTITUTION_DIR="$PWD" \
    python3 -m pytest -q
```

In kaplansky:

```sh
/Users/erinprokopiw/Documents/andrei/math/.venv/bin/python -m pytest --no-cov -q
```
