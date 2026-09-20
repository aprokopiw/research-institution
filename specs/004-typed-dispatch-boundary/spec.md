# Feature Specification: Typed Dispatch Boundary Across the Institution

**Feature Branch**: `[004-typed-dispatch-boundary]`
**Created**: 2026-09-20
**Status**: Draft
**Input**: User demand — "make the dispatch envelope 3x stricter than
Haskell would do it. Weak types are mortal enemy. Use spec-kit. You
are free to change all four repos (research-institution, math,
pi_monitor, kaplansky)."

> The institution now spans four repos. Every byte of state that
> crosses between them — between research-institution's OS layer
> and math's kernel, between math's kernel and pi_monitor's
> supervisor, between any of them and a research program
> (kaplansky) — must be statically checked. The dispatch envelope
> has been a recurring failure locus and is now a typed-boundary
> problem, not a runtime-validation problem.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Engineer Edits A Source And Pyright Catches A Wire Drift

An engineer adds a field to the supervisor's `Dispatch` envelope
in `pi_monitor/src/pi_monitor/work_source.py`. Pyright immediately
flags every call site that constructs `Dispatch(...)` without the
new field. Pyright also flags the OS provider's adapter that
constructs `Wait(...)` with the wrong shape. The engineer never
ships an invalid envelope. No runtime test is needed because the
compiler refused to build.

**Why this priority**: This is the *entire point* of the feature.
The original failure mode was a 02:00 `WireError("unexpected
field(s) ['work']")` after days of test hardening. Compiler-level
prevention is the only durable answer.

**Independent Test**: Add a sentinel field to a typed envelope in
pi_monitor. Run `pyright` against all four repos. Observe that
every call site is flagged. Remove the sentinel. Confirm the
build passes again.

**Acceptance Scenarios**:

1. **Given** the typed envelope package `dispatch_protocol` with
   `py.typed`, **When** the engineer mutates one dataclass field,
   **Then** pyright reports the new field's missing-call-site
   count equal to the number of `Dispatch(...)` constructions.
2. **Given** the strict pyright config in every repo's
   `pyproject.toml`, **When** the engineer constructs a
   `Dispatch(work=[])` instead of `Dispatch(work=[WorkRequest(...)])`,
   **Then** pyright reports a missing-type-argument error.
3. **Given** the typed envelope's `from_wire` / `to_wire`
   converters, **When** the engineer adds a field, **Then** the
   `_from_wire` constructor is forced by the type system to read
   it and `_to_wire` is forced to write it; any forgotten half
   is a pyright error.

### User Story 2 — Researcher Runs The Supervisor And Sees No Wire Errors

A researcher launches the kaplansky research program through
`research start kaplansky`. The supervisor spawns a math kernel
subprocess. The math kernel instantiates the OS provider. The OS
provider emits a typed `Wait(...)` envelope. The supervisor
serialises it through `to_wire()`. The supervisor deserialises
the next OS provider `Wait(...)` via `from_wire()`. Nothing is
hand-rolled. `health.json` shows `live:True ready:True source.kind:wait
degraded:[]`. **No `WireError`. No `unexpected field(s)`.**

**Why this priority**: This is the regression test for the bug
that triggered the feature. Anything less strict than a
discriminated union with frozen dataclasses reintroduces the bug.

**Independent Test**: A single end-to-end supervisor run with one
OS provider decision captured in `state_dir/health.json`. Assert
no `WireError` in the captured log. Assert envelope shape matches
the typed definition byte-for-byte.

**Acceptance Scenarios**:

1. **Given** the strict-typed envelope, **When** the supervisor
   observes the first `Dispatch` or `Wait` from the OS provider,
   **Then** the supervisor's wire log contains no `WireError`
   token.
2. **Given** the strict-typed envelope, **When** the supervisor
   serialises the envelope to disk, **Then** the JSON output's
   field set is a subset of the dataclass's declared fields
   (proved by test, not just convention).

### User Story 3 — Math Kernel Cannot Mistakenly Import pi_monitor At Runtime

A future contributor accidentally adds
`from pi_monitor.work_source import Wait` to a math module. Pyright
flags it as a `reportPrivateImport` (because math is not in
pi_monitor's [tool.mypy / pyright] allow-list) and the CI fails.

**Why this priority**: Direction-of-import rules (`@ADR-0014`,
`@ADR-0006`) are mechanical: if the runtime import graph can
silently grow, it will eventually route back the wrong way and
break the layering.

**Independent Test**: Add a fake `from pi_monitor ...` line to a
math module. Run pyright. Observe failure. Remove it. Build
passes.

**Acceptance Scenarios**:

1. **Given** the strict pyright config, **When** a math module
   imports `pi_monitor` at runtime, **Then** pyright reports
   `reportPrivateImport` and CI blocks the change.
2. **Given** the `dispatch_protocol` package, **When** math uses
   `TYPE_CHECKING` to import `dispatch_protocol.SourceDecision`,
   **Then** pyright resolves the symbol and the runtime import
   graph stays clean.

### User Story 4 — Program Slot Composition Is Frozen And Verified

A future contributor adds a new field to `ProgramProviders` in
math. Pyright flags every callsite in kaplansky's
`mathlint_plugin.register` and in research-institution's OS
provider. The OS provider's `dataclasses.replace(merged_state,
work_source_provider=...)` call is the only sanctioned place
where the kernel state mutates; every other mutation is a
pyright error.

**Why this priority**: `@ADR-0007` makes the OS-provider-
composition pattern the canonical wiring. Drift here re-opens
the bug we just fixed.

**Independent Test**: Add a sentinel field to `ProgramProviders`.
Pyright reports the missing call sites. Remove the sentinel.

**Acceptance Scenarios**:

1. **Given** `ProgramProviders` is `frozen=True, slots=True`,
   **When** a contributor adds a field, **Then** pyright reports
   every construction site.
2. **Given** the OS provider's `dataclasses.replace(...)`
   pattern, **When** the contributor re-uses it, **Then** the
   `replace(...)` is the only place that constructs the final
   merged state, and tests assert this.

## Functional Requirements

### The typed envelope package `dispatch_protocol`

- **FR-001** A new package `research_institution/dispatch_protocol`
  exists, with `__init__.py`, `envelope.py`, `py.typed`, and a
  `__init__.py` that re-exports the public types.
- **FR-002** The package contains zero runtime logic. All
  definitions are `TYPE_CHECKING`-gated re-exports from
  `pi_monitor.work_source` plus local `TypeAlias` declarations
  for any types that are not in pi_monitor.
- **FR-003** Every envelope class in `dispatch_protocol.envelope`
  is `@dataclass(frozen=True, slots=True)`. Constructors take
  only the required field set as declared in pi_monitor's
  source-of-truth definitions.
- **FR-004** The package contains `_to_wire(self) -> dict` and
  `from_wire(cls, raw: dict) -> Self` converters, both colocated
  with the type, both statically typed, both required by the
  constructor signatures.
- **FR-005** A round-trip test lives next to each envelope class
  and asserts `t == t.from_wire(t.to_wire())`.

### The math-side `WorkSourceProvider` protocol

- **FR-010** `mathlint/program_providers.py` defines
  `WorkSourceProvider` as a `Protocol` whose `__call__` returns
  `Dispatch | Wait | OperatorRequired | Stop` via the typed
  envelope package's `SourceDecision` union.
- **FR-011** All typed references to the envelope use
  `TYPE_CHECKING` so that math's runtime import graph stays clean
  (`@ADR-0014`).
- **FR-012** `ProgramProviders` is `@dataclass(frozen=True,
  slots=True)` with no `**kwargs`. Every field has an explicit
  type. New fields require an ADR.

### The pi-monitor side: keep the canonical types

- **FR-020** `pi_monitor/work_source.py` remains the
  authoritative runtime definition for `Dispatch`, `Wait`,
  `OperatorRequired`, `Stop`, `WorkRequest`, `SourceRevision`.
- **FR-021** These classes are `@dataclass(frozen=True,
  slots=True)` and pyright strict.
- **FR-022** The wire converters are exposed as
  `envelope_to_wire(envelope) -> dict` and
  `envelope_from_wire(raw: dict, kind: str) -> SourceDecision`.

### The research-institution OS provider

- **FR-030** `research_institution/providers/research_institution_provider.py`
  imports the envelope types via the typed package. Its
  `select_next_work_for_supervisor` returns a typed `Wait(...)`,
  not a dict.
- **FR-031** The provider does not have `dict[str, object]` in any
  return type, attribute annotation, or local binding.
- **FR-032** The provider's `register()` constructs
  `ProgramProviders(work_source_provider=...)` via
  `dataclasses.replace` against the post-composition merged state
  and returns the result.

### The kaplansky program plugin

- **FR-040** `kaplansky.mathlint_plugin.register` returns
  `ProgramProviders` with all eleven typed contribution slots
  populated by typed callables (no bare `Callable`).
- **FR-041** `register()` is fully type-annotated, including the
  optional kwargs, the contribution list, and the
  `ProgramProviders(...)` construction.

### The strict pyright configuration

- **FR-050** Each of `research-institution`, `math`, `pi_monitor`,
  and `kaplansky` ships a `pyrightconfig.json` (or `[tool.pyright]`
  in `pyproject.toml`) with `typeCheckingMode = "strict"` plus the
  eight extra report flags from Constitution Principle V.
- **FR-051** Each repo runs `pyright` on its source tree on every
  CI run. A non-zero exit blocks the PR.
- **FR-052** Each repo's `py.typed` marker is present.

### Escape-hatch ledger

- **FR-060** A central file
  `research-institution/.specify/memory/type-escapes.toml`
  tracks every `# type: ignore[...]` and `cast(...)` call site
  touching a typed boundary.
- **FR-061** No new entry is added without an ADR reference. CI
  fails if a `# type: ignore` exists outside this ledger.

## Success Criteria *(measurable)*

- **SC-001**: `pyright` against all four repos' source trees
  reports zero errors in steady state. Time to compute the
  result: under 60 seconds per repo.
- **SC-002**: a sentinel mutation to `Dispatch` in
  `pi_monitor/work_source.py` produces exactly N pyright errors
  where N equals the number of `Dispatch(...)` call sites in the
  other three repos. Removing the sentinel brings the error count
  back to zero.
- **SC-003**: a single end-to-end supervisor run (one spawn, one
  `health.json` written) contains zero `WireError` tokens in the
  supervisor log.
- **SC-004**: grepping the source tree for `dict[str, object]`,
  `object`, `: Any`, `cast(`, or `Optional[Any]` against the
  dispatch surface returns zero hits.
- **SC-005**: `ProgramProviders(...)` constructions outside the OS
  provider's `register()` produce a pyright warning (caller's
  responsibility to satisfy `frozen=True`).

## Key Entities

- **`dispatch_protocol` package**: typed-only re-export hub. Has a
  `py.typed` marker. Has zero runtime logic. Stays at the
  institution's source-of-truth level so other repos can import
  types via `TYPE_CHECKING`.
- **`SourceDecision`**: a `TypeAlias` for the discriminated union
  `Dispatch | Wait | OperatorRequired | Stop`. Lives in
  `dispatch_protocol.envelope`.
- **`WorkSourceProvider`**: a `Protocol` whose `__call__` returns
  `SourceDecision`. Lives in `mathlint/program_providers.py`.
- **`ProgramProviders`**: a `@dataclass(frozen=True, slots=True)`
  contribution-record class with eleven typed callable fields.
  Lives in `mathlint/program_providers.py`. Frozen.
- **`type-escapes.toml`**: a ledger that records every approved
  escape with an ADR reference.

## Edge Cases & Failure Handling

- A future contributor adds a field to the kernel's
  `ProgramProviders` without updating every program's
  `register()`. Pyright catches this immediately. The
  replacement mechanism in the OS provider is the single
  sanctioned place that knows how to merge partial
  `ProgramProviders` instances.
- A future contributor accidentally imports `pi_monitor` from
  math at runtime. Pyright flags
  `reportPrivateImport`. CI fails.
- A future contributor hand-rolls a JSON-shaped dict to pass
  through the dispatch boundary. Pyright flags the missing
  type-argument on the dict. CI fails.
- The supervisor's wire deserialiser encounters an envelope
  with an unknown `kind` field. It returns a typed
  `OperatorRequired(...)` envelope rather than raising
  silently. (Future: the typed envelope's `from_wire` is
  exhaustive over `Literal["dispatch", "wait", ...]`.)

## Out of Scope

- The math kernel's own `real_source._source_for` path (separate
  per `@ADR-0006` and the pre-existing `--repo` flag absence).
  Re-routing the math kernel's internal dispatch is a
  separate, math-internal workstream.
- The pre-existing live-mode test failures from
  `tests/test_cold_start_hermetic.py` (math-engine pyramid-
  inversion G1..G6). Out of institution scope.
- A GUI / web consumer of the typed envelope. The 003-operator-
  status-surface feature owns that.

## Assumptions

- Each repo can install `pyright` in its development
  environment. The bootstrap already installs `ruff`; the same
  pattern applies to `pyright`.
- The `dispatch_protocol` package will be a subpackage of
  `research_institution`. Because math's runtime-import graph
  cannot reach `research_institution` (per `@ADR-0006`), math
  sees `dispatch_protocol` via `TYPE_CHECKING` only.
- The current `WorkSourceProvider` Protocol does not carry any
  payload-shape data — it returns the envelope directly.

## Dependencies

- `@ADR-0006` (research-institution owns only the four boundary
  surfaces).
- `@ADR-0007` (OS-provider composition pattern).
- `@ADR-0014` (mathlint does not import program-named modules,
  and does not runtime-import siblings).
- Constitution v1.0.0 (this document).

## Open Questions

None. All decision-blocking ambiguities were resolved during
drafting: typed-only via `TYPE_CHECKING` (already proven safe
in math's existing `@ADR-0066` typed-boundary pattern); four-
repo pyright config is a small additive edit; the `dispatch_protocol`
package's exact location is institution-local, which is the
canonical OS location per `@ADR-0006`.
