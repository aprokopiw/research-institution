# research-institution — typing constitution

> This constitution governs all code that crosses research-institution,
> math-engine, pi-monitor, or any research-program boundary. The
> principles here are non-negotiable. They supersede local style
> wherever the two disagree. Escapes (`# noqa`, `reportAny`, `cast`,
> `Any`, `object`, `dict[str, object]`) are tracked centrally and
> reviewed on every touch of a typed surface.

**Version**: 1.0.0
**Ratified**: 2026-09-20
**Last amended**: 2026-09-20

---

## Principle I — `Any`, `object`, and `dict[str, object]` are forbidden on the dispatch envelope

The dispatched envelope between any agent, kernel, supervisor, or
research-program is a **closed discriminated union of frozen
dataclasses** with a strictly-typed optional `payload` channel.
No runtime `dict`, `object`, `Any`, `cast`, `Optional[...]`-of-`Any`,
or hand-rolled JSON shape may stand in for the typed envelope.

- **Rule I.1**: every envelope class is `@dataclass(frozen=True,
  slots=True)` with required fields. No `field(default=...)` on a
  required slot. Defaults are declared only where the wire spec
  specifies them.
- **Rule I.2**: any field that is "opaque to core" is typed
  `Mapping[str, JsonValue]` or a closed `Literal` enum. `dict` is
  never used.
- **Rule I.3**: `pi.typed` and `pyright reportAny` must both pass
  with zero annotations on the dispatch surface. New `Any`-typed
  annotations require a per-line `# type: ignore[reportAny]`
  comment that this constitution tracks.
- **Rule I.4**: serialisation may convert typed envelopes to a
  dict only at the JSON wire boundary, behind a `_to_wire()` /
  `_from_wire()` pair of converters colocated with the type
  definitions and pin-bounded by a `cast`/`from_dict` audit.

**Rationale**: We have spent days hunting wire-shape mismatches
that the type system was supposed to catch. The mathlint↔pi_monitor
envelope is the failure locus. Discriminated unions with frozen
fields and strict pyright enforcement eliminate this class of bug
at compile time, not at 03:00 when the supervisor emits `blocked`.

## Principle II — `Callable`, `Callable | None`, and bare `object` are forbidden in cross-boundary slots

The `ProgramProviders` dataclass, `WorkSourceProvider` Protocol,
and every other cross-boundary slot is a closed union of typed
callables. Bare `Callable`, `Callable | None`, or `object` is not
acceptable.

- **Rule II.1**: every callable slot has an explicit signature:
  `Callable[[Argument], ReturnType]` or a `Protocol` subclass with
  method-level annotations.
- **Rule II.2**: optional slots are `Callable[...] | None`, never
  bare `Callable | None`.
- **Rule II.3**: the `ProgramProviders` dataclass is `frozen=True,
  slots=True` with no `**kwargs`. New fields require an ADR +
  ADR-anchored patch.

## Principle III — `TYPE_CHECKING` is the only legal runtime-free import boundary between siblings

Math-engine may not import pi-monitor at runtime (`@ADR-0014`).
The reverse would also be illegal. Type-sharing across this
boundary happens via:

- a typed-only stub package `dispatch_protocol` (in
  research-institution; ships a `py.typed` marker and zero
  runtime code), or
- a `typing.TYPE_CHECKING` guard around `import`.

Both clients emit code that pyright can resolve, but no runtime
import crosses the boundary. The runtime path is normalised
through one canonical converter pair.

## Principle IV — Every cross-boundary type is `py.typed`

Every repo in the institution ships a `py.typed` marker file.
Every public re-export is type-annotated. Pyright runs in
`typeCheckingMode: strict` against every repo's source tree on
every PR. Lint failures are blocking.

## Principle V — Strict-mode flags are not negotiable

Each repo's `pyproject.toml` enables (at minimum):

```toml
[tool.pyright]
typeCheckingMode = "strict"
reportAny = "error"
reportUnknownArgumentType = "error"
reportUnknownMemberType = "error"
reportUnknownVariableType = "error"
reportUnknownLambdaType = "error"
reportUnknownParameterType = "error"
reportMissingTypeArgument = "error"
reportMissingTypeStubs = "error"
reportImportCycles = "error"
reportPrivateImport = "error"
reportUntypedFunctionDecorator = "error"
reportUntypedClassDecorator = "error"
reportUntypedBaseClass = "error"
reportUntypedNamedTuple = "error"
reportMissingModuleSource = "error"
```

If a real bug surfaces that requires a one-line suppression, the
fix is an ADR plus a pragma comment, not a config edit. Config
edits are reviewed on every PR.

## Principle VI — Three-strikes before declaring a type impossible

A type that can be removed but not simplified is not yet solved.
Before declaring `Any` or `cast` necessary, the engineer must:

1. Try a tighter `TypeAlias` or `NewType`.
2. Try a `Protocol` to capture the structural shape.
3. Try a `Generic` parameter on the relevant abstraction.

Three failed attempts are required for any escape hatch approval.
The constitution tracks each approved escape in a single ledger
file (`.specify/memory/type-escapes.toml`).

## Principle VII — Every typed surface is round-trippable

Any typed envelope that crosses a wire must have, in the same
module:

1. an authoritative `from_wire(dict) -> T` constructor,
2. an authoritative `T.to_wire() -> dict` serialiser,
3. a `@staticmethod` test that round-trips through both with
   `assert t == t.from_wire(t.to_wire())`.

The converters and tests live next to the type definitions, not
in the caller.

## Principle VIII — Strictness review is a PR gate, not an honor system

Every PR that touches a typed boundary must:

1. run `pyright` against the touched files with no escape
   suppressions added,
2. pass `pytest -m contract` (any test marked `contract` for
   typed surfaces),
3. cite which constitution principles a change advances or
   weakens, in the PR body.

## Governance

- **Amendments**: bumps to MAJOR when a principle is removed,
  redefined, or replaced. Bumps to MINOR when a new principle is
  added. Bumps to PATCH for clarification. Every amendment cites
  the issue/PR that motivated it.
- **Audit**: every quarter, an automated review scans for
  `# type: ignore[reportAny]` comments and `cast(...)` call
  sites touching dispatch surfaces. Drift beyond an absolute
  count of zero is a blocking defect.
- **Escalation**: ambiguous-type design questions live in
  `/Users/erinprokopiw/Documents/andrei/research-institution/.specify/memory/type-escapes.toml`
  and require an ADR to be added.
