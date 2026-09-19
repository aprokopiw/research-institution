"""Architecture-review gate verdict (B.1.2).

The dispatcher refuses to launch a program while its
architecture-review gate is closed. mathlint emits a structured
roadmap output with a `TASK KIND: <value>` line; we parse that line
into a :class:`GateVerdict` and refuse when the verdict is
`GateVerdictStatus.CLOSED`.

This module is a pure domain type — it does NO subprocess I/O. The
subprocess wrapper lives in `research_institution.cli.check_gate`.
Tests can construct verdicts directly via :meth:`GateVerdict.from_text`
with golden roadmap snapshots (see `tests/test_gate_check.py`).

Why this lives in `contracts/` (not `cli.py`):

  - The dispatcher (`research_institution.dispatcher`) needs to
    read the gate verdict without depending on the Typer CLI module.
    Putting the type here lets the dispatcher import a contracts-
    level symbol, not a presentation-level one.
  - The skill template (`contracts.skill_template`) and the catalog
    loader are also consumers of this type's status values; they
    must not transitively pull in `typer` and CLI machinery.

Wire format pinned by `tests/test_contracts.py` +
`tests/test_gate_check.py`. Drift in mathlint's roadmap emitter
surfaces immediately as a test failure.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Import from the leaf vocabulary module (NOT the contracts package
# __init__) to avoid a circular import: this module is imported by
# the contracts __init__ during initial load, and a top-level
# `from research_institution.contracts import …` here would
# re-enter __init__ before it's fully initialized.
from research_institution.contracts.vocabulary import (
    GateVerdictStatus,
    TaskKind,
    gate_verdict_from_task_kind,
)

# Structured lines parsed from `mathlint roadmap` output.
# Pinned at this regex width so a mathlint emitter change surfaces
# as a contract-test failure, not a silent behavior change.
_TASK_KIND_RE = re.compile(r"^TASK KIND:\s*(\S+)\s*$", re.MULTILINE)
_REASON_LINE_RE = re.compile(r"^REASON:\s*(.+?)$", re.MULTILINE)

# Sentinel used when roadmap produced no TASK KIND line at all.
# Not a member of TaskKind so consumers can distinguish "explicit
# TaskKind.OTHER" from "no line emitted" — useful for diagnostics.
TASK_KIND_ABSENT = "(absent)"


@dataclass(frozen=True, slots=True)
class GateVerdict:
    """The result of one architecture-review gate check.

    `task_kind` is the parsed value of the `TASK KIND:` line in
    `mathlint roadmap` output, mapped to a `TaskKind` enum member
    (unknown values -> `TaskKind.OTHER`). The literal string
    `(absent)` is used when no TASK KIND line appears at all.

    `status` is the dispatcher-side verdict enum: `OPEN`, `CLOSED`,
    or `UNKNOWN`. The check `status == GateVerdictStatus.OPEN` is
    the canonical "safe to launch" predicate.

    `reason` is the parsed value of the `REASON:` line, if present.
    `raw_excerpt` is the last 400 chars of roadmap output for the
    operator's diagnostic when the gate is closed.
    """

    task_kind: str
    status: str  # GateVerdictStatus value; string for dataclass slot-compat
    reason: str = ""
    raw_excerpt: str = ""

    def __post_init__(self) -> None:
        # Runtime guard: status must be a GateVerdictStatus value.
        # Catches typos at construction time, not at the call site.
        valid = {s.value for s in GateVerdictStatus}
        if self.status not in valid:
            raise ValueError(
                f"GateVerdict.status must be one of {valid}; got {self.status!r}"
            )

    @property
    def gate_open(self) -> bool:
        """Backwards-compat predicate for the dispatcher CLI."""
        return self.status == GateVerdictStatus.OPEN

    @classmethod
    def from_text(cls, text: str) -> "GateVerdict":
        """Parse a `mathlint roadmap` output string into a verdict.

        Pure function (no subprocess, no I/O). Use this in tests with
        golden roadmap snapshots; use `check_gate` (in
        `research_institution.cli`) for the live subprocess wrapper.
        """
        kind_match = _TASK_KIND_RE.search(text)
        reason_match = _REASON_LINE_RE.search(text)
        if kind_match is None:
            return cls(
                task_kind=TASK_KIND_ABSENT,
                status=GateVerdictStatus.OPEN,
                raw_excerpt=text[-400:],
            )
        raw_kind = kind_match.group(1).strip()
        try:
            task_kind = TaskKind(raw_kind)
        except ValueError:
            task_kind = TaskKind.OTHER
        return cls(
            task_kind=task_kind.value,
            status=gate_verdict_from_task_kind(task_kind),
            reason=reason_match.group(1).strip() if reason_match else "",
            raw_excerpt=text[-400:],
        )


__all__ = [
    "GateVerdict",
    "TASK_KIND_ABSENT",
]
