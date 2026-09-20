---
id: CTR-0094
kind: contract
status: active
title: WorkSourceProvider dispatch envelope contract
introduced: 2026-09-20
related: [ADR-0007, INV-0091, CTR-0020]
parties: research_institution (provider), mathlint (consumer)
---

# CTR-0094: WorkSourceProvider dispatch envelope contract

## Boundary

`research_institution.providers.research_institution_provider.select_next_work_for_supervisor`
returns a `dict[str, object]` that mathlint consumes as the
dispatch envelope for the supervisor's next iteration.

## Producer

`research_institution.providers.research_institution_provider.register`
populates `ProgramProviders.work_source_provider` with
`select_next_work_for_supervisor`. The callable accepts one
positional argument:

* `repository: Path` — absolute path to the supervised program's
  local checkout (resolved by mathlint from the supervisor's
  `KAPLANSKY_REPOSITORY`-equivalent env var, populated by the
  dispatcher when launching the program).

## Required keys

The returned `dict[str, object]` MUST contain exactly these
keys, with these value shapes:

| Key | Type | Semantics |
|---|---|---|
| `kind` | `Literal["Dispatch", "Wait", "OperatorRequired", "Stop"]` | Action for the supervisor to take. `Wait` means "no work right now"; the supervisor parks until the next tick. `Stop` means "gracefully shut down the supervisor." |
| `reason` | `str` | One-line human-readable diagnostic. Surfaced in the supervisor's `latest.json` under `stall.reason`. |
| `source_revision` | `dict[str, object]` | MUST contain: `fingerprint: str` (40-hex-char git SHA of the revision being worked), `observed_unix: float` (wall-clock of the observation), `label: str` (human-readable label, e.g. the program name + roadmap tick). |
| `work` | `list[dict[str, object]]` | Zero or more work items. The supervisor processes items in order. Empty list is equivalent to `kind="Wait"`. |

## Per-work-item keys

When `work` is non-empty, each item MUST contain:

| Key | Type | Semantics |
|---|---|---|
| `source_identity` | `str` | Stable identifier for the source of this work (e.g. `"kaplansky-roadmap-tick-42"`). Used as the audit chain key. |
| `operation_id` | `str` | Globally unique within the source identity; UUIDv4 is acceptable. |
| `operation_kind` | `str` | Coarse operation class (e.g. `"prove-theorem"`, `"recompute-lemma"`, `"explore-counterexample"`). |
| `role` | `Literal["MATHEMATICAL_RESEARCH", ...]` | The class of work; the operator pins one role per program in the catalog. |
| `workspace` | `str` | Logical workspace name (e.g. `"kaplansky-workspace-1"`). The supervisor creates one if absent. |
| `payload` | `dict[str, object]` | Operation-specific payload. The program-side schema is out of scope here. |
| `execution_policy` | `dict[str, object]` | Empty dict when the program accepts mathlint defaults. Populated for programs with bespoke timeouts or backoff. |
| `session_policy` | `dict[str, object]` | Empty dict when the program accepts mathlint defaults. |
| `isolation` | `dict[str, object]` | Empty dict when the program accepts mathlint defaults. |
| `budget` | `dict[str, object]` | Empty dict when the program accepts mathlint defaults. |
| `execution_profile` | `str` | Empty string for the default profile; otherwise the profile name from the catalog. |
| `lease_until_unix` | `float \| None` | `None` for work that has no time-bound lease; otherwise the wall-clock unix timestamp after which the supervisor drops the lease. |

## Consumer

`mathlint.orchestration.real_source.configured_provider`
is the canonical consumer. It:

1. Calls `work_source_provider_slot()` to retrieve the
   registered `WorkSourceProvider`.
2. Calls the slot with `repository` set to the supervised
   program's local checkout.
3. Validates the returned dict against the schema above
   (presence of all required keys, correct literal types).
4. Emits the dispatch envelope to the supervisor's
   `latest.json` under the `work` key.

## Failure modes

The consumer MUST raise `WorkSourceProviderError` with a
`SOURCE_*` error code when:

* The provider returns a dict missing any required key
  (`SOURCE_BAD_ENVELOPE`).
* The provider raises during invocation
  (`SOURCE_PROVIDER_RAISED`).
* The `kind` value is not in the closed vocabulary above
  (`SOURCE_BAD_KIND`).

The consumer MUST raise `WorkSourceProviderError` with
`SOURCE_NO_PROVIDER` when no `WorkSourceProvider` is
registered. Per `@ADR-0007`, this state should never be
reached on a wired operator machine because
research-institution's plugin fills the slot.

## Cross-references

* `@ADR-0007` — research-institution owns the slot.
* `@INV-0091` — mathlint is program-agnostic; this contract
  is the kernel/OS boundary.
* `@CTR-0020` — the entry-point group through which the
  plugin is discovered.
