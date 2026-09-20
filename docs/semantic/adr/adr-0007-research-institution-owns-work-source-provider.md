---
id: ADR-0007
kind: decision
status: accepted
title: Research-institution owns the WorkSourceProvider slot in mathlint
date: 2026-09-20
related:
  - ADR-0006
  - INV-0091
  - INV-0092
  - INV-0093
  - ADR-0014
  - CTR-0020
supersedes: []
---

# ADR-0007: Research-institution owns the WorkSourceProvider slot in mathlint

## Context

`@INV-0091` (mathlint is program-agnostic) and `@CTR-0020` (the
generic `mathlint.providers` entry point is the canonical discovery
surface for proof programs) together define an extension point:
mathlint's `ProgramProviders.work_source_provider` slot is a
`WorkSourceProvider` Protocol that any installed plugin can fill.
A registry helper (`discover_program_providers()` in
`mathlint.program_providers`) loads the sole installed
`mathlint.providers` entry point and calls its `register()`.

Until now kaplansky — a research *program* (i.e. the artifact the
institution produces by directing the kernel to investigate the
Kaplansky conjecture) — filled this slot. That assignment is a
category error:

- The kernel/OS mental model (operator-confirmed 2026-09-20):
  mathlint is the kernel; research-institution is the OS; kaplansky
  is the output of the OS directing the kernel to investigate
  Kaplansky's conjecture under pi_monitor supervision.
- `@ADR-0006` enumerates the OS's concerns: catalog, bootstrap,
  green-gate, dispatcher CLI, and the path-resolution
  (`resolve_model_route`, `pi_monitor_state_dir`,
  `pi_monitor_config_path`) that already gives the OS all the
  state needed to decide *which* work to dispatch.
- The OS already owns five of the six inputs needed for that
  decision:
  1. *What* programs exist (catalog).
  2. *Where* each program's roadmap lives
     (`program_providers.roadmap_path`, populated by each program's
     `register()`).
  3. *When* a dispatch is appropriate (gate check,
     `probe_default_supervisor`).
  4. *Which* model to use (`resolve_model_route`).
  5. *How* the supervisor writes its state
     (`pi_monitor_state_dir`, `pi_monitor_config_path`).
  6. *Why* any of the above — also owned by the OS, via the
     catalog's `display_name` and `repository`.

The missing piece — *which work item to dispatch next given
all of the above* — naturally belongs to the OS, not to any
single program. Putting it in a program means each program
duplicates the OS's work and they fight over the slot.

## Decision

**Research-institution registers a `mathlint.providers` entry
point named `research_institution` whose `register()` populates
`ProgramProviders.work_source_provider`.** Kaplansky no longer
fills this slot. Kaplansky continues to populate every other
slot it already populates (theorem view, audit reports,
obligation labels, etc.) — those are *content contributions*,
not *work-selection contributions*, and they belong with the
program.

The new plugin lives at
`research_institution/providers/research_institution_provider.py`.
Its `register()`:

1. Constructs a `WorkSourceProvider` callable named
   `select_next_work_for_supervisor` (see
   `@CTR-0094` for the contract on the returned dict shape).
2. Populates `ProgramProviders(work_source_provider=...)` via
   the existing `register_program_providers` from
   `mathlint.program_providers`.
3. Does NOT populate any other field of `ProgramProviders` —
   those remain owned by kaplansky's plugin or future programs.

## Rationale

- **OS ownership is locally sufficient.** The OS already owns
  every input the work-selection needs. Adding one function
  that reads those inputs and returns a dispatch envelope does
  not introduce any new cross-boundary import — it only uses
  state the OS already maintains.

- **Kaplansky becomes content-only.** Kaplansky's
  `mathlint_plugin.register()` continues to install theorem
  views, audit reports, and roadmap metadata. Those are *what
  the work produces*. Removing the `work_source_provider`
  attempt from kaplansky's plugin eliminates the category
  error entirely; kaplansky no longer tries to tell the OS
  what to do.

- **The slot becomes genuinely generic.** With kaplansky gone
  from the slot, any future program lands naturally: it just
  contributes its content (theorem view, audit reports), and
  research-institution's single OS-level
  `select_next_work_for_supervisor` reads the catalog to
  decide which program's roadmap to drive. Adding a 100th
  program is a one-line catalog edit.

- **Operator muscle memory preserved.** `research start
  <program>`, `research stop <program>`, `research status
  <program>` keep their existing semantics. The change is
  invisible to operators — it's an internal improvement to
  which entry point fills which slot.

- **Boundary checks enforced.** `@ADR-0006` continues to
  apply: the dispatcher CLI is the only application code the
  OS owns. The new
  `research_institution_provider.py` is application code, but
  it ships from the OS repo (research-institution) rather than
  from the kernel (mathlint), satisfying the boundary.

## Alternatives considered

- **5a-in-kaplansky** (original proposal): kaplansky fills the
  slot with its own `next_kaplansky_work` callable. Rejected:
  the callable must read supervisor state and the catalog —
  cross-repo imports that violate `@ADR-0014` ("mathlint does
  not import any program-named module"). Kaplansky would
  import mathlint's `program_providers` types and the OS's
  path-resolution functions. That is the OS reaching into
  the program repo.

- **5b-explicit-fail-closed**: mathlint raises
  `WorkSourceProviderError` with `code="SOURCE_NO_PROVIDER"`
  when the slot is unset. Rejected: this leaves the kernel
  unable to drive *any* program through the generic bridge.
  The operator's model (mathlint as kernel) requires the
  kernel to have a producer for every syscall — including
  the "decide next work" syscall. 5b is equivalent to leaving
  `select_next_work` unimplemented in a real kernel.

- **WorkSourceProvider in mathlint itself**: mathlint ships a
  default work-selection implementation. Rejected:
  `@INV-0091` forbids this. A kernel does not decide what
  work the OS should queue.

## Consequences

- A new file
  `research_institution/providers/research_institution_provider.py`
  (~100 lines) ships with research-institution. It exports a
  `select_next_work_for_supervisor(repository: Path) -> dict`
  function plus a `register()` that wires it into the
  `WorkSourceProvider` slot.

- Research-institution's `pyproject.toml` gains a
  `[project.entry-points."mathlint.providers"]` section with
  `research_institution = "research_institution.providers.research_institution_provider:register"`.

- Kaplansky's `mathlint_plugin.register()` is simplified: the
  documentation note that says "see ADR-0014" becomes a
  positive "this plugin does NOT install a work-source
  provider; that's research-institution's job."

- A new `@CTR-0094` (WorkSourceProvider dispatch envelope
  contract) is added to `docs/semantic/contracts/` to make
  the dispatch envelope shape explicit (the kernel/OS contract
  for what `select_next_work` returns).

- Tests for the new plugin ship in
  `tests/test_research_institution_provider.py`. They exercise:
  the entry-point registration, the dispatch envelope shape
  (against `@CTR-0094`), and the integration with
  `discover_program_providers` (no entry-point collision with
  kaplansky's plugin).

## Change triggers

Revisit if:

- A second program lands and the OS-level work-decision needs
  per-program branches (e.g. kaplansky uses roadmap files,
  but a new program uses a different schema). Add per-program
  adapter logic; keep the slot owner in research-institution.
- Mathlint ships its own work-decision implementation (i.e.
  the kernel adds a default `select_next_work` syscall). The
  OS-level plugin becomes an override rather than the default;
  update the ADR.
- The supervisor state directory is moved out of
  `pi_monitor_state_dir()` (e.g. into a per-program tree).
  The OS-level plugin must track this move; tests catch it.
