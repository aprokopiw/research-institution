# Research-Institution Hardening Checklist

**Status:** active backlog. Update as work lands. Cite `@ADR-NNNN` / `@INV-NNNN` / `@CTR-NNNN` anchors; never cite transient plan docs.

**Created:** 2026-09-13 from the "187 attempts of `blocked/stalled` on the same op" postmortem.
**Re-scoped:** 2026-09-13 per `@ADR-0006` — research-institution owns no application code.
**Last update:** 2026-09-19 — dispatcher CLI landed; cross-repo requests drafted.

**Scope:** research-institution (this repo) is a thin dispatcher over mathlint + pi_monitor + the catalog. The checklist contains only work this repo owes. Cross-repo ADRs (mathlint, pi_monitor) are documented as **drafted requests** to sibling maintainers under `docs/semantic/adr/cross-repo-requests/`; no source changes from this repo.

**Severity legend:**

- 🔴 **P0** — the original bug, or a direct enabler of it.
- 🟠 **P1** — observed during the run, will recur on the next run.
- 🟡 **P2** — defense-in-depth or operator UX.
- 🟢 **P3** — nice-to-have, observability polish.

**Status legend:**

- [ ] **TODO** — not started.
- [~] **WIP** — in progress (drafted ADR; awaiting sibling ratification).
- [x] **DONE** — landed + verified.
- [!] **BLOCKED** — needs cross-repo decision before it can land.

---

## A. Postmortem (read this first)

**The bug:** worker published `outcome=blocked` for
`work.kaplansky.extract-minimal-rigidity-overlap` 187 times. Supervisor
kept re-dispatching the same operation because the source's
`decide_next` returned the same `operation_id` from `mathlint next-step`
(the architecture-review gate is unresolved; the roadmap still points at
this op). No consecutive-same-outcome circuit exists in pi_monitor.
No operator-visible signal fired.

**Root cause (chain):**

1. Worker's `publication.summary`: "Configured WorkSource reports
   completed target with no unique approved `on_failure` edge;
   proof-architecture-review and explicit program decision required.
   Existing counterexample and commit `7de9255` preserved; no work
   repeated."
2. `decide_next` (`mathlint/orchestration/real_source.py:114`) parses
   `ACTION:` from `mathlint next-step` output and returns `Dispatch`
   without checking whether the same op was just dispatched.
3. Supervisor (`pi_monitor/supervisor.py:1394`) treats re-dispatch of
   the same key as `reactivate` (`@ADR-0014`) — a deliberate design
   choice for legitimate re-asks. No defense against repeated
   `blocked`.
4. Result: 187 attempts in ~7 min, all `blocked/stalled`. The operator
   had no signal because research-institution's observability surface
   was empty (this repo owned nothing).

**What's actually correct:**

- Worker did its job — wrote the counterexample
  (`mathematics/counterexamples/...md`), wrote the result envelope
  (`build/results/...yaml`), published `outcome: counterexample`.
- Roadmap correctly says `TASK KIND: ARCHITECTURE_REVIEW_REQUIRED`.
- The system is *waiting for an operator decision* — the loop is the
  supervisor's, not the worker's.

**Three real fixes** (none of them are this repo's source change; they
are cross-repo requests):

1. **Operator-visible signal** — ✅ DONE in this repo as B.1.2
   (`research start <program>` reads `mathlint roadmap` and refuses
   on `ARCHITECTURE_REVIEW_REQUIRED`). The robust programmatic
   verdict is the cross-repo ask @ADR-0007.
2. **Source-side repeat limit** — drafted as
   `docs/semantic/adr/cross-repo-requests/adr-0008-mathlint-source-side-repeat-limit.md`
   (cross-repo).
3. **Supervisor-side repeat circuit** — drafted as
   `docs/semantic/adr/cross-repo-requests/adr-0009-pi-monitor-supervisor-side-repeat-circuit.md`
   (cross-repo).

---

## B. Research-institution items (this repo)

### B.1 P0 — dispatcher + circuit delegation

| ID | Title | Severity | Status | Anchor |
|---|---|---|---|---|
| **B.1.1** | `research_institution/` Python package with Typer CLI: `list`, `doctor`, `start`, `stop`, `status`, `watch`, `install-skills` | 🔴 | [x] DONE 2026-09-19 | `@ADR-0006` |
| **B.1.2** | `research start <program>` refuses on closed architecture-review gate (parses `mathlint roadmap` output for `TASK KIND: ARCHITECTURE_REVIEW_REQUIRED`); `--skip-gate` operator override | 🔴 | [x] DONE 2026-09-19 | `@ADR-0006`, `@ADR-0007` |
| **B.1.3** | `research doctor [--live]` delegates to `green-gate/check-institution.sh`; `--program <name>` scopes to one program via `--skip-program=<name>` | 🔴 | [x] DONE 2026-09-19 | `@ADR-0006` |
| **B.1.4** | `research watch <program>` delegates to `pi-monitor watch --config <catalog-derived-path>` | 🟠 | [x] DONE 2026-09-19 | `@ADR-0004` |
| **B.1.5** | `research install-skills` generates per-program skill markdown from the catalog; idempotent; symlinks into `$PI_AGENT_SKILLS_DIR` | 🟢 | [x] DONE 2026-09-19 | `@ADR-0002` |

**B.1.2 implementation notes:**

- Gate check is `research_institution/cli.py::check_gate(prog)`. Parses
  `mathlint roadmap` output (read-only; ~0.6s; safe with supervisor running).
- Detects `TASK KIND: ARCHITECTURE_REVIEW_REQUIRED` and refuses with
  exit code `5`. Other values (including absent / unrecognized) are
  treated as gate-open (defensive default).
- `--skip-gate` is the operator escape hatch; logged.
- The roadmap-parse path is a fallback once `@ADR-0007` ships
  (`mathlint architect-review --verdict --program <name>`).
- Contract tests: `tests/test_gate_check.py` (6 tests covering closed,
  open, absent, roadmap-failure, end-to-end refusal, end-to-end skip).

### B.2 P1 — bootstrap hardening

| ID | Title | Severity | Status | Anchor |
|---|---|---|---|---|
| **B.2.1** | `bootstrap-institution.sh`: tolerate missing `uv` (warn + skip dev-dep install) | 🟠 | [x] DONE 2026-09-19 | `@ADR-0006` |
| **B.2.2** | `bootstrap-institution.sh`: tolerate empty catalog (skip the iteration loop, succeed) | 🟠 | [x] DONE 2026-09-19 | `@ADR-0006` |
| **B.2.3** | `bootstrap-institution.sh`: install textual into the pi_monitor venv | 🟠 | [ ] TODO | `@ADR-0004` |
| **B.2.4** | `bootstrap-institution.sh`: add a final `git -C $program_local_path clean -fdX` step (transient-state purge) | 🟠 | [ ] TODO | postmortem |
| **B.2.5** | `tests/test_bootstrap_dry_run.py`: contract tests for the script (executable, tolerates empty catalog, prints success marker) | 🟠 | [x] DONE 2026-09-19 | `@ADR-0006` |

### B.3 P1 — green-gate hardening

| ID | Title | Severity | Status | Anchor |
|---|---|---|---|---|
| **B.3.1** | `green-gate/check-institution.sh`: when iterating over catalog programs, check `MATHLINT_INSTITUTION_DIR` is set (or default to the repo root) | 🟠 | [x] DONE (default ROOT already used) | `@ADR-0006` |
| **B.3.2** | `green-gate/check-institution.sh`: add `--program=<name>` flag (run gate for one catalog program); reuse existing `--skip-program=<name>` semantics | 🟡 | [x] DONE (delegated via `research doctor --program <name>`) | `@ADR-0006` |
| **B.3.3** | `tests/test_cold_start_hermetic.py`: contract tests for AGENTS.md §Cold-start (list, doctor --hermetic, doctor --live) | 🟠 | [x] DONE 2026-09-19 | `@ADR-0006` |

### B.4 P2 — config reference docs

| ID | Title | Severity | Status | Anchor |
|---|---|---|---|---|
| **B.4.1** | `docs/operations/pi-monitor-config-reference.md` — full table of `[section].key` in `local-pi-monitor.toml` with safe values + ADR anchor + one-line rationale | 🟡 | [ ] TODO | `@ADR-0003` |
| **B.4.2** | `docs/operations/research-institution-troubleshooting.md` — symptom → cause → fix; cross-links to B.1.x and B.3.x | 🟡 | [ ] TODO | postmortem |
| **B.4.3** | `docs/operations/pi-monitor-debug-logging.md` — `MATHLINT_SOURCE_LOG_LEVEL=DEBUG` recipe + how to read structured stderr events | 🟡 | [ ] TODO | none |
| **B.4.4** | `docs/operations/dispatcher-cli-reference.md` — full `research <verb>` reference | 🟡 | [x] DONE 2026-09-19 | `@ADR-0006` |
| **B.4.5** | `docs/operations/bootstrap-and-cold-start.md` — fresh-checkout walkthrough | 🟡 | [x] DONE 2026-09-19 | `@ADR-0006` |
| **B.4.6** | `docs/operations/architecture-review-gate.md` — gate semantics + how to apply | 🟡 | [x] DONE 2026-09-19 | `@ADR-0006`, `@ADR-0007` |

### B.5 P2 — observability polish (this repo only)

| ID | Title | Severity | Status | Anchor |
|---|---|---|---|---|
| **B.5.1** | `research status <program>` returns a one-line "headline" (running / stopped / gate-closed / circuit-tripped) when called without `--verbose`; with `--verbose` it delegates to `mathlint research-status` | 🟡 | [ ] TODO | `@ADR-0006` |

### B.6 P3 — script cleanup

| ID | Title | Severity | Status | Anchor |
|---|---|---|---|---|
| **B.6.1** | `scripts/{launch,stop,watch,rollback,update}-program.sh` + `install-kaplansky-skills.sh` + `monitor-kaplansky.sh`: all deleted (subsumed by `research <verb>`) | 🟢 | [x] DONE 2026-09-19 | `@ADR-0006` |
| **B.6.2** | `skills/kaplansky/` directory + 4 skill files: deleted (now generated by `research install-skills`) | 🟢 | [x] DONE 2026-09-19 | `@ADR-0002`, `@ADR-0006` |
| **B.6.3** | `tests/test_{launch,stop,watch,rollback}_program_dry_run.py`: deleted (subsumed by `tests/test_cli.py`) | 🟢 | [x] DONE 2026-09-19 | `@ADR-0006` |

---

## C. Cross-repo requests (drafted ADRs; no source changes from this repo)

These are **drafted requests** to mathlint and pi_monitor maintainers,
recorded under `docs/semantic/adr/cross-repo-requests/`. Each draft
contains the full rationale + proposed semantics + acceptance criteria.
Implementation lands in the target repo when its maintainers ratify.

### C.1 mathlint — `@ADR-0007`: programmatic gate verdict

**Title:** `mathlint architect-review` must accept `--program <name>` and expose a machine-readable verdict (`--verdict` or `--json`).

**Severity:** 🔴 P0 (cross-repo).

**Draft:** `docs/semantic/adr/cross-repo-requests/adr-0007-mathlint-architect-review-program-flag.md`.

**Status:** [~] WIP (drafted 2026-09-19; awaiting ratification in math-engine).

**This repo's fallback:** the dispatcher reads `mathlint roadmap`
output (`TASK KIND:` line) and parses it. Falls back gracefully until
mathlint ships the verdict command. Tests in `tests/test_gate_check.py`
pin the fallback behavior.

### C.2 mathlint — `@ADR-0008`: source-side repeat limit

**Title:** `decide_next` must count consecutive `blocked` outcomes per
`(source_identity, operation_id, work_key)` and refuse to return the
same op after N (`MATHLINT_DECIDE_NEXT_REPEAT_LIMIT`, default 3).

**Severity:** 🔴 P0 (cross-repo).

**Draft:** `docs/semantic/adr/cross-repo-requests/adr-0008-mathlint-source-side-repeat-limit.md`.

**Status:** [~] WIP (drafted 2026-09-19; awaiting ratification in math-engine).

### C.3 pi_monitor — `@ADR-0009`: supervisor-side repeat circuit

**Title:** Supervisor must refuse re-dispatch when N consecutive
attempts on the same `(operation_id, outcome, status)` triple have
all returned the same non-success result.

**Severity:** 🔴 P0 (cross-repo).

**Draft:** `docs/semantic/adr/cross-repo-requests/adr-0009-pi-monitor-supervisor-side-repeat-circuit.md`.

**Status:** [~] WIP (drafted 2026-09-19; awaiting ratification in pi_monitor).

### C.4 pi_monitor — `@ADR-0010`: bounded re-ask during stuck loops

**Title:** When `decide_next` returns the same op as the last N
dispatches with non-success outcome, force `next_ask_unix` to
`now + 600s` (default) instead of immediate re-ask.

**Severity:** 🟡 P2 (cross-repo).

**Status:** [ ] TODO (no draft yet).

### C.5 pi — `@ADR-0011`: reasoning text in TUI

**Title:** pi's TUI should expose the worker's chain-of-thought
reasoning as a new panel or via `--show-reasoning` flag, sourced from
the session JSONL pi already writes.

**Severity:** 🟡 P2 (cross-repo).

**Status:** [ ] TODO (no draft yet; supersedes the original
`@ADR-0005` whose repo placement was wrong).

### C.6 math-engine — `@ADR-0012`: outcome standardization + required_action

**Title:** `outcome=blocked` envelopes must carry a `required_action`
field with one of `["operator_decision", "architecture_review",
"external_input", "wait_for_change"]`.

**Severity:** 🟡 P2 (cross-repo).

**Status:** [ ] TODO (no draft yet).

### C.7 pi_monitor — `@ADR-0013`: structured debug log surface

**Title:** Add a `--debug-source` flag to `pi-monitor run` that mirrors
`MATHLINT_SOURCE_LOG_LEVEL=DEBUG` events from stderr into the
supervisor's audit chain.

**Severity:** 🟢 P3 (cross-repo).

**Status:** [ ] TODO (no draft yet).

---

## D. Verification plan (run after every P0/P1 lands)

After the dispatcher CLI ships, the smoke-test chain is:

```sh
# 1. List catalog
python -m research_institution list
# EXPECTED: prints kaplansky entry from catalog/programs.toml

# 2. Doctor (hermetic)
python -m research_institution doctor
# EXPECTED: GREEN INSTITUTION READY (delegated from green-gate --hermetic)

# 3. Doctor (live)
MATHLINT_MODEL_ROUTE=openai-codex/gpt-5.6-luna python -m research_institution doctor --live
# EXPECTED: GREEN INSTITUTION READY (delegated from green-gate --live)

# 4. Start (refused because gate is closed today)
python -m research_institution start kaplansky
# EXPECTED: GATE NOT OPEN; reason surfaces the architecture-review decision needed

# 5. Start (dry-run, allowed even with closed gate)
python -m research_institution start kaplansky --dry-run
# EXPECTED: shows what would launch; exits 0

# 6. Start (skip-gate override; logged)
python -m research_institution start kaplansky --skip-gate
# EXPECTED: proceeds past gate check; delegates to mathlint live-run

# 7. Status / Stop
python -m research_institution status kaplansky
python -m research_institution stop kaplansky

# 8. Watch (TTY required)
python -m research_institution watch kaplansky

# 9. Install skills
python -m research_institution install-skills
# EXPECTED: ~/.pi/agent/skills/kaplansky -> <repo>/skills/kaplansky.md

# 10. Test suite (39 tests; 6.0s on this machine)
.venv/bin/python -m pytest tests/

# 11. Prime-directive grep (no transient references)
grep -rnE 'plan-00[5-9]|plan-01[0-1]' catalog/ scripts/ green-gate/ \
    research_institution/ docs/ tests/ README.md AGENTS.md HARDENING-CHECKLIST.md pyproject.toml \
    | grep -v 'plan-010 VERIFY-EVERYTHING'
# EXPECTED: empty
```

For the green gate to pass after P0+P1 lands:

```sh
bash green-gate/check-institution.sh --hermetic
MATHLINT_MODEL_ROUTE=openai-codex/gpt-5.6-luna bash green-gate/check-institution.sh --live
# BOTH must print "GREEN INSTITUTION READY"
```

---

## E. Progress log

| Date | Item(s) closed | Notes |
|---|---|---|
| 2026-09-19 | B.1.1–B.1.5 (dispatcher CLI), B.2.1–B.2.2, B.2.5, B.3.x, B.4.4–B.4.6, B.5.x deferred, B.6.1–B.6.3 | Cross-repo request ADRs @ADR-0007 / @ADR-0008 / @ADR-0009 drafted. 39/39 tests passing. Green gate GREEN INSTITUTION READY. Bootstrap hardened (tolerates missing `uv`, empty catalog). Architecture-review gate refusal landed with roadmap-parse fallback. Prime-directive grep clean. |
| 2026-09-13 | cleanup | Deleted 5 shell scripts + 4 skill files + 2 superseded ADRs; rewrote HARDENING-CHECKLIST per `@ADR-0006` |

---

## F. Open questions for the operator

1. **Section C.1**: ship mathlint `architect-review --verdict --program <name>` first or land the source-side counter (`@ADR-0008`) first? Either closes the loop; the order determines which defense fires first.
2. **Section C.4–C.7**: any drafts to elevate to ADRs this week? Or defer to the next hardening pass?
3. **Section B.5.1**: should `research status` parse the headline itself, or should mathlint gain a `mathlint research-headline --program <name>` (cross-repo ask)?

---

## G. Cross-references

- `@ADR-0001` — kaplansky uses pi OAuth, not an OpenAI API key.
- `@ADR-0002` — operator UX is a thin skill wrapper (status: superseded by `@ADR-0006`).
- `@ADR-0003` — slow-iteration safeguards: token cap, attempt cap, shadow-mode by default.
- `@ADR-0004` — one-keystroke TUI launcher (`monitor-<program>.sh`, generic; today's only instance was `monitor-kaplansky.sh`, deleted in B.6.1).
- `@ADR-0005` — reasoning tail (SUPERSEDED by `@ADR-0006`; reasoning tail belongs in pi, not this repo).
- `@ADR-0006` — research-institution owns only catalog + bootstrap + green gate + dispatcher.
- `@ADR-0007` — cross-repo request: mathlint programmatic gate verdict (drafted).
- `@ADR-0008` — cross-repo request: mathlint source-side repeat limit (drafted).
- `@ADR-0009` — cross-repo request: pi_monitor supervisor-side repeat circuit (drafted).
- `@INV-0091` — mathlint does not ship program launchers.
- `@INV-0092` — pi_monitor does not name mathlint.
- `@INV-0093` — institution green gate is the canonical wiring evidence.
- `@TOOL003` — math-engine invariant: live preflight requires `shadow_mode = false`.
- `plan-010 VERIFY-EVERYTHING.md` — math-engine one-line answer (sanctioned by math-engine AGENTS.md).
