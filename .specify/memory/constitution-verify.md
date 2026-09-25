# research-institution — verify-constitution (cross-repo canonical)

> This is the second of two constitutions. It governs the **verification
> surface** of the entire institution (research-institution, math-engine,
> pi_monitor, kaplansky, and any future research program). The other
> constitution — `.specify/memory/constitution.md` (typing, 8 principles
> I–VIII) — governs the typing surface. The two are co-equal; neither
> supersedes the other. Where their rules touch (e.g. typing of report
> payloads, typing of cross-repo scenario JSON, typing of gate report
> structured rows), both apply simultaneously and the stricter rule wins.

**Owner repository of the canonical text:** `research-institution`
(`.specify/memory/constitution-verify.md`). Sibling repos re-export via a
machine-checked comment at the top of their own `.specify/memory/`
directory if and when one exists; today none do (math-engine,
pi_monitor, kaplansky ship no `.specify/` tree), so this file is the
single source.

**Version:** 0.0.0 (pre-ratification)
**Ratified:** pending — gated on `git commit` after spec `00-verify-constitution-ratification`
completes its audit-close-out.
**Last amended:** pending.

**Authority chain.** This constitution is the cross-repo canonical
verify-constitution. Per `research-institution/.agents/transient/test_and_simulation_suite.md`
(the Spec-Kit implementation program) and the architecture described in
`research-institution/docs/concepts/architecture.md`, research-institution
owns cross-repo orchestration. Cross-repo verify-policy therefore lives
here. Sibling repositories may add **local** verify clauses (e.g.
`pi_monitor` adds watcher-specific runtime fences) but may not weaken
these rules.

---

## §0. How to read this constitution

The twelve sections that follow are organized by concern, not by repo.
Every section has: a Title, a Statement, Sub-Rules (numbered S§N.M),
and **Linked durable anchors** recording the cross-repo ADR/INV/CTR/CON
that already encodes a related durable decision. New durable anchors
must be added (and linked here) under the spec that introduces them
— see §11 (audit-close-out).

When a sub-rule references an action verb (MUST, MUST NOT, SHOULD,
SHOULD NOT, MAY), the meaning follows RFC 2119.

When a sub-rule references a tier or dependency marker, the
**closed vocabularies** in §1 and §2 are exhaustive. New markers require
a constitution amendment (MINOR bump) and an `@ADR-NNNN` justification.

When a sub-rule references a gate, see §4 for the catalogue
(VG-0…VG-8) and §5 for the canonical action matrix.

---

## §1. Tier vocabulary is a closed set of eight markers

**Statement.** Every collected test in every repo carries **exactly one**
primary `tier` marker. Directory placement does not encode tier. No file
naming convention encodes tier. The closed set is:

| Marker | Definition |
|---|---|
| `unit` | one unit; no filesystem / process / network / time / env mutation |
| `property` | generative, metamorphic, or state-machine evidence under the same `unit` discipline |
| `contract` | one boundary's type / schema / wire / API contract |
| `integration` | multiple production components in one process |
| `process` | one or more real subprocesses with isolated local resources |
| `deployment` | canonical package / config / launcher / service composition |
| `provider_live` | real external provider or credentials |
| `soak` | duration / resource stability |

**Sub-rules.**

- **S1.1.** Each test has **exactly one** primary tier marker. Two
  primary markers = constitution defect; gate `FAIL`.
- **S1.2.** Six strings are **forbidden as primary tier markers**
  because they encode different dimensions and produced documented drift:
  `e2e`, `smoke`, `acceptance`, `endurance`, `live`, `chaos`. Any
  existing occurrence is grandfathered only via the registry at
  `research-institution/.specify/memory/transient-exemptions.toml`
  with an expiry date (default: spec completion of `01-…`,
  `02-…`, or `03-…` that retires it).
  - `chaos` is a technique/fault profile, not an execution boundary.
  - `acceptance` is a claim role, not an execution boundary.
  - `live` is dependency provenance, not evidence strength.
  - `smoke` describes breadth / runtime, not oracle.
  - `endurance` is `soak`.
  - `e2e` is replaced by explicit `process`, `deployment`, or `provider_live`.
- **S1.3.** `unit` MUST NOT depend on filesystem, subprocess, sleep,
  network, or environment mutation. A test violating this is
  reclassified, not suppressed.
- **S1.4.** `provider_live` MUST require an explicit `--live` opt-in via
  the institution verification CLI
  (`python -m research_institution verify-simulation --tier provider-canary --live`).
- **S1.5.** `soak` MUST require an explicit duration (`--hours N` or
  equivalent). Missing duration = gate `FAIL`.

**Enforcement.** `tests/static/test_closed_tier_vocabulary.py` per
repo (added in spec `01-…` for math, `02-…` for pi_monitor, `03-…` for
kaplansky, and `06-…` for research-institution).

**Linked durable anchors:** `@INV-0088` (sample fixture requires no
external state); `@INV-0093` (institution green gate is canonical wiring
evidence).

---

## §2. Dependency vocabulary is a closed set, pre-flighted to BLOCKED

**Statement.** Every non-`unit` test declares the dependencies it
requires via `@pytest.mark.dependencies(...)` (or per-repo equivalent).
The closed dependency set is:

```
filesystem, git, subprocess, postgres, pi_executable,
pi_monitor_executable, model_provider, network,
macos_launchd, formal_backend_flint, formal_backend_gap
```

**Sub-rules.**

- **S2.1.** A missing required dependency yields **lane `BLOCKED`**,
  not green pytest with skips. Skipping within a required lane is gate
  `FAIL`.
- **S2.2.** `pi_executable` and `pi_monitor_executable` refer to
  executable artifacts, not Python imports. The harness checks the
  `--print`/`--version` exit code, not importability.
- **S2.3.** `model_provider` requires a path or env-var fingerprint for
  the route, not a key. Faking the route is gate `FAIL`.
- **S2.4.** `network` covers DNS, HTTP, IMAP, webhook. `localhost` is
  not excluded; it is `network` unless the test owns the server
  process.
- **S2.5.** Per-test opt-out via per-test marker is forbidden. Lane
  declaration is via gate manifest, not per-test invention.

**Linked durable anchors:** `@ADR-0088`, `@ADR-0089` (sample fixture
provenance), `@CTR-0020` (three-repo wire contract).

---

## §3. Gate-status algebra has five verdicts, never coalesced

**Statement.** Every gate emits one of exactly five status values,
valid for every row and every roll-up:

```
PASS | FAIL | BLOCKED | NOT_RUN | NOT_APPLICABLE
```

**Sub-rules.**

- **S3.1.** `BLOCKED` is a **terminal** state for release. `BLOCKED`
  may not be auto-coerced to `PASS` or `FAIL`.
- **S3.2.** `NOT_RUN` is a gate-disabling miss. It may not be silently
  masked as `PASS`.
- **S3.3.** `NOT_APPLICABLE` requires justification per row; bulk
  `NOT_APPLICABLE` is gate `FAIL`.
- **S3.4.** Gate roll-ups at higher tiers (release) inherit the strictest
  child verdict: `FAIL > BLOCKED > NOT_RUN > PASS > NOT_APPLICABLE`.
  An overall release `PASS` requires every required gate `PASS`.
- **S3.5.** Anti-cheat rules from the test-and-simulation guide are
  encoded as S3 sub-rules here:
  - **S3.5.a** Gate command == CI command. Implementation drift =
    gate `FAIL`.
  - **S3.5.b** No substring test selection (`-k foo` against required
    test IDs is gate `FAIL`).
  - **S3.5.c** Required evidence cannot use `pytest.warns` /
    `conftest.skip` / `pytest.mark.xfail` to convert non-zero to zero.
  - **S3.5.d** Required evidence cannot depend on `unittest discover`
    parity looseness. Collector parity (`pytest --collect-only` lists
    exactly the same nodes as the canonical collector) is itself a
    VG-0 invariant; absence is gate `FAIL`.
  - **S3.5.e** Required evidence cannot pickle/deepcopy instead of
    exercising a restart. Required restart claims require an S2 process
    restart.

**Linked durable anchors:** `@INV-0093` (institution green gate);
`@INV-0094` (no-delta loop is source-side); `@ADR-0011` (stagnation
handling is a source decision); pi_monitor `@ADR-0001` (source owns
domain meaning, monitor owns execution).

---

## §4. VG-0 through VG-8 are sequential, required, non-bypassable

**Statement.** The eight verification gates are:

| Gate | Purpose | Owner |
|---|---|---|
| **VG-0** | Repository and collection integrity (no-coverage collection; deterministic inventory hash; manifest references exist) | every repo |
| **VG-1** | Classification integrity (exactly one tier marker per test; dependencies valid) | every repo |
| **VG-2** | Skip / xfail / quarantine integrity (zero required skips; legacy skip baseline ratchets down) | every repo |
| **VG-3** | Fast deterministic gate (S0+S1 evidence; no network, model, or PG) | every repo |
| **VG-4** | Process simulation gate (S2 scenarios through real subprocesses) | research-institution |
| **VG-5** | Deployment composition gate (S3 isolated canonical launcher, four cwds) | research-institution |
| **VG-6** | Adversarial assurance gate (mutation; property; fault matrix; surviving critical mutant = `FAIL`) | research-institution |
| **VG-7** | External canary gate (real Pi/provider, `--live`, BLOCKED if no creds, disposable program) | research-institution |
| **VG-8** | Soak / release gate (declared duration; signed/hash-tagged report) | research-institution |

**Sub-rules.**

- **S4.1.** Required-tier evidence MUST land at the gate named in §5.
  A claim that a lower gate "suffices" is gate `FAIL`.
- **S4.2.** Every gate's output is a **structured report** with rows:
  `status`, `tier`, `scenario_or_test_id`, `claim_id`, `owner_repo`,
  `duration_seconds`, `artifact_paths`, `error_summary`, `gate_version`.
- **S4.3.** Every report binds (per §3.5) repo SHAs, dirty state,
  Python version, package version, config fingerprint, selected
  scenarios/claims, and counts by status. Missing fields = gate `FAIL`.
- **S4.4.** Every gate has **gate self-tests** proving the gate itself
  fails-loud against seeded bad fixtures (collection error, missing
  referenced test, duplicate claim ID, claim with zero evidence, unit
  test launching subprocess, unknown marker, required skipped test,
  non-strict xfail, unexpected pass, fake-GREEN-line + non-zero exit,
  stale report, wrong config fingerprint, test deselection removing
  required scenario, process leak, audit corruption, manual finalization,
  deployment bypassing canonical launcher, provider canary absent during
  release). Self-test failure is gate `FAIL`.
- **S4.5.** Mutation-test gate aggregator is required to **kill** every
  named critical mutant from §12 of the test-and-simulation guide.
  Surviving critical mutant = release-blocking `FAIL`.

**Linked durable anchors:** pi_monitor `@ADR-0005` (audit
append-only hash-chained); `@INV-0093` (institution green gate is
canonical wiring evidence); `@INV-0094` (no-delta loop is
source-side); `@CTR-0094` (work-source provider dispatch envelope).

---

## §5. Action matrix is the canonical "what gate runs when"

| Action | Required gates (owner) |
|---|---|
| `local_edit` | owner VG-0, VG-1, focused VG-3 |
| `commit` | owner VG-0…VG-3 |
| `merge` (protected branch) | changed owners VG-0…VG-3 + institution VG-4 |
| `deployment_config_lifecycle_merge` | above + VG-5 + critical VG-6 subset |
| `nightly` | all deterministic gates + full VG-6 + platform / compatibility matrix |
| `release_candidate` | VG-0…VG-7 + install / upgrade / restore matrix |
| `autonomous_research_release` | all above + VG-8 soak |

**Sub-rules.**

- **S5.1.** An implementation goal cannot be marked complete until the
  row above its action lands `PASS` at current repository SHAs.
- **S5.2.** A `BLOCKED` row is not auto-converted to "code complete."
- **S5.3.** Provider / soak evidence unavailable today remains
  `BLOCKED` until it is executed; verbal override is impossible.

**Linked durable anchors:** `@INV-0093` (institution green gate is
canonical); pi_monitor `@ADR-0005` (audit append-only hash-chained).

---

## §6. No second supervisor / no second source / no second campaign engine

**Statement.** All simulation work **extends** the existing assets:

- math self-test sample: `math/src/mathlint/self_test/sample_program/`
- pi_monitor fake Pi: `pi_monitor/tests/helpers.py::make_fake_pi` → consolidated to `pi_monitor/tests/support/fake_pi_rpc.py`
- pi_monitor fixture: `pi_monitor/tests/mathlint_fixture/`
- pi_monitor campaign: `pi_monitor/tests/mathlint_campaign.py`
- math fault doubles: `math/tests/support/fake_worker.py`,
  `math/tests/support/fake_mathlint_roadmap.py`,
  `math/tests/support/fake_boundaries.py`,
  `math/tests/orchestration/_support/fake_live_source.py`
- institution fakes: `research-institution/tests/_fakes.py`
  (decomposed along owner boundaries — not one helper per file)
- institution gate: `research_institution/gates/aggregate.py`
  (its `v-compose` stage is the **single canonical seam** for the
  verify-simulation CLI)

**Sub-rules.**

- **S6.1.** A new helper MUST cite (in its module docstring, with a
  relative-path reference to the canonical helper it extends or
  replaces) which existing asset it extends, and MUST NOT duplicate an
  existing behavior under a new name.
- **S6.2.** New helper behavior MUST be consolidated back into the
  canonical owner when the spec that introduced it completes (per the
  master guide §11 set-up rules).
- **S6.3.** No private supervisor method calls in S2/S3 process
  simulation. No manual finalization via `complete_active` /
  `finalize_attempt` / `finalize_record` / `record_publication` in S2/S3
  evidence.
- **S6.4.** No `time.time` / `time.sleep` monkeypatch across processes.
  S0/S1 use `FakeClock`; S2/S3 use short real deadlines.

**Linked durable anchors:** `@ADR-0014` (mathlint does not import
program-named modules); `@ADR-0091` (mathlint ships no program launchers);
`@ADR-0006` (research-institution scope is catalog + bootstrap + green
gate + thin dispatcher); `@CTR-0020` (three-repo wire contract);
`@CTR-0094` (work-source provider dispatch envelope).

---

## §7. Stateful sample program contract

**Statement.** `math/src/mathlint/self_test/sample_program/` ships in
two explicit modes, selected by environment:

| Mode | Trigger | Behavior |
|---|---|---|
| **readiness** | default (any environment without `MATHLINT_SELF_TEST_MODE=simulation`) | frozen `Dispatch` envelope; fixed operation_id, fingerprint `self-test-fixture-v1`, `decided_unix=0.0`; ignores repository. Hermetic by construction. |
| **simulation** | `MATHLINT_SELF_TEST_MODE=simulation` | stateful multi-cycle reducer driven by `<program-root>/.simulation/{scenario.json, frontier.json, reports.jsonl, decisions.jsonl, artifacts/}` |

**Sub-rules.**

- **S7.1.** The **readiness envelope MUST remain byte-for-byte
  equivalent** to today's `sample_work_source(/_build_envelope()` when
  simulation mode is absent. A change to the envelope requires an
  `@ADR-NNNN` plus a wave of compatibility tests.
- **S7.2.** Simulation state is local to the disposable program root;
  the simulation mode NEVER touches real Kaplansky repo state.
- **S7.3.** Sample register (`register.py`) MUST always emit a
  non-`None` `ProgramProviders` so `discover_program_providers()` does
  not raise "did not register providers." The sample `WorkSourceProvider`
  slot is populated only when `MATHLINT_SELF_TEST_PROVIDER=1`. Mathlint
  ships ONE `mathlint.providers` entry point per machine; sample never
  shadows kaplansky without an explicit opt-in.
- **S7.4.** Any new field on `ProgramProviders` (e.g. typed report
  callback) MUST ship with: a default-`None` declaring the existing
  shape compatible, a typed `Callable` protocol, an entry-point
  compat test, a real-source adapter test, a sample-registration test,
  and zero import of a program-named module from generic mathlint.
- **S7.5.** Simulation mode uses **canonical bytes** (no XML YAML
  incidental whitespace; JSON encoding fixed-order; `sorted_keys=True`;
  trailing newline fixed) to derive the deterministic revision
  fingerprint.

**Linked durable anchors:** `@ADR-0088` (sample fixture
classification); `@ADR-0089` (sample fixture as canonical CI fixture);
`@INV-0088` (sample fixture requires no external state); `@CTR-0085`
(sample-program dispatch envelope shape); `@CTR-0020` (three-repo wire
contract).

---

## §8. Fake-Pi ownership and consolidation

**Statement.** The fake-Pi protocol is owned by `pi_monitor`. The
single canonical executable lives at
`pi_monitor/tests/support/fake_pi_rpc.py`. Research-institution's
process-simulation runner invokes it as a subprocess; it **must not
import** pi_monitor test internals into production code.

**Sub-rules.**

- **S8.1.** `pi_monitor/tests/helpers.py::make_fake_pi` becomes a thin
  wrapper around `fake_pi_rpc.py`, preserving existing pi_monitor
  test call-sites' behavior on the happy path.
- **S8.2.** A scenario document is **JSON**, validated by a closed
  action vocabulary before process start; unknown action = immediate
  process-fail with actionable error.
- **S8.3.** Fake actions reuse existing names from
  `math/tests/support/fake_worker.py` and
  `pi_monitor/tests/mathlint_fixture/server.py` — no duplicate
  scenarios under new spelling.
- **S8.4.** The fake sanitizes its environment. The fake-process
  launcher MUST explicitly fail the test if known real-credential
  variables (e.g. `OPENAI_API_KEY`, `MATHLINT_MODEL_ROUTE` carrying
  a secret-prefix, `~/.pi/agent/auth.json` resolved to a path in
  scope) are present in the deterministic-tiers environment.
- **S8.5.** Transcript capture is separate from `pi_monitor.state.audit`
  (separate file, separate chain). Transcript excludes secrets by
  construction (no env-var interpolation in transcript lines).
- **S8.6.** Process-tree cleanup uses `start_new_session` + `killpg`
  on stop; the detached grandchild scenario verifies the cleanup
  reaches it.

**Linked durable anchors:** pi_monitor `@ADR-0006` (long-running
command protection); pi_monitor `@ADR-0007` (deterministic context
controller shadow mode — fake-Pi is the deterministic context
controller); pi_monitor `@ADR-0009` (bounded recovery and soft
circuit).

---

## §9. One source of simulation truth per concept (no cross-repo fixture sprawl)

**Statement.** Scenarios live with their semantic owner:

| Concern | Owner repo / location |
|---|---|
| Sample / frontier / report semantics | math (`math/src/mathlint/self_test/sample_program/`) |
| Supervisor transport / process / RPC faults | pi_monitor (`pi_monitor/tests/support/fake_pi_rpc.py`, `pi_monitor/tests/mathlint_fixture/`) |
| Cross-repo scenario composition + expected final transcript | research-institution (`research-institution/tests/simulation/scenarios/`) |
| Canonical verification CLI | research-institution (`python -m research_institution verify-simulation`) |

**Sub-rules.**

- **S9.1.** A scenario file lives in **one** repo. Cross-repo references
  cite named capabilities from the owner fixture by string reference,
  not by full text duplication.
- **S9.2.** The verification CLI exposes one canonical command
  (`python -m research_institution verify-simulation`) per tier
  (`--tier fast|full|process|deployment|provider-canary|soak`)
  and one canonical implementation path
  (`research_institution.gates.verify_simulation`). No competing
  runner script.
- **S9.3.** `scripts/verify-institution.sh` invokes deterministic
  required tiers through `gates/aggregate.check_institution` (the
  existing `v-compose` stage). It does NOT shell out to a parallel
  suite runner.

**Linked durable anchors:** `@ADR-0006` (research-institution scope);
`@INV-0093` (institution green gate); `@CTR-0088` (catalog schema).

---

## §10. Prime-directive mechanical enforcement is cross-repo

**Statement.** The prime-directive —
`(\b[Pp][Ll][Aa][Nn]|\b[Ss][Pp][Ee][Cc])[-_ ]?[0-9]{2,}` — is enforced
institution-wide with symmetric CI gates and a shared runtime
extension.

**Sub-rules.**

- **S10.1.** `scripts/check-prime-directive.sh` lives canonically at
  `research-institution/scripts/check-prime-directive.sh` and is
  symlinked (or copied with byte-diff-equivalence assertion) into
  every sibling repo. Each repo exposes `make check-prime-directive`
  as the canonical gate target.
- **S10.2.** The pi extension
  `~/.pi/agent/extensions/prime-directive-guard.ts` exists in one
  copy and auto-loads for every workspace. Its sanctioned-glob list
  matches the canonical exemption registry at
  `research-institution/.specify/memory/transient-exemptions.toml`.
  Adding a new exemption requires editing that registry and bumping
  the registry's `version`, which extends the SANCTIONED_GLOBS list
  on the next extension load.
- **S10.3.** Every sanctioned transient form cited by any exception
  class is **deletion-coupled** to the removal of the artifact that
  required it. When the deletion occurs, the exemption row retires in
  the same commit, the registry's ratchet `version` bumps, and the
  pi extension reloads.
- **S10.4.** Reports of `BLOCKED` / `FAIL` / stale gate must cite the
  canonical durable anchor mapping (`@ADR-NNNN` / `@INV-NNNN` /
  `@CTR-NNNN` / `@CON-NNNN`). Agents MAY NOT cite transient IDs even
  in violation logs.
- **S10.5.** `make check-prime-directive-enforced` (a sibling to
  `make check-prime-directive`, introduced by spec `09-…`) verifies:
  every durable path passes the strengthened grep at current SHA;
  every PR merged to the protected branch carries at least one
  attestation in `.pi-prime-attestations/` for the relevant spec-id;
  no `.pi-prime-attestations/*.json` references a SHA absent from
  any local git reflog (stale-rejection rule). Failure is gate
  `FAIL`.

**Linked durable anchors:** `research-institution/AGENTS.md` prime
directive; `pi_monitor/AGENTS.md` INV-024 + §PRIME DIRECTIVE;
`math/AGENTS.md` §22 exceptions; `kaplansky/AGENTS.md` institution-wide
prevention layer; `@ADR-0095-prime-directive-mechanical-enforcement`
(NEW, ratified by spec `00-…`).

---

## §11. Audit-close-out is required for every spec

**Statement.** A spec is not "done" when its code merges. It is "done"
when its `META.md` exists, binds to gate evidence at current SHAs, and
explicitly unblocks (or holds) the next dependent spec.

**Sub-rules.**

- **S11.1.** Every spec dir (under
  `research-institution/.specify/specs/NN-slug/`) carries:
  `spec.md`, `plan.md`, `tasks.md`, `research.md`, `data-model.md`
  (or N/A rationale), `contracts/` (or N/A rationale), `quickstart.md`,
  optional `checklists/requirements.md`, and a final `META.md`.
- **S11.2.** `META.md` schema (machine-checked by
  `spec_audit_close.META_validator` from spec `09-…`):
  - `spec_id` (zero-padded numeric prefix + slug, must match dir name);
  - `owner_repo` (single) and `owner_repos` (set, when >1);
  - `baseline_sha` (input SHA at spec start);
  - `completion_sha` (HEAD on close);
  - `gate_report_digest` (sha256 of the most recent gate report);
  - `durable_anchors_added` (list of `@ADR-NNNN` / `@INV-NNNN` /
    `@CTR-NNNN` / `@CON-NNNN` introduced);
  - `durable_anchors_cited` (list);
  - `transient_anchors_retired` (list, with tombstone commit SHA);
  - `unblocked_dependents` (next-spec name OR `HOLD:` reason);
  - `constitution_compliance` (boolean + the §N sub-rules checked).
- **S11.3.** META emission is mechanized by
  `research_institution.prime_directive.attest(spec_id, …)` (added by
  spec `09-…`). Manual emission by hand is gate `FAIL`.
- **S11.4.** A spec whose META.md is absent is **not closed**, even
  if its code merged. The dependent spec cannot begin until the
  prior META is valid.
- **S11.5.** Spec numbering is **zero-padded `00-slug/`…`10-slug/`**.
  Lex sort = execution order. Renumbering is a MAJOR-version
  constitution amendment.
- **S11.6.** All spec dirs live under
  `research-institution/.specify/specs/`. Lifting a spec to a sibling
  repo is **forbidden**; the single mount point IS the program
  contract.

**Linked durable anchors:** `@INV-0093` (institution green gate is
canonical wiring evidence); `@INV-0094` (no-delta loop is source-side);
`@CTR-0094` (work-source provider dispatch envelope).

---

## §12. The institution-wide semantic-record ownership

**Statement.** The single durable-anchor registry lives at
`research-institution/docs/semantic/SEMANTIC_REGISTRY.md`. The
full record set as of the date this constitution is ratified is
encoded into a new durable record:
`@ADR-0095-prime-directive-mechanical-enforcement` and
`@INV-0095-prg-anchor-ownership` (introduced by spec `00-…`).

**Sub-rules.**

- **S12.1.** Each repo owns its own ID namespace. The same ID in two
  repos with the same kind IS permitted (e.g. two `@CTR-0095-live-…`
  contracts in different repos); disambiguation is by repo. The cross-
  repo registry disambiguates by listing each anchor's repo.
- **S12.2.** Two records in **different** repos with the **same ID and
  the same kind** IS a **real RC0 contradictory authority** — one
  must be renumbered to a free ID before cross-repo references are
  written. The cross-repo live-source-snapshot contract renumbering
  `@CTR-0095` → `@CTR-0100` is the canonical example.
- **S12.3.** Specific durable anchors this constitution depends on,
  at ratification:
  - math: `@ADR-0014` (program-agnostic imports), `@ADR-0091`
    (no program launchers), `@ADR-0088` (sample fixture is not a
    proof program), `@ADR-0089` (sample as canonical CI fixture),
    `@INV-0088` (sample requires no external state), `@CTR-0020`
    (three-repo wire contract), `@CTR-0085` (sample dispatch
    envelope shape);
  - pi_monitor: `@ADR-0001` (source owns domain, monitor owns
    execution); `@ADR-0005` (audit append-only hash-chained);
  - research-institution: `@ADR-0001` (pi OAuth, no OPENAI_API_KEY);
    `@ADR-0006` (scope); `@ADR-0007` (work-source provider slot);
    `@ADR-0011` (stagnation is a source decision); `@CTR-0088`
    (catalog schema); `@CTR-0094` (work-source dispatch envelope);
    `@CTR-0100` (live-source snapshot contract); `@INV-0093`
    (institution green gate is canonical wiring evidence);
    `@INV-0094` (no-delta loop is source-side).

---

## Governance

- **Amendments**: bumps to MAJOR when a §N section is removed,
  redefined, or replaced. Bumps to MINOR when a §N section is added.
  Bumps to PATCH for clarification. Every amendment cites the issue
  / PR / spec-id that motivated it.
- **Self-tests**: `tests/static/test_constitution_consistency.py` in
  research-institution checks that: this file parses; every linked
  durable anchor (`@ADR-NNNN`/etc.) referenced in §N sub-rules
  exists in the registry at the cited path; every numbered §N has
  Statement + Sub-Rules + Linked durable anchors.
- **Escalation**: ambiguity in §N sub-rules is a spec
  (`research_institution.specs.spec_id`) authoring action, not an
  in-PR clarification. Edit the spec to amend the constitution.

---

## End of constitution. The next file is `.specify/specs/00-verify-constitution-ratification/spec.md`.
