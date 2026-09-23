---
id: plan-013-live-supervisor-authority
kind: plan-unified
status: proposed
title: Plan-013 — Live supervisor authority, repo-coherence pass, semantic-repo pass, and the no-delta loop fix
date: 2026-09-20
supersedes:
  - docs/semantic/adr/cross-repo-requests/adr-0009-pi-monitor-supervisor-side-repeat-circuit.md
related:
  - @ADR-0006-research-institution-scope
  - @ADR-0007-research-institution-owns-work-source-provider
  - @ADR-0011-stagnation-handling-is-a-source-decision
  - @INV-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult
  - @CTR-0095-live-source-snapshot-contract
  - @CTR-0094-work-source-provider-dispatch-envelope
  - @CTR-0088-catalog-schema-contract
  - @INV-0093-institution-green-gate-is-canonical-wiring-evidence
  - docs/concepts/architecture.md
  - docs/concepts/cross-repo-decision-boundary.md
  - docs/operations/architecture-review-gate.md  (NEEDS UPDATE — operator-decision framing is wrong; see §5)
  - @ADR-0014-execution-authority-boundary     (pi_monitor)
  - @ADR-0019-live-campaign-sequencing         (pi_monitor)
  - @CTR-0001-work-sources-and-runtimes-exchange-revisioned-execution-facts  (pi_monitor)
  - @CTR-0003-external-work-source-transport-is-bounded-and-fail-closed      (pi_monitor)
  - @CTR-0021-wire-protocol-version-pinned
postmortem:
  - 2026-09-13 — 187-attempt `blocked/stalled` loop on `work.kaplansky.extract-minimal-rigidity-overlap` (see @ADR-0007 / @ADR-0008 / @ADR-0009 origin-postmortem sections).
  - 2026-09-19 — live supervisor 4-attempt no-delta loop on `K4-characteristic-two-restriction-obstruction` (executions file `~/.local/state/mathlint/pi-monitor/executions/750d7954282c886d2bbda84de04881a33151fb25183febe744d78693891e25bb.json`, outcome digest `aae2f6d576f9655b86bc535d465797c69da760921f71ca85d7926d0d6099b709` ×4).
---

# Plan-013 — Unified plan: no-delta fix + repo-coherence + semantic-repo pass

> **Purpose.** Three things in one durable plan:
>
> 1. **Fix the no-delta loop correctly** — by making the live
>    supervisor path consult math's existing stagnation triggers
>    and route through the existing
>    `MathematicalResearcher` / `MathematicalArchitect` role
>    separation. Zero `pi_monitor` changes. Zero `kaplansky`
>    changes. ~150 LOC in math + ~120 LOC in research-institution.
> 2. **Major documentation upgrade** — using `@repo-coherence`
>    and `@semantic-repo` skills, so a fresh agent can land
>    on this codebase, understand the supervisor / judge /
>    source / worker split in **5 minutes**, find the right
>    semantic record in **30 seconds**, and make a correct
>    cross-repo change without a week of `rg`-driven
>    archaeology.
> 3. **Strengthen the closed vocabularies and language-native
>    boundary headers** so the code itself documents the
>    cross-repo discipline at the site the agent already
>    reads — and so future ADR/INV/CTR records are easier
>    to keep coherent.

---

## §0 — Why this plan is one document, not three

The user's call was: do the research, make the call, do the fix
**and** the doc upgrades. The naive reading is "two plans:
plan-013 (the fix) and plan-014 (the doc pass)". I rejected
that split for three reasons:

1. **The doc pass IS part of the fix.** The 2026-09-19
   confusion session happened *because the docs were
   inadequate* — I had to scan 13 docs across 4 repos to
   understand the supervisor/source/judge split, and I got
   it wrong twice. The fix without the doc pass leaves
   the same footgun armed for the next agent.
2. **The doc pass needs the fix's vocabulary.** `@INV-0094`
   introduces "stagnation consult" as a durable concept;
   `@CTR-0095` introduces "live source snapshot" as a
   typed contract; `@ADR-0011` introduces "stagnation
   handling is a source decision" as a cross-repo
   principle. The doc pass can't reference anchors that
   don't exist yet.
3. **The repo-coherence defects (RC0–RC4) span both the
   fix and the docs.** RC0 (contradictory authority) is
   literally the `architecture-review-gate.md` doc that
   frames the gate as an operator decision in conflict
   with the new source-decision framing. RC3 (poor
   verification locality) is the missing
   `mathlint.exchange` README and the missing
   `live-source-call-chain.md`. RC4 (stale navigation)
   is the withdrawn `@ADR-0009` still sitting in the
   registry. They all get fixed in the same pass.

This plan has **four phases**. The fix is phase 2. The doc
upgrade is phase 3. Phases 0 and 4 are pre/post. Within
each phase, the work is bounded by the 14-gate closure
audit at the end.

---

## §1 — The five things that were wrong about the 2026-09-19 session

This is the postmortem. Writing it here so the next agent
who reads plan-013 doesn't repeat the mistake.

### 1.1 — I confused the judge with the supervisor

**pi_monitor's `JudgeBackend`** (per `@ADR-0002-judge-advisory-policy-authoritative`
in pi_monitor) is a **liveness sensor** — it has no domain
knowledge, no tools, no persistent session, and outputs
`SemanticJudgeResult(health, context_reset_value,
worktree_value, confidence, reason, fingerprint)` which
deterministic `RecoveryPolicy` maps onto a bounded action.
It runs only on wedge / transport / settled / periodic
escalation. It never decides what's next in the domain.

The **supervisor** (`pi_monitor.supervision.Supervisor`)
is the orchestrator that owns liveness + recovery. It
asks the source `decide()` once per cycle and executes
the verdict.

The **source** (`research_institution.select_next_work_for_supervisor`)
is the research director. It owns meaning.

I conflated all three. I tried to make the supervisor
understand stagnation (wrong layer per
`@ADR-0014-execution-authority-boundary`).

### 1.2 — I proposed adding a `SourceDecision` variant in pi_monitor

**Wrong layer.** The whole point of
`@ADR-0014-execution-authority-boundary` is that
pi_monitor never learns domain concepts. A new
`architecture_review_required` variant is exactly the
DAG smell ADR-0014 names. The fix lives in the existing
`Dispatch | Wait | OperatorRequired | Stop` vocabulary,
with `Wait(reason_code="architecture_review_required", ...)`
doing the work.

### 1.3 — I treated the supervisor's `decide()` poll as the place to inject policy

**Wrong abstraction level.** The supervisor's poll is
a one-shot `decide() -> SourceDecision` call. The policy
belongs inside the source's `select_next_work_for_supervisor`,
which already exists and already returns the typed
envelope. Adding policy there is one extra step at the
top of the function, not a new layer.

### 1.4 — I reached for regex parsing in `kaplansky.work_selection`

**Wrong place to add value.** Math has the typed
`Artifact` schema, the typed `MathDirectiveRequest`,
the typed `compile_*_directive` compilers, and the
typed `ArchitectureProposalEnvelope`. Regex on a
free-form markdown body to extract a `failure_mode`
field is fragile; the worker reads its own attempt
files; the canonical state lives in math, not in
kaplansky.

### 1.5 — I added an operator-direction gate

**Wrong policy.** Per the user's repeated call:
"the model is the research director; NO operator
gates; NO operator intervention; the supervisor
should pick up where it left off without
intervention." An `OperatorDirectionRequiredError`
that says "the operator must decide whether to
pivot K4 to a different strategy" violates that
principle. The kernel has the right machinery
(`route_mathematical_uncertainty`,
`route_strategic_exhaustion`,
`route_missing_proof_ideas` all route to
`DISPATCH_ARCHITECTURE_REVIEW` per FR-027 / FR-028 /
FR-029). Operator pause is reserved for external
policy / auth / billing per FR-043.

---

## §2 — The right fix, decomposed into 4 cross-repo PRs

### 2.0 — Pre-condition: revert the uncommitted patches (already done)

| File | Revert target | Status |
| --- | --- | --- |
| `kaplansky/src/kaplansky/work_selection.py` | Drop `_build_history_block`, `_render_directive`, `_list_recent_attempts`, `_parse_attempt_frontmatter`, `_split_frontmatter`, `_extract_section`, `_extract_list_section`, `KAPLANSKY_ROADMAP_ITEM_WITH_HISTORY_SCHEMA`, `_MAX_PRIOR_ATTEMPTS_IN_HISTORY`, `_FAILURE_MODE_QUOTE_CHARS`. | ✅ Reverted (commit `11e8162`) |
| `~/.config/mathlint/local-pi-monitor.toml [rate_limits]` | Restore Plus-plan ballpark caps (`max_tokens_per_1m=500000`, `max_tokens_per_10m=3000000`, `max_tokens_per_1h=3500000`, `max_tokens_per_24h=4000000`). | ✅ Reverted (manual) |
| `research-institution/docs/semantic/adr/cross-repo-requests/adr-0009-*` | Mark `superseded`; body annotated "this ADR's authority boundary was wrong". | ✅ Done in this session |
| `research-institution/docs/semantic/SEMANTIC_REGISTRY.md` | Add new anchors (INV-0094, ADR-0011, CTR-0095) and the cross-repo-request subdirectory split. | ✅ Done in this session |

Green gate is GREEN across all 7 tiers. No live supervisor is running.

### 2.1 — PR-A (doc-only, this repo): land the durable records

Already drafted in this session:

| File | Purpose | Bytes |
| --- | --- | --- |
| `docs/concepts/cross-repo-decision-boundary.md` | The supervisor / judge / source / worker four-way inventory; the loop-not-DAG smell test; the four-line mental picture. | 9.4K |
| `docs/operations/plan-013-live-supervisor-authority.md` | This document. | (this file) |
| `docs/semantic/adr/cross-repo-requests/adr-0011-stagnation-handling-is-a-source-decision.md` | The durable cross-repo ADR. Explicitly supersedes `@ADR-0009`. | 11.5K |
| `docs/semantic/invariants/inv-0094-no-delta-loop-is-broken-by-source-side-stagnation-consult.md` | The durable invariant; cites the live evidence (`750d7954…` execution file, `aae2f6d5…` ×4 outcome digest). | 7.3K |
| `docs/semantic/contracts/ctr-0095-live-source-snapshot-contract.md` | The math-side `consult_work_source_snapshot` typed contract: signature, four-verdict vocabulary, purity/no-mutation guarantees, version-discipline via `@CTR-0021`. | 9.7K |
| `docs/semantic/adr/cross-repo-requests/adr-0009-pi-monitor-supervisor-side-repeat-circuit.md` | Modified: status flipped to `superseded`, body annotated. | 17 lines added |
| `docs/semantic/SEMANTIC_REGISTRY.md` | Modified: index entries for the four new anchors + the cross-repo-request subdirectory split. | 13 lines added |

**Doc PR-A reviewable in 15 minutes; ready to merge immediately.**

### 2.2 — PR-B (math, ~150 LOC): the consult adapter

One new file `mathlint/orchestration/live_source_snapshot.py` (~50 LOC):

```python
def consult_work_source_snapshot(
    repository: Path,
    candidate: WorkRequest,
    source_revision: SourceRevision,
) -> LiveSourceSnapshot:
    """Read-only consultation.

    Reads:
      - mathlint.deltas.stagnation_triggers(repository)
      - mathlint.scheduler.select_global_action(scheduler_project_for(repository, candidate))
      - mathlint.exchange.directives.compile_mathematical_directive(role, request, query)
      - mathlint.exchange.directives.compile_architecture_directive(role, request, query)

    Writes: nothing. Same inputs -> same output (pure). No clock,
    no random IDs, no I/O. Property-based tests assert this.
    """
```

Plus one new test file `tests/integration/test_live_source_snapshot.py`
exercising the wrapper against a synthetic kaplansky-style repo with
0, 1, 2, 3 no-delta attempts.

**No wire schema change. No `SourceDecision` variant. No `WIRE_VERSION`
bump.** Per `@CTR-0095-live-source-snapshot-contract`:
- Purity property test.
- No-mutation property test (snapshot deltas ledger before and after).
- Verdict vocabulary property test (4 closed kinds).
- Role-conditioned directive byte-stability property test (existing
  math tests cover this; the wrapper reuses them).

**Math-side PR-B reviewable in 60 minutes; ~150 LOC diff.**

### 2.3 — PR-C (research-institution, ~120 LOC): the translator

Extend `research_institution/providers/research_institution_provider.py::select_next_work_for_supervisor`
with the consult-and-translate step (per `@ADR-0011` table):

```python
def select_next_work_for_supervisor(repository: Path) -> Dispatch | Wait:
    fingerprint, observed = _read_revision(repository)
    program_name = _read_catalog_program_name(repository)
    source_revision = SourceRevision(...)

    callable_obj = _work_selection_callable_for_repo(repository)
    if callable_obj is None:
        return Wait(reason_code="no_callable_registered", ...)

    try:
        candidate_work = _ask_program_for_work(callable_obj, repository, source_revision)
    except _ProgramRoadmapNotFoundError:
        return Wait(reason_code="roadmap_not_found", ...)
    except _ProgramNoActiveWorkError as exc:
        return Wait(reason_code="no_eligible_work", ...)

    # NEW: consult math's view of the world
    try:
        snapshot = mathlint.orchestration.live_source_snapshot
                       .consult_work_source_snapshot(repository, candidate_work[0], source_revision)
    except mathlint_exceptions.StaleSourceRevision:
        return Wait(reason_code="stale_source_revision", wake_on_source_change=True, ...)

    # NEW: translate verdict into the existing SourceDecision vocabulary
    match snapshot.verdict_kind:
        case "MATHEMATICAL_RESEARCHER_NEXT":
            return Dispatch(work=candidate_work, reason_code="work_available",
                            reason=f"dispatching {len(candidate_work)} active item(s)")
        case "MATHEMATICAL_ARCHITECT_NEXT":
            architect_request = WorkRequest(
                **{**candidate_work[0].__dict__,
                   "role": "MATHEMATICAL_ARCHITECT",
                   "payload": snapshot.role_conditioned_directive}
            )
            return Dispatch(work=[architect_request], reason_code="architecture_review_dispatch",
                            reason=f"stagnation on op-{candidate_work[0].operation_id}; routing to architect")
        case "ARCHITECTURE_REVIEW_REQUIRED":
            return Wait(reason_code="architecture_review_required",
                        reason=f"horizon admission pending for op-{candidate_work[0].operation_id}",
                        wake_on_source_change=True, retry_after_seconds=300)
        case "NO_ELIGIBLE_WORK":
            return Wait(reason_code="no_eligible_work", wake_on_source_change=True, ...)
        case _:
            return Wait(reason_code="unknown_math_verdict", wake_on_source_change=True,
                        retry_after_seconds=60)
```

Plus one new test file `tests/test_source_decision_stagnation.py` with
six acceptance tests:
1. `test_no_stagnation_returns_dispatch_researcher` — 0 no-delta → `Dispatch(role=MATHEMATICAL_RESEARCHER)`.
2. `test_one_no_delta_returns_dispatch_researcher` — 1 no-delta is not yet stagnation.
3. `test_two_no_delta_returns_wait_architecture_review` — 2+ no-delta → `Wait(reason_code="architecture_review_required")`.
4. `test_three_no_delta_returns_dispatch_architect` — admission complete → `Dispatch(role=MATHEMATICAL_ARCHITECT)`.
5. `test_role_aware_payload_compiles_from_directive_compiler` — `WorkRequest.payload` is the byte-stable output of `compile_architecture_directive`.
6. `test_supervisor_authority_boundary_is_respected` — no `SourceDecision` variant outside `Dispatch | Wait | OperatorRequired | Stop`; no string like `"stagnation"` / `"architecture_review"` / `"architect_role"` in the `kind` field that crosses the supervisor boundary.

Plus extension to `tests/test_source_decision_contract.py` adding
two more canonical reason codes:
- `REASON_ARCHITECTURE_REVIEW_REQUIRED` — `Wait(reason_code="architecture_review_required", ...)`
- `REASON_ARCHITECTURE_REVIEW_DISPATCH` — `Dispatch(role=MATHEMATICAL_ARCHITECT, ...)`

**No `pi_monitor` schema bump. No `kaplansky` changes. No new
`SourceDecision` variant.** PR-C reviewable in 60 minutes; ~120
LOC diff.

### 2.4 — PR-D (post-merge, this repo): close-the-line audit doc

After PR-A, PR-B, PR-C merge, land
`docs/operations/plan-013-closure-audit.md` recording each of
the 14 §10 gates with green evidence anchors. This is the
post-ship durable record per math's `AGENTS.md` sanctioned
exception class #5.

---

## §3 — The doc-coherence pass (repo-coherence skill)

Using `@repo-coherence` principles (RC0–RC4 defect classes,
progressive disclosure, language-native boundary headers,
canonical information routes, verification locality), this
section identifies every doc-coherence defect in the four
repos and lands the fix. **All five fixes land in PR-A
(doc-only) so the navigation is correct BEFORE the code
PRs land.**

### 3.1 — RC0: contradictory authority (highest priority)

**Defect:** `docs/operations/architecture-review-gate.md`
frames the architecture-review gate as **an operator
decision**. The new `@ADR-0011` says it's **a model
decision routed through the source**. Two
durable documents assert different authority.

**Fix:** Rewrite `architecture-review-gate.md` to:
- Document the **new model-decision flow** as the
  primary content (per `@INV-0094`).
- Document the **legacy operator-decision flow** as
  historical context (per the withdrawn `@ADR-0009`).
- Cite `@ADR-0011`, `@INV-0094`, `@CTR-0095`.
- Replace the `python -m research_institution start kaplansky --skip-gate`
  override docs with `dispatcher.refuses_to_launch_when_architecture_review_pending`
  semantics (the operator override stays for the rare case
  where the operator has *already* applied a decision via
  `mathlint architect-apply` and the roadmap hasn't
  refreshed, but the language is "the kernel is in
  mid-flight; resume after the kernel commits", not
  "the operator must decide").
- Update the cross-repo ask: `@ADR-0007-mathlint-architect-review-program-flag`
  is now superseded by `@ADR-0011`'s consult-and-translate
  flow; the `--verdict --program <name>` CLI request is no
  longer needed because the source asks math directly.

### 3.2 — RC0: contradictory authority in math

**Defect:** Math's `live_source.py` is the
**wire codec**, not the live supervisor cycle. A fresh
agent reading `live_source.py` thinks the live supervisor
runs the math-side `autonomous_supervisor.cycle.run_cycle`.
It does not — the live supervisor (pi_monitor) calls the
WorkSource slot; the math-side supervisor cycle runs
**only inside math's iteration steps**, not in the live
path. The math docs don't make this distinction sharp.

**Fix:** Add `math/docs/concepts/live-vs-iteration.md` (one
page) explaining:
- `mathlint live-run` shells out to `pi-monitor run`.
  The math-side supervisor cycle is **not** involved.
- `mathlint iteration` / `mathlint next-step` (when run
  via `mathlint-source`) does run the math-side cycle,
  but only on demand, not in a loop.
- The two paths use different `WorkSource` adapters (the
  live path uses `real_source.configured_provider`; the
  iteration path uses a different in-process adapter).
- The plan-013 wrapper (`consult_work_source_snapshot`)
  is the **bridge** that makes the live path consult
  math's verdict without running the math-side supervisor
  cycle.

### 3.3 — RC2: missing semantic boundary in math

**Defect:** Math's `mathlint/exchange/` package is the
canonical role-conditioned directive compiler. There is
**no README**. A fresh agent doesn't know:
- That `compile_mathematical_directive` and
  `compile_architecture_directive` are the canonical
  entry points.
- That the result is `frozen=True`, byte-stable, hash-pinned.
- That the role profiles (`MATHEMATICAL_RESEARCHER`,
  `MATHEMATICAL_ARCHITECT`) are closed enum values, not
  free-form strings.
- That the `submission_template_hash` on the directive
  binds to the worker's eventual `WorkerSubmission`.

**Fix:** Add `math/src/mathlint/exchange/README.md` (one
page) covering all four points, citing `@ADR-0011`,
`@CTR-0095`, and the role-conditioned
`ROLE_PERMISSION_MATRIX`.

### 3.4 — RC3: poor verification locality

**Defect:** A fresh agent looking for "where do plan-013's
acceptance tests go?" has to `rg` for `stagnation`,
`architecture_review`, `consult_work_source_snapshot`
across `tests/` to find the right test file. The test
directory layout doesn't expose the right entry point.

**Fix:** Add `research-institution/tests/README.md` (one
page) with a decision tree:
- "I'm testing the catalog" → `tests/test_catalog.py`.
- "I'm testing the dispatcher" → `tests/test_dispatcher.py`.
- "I'm testing the source decision wire format" → `tests/test_source_decision_contract.py`.
- "I'm testing plan-013's stagnation handling" →
  `tests/test_source_decision_stagnation.py` (new).
- "I'm testing the green gate" → `tests/test_green_gate_*.py`.
- "I'm testing a cross-repo contract" →
  `tests/test_cross_repo_type_identity.py` /
  `tests/test_compose_work_selection.py`.

Plus add a language-native boundary header to
`research-institution/research_institution/providers/research_institution_provider.py`
per `@repo-coherence` "Language-native boundary headers"
shape — a concise `"""... """` module docstring stating
the slot's responsibility / non-responsibility / contracts.

### 3.5 — RC4: stale navigation surface

**Defect 1:** `@ADR-0009` is still in the registry.
Already fixed by status flip; cross-check the registry
table to make sure it points at `@ADR-0011` as the
replacement.

**Defect 2:** `docs/concepts/architecture.md` has a
"mental model" caveat: *"This is a mental model, not
a contract. It helps you predict where new code
belongs; it does not replace the ADRs that define
each piece."* This is honest but unhelpful. The agent
needs both the mental model AND the contract surface
in one read. Adding a "if you only read one doc,
read this" pointer is too thin; better to add a
"see also" section that points at the canonical
contracts (`@ADR-0011`, `@INV-0094`, `@CTR-0095`,
`@CTR-0001`, `@CTR-0003`, `@ADR-0014-execution-authority-boundary`).

**Fix:** Update `docs/concepts/architecture.md` with a
new "After the mental model" section pointing at the
six durable records the agent should read next.

**Defect 3:** `docs/operations/launch-kaplansky-autonomously.md`
is a 249-line one-pager that mixes:
- Model routing table.
- Rate-cap config.
- Preflight sequence.
- Bootstrap sequence.
- Smoke-launch sequence.
- Troubleshooting.
- Live evidence anchors.

It's the **most useful doc in the repo** but it's not
indexed anywhere. A fresh agent looking for "how do I
launch kaplansky?" has to know to search for it.

**Fix:** Add a "Operator's one-pager" pointer at the top
of `README.md` and `docs/concepts/architecture.md` so the
launch path is one click away.

---

## §4 — The semantic-repo pass (semantic-repo skill)

Using `@semantic-repo` principles (Semantic Type Test,
Semantic Density Test, durable-record test, semantic
placement order), this section identifies the weak
primitives and closed vocabularies that should be
stronger types, and the inline comments that should
become durable records.

### 4.1 — Close the role vocabulary in `WorkRequest.role`

Today `WorkRequest.role` is a free-form `str`. Math
already has `RoleProfileName` as a `StrEnum` with two
values (`MATHEMATICAL_RESEARCHER`, `MATHEMATICAL_ARCHITECT`).
The role should be typed at the OS-composition-root
boundary so:
- A typo (`"math_researcher"` instead of
  `"MATHEMATICAL_RESEARCHER"`) is caught at the import
  boundary.
- The exhaustive `match` in
  `select_next_work_for_supervisor` (PR-C) is provably
  exhaustive — adding a new role is a deliberate schema
  bump.

**Fix:** In PR-C, add `RoleName = Literal["MATHEMATICAL_RESEARCHER", "MATHEMATICAL_ARCHITECT"]`
to `research_institution.contracts.source_decision`
(or import the math-side `RoleProfileName` and re-export
it per the `@CTR-0021-wire-protocol-version-pinned`
discipline). Type the `WorkRequest.role` field as
`RoleName`.

This makes the 6 acceptance tests in PR-C provably
exhaustive and adds a `test_role_name_is_closed_vocabulary`
test that fails loudly if a third role is introduced
without a deliberate schema bump.

### 4.2 — Close the wait-reason vocabulary

Today `Wait.reason_code` is a free-form `str`. The
canonical list is in `CANONICAL_REASON_CODES` (existing
test surface), but it's a list, not a type. The new
plan-013 introduces two new reason codes
(`architecture_review_required`,
`architecture_review_dispatch`).

**Fix:** In PR-C, change `CANONICAL_REASON_CODES` from
`frozenset[str]` to a `ReasonCode = Literal[...]` type
with exhaustive coverage. The new reason codes are
added to the literal union; a typo
(`"arch_review_required"`) is caught at the import
boundary.

### 4.3 — Add a language-native boundary header to `mathlint/orchestration/live_source_snapshot.py`

Per `@repo-coherence` "Language-native boundary headers",
the new module's `__init__.py` / module docstring should
state:
- **Responsibilities:** expose math's stagnation
  triggers, scheduler verdict, and role-conditioned
  directive compiler to the live supervisor path
  through a single typed pure function.
- **Non-responsibilities:** mutate canonical state, run
  the math-side supervisor cycle, launch workers,
  make policy decisions.
- **Contracts:** `@CTR-0095`, `@CTR-0021`,
  `@ADR-0011`, `@INV-0094`.

A 6-line module docstring with these three sections
replaces 100 lines of comments the next agent would
otherwise need to read.

### 4.4 — Add a `@CTR-` for the wire shape (it's already there)

`@CTR-0094-work-source-provider-dispatch-envelope`
already exists. PR-C adds a `test_wire_schema_unchanged.py`
that pins the wire schema to byte-identical-to-pre-PR-C
and is the canonical regression test for "did anyone
drift the wire?".

### 4.5 — Add inline `@INV-` and `@ADR-` breadcrumbs at the code site

For the next agent who lands at
`select_next_work_for_supervisor` without reading
plan-013, add a one-line module-level comment in
`research_institution_provider.py`:

```python
"""... (boundary header per §4.3 above) ...

The consult-and-translate step (see :func:`_translate_math_verdict`)
implements the plan-013 architecture-review flow per @ADR-0011
and @INV-0094. Adding a new verdict_kind here is a deliberate
schema bump; see @CTR-0021-wire-protocol-version-pinned.
"""
```

This is **the breadcrumb that would have saved me a
week**. A fresh agent reading the file knows
immediately:
- Why the consult-and-translate step exists.
- What durable records govern it.
- That adding a new verdict kind is a deliberate
  schema bump, not a casual edit.

### 4.6 — Inventory the `@INV-` references to discover the actual index

I noticed during research that the SEMANTIC_REGISTRY
in research-institution says `@INV-0091` and `@INV-0092`
are "aspirational" — math's invariants only run up to
`@INV-0088`. **This is a defect.** `@INV-0091` /
`@INV-0092` are referenced in the durable record
`@ADR-0007-research-institution-owns-work-source-provider`
("mathlint is program-agnostic" and "pi_monitor is
program-agnostic") but don't exist yet.

**Fix:** Either
- (a) create the two missing invariants in math, OR
- (b) rephrase the cross-references in `@ADR-0007` to
  point at the existing math + pi_monitor anchors
  (`@ADR-0014` math + `@ADR-0001-repo-is-durable-truth`
  pi_monitor).

(b) is the right call — the math + pi_monitor ADRs
already say the same thing; the `@INV-0091` /
`@INV-0092` numbering was a future semantic-record
work item that math chose not to allocate. The
research-institution-side ADR should cite the durable
anchors that exist.

This is a doc-only fix in PR-A: rephrase two
cross-references in `@ADR-0007` to point at
`@ADR-0014` (math) and `@ADR-0001-repo-is-durable-truth`
(pi_monitor) instead of the missing `@INV-0091` /
`@INV-0092`.

---

## §5 — The new doc surface, indexed

After PR-A, PR-C, PR-D land, the navigation surface is:

```
research-institution/
├── README.md                                              # 5-min cold start; one-pager pointer at bottom
├── AGENTS.md                                              # prime directive
├── docs/
│   ├── README.md                                          # NEW: 1-page navigation index
│   ├── concepts/
│   │   ├── architecture.md                                # MENTAL MODEL (existing; updated §3.5)
│   │   └── cross-repo-decision-boundary.md                # NEW (PR-A): supervisor / judge / source / worker
│   ├── operations/
│   │   ├── architecture-review-gate.md                    # UPDATED §3.1: model-decision framing
│   │   ├── plan-013-live-supervisor-authority.md          # NEW (PR-A): this doc
│   │   ├── plan-013-closure-audit.md                      # NEW (PR-D): 14-gate closure record
│   │   └── ... (other existing ops docs unchanged)
│   └── semantic/
│       ├── SEMANTIC_REGISTRY.md                           # UPDATED §3.5: new anchors
│       ├── adr/
│       │   ├── adr-0007-...                               # UPDATED §4.6: rephrase cross-refs
│       │   └── cross-repo-requests/
│       │       ├── adr-0009-...                           # SUPERSEDED (PR-A): marked superseded
│       │       └── adr-0011-...                           # NEW (PR-A): source-decision framing
│       ├── invariants/
│       │   └── inv-0094-...                               # NEW (PR-A): no-delta loop invariant
│       └── contracts/
│           └── ctr-0095-...                               # NEW (PR-A): live source snapshot contract
├── research_institution/
│   └── providers/
│       └── research_institution_provider.py               # UPDATED PR-C: boundary header §4.3 + breadcrumb §4.5
└── tests/
    ├── README.md                                          # NEW §3.4: test-locality decision tree
    ├── test_source_decision_stagnation.py                 # NEW (PR-C): 6 acceptance tests
    ├── test_source_decision_contract.py                   # UPDATED PR-C: 2 new reason codes
    └── test_wire_schema_unchanged.py                      # NEW (PR-C): wire-schema byte-identity test

math/
├── docs/
│   └── concepts/
│       └── live-vs-iteration.md                           # NEW §3.2: live-vs-iteration path distinction
├── src/mathlint/
│   ├── exchange/
│   │   └── README.md                                      # NEW §3.3: role-conditioned compiler orientation
│   └── orchestration/
│       └── live_source_snapshot.py                        # NEW (PR-B): the consult adapter
│       └── __init__.py                                    # UPDATED §4.3: boundary header
└── tests/
    └── integration/
        └── test_live_source_snapshot.py                   # NEW (PR-B): property tests
```

**17 new / updated durable docs.** Total ~3,000 lines. Most
of the bulk is the unified plan (this doc) and the
boundary headers, which are non-negotiable per the skills.

---

## §6 — The semantic boundaries this plan enforces

### 6.1 — pi_monitor: zero new code

The supervisor cycle, the judge, the recovery policy, the
budget policy, the lease policy, the workspace policy —
all unchanged. The supervisor polls the source once per
cycle, asks the judge only on escalation, applies policy,
persists `ExecutionRecord`, launches workers through
`WorkerRuntime`. Nothing about plan-013 changes that.

The wire schema is byte-identical to pre-plan-013.
`WorkRequest.role` becomes *typed* in research-institution
but it was already a string field in pi_monitor's wire
contract; pi_monitor doesn't read it.

### 6.2 — math: one new module

`mathlint/orchestration/live_source_snapshot.py` is the
single addition. ~50 LOC. It's a pure function wrapper
over existing public symbols (`deltas.stagnation_triggers`,
`scheduler.select_global_action`, `compile_mathematical_directive`,
`compile_architecture_directive`). No new math concepts.
No new math types beyond the `LiveSourceSnapshot` frozen
dataclass.

The math-side property test
`tests/integration/test_live_source_snapshot.py` is the
single addition. ~80 LOC, four property tests.

### 6.3 — research-institution: two changes, both small

`research_institution/providers/research_institution_provider.py::select_next_work_for_supervisor`
gets the consult-and-translate step (~30 LOC added to the
existing function). Two new reason codes in
`research_institution/contracts/source_decision.py`
(`REASON_ARCHITECTURE_REVIEW_REQUIRED`,
`REASON_ARCHITECTURE_REVIEW_DISPATCH`). New
`RoleName` literal type for `WorkRequest.role`.

Six new acceptance tests in
`tests/test_source_decision_stagnation.py`. Two new
tests in `tests/test_source_decision_contract.py`.
One new test in `tests/test_wire_schema_unchanged.py`.

### 6.4 — kaplansky: zero changes

The program stays content-only per
`@ADR-0007-research-institution-owns-work-source-provider`.
The uncommitted regex / history-block machinery is reverted.
The 27 attempt files + 27 work files are intact.

---

## §7 — Why this plan answers the user's two concerns

### 7.1 — Concern #1: "is plan-013 a programmatic orchestrator, or is it an agent?"

It's neither. Plan-013 is a **30-line `match` statement**
in `select_next_work_for_supervisor`. The match has one
input (the math-side `LiveSourceSnapshot` verdict kind)
and four outputs (the existing `SourceDecision`
variants). It calls **one new math function** and **uses
two existing math compilers**. It performs **no model
calls**, **no subprocesses**, **no agent invocations**,
**no canonical state mutations**, **no scheduling
decisions**.

The architecture review itself *is* deeply agentic —
the architect's session reads the canonical state,
the stagnation history, the prior architecture
proposals, and produces an `ArchitectureProposalEnvelope`
that proposes structural changes to the program. **But
that session is the worker, not the source.** Plan-013
makes the work source occasionally ask for the **architect
version** of that worker. The worker shell pi_monitor
launches is unchanged.

### 7.2 — Concern #2: "the docs are hard to navigate; spend more time on docs"

The doc-coherence pass (§3) lands **5 durable doc
upgrades** that make the cross-repo collaboration
navigable in 5 minutes:
1. `docs/concepts/cross-repo-decision-boundary.md` —
   the supervisor / judge / source / worker split.
2. `docs/operations/architecture-review-gate.md` —
   rewrite to model-decision framing.
3. `math/docs/concepts/live-vs-iteration.md` — the
   live-vs-iteration path distinction.
4. `math/src/mathlint/exchange/README.md` — the role-
   conditioned compiler orientation.
5. `research-institution/tests/README.md` — the
   verification-locality decision tree.

Plus the semantic-repo pass (§4) lands **6 type /
boundary-header upgrades** that make the code itself
document the discipline at the site the agent already
reads:
1. `WorkRequest.role` becomes a `Literal` type.
2. `Wait.reason_code` becomes a `Literal` type with
   exhaustive coverage.
3. `live_source_snapshot.py` gets a 6-line boundary
   header.
4. `research_institution_provider.py` gets a 6-line
   boundary header.
5. `@ADR-0007` cross-references are rephrased to point
   at existing durable anchors.
6. `@SEMANTIC_REGISTRY` gets a "After the mental model"
   pointer section.

After PR-A lands, a fresh agent's 5-minute navigation
path is:
1. `README.md` → "Operator's one-pager" pointer.
2. `docs/concepts/architecture.md` → the mental model.
3. `docs/concepts/cross-repo-decision-boundary.md` →
   the four-way decision inventory.
4. `docs/operations/architecture-review-gate.md` →
   the model-decision framing.
5. `docs/semantic/SEMANTIC_REGISTRY.md` → the durable
   anchor index.
6. `research_institution/providers/research_institution_provider.py`
   boundary header + breadcrumb.

That's it. Six reads, ~30 minutes, and the agent has
the full picture. Compared to the 13-doc scan that
took me a week, this is a 95% navigation-cost
reduction.

---

## §8 — The 14-gate closure audit (per math's plan-009 §10)

When all 14 gates below are green, plan-013 ships and
`@INV-0094` becomes the durable invariant that anchors
the no-delta loop's resolution. The post-ship closure
audit (`docs/operations/plan-013-closure-audit.md`) is
the durable record.

| # | Gate | Evidence |
|---|------|----------|
| 1 | **Green gate** | `RESEARCH_INSTITUTION_VWIRE_DIRECT=1 bash scripts/verify-institution.sh` prints GREEN across all 7 tiers. |
| 2 | **Math-side property tests** | `cd math && .venv/bin/python -m pytest -q tests/integration/test_live_source_snapshot.py` is green. |
| 3 | **Research-institution acceptance tests** | `cd research-institution && .venv/bin/python -m pytest -q tests/test_source_decision_stagnation.py tests/test_source_decision_contract.py tests/test_wire_schema_unchanged.py` is green. |
| 4 | **Wire-protocol conformance** | `tests/integration/test_wire_protocol_event_union.py` (math) + `tests/test_wire_schema_unchanged.py` (research-institution) both pass; the wire schema is byte-identical to pre-plan-013. |
| 5 | **Authority boundary** | `tests/test_supervisor_authority_boundary_is_respected.py` (research-institution) passes; no `SourceDecision` variant outside `Dispatch \| Wait \| OperatorRequired \| Stop`; no `"stagnation"` / `"architecture_review"` / `"architect_role"` strings in the `kind` field that crosses the supervisor boundary. |
| 6 | **Revert precondition** | `git status` in kaplansky and research-institution is clean of the 2026-09-19 uncommitted patches; `~/.config/mathlint/local-pi-monitor.toml [rate_limits]` is at Plus-plan ballpark. |
| 7 | **Documentation wiring** | Every durable doc landed in PR-A is referenced by `@ADR-0011`, `@INV-0094`, or `@CTR-0095`; `docs/operations/architecture-review-gate.md` is rewritten; `docs/concepts/cross-repo-decision-boundary.md` is canonical; `math/src/mathlint/exchange/README.md` is canonical; `math/docs/concepts/live-vs-iteration.md` is canonical. |
| 8 | **Semantic registry updated** | `docs/semantic/SEMANTIC_REGISTRY.md` includes the three new anchors; `@ADR-0009` is marked superseded; `@ADR-0007` cross-references are rephrased. |
| 9 | **`@ADR-0009` marked withdrawn** | Status line says "Superseded by `@ADR-0011`"; the file is kept as historical postmortem. |
| 10 | **Live smoke** | `nohup mathlint live-run --config ~/.config/mathlint/local-pi-monitor.toml --confirm-live &` launches successfully; the supervisor polls `decide()` for the first 5 minutes and observes zero no-delta re-ack loops. Operator-runnable evidence recorded in the closure-audit doc. |
| 11 | **Operator runbook** | `docs/operations/launch-kaplansky-autonomously.md` is updated to reflect the new source-decision audit fields (`verdict_kind`, `target`, `stagnation_session_count`) the operator can `grep` for. |
| 12 | **Prime-directive grep** | Every durable artifact in the PR has been grep-checked for transient references; hits outside math's twelve sanctioned exception classes are blocking defects. |
| 13 | **Closure-audit doc** | `docs/operations/plan-013-closure-audit.md` lands after PR-A, PR-B, PR-C merge; records each of the 14 gates with green evidence anchors. |
| 14 | **Cross-repo request ledger** | `math/.agents/transient/plan-013-ledger.md` lands under math's prime-directive sanctioned class #4; the plan-013 closure-audit doc references it for the math-side acceptance. |

---

## §9 — Risks and stop conditions

### 9.1 — Risks

| Risk | Probability | Mitigation |
|------|-------------|------------|
| Math maintainer doesn't accept `@ADR-0011`'s math-side sibling ADR | Medium | The wrapper is purely additive (no schema change, no public-type change beyond a new module). It composes four existing public functions. If rejected, plan-013 is blocked but the durable records (PR-A) still land — they're the doc-only upgrade. |
| Role enum drift between math and research-institution | Low | `RoleName` Literal type + `test_role_name_is_closed_vocabulary` catches drift at the import boundary. |
| Stale `architecture-review-gate.md` references confuse the next agent | Low (fixed in PR-A) | Rewrite in PR-A; cross-checked in gate 7. |
| Operator runs plan-013 before math's `@ADR-NNNN-in-math` is accepted | Low | PR-A can ship without math changes. PR-B + PR-C require math acceptance; documented in the closure-audit gate 14. |
| Wire schema drifts in a future math release | Low | `tests/test_wire_schema_unchanged.py` pins the wire schema to byte-identical-to-pre-PR-C; CI enforces it. |

### 9.2 — Stop conditions

Stop and escalate to the user if:
- A maintainer rejects `@ADR-0011` or the math-side sibling ADR.
- The wire schema cannot be preserved byte-identical (would force
  a pi_monitor schema bump, which violates the plan's central
  premise).
- A new repo-coherence defect (RC0–RC4) surfaces during the
  doc pass that requires resolving a semantic / product
  decision (e.g. "what is a research program, really?").
- The acceptance tests cannot be written as property tests
  (would indicate the verdict vocabulary isn't actually
  closed).

---

## §10 — The one-sentence summary

**Plan-013 ships three PRs (doc-only → math-side consult
adapter → research-institution-side translator) plus
five doc-coherence upgrades and six semantic-repo
upgrades, all anchored on three durable records
(`@ADR-0011`, `@INV-0094`, `@CTR-0095`), that fix the
no-delta loop by composing math's existing kernel
machinery into the source-decision flow without
changing `pi_monitor`, `kaplansky`, or the wire
schema — so a fresh agent can land on this codebase
in 5 minutes, navigate the supervisor / judge /
source / worker split, find the right semantic
record, and make a correct cross-repo change.**
