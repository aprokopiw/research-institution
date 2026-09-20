"""Closed stringly-typed vocabularies for research-institution DTOs.

Following @ADR-0006 + the pattern established by
`mathlint.orchestration.vocabulary`, every string that crosses a
boundary lives here as a `StrEnum`. New values require adding a member
to the enum (single-place edit, exhaustively checked by type checkers
and runtime guards). No inline strings, no `Literal[...]` aliases.

Vocabularies:

* :class:`TaskKind` — the parsed value of `TASK KIND:` in `mathlint
  roadmap` output. The dispatcher uses this to decide whether the
  architecture-review gate is open.

* :class:`GateVerdictStatus` — the dispatcher's gate verdict enum
  (open / closed / unknown). Derived from `TaskKind` via the
  `from_task_kind` helper.

* :class:`ExitCode` — the dispatcher's documented exit codes for
  every verb. Matches the bash convention; stable for operators and
  CI scripts.

* :class:`DispatcherVerb` — the canonical verb names exposed by the
  dispatcher CLI. The `install-skills` skill template reads from this
  enum; renaming a verb updates the template automatically.

Why StrEnum: same JSON round-trip semantics as mathlint's vocab
module — equality against literal strings keeps working without
explicit `.value` access; pyright strict exhaustiveness checks
fire the same way as Literal[...] aliases.
"""

from __future__ import annotations

from enum import StrEnum


class TaskKind(StrEnum):
    """The parsed value of `TASK KIND:` in `mathlint roadmap` output.

    A subset of mathlint's actual task-kind vocabulary, filtered to
    the values the dispatcher's gate check needs to discriminate.
    Unknown values are mapped to :attr:`OTHER` (defensive default).

    The full enum lives in mathlint's roadmap emitter; this enum
    is the dispatcher's *consumer-side* view, pinned by contract
    tests so format changes surface immediately.
    """

    RESEARCH = "RESEARCH"
    ARCHITECTURE_REVIEW_REQUIRED = "ARCHITECTURE_REVIEW_REQUIRED"
    INFRASTRUCTURE_REPAIR = "INFRASTRUCTURE_REPAIR"
    OTHER = "OTHER"  # any unrecognized value


class GateVerdictStatus(StrEnum):
    """The dispatcher's gate verdict enum.

    `OPEN` — safe to launch.
    `CLOSED` — gate is closed; refuse to launch.
    `UNKNOWN` — the gate could not be determined (e.g. roadmap
    failed to parse, mathlint exited non-zero, no TASK KIND line).
    The dispatcher's policy: refuse on UNKNOWN.
    """

    OPEN = "open"
    CLOSED = "closed"
    UNKNOWN = "unknown"


class ExitCode(StrEnum):
    """Documented exit codes for every dispatcher verb.

    Numeric values match the operator's bash convention. Stable
    for operator scripts and CI tooling.

    Convention (per dispatcher-cli-reference.md):
    - 0  — success.
    - 1  — internal failure.
    - 2  — usage error.
    - 3  — catalog-local error.
    - 4  — credential error.
    - 5  — gate closed.
    - 127 — binary missing.
    """

    SUCCESS = "0"
    INTERNAL_FAILURE = "1"
    USAGE_ERROR = "2"
    CATALOG_ERROR = "3"
    CREDENTIAL_ERROR = "4"
    GATE_CLOSED = "5"
    ALREADY_RUNNING = "6"
    BINARY_MISSING = "127"


class DispatcherVerb(StrEnum):
    """The canonical verb names exposed by the dispatcher CLI.

    Adding a new verb requires adding a member here AND a Typer
    command. Renaming a verb is a breaking change for operator
    scripts and the per-program skill templates.
    """

    LIST = "list"
    DOCTOR = "doctor"
    START = "start"
    STOP = "stop"
    STATUS = "status"
    WATCH = "watch"
    INSTALL_SKILLS = "install-skills"


def gate_verdict_from_task_kind(task_kind: TaskKind) -> GateVerdictStatus:
    """Map a TaskKind to the dispatcher's GateVerdictStatus.

    Per @ADR-0006 + B.1.2, only `ARCHITECTURE_REVIEW_REQUIRED` closes
    the gate. Everything else (including `OTHER` and unrecognized
    values the parser maps to `OTHER`) is treated as gate-open.

    Rationale for the defensive default: a refusal caused by an
    unrecognized task kind would lock the operator out of every
    program until mathlint ships an enum extension. Better to launch
    with a known-bad verdict than to brick the dispatcher.
    """
    if task_kind == TaskKind.ARCHITECTURE_REVIEW_REQUIRED:
        return GateVerdictStatus.CLOSED
    return GateVerdictStatus.OPEN


__all__ = [
    "DispatcherVerb",
    "ExitCode",
    "GateVerdictStatus",
    "TaskKind",
    "gate_verdict_from_task_kind",
]
