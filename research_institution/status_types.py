"""Typed Pydantic wire models for the supervisor status payloads.

The dispatcher's :func:`research_institution.status.read_status_headline`
reads two files written by the pi_monitor supervisor:

- ``health.json`` \u2014 the live supervisor health snapshot.
- ``latest.json`` \u2014 the most recent supervisor observation.

These are cross-process wire documents (pi_monitor writes them;
ri reads them). Until now they were declared as TypedDicts
(``HealthPayload``, ``LatestPayload``) which give a typed shape
but do not enforce it at runtime \u2014 a malformed field slips
through to the classifier, surfacing as a confusing
``KeyError``/``TypeError`` deep inside the dispatch logic.

This module defines Pydantic models that own the wire shape.
Pydantic's ``model_validate`` is the typed parse boundary; the
classifier sees typed attributes (no ``dict.get(...)`` dance,
no ``cast(\"HealthPayload | None\", ...)``).

``extra=\"allow\"`` on every model keeps forward-compat: a
future pi_monitor version may add a new field and ri's parser
still accepts the document.

Why Pydantic and not TypedDict:
- TypedDict doesn't validate types at runtime; a
  ``supervisor_pid = \"6339\"`` (string instead of int) would
  slip through.
- Pydantic's ``model_validate`` is the typed parse boundary.
- TypedDict hides the field access pattern (``health.get(\"x\")``)
  which is a runtime shape probe that pyright can't help with;
  Pydantic's attribute access lets pyright track the typed shape
  through the classifier.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _StatusWireMixin(BaseModel):
    """Base for cross-process supervisor status wire models.

    ``extra=\"allow\"`` keeps forward-compat (pi_monitor may add
    new fields in a future version; ri's parser must accept them).
    """

    model_config = ConfigDict(extra="allow")


class CircuitSnapshot(_StatusWireMixin):
    """Wire shape of the supervisor's circuit-breaker state.

    The circuit is a closed sub-record: ``open`` is the breaker
    status, ``trip_count`` is the cumulative trip counter,
    ``soft_until_unix`` is the soft-cool-off boundary (used by
    the classifier for ``CIRCUIT_OPEN`` detection). ``trip_count``
    is monotonically non-decreasing across the supervisor's
    lifetime; a future field is fine via ``extra=\"allow\"``.
    """

    open: bool = False
    trip_count: int = 0
    soft_until_unix: float = 0.0


class AuditSnapshot(_StatusWireMixin):
    """Wire shape of the supervisor's audit-chain state.

    Only the field the ri classifier cares about
    (``chain_breaks``) is declared. ``prev_hash`` /
    ``head_hash`` / ``length`` would also belong here if the
    classifier grew to inspect them.
    """

    chain_breaks: int = 0


class ExecutionStateSnapshot(_StatusWireMixin):
    """Wire shape of the supervisor's execution sub-record.

    Shared between ``health.json`` and ``latest.json``. The
    ``outcome`` field is the closed vocabulary ``attempt_terminated`` /
    ``completed`` / ``blocked`` / ``running``; the ri classifier
    branches on ``outcome == \"blocked\"``.
    """

    outcome: str = ""
    attempt_ordinal: int = 0
    outcome_unix: float = 0.0
    active_key: str = ""


class HealthPayload(_StatusWireMixin):
    """Wire shape of ``health.json`` as written by pi_monitor.

    All fields are optional because the supervisor emits
    incrementally; the classifier uses ``or <default>`` to
    handle the missing-field case. ``supervisor_pid`` may be
    ``None`` when the test fixture wants to skip the liveness
    probe without setting a real PID.
    """

    supervisor_pid: int | None = None
    audit: AuditSnapshot = Field(default_factory=AuditSnapshot)
    circuit: CircuitSnapshot = Field(default_factory=CircuitSnapshot)
    degraded: list[str] = []
    execution: ExecutionStateSnapshot = Field(
        default_factory=ExecutionStateSnapshot
    )


class LatestPayload(_StatusWireMixin):
    """Wire shape of ``latest.json`` as written by pi_monitor."""

    observed_unix: float = 0.0
    execution: ExecutionStateSnapshot = Field(
        default_factory=ExecutionStateSnapshot
    )


__all__ = [
    "AuditSnapshot",
    "CircuitSnapshot",
    "ExecutionStateSnapshot",
    "HealthPayload",
    "LatestPayload",
]
