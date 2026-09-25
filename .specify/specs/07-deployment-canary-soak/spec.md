# 07 — Canonical Deployment, Provider Canary, and Soak

> **Spec-Kit** artifact. Zero-padded `00–10`. This is `07`. Depends on
> `06`. Unblocks `08`.

## Identity

- **spec_id:** `07-deployment-canary-soak`
- **owner_repo:** `research-institution`
- **owner_repos:** `{research-institution, math, pi_monitor}`
- **status:** draft
- **depends_on:** `06-autonomous-composed-simulation`
- **unblocks:** `08-installed-compatibility-recovery`

## Primary actor

The maintainer / SRE who runs deployment and the operator who runs
the canary against a real provider. Implicit audience: entry 10
(release closure references entry 07's evidence).

## Problem statement

Today there is no single command that:

- Spawns the institution via the canonical
  `research start kaplansky --dry-run` from any of four cwds.
- Renders LaunchAgent `ProgramArguments` deterministically.
- Runs an opt-in macOS-only deployment test that bootout the
  isolated label on completion.
- Runs the provider canary (`--tier provider-canary --live`)
  with a disposable simulation program + real Pi + real model.
- Runs a soak (`--tier soak --hours N`) with declared duration
  + resource oracle.

Per the master guide §3 ("Simulation architecture") + §6
("Deployment/config antagonists") + Stage F (production-composed
isolated launch) + Stage H (provider canary and soak).

## Independent user stories

1. As a **CI author**, I run
   `python -m research_institution verify-simulation --tier deployment`;
   the harness instantiates a temp HOME / state / config, invokes
   the canonical `research start --dry-run` from institution
   root / math root / tmp program root / unrelated dir, asserts
   the rendered `ProgramArguments` matches the actual
   `pi-monitor run --config <temp>` invocation.
2. As a **macOS operator**, I run
   `--tier deployment --macos-isolated-label`; the harness
   loads the LaunchAgent under an isolated label and bootouts
   in `finally`.
3. As a **real-provider operator**, I run
   `--tier provider-canary --live`; one bounded operation; the
   canary produces a typed report `CANARY_PASS | CANARY_BLOCKED`
   against a disposable program.

## Functional requirements

FR-1. **`research_institution/gates/verify_simulation/`** extends:

   - `deployment.py` — temp `HOME` / `XDG_STATE_HOME` /
     `XDG_CONFIG_HOME` / `PYTHONPATH`; isolated invocation.
   - `cli.py` adds `--tier deployment` with subflags:
     `--macos-isolated-label=<unique>`.
   - `cli.py` adds `--tier provider-canary --live` with
     `--scenario rate-defer-restart` (the only canonical
     canary scenario at first).
   - `cli.py` adds `--tier soak --hours N` with explicit
     duration.
   - Each `--tier` refuses to run without the right argument
     (`--live` for provider-canary; `--hours` for soak).

FR-2. **Rendered `ProgramArguments`** captured at the same
`PyInstaller`-equivalent resolution the production launcher uses
(executable resolution + Python environment + state dir +
`pi_monitor_config_path`). The harness asserts the dry-run prints
the identical arguments.

FR-3. **Cross-cwd test** confirms `research doctor` from each of
four cwds:

   - research-institution root;
   - math root;
   - temporary program root;
   - unrelated directory.

FR-4. **macOS deployment test** (opt-in via
`--macos-isolated-label=<unique>`):

   - write a temp plist with `ProgramArguments` from the
     rendering;
   - `launchctl load -w <plist>`;
   - poll status JSON;
   - `launchctl bootout` in `finally`;
   - assert no user HOME / state / service is mutated when the
     isolated label exits.

FR-5. **`--tier provider-canary --live`**:

   - asserts `MATHLINT_MODEL_ROUTE` is set (per
     `@ADR-0001`-style routing);
   - asserts `~/.pi/agent/auth.json` is reachable (the OAuth
     grant, per kaplansky's auth path);
   - spins a disposable simulation program (entry 04);
   - runs ONE bounded operation against real Pi + real model;
   - asserts credential validity, real protocol, real usage
     telemetry, artifact write, outcome report, next decision;
   - **never mutates kaplansky's production frontier**;
   - emits `CANARY_PASS` or `CANARY_BLOCKED`;
   - `BLOCKED` if credentials absent.

FR-6. **`--tier soak --hours N`**:

   - alternates productive / no-delta / slow-active / wait /
     rate-defer scenarios (per master guide Stage H);
   - samples memory, CPU, process count, state-file growth,
     audit verification, duplicate reports, cycle latency;
   - records with bounded evidence archive (commit / config /
     scenario hashes);
   - fails on operator pause not explicitly scripted, hot loop,
     orphan process, stalled wake, or unbounded state growth.

FR-7. **Soak duration is mandated**; missing `--hours` = gate
`FAIL`.

## Explicit exclusions

- Cross-repo compatibility matrix (entry 08).
- Real `provider_live` runs against kaplansky's production
  frontier (refused; FR-5).
- Authoring mutation tests (entry 10).

## Measurable success criteria

- `--tier deployment` exits 0 from each of four cwds.
- The rendered `ProgramArguments` is identical between dry-run
  and the actual subprocess invocation (byte-equal).
- `--tier deployment --macos-isolated-label=<unique>` exits 0
  on macOS; the isolated LaunchAgent is bootout in `finally`.
- `--tier provider-canary --live` exits 0 in < 10 min (hard
  deadline).
- `--tier soak --hours 8` exits 0; the bounded evidence archive
  is produced and signed (per `constitution-verify.md` §10).

## Failure and edge cases

- **F-1.** LaunchAgent load fails. The harness emits actionable
  error; gate `FAIL`.
- **F-2.** Provider canary detects missing credentials.
  `CANARY_BLOCKED`; gate not `PASS`. Allowed at release; required
  release-blocker only with credentials present.
- **F-3.** Soak detects a hot loop. Process tree oracle catches;
  FAIL.

## Dependencies on earlier entries

- **Entry 00** — verify-constitution §3, §5, §10.
- **Entry 04** — sample program.
- **Entry 05** — substrate helpers.
- **Entry 06** — canonical CLI.

## "Cannot claim done when…"

1. `--tier deployment` does not exit 0 from at least one of the
   four cwds.
2. Rendered `ProgramArguments` differs from actual subprocess
   invocation.
3. macOS deployment test mutates user HOME / state / service.
4. `--tier provider-canary --live` runs without `--live` flag
   (silent) or mutates production frontier.
5. `--tier soak --hours N` runs without `--hours`.
6. The dispatch envelope shape drifts from `@CTR-0094`.
7. Real-provider canary is marked `PASS` while credentials are
   absent (no LIVE run actually executed).
8. `make check-prime-directive` exits non-zero at HEAD.
9. Entry 00/04/05/06 cannot-claim-done clauses do NOT hold.
10. Soak evidence archive is unsigned.
11. Provider canary lingers past 10 min.
12. The hot-loop oracle reports a surviving hot loop.

## Non-goals

- Cross-repo compatibility (entry 08).
- Release closure (entry 10).
- Authoring new `process`-tier scenarios (entry 06 owns).

## Cross-references

- `.specify/memory/constitution-verify.md` §3, §4, §5, §10, §11.
- `@ADR-0001` (kaplansky uses pi OAuth).
- `@ADR-0006` (research-institution scope).
- `@CTR-0094` (work-source dispatch envelope).
- `@INV-0093` (institution green gate).
- pi_monitor `@ADR-0004` (macOS LaunchAgent).
