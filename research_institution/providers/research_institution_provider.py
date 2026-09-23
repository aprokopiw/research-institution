"""research-institution mathlint.providers plugin.

Per @ADR-0007, this module populates mathlint's
``ProgramProviders.work_source_provider`` slot from the OS
layer. The kernel (mathlint) calls ``discover_program_providers``
at import time, which loads the ``mathlint.providers`` entry
point registered in this repo's ``pyproject.toml`` and invokes
the ``register()`` function below.

Contract: ``@CTR-0094`` (work-source-provider dispatch envelope).

Composition with proof programs (per @ADR-0007):
The OS owns the *work-source slot* AND the *work-selection
call*. Each proof program owns its *content contributions*
(theorem view, audit reports, obligation labels, etc.).

The OS never hardcodes a program name in source. Program
discovery is by two kernel-blessed surfaces:

* ``mathlint.providers`` entry point (already present in
  math) — each program declares its ``register()`` there;
  the OS reads each entry-point string from the institution
  catalog and invokes it via :func:`importlib.import_module`.
* ``mathlint.program_work_selection`` entry point
  (``mathlint.program_providers.PROGRAM_WORK_SELECTION_GROUP``,
  added in @ADR-0007 follow-up) — each program declares its
  ``next_active_work`` callable there; the OS reads it via
  :func:`mathlint.program_providers.work_selection_callables`
  keyed by the entry-point ``name`` (which the OS does not
  hardcode either — it looks the name up from the catalog
  entry whose ``local_path`` matches the current repo).

Adding a second research program means adding it to the
catalog AND declaring both entry points in its ``pyproject.toml``;
no OS code edit is needed.

The legacy ``_DEFAULT_PROGRAM_ENTRY_POINTS = ("kaplansky.mathlint_plugin:register",)``
fallback has been removed (was @ADR-0007 violation): if the
catalog is unreadable, the OS emits a clear diagnostic and
operates without program content rather than silently
fabricating a kaplansky entry.
"""

from __future__ import annotations

import dataclasses
import importlib
import logging
import time
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from mathlint.program_providers import (
    ProgramProviders,
    WorkSourceProvider,
    register_program_providers,
)

# Single typed-envelope surface. The contracts module re-exports
# pi_monitor's dataclasses by identity (no mirror) so isinstance
# and dataclass equality hold across the institution boundary.
from research_institution.contracts.source_decision import (
    REASON_NO_ELIGIBLE_WORK,
    REASON_OPERATOR_REQUIRED,
    REASON_WAIT_REQUESTED,
    REASON_WORK_AVAILABLE,
    Dispatch,
    OperatorRequired,
    SourceRevision,
    Wait,
    WorkRequest,
)

if TYPE_CHECKING:
    pass

__all__ = [
    "register",
    "select_next_work_for_supervisor",
    "_compose_programs",
]

_LOG = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Program discovery: every call goes through the institution catalog +
# kernel-blessed entry-point groups. The OS never names a program in
# source. To add a second program, edit ``catalog/programs.toml`` and
# declare both entry points in the program's ``pyproject.toml``.
# ---------------------------------------------------------------------------


def _entry_points_from_catalog() -> tuple[tuple[str, str], ...] | None:
    """Return ``((catalog_name, entry_point), ...)`` from the catalog.

    Returns ``None`` when the catalog cannot be read (the normal
    state for math-only venvs and CI runners); the caller decides
    whether to fall back, warn, or raise. Never hardcodes a
    program name — the catalog is the OS's single source of truth
    for "what programs exist".
    """
    try:
        # Import lazily so import-time errors don't poison the
        # entry-point discovery path.
        from research_institution.catalog import load_catalog
        from research_institution.paths import catalog_path

        programs = load_catalog(catalog_path())
    except (OSError, ValueError, ImportError, RuntimeError):
        # RuntimeError covers "MATHLINT_INSTITUTION_DIR not set"
        # which is the expected state for hermetic tests and
        # math-only venvs.
        return None
    return tuple((p.name, p.entry_point) for p in programs)


def _work_selection_callable_for_repo(
    repository: Path,
) -> Callable[..., object] | None:
    """Resolve the program-supplied ``next_active_work`` callable for ``repository``.

    Resolution order:

    1. Identify the catalog program whose ``local_path`` matches
       the repository (or whose ``program_markers`` match; see
       :func:`_read_catalog_program_name`). The OS reads the
       catalog; it does not name the program.
    2. Ensure the per-program work-selection registry has been
       populated. ``mathlint.cli`` calls
       ``discover_work_selection_programs()`` at import time;
       the OS also calls it eagerly in :func:`register`. The
       defensive call here keeps the OS safe when neither path
       has fired (e.g. a test calls this function directly).
    3. Look up the entry-point-loaded callable under the program
       name in ``mathlint.program_providers.work_selection_callables()``.

    Returns ``None`` when no catalog match exists OR no entry
    point is registered for the program name. The OS treats
    both cases the same way: emit a Wait with the canonical
    "no roadmap" reason, never crash.

    The kernel never inspects the callable's return type; the
    OS interprets the program-typed work items per
    ``@CTR-0094``.
    """
    program_name = _read_catalog_program_name(repository)
    if not program_name:
        return None
    try:
        from mathlint.program_providers import (
            discover_work_selection_programs as _discover_ws,
        )
        from mathlint.program_providers import work_selection_callables
    except ImportError:
        return None
    _discover_ws()
    return work_selection_callables().get(program_name)


def _read_revision(repo: Path) -> tuple[str, float]:
    """Return (fingerprint, observed_unix) for the repo's current HEAD.

    Falls back to (zeros, now) when the repo isn't a git checkout —
    this preserves the contract's required-key shape even on a
    broken machine.
    """
    import subprocess as _sp

    try:
        completed = _sp.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo),
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        fingerprint = (
            completed.stdout.strip() if completed.returncode == 0 else "0" * 40
        )
    except (OSError, _sp.TimeoutExpired):
        fingerprint = "0" * 40
    return fingerprint, time.time()


def _read_catalog_program_name(repo: Path) -> str | None:
    """Best-effort: name the catalog program whose ``local_path`` matches ``repo``.

    Resolution is catalog-driven and runs in two passes (both
    catalog-sourced; the OS does NOT hardcode any program name
    in source):

    1. **Primary** — match by ``local_path``: the operator's
       declared on-disk location for the program.
    2. **Secondary** — match by ``program_markers``: when
       ``local_path`` does not match (tests, fresh checkouts,
       ops mirrors), the OS still resolves the program name as
       long as any catalog-declared marker exists under
       ``repo``. This is what makes the OS work with a test
       that synthesises a temp repo and writes the program's
       canonical roadmap there.

    Returns ``None`` when no catalog entry matches OR when the
    institution directory isn't configured (the normal state
    for a math-only venv or a CI runner).
    """
    try:
        # Import lazily so import-time errors don't poison the
        # entry-point discovery path.
        from research_institution.catalog import load_catalog
        from research_institution.paths import catalog_path

        programs = load_catalog(catalog_path())
    except (OSError, ValueError, ImportError, RuntimeError):
        return None
    repo_str = str(repo).rstrip("/")
    # Primary: local_path match.
    for program in programs:
        try:
            resolved = str(program.resolved_local_path).rstrip("/")
        except (OSError, RuntimeError):
            continue
        if resolved == repo_str:
            return program.name
    # Secondary: marker-file match (catalog-driven).
    for program in programs:
        markers = getattr(program, "program_markers", None) or []
        for marker in markers:
            if (repo / marker).is_file():
                return program.name
    return None


def select_next_work_for_supervisor(
    repository: Path,
) -> Dispatch | Wait | OperatorRequired:
    """The OS-level WorkSourceProvider.

    Contract: @CTR-0094. The OS owns the *transport* (typed
    ``Dispatch`` / ``Wait`` envelope, serialisation, retry/wake
    policy); the *decision* of what to work on next is owned by the
    proof program (resolved through the kernel-blessed
    ``mathlint.program_work_selection`` entry-point group, keyed
    by the catalog program name — never by hardcoded import).

    Composition:

      1. The OS reads the source revision (git HEAD fingerprint, or
         the roadmap's content fingerprint when not a git checkout).
      2. The OS identifies the catalog program whose ``local_path``
         matches the repo (so the OS does NOT name the program in
         source). It then looks up that program's work-selection
         callable via the entry-point registry.
      3. The OS calls that callable, asking the program "what should
         mathlint work on next?". The program owns the answer; the
         OS does NOT inspect the roadmap TOML itself.
      4. If the program returns one or more WorkRequests, the OS
         wraps them in a typed :class:`Dispatch` with the canonical
         ``reason_code="work_available"``.
      5. If the program has no active work
         (``NoActiveWorkError``), the OS emits a :class:`Wait` with
         ``wake_on_source_change=True`` so the supervisor re-decides
         as soon as the program moves an item to ``active``.
      6. If the program is not catalog-registered for this repo
         OR has no entry-point-registered work-selection callable,
         the OS emits a Wait with a clear diagnostic naming only
         the *catalog key* (not the program python module).

    The return type is the typed dispatch envelope's discriminated
    union (``Dispatch | Wait``); pyright enforces the required field
    set on each variant and forbids any hand-rolled dict construction
    at the dispatch boundary. Envelope serialisation is the
    supervisor's responsibility — see ``pi_monitor.protocol.source_wire``.

    Defect class (if regressed): a future refactor that returns a
    ``Dispatch`` with an empty ``work`` list would silently park
    the supervisor with no progress. ``next_active_work`` raises
    ``NoActiveWorkError`` (not empty list) when there is nothing
    to dispatch; the OS catches it and emits a Wait.
    """
    fingerprint, observed = _read_revision(repository)
    program_name = _read_catalog_program_name(repository)
    label = f"{program_name or 'unknown-program'}-tick-{int(observed)}"
    source_revision = SourceRevision(
        fingerprint=fingerprint,
        observed_unix=observed,
        label=label,
    )
    callable_obj = _work_selection_callable_for_repo(repository)
    if callable_obj is None:
        return Wait(
            source_revision=source_revision,
            decided_unix=observed,
            reason_code=REASON_WAIT_REQUESTED,
            reason=(
                f"no work-selection callable registered for catalog "
                f"program {program_name!r}; install the program package "
                f"and ensure it declares "
                f"mathlint.program_work_selection entry point"
            ),
            wake_on_source_change=True,
            retry_after_seconds=30.0,
        )
    try:
        work = _ask_program_for_work(callable_obj, repository, source_revision)
    except _ProgramRoadmapNotFoundError:
        return Wait(
            source_revision=source_revision,
            decided_unix=observed,
            reason_code=REASON_WAIT_REQUESTED,
            reason=(
                f"no roadmap found in {repository}; "
                "supervisor will re-decide on source change"
            ),
            wake_on_source_change=True,
            retry_after_seconds=30.0,
        )
    except _ProgramOperatorDirectionRequiredError as exc:
        # Per @INV-0094: every active item is gated on operator
        # input; the math agent is in the no-delta loop. Emit
        # ``operator_required`` so the supervisor pauses and the
        # operator sees the parked questions inline. This
        # replaces the "Wait with no_eligible_work, re-ask in
        # 60s" pattern that drives the 187-attempt bug
        # (ADR-0009 is the durable supervisor-side fix; this is
        # the program-side interlock that closes the loop on
        # the math side until ADR-0009 ships).
        return OperatorRequired(
            source_revision=source_revision,
            decided_unix=observed,
            reason_code=REASON_OPERATOR_REQUIRED,
            reason=str(exc),
        )
    except _ProgramNoActiveWorkError as exc:
        return Wait(
            source_revision=source_revision,
            decided_unix=observed,
            reason_code=REASON_NO_ELIGIBLE_WORK,
            reason=str(exc),
            wake_on_source_change=True,
            retry_after_seconds=60.0,
        )
    if not work:
        # Defensive: a registered program returned an empty list
        # rather than raising NoActiveWorkError. Treat as "wait".
        return Wait(
            source_revision=source_revision,
            decided_unix=observed,
            reason_code=REASON_NO_ELIGIBLE_WORK,
            reason=(
                "proof program returned an empty work list; "
                "treating as 'no active item' so the supervisor re-decides"
            ),
            wake_on_source_change=True,
            retry_after_seconds=60.0,
        )
    label_summary = ", ".join(req.operation_id for req in work)
    return Dispatch(
        source_revision=source_revision,
        decided_unix=observed,
        work=work,
        reason_code=REASON_WORK_AVAILABLE,
        reason=f"dispatching {len(work)} active item(s) from proof program: {label_summary}",
    )


# ---------------------------------------------------------------------------
# Boundary types for the proof-program → OS composition seam
# ---------------------------------------------------------------------------


class _ProgramRoadmapNotFoundError(LookupError):
    """Proof program's roadmap file is missing — caller emits Wait."""


class _ProgramNoActiveWorkError(LookupError):
    """Proof program has zero active items with next_action."""


class _ProgramOperatorDirectionRequiredError(LookupError):
    """Proof program has ACTIVE items but every one is operator-blocked.

    Per @INV-0094, this is the institutional signal that the math
    agent has bounded its work and the supervisor must surface
    ``operator_required`` instead of re-dispatching into the
    no-delta loop.
    """


def _ask_program_for_work(
    callable_obj: Callable[..., object],
    repository: Path,
    source_revision: SourceRevision,
) -> list[WorkRequest]:
    """Delegate to the program-supplied ``next_active_work`` callable.

    The callable is resolved through the kernel-blessed
    ``mathlint.program_work_selection`` entry-point group
    (see :func:`_work_selection_callable_for_repo`); the OS
    does not import any program-named module by hand.

    Exception family is the proof program's own (re-exported
    by ``kaplansky.work_selection`` today, by future programs
    tomorrow); the OS catches the duck-typed exceptions
    ``RoadmapNotFoundError``, ``NoActiveWorkError``, and
    ``RoadmapParseError`` by attribute lookup on the callable's
    module rather than by direct module import. That keeps
    the OS program-agnostic: a second program with the same
    exception family works without OS code changes.
    """
    callable_module = getattr(callable_obj, "__module__", "")
    try:
        exc_module = importlib.import_module(callable_module)
    except ImportError:
        exc_module = None
    roadmap_not_found = getattr(exc_module, "RoadmapNotFoundError", None)
    no_active_work = getattr(exc_module, "NoActiveWorkError", None)
    operator_direction_required = getattr(exc_module, "OperatorDirectionRequiredError", None)
    roadmap_parse = getattr(exc_module, "RoadmapParseError", None)

    try:
        result = callable_obj(repository, source_revision=source_revision)
    except Exception as exc:  # noqa: BLE001 — boundary catch
        if roadmap_not_found is not None and isinstance(exc, roadmap_not_found):
            raise _ProgramRoadmapNotFoundError(str(exc)) from exc
        if operator_direction_required is not None and isinstance(exc, operator_direction_required):
            # Per @INV-0094: the program has bounded every available
            # item; the math agent is in the no-delta loop. Forward
            # the exception (the Wait envelope below converts it to
            # an operator_required signal).
            raise _ProgramOperatorDirectionRequiredError(str(exc)) from exc
        if no_active_work is not None and isinstance(exc, no_active_work):
            raise _ProgramNoActiveWorkError(str(exc)) from exc
        if roadmap_parse is not None and isinstance(exc, roadmap_parse):
            # Re-raise: a malformed roadmap is a config defect,
            # not a "no work" signal. The supervisor should see
            # the crash rather than silently parking.
            raise
        # Unknown exception family from the program: surface the
        # diagnostic so the supervisor's catch-all can record it,
        # but do not crash the OS.
        raise

    # Normalise: the contract says the callable returns a list of
    # WorkRequest, but the OS does not trust the type at the
    # dispatch boundary — the contracts module re-exports the
    # canonical WorkRequest class so isinstance works.
    from research_institution.contracts.source_decision import (
        WorkRequest as _WR,  # noqa: N814
    )

    if not isinstance(result, list):
        raise _ProgramRoadmapNotFoundError(
            f"work-selection callable returned non-list: {type(result).__name__}"
        )
    for item in result:
        if not isinstance(item, _WR):
            raise _ProgramRoadmapNotFoundError(
                f"work-selection callable returned non-WorkRequest item: {type(item).__name__}"
            )
    return result


def _call_program_register(entry_point: str) -> None:
    """Invoke one proof program's ``register()`` callback.

    The ``entry_point`` string follows the
    ``module:attribute`` convention that
    ``importlib.metadata.EntryPoint.load()`` uses. Failures are
    logged at WARNING level and swallowed so a missing or
    broken program does not poison the OS-level registration
    (the operator may legitimately be running mathlint without
    any proof program installed).
    """
    module_name, separator, attribute = entry_point.partition(":")
    if not separator or not module_name or not attribute:
        _LOG.warning(
            "skipping malformed program entry point %r; expected 'module:attribute'",
            entry_point,
        )
        return
    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        _LOG.warning(
            "proof program module %s is not installed; skipping (%s)",
            module_name,
            error,
        )
        return
    callback = getattr(module, attribute, None)
    if not callable(callback):
        _LOG.warning(
            "proof program module %s has no callable %s; skipping",
            module_name,
            attribute,
        )
        return
    try:
        result = callback()
    except Exception as error:  # noqa: BLE001 — intentional fail-open
        _LOG.warning(
            "proof program %s raised during register(); skipping (%s)",
            entry_point,
            error,
        )
        return
    if result is not None:
        _LOG.warning(
            "proof program %s must return None from register(); got %r",
            entry_point,
            result,
        )


def _program_entry_points() -> Iterable[str]:
    """Yield every proof program's ``register()`` entry-point string.

    Reads the institution catalog exclusively. If the catalog
    cannot be read, returns an empty tuple — the OS does NOT
    fall back to a hardcoded program name (that was an
    @ADR-0007 violation; the catalog is the OS's only source
    of truth for "what programs exist").

    Each entry is the ``entry_point`` declared in
    ``catalog/programs.toml`` (e.g.
    ``"kaplansky.mathlint_plugin:register"``).
    """
    pairs = _entry_points_from_catalog()
    if pairs is None:
        return ()
    return tuple(ep for _, ep in pairs)


def _merge_work_source(
    program_state: ProgramProviders | None,
    work_source: WorkSourceProvider,
) -> ProgramProviders:
    """Build a new ``ProgramProviders`` carrying both OS and program slots.

    The kernel's ``register_program_providers`` is wholesale
    (replaces the whole state). After each proof program's
    ``register()`` has populated theorem_view / audit_reports /
    obligation_labels / etc., this function emits the final
    state in one kernel call so neither side clobbers the
    other.
    """
    base = program_state if program_state is not None else ProgramProviders()
    return dataclasses.replace(base, work_source_provider=work_source)


def _compose_programs() -> ProgramProviders | None:
    """Run every proof program's ``register()`` and return the merged state.

    The returned object has the program's content contributions
    and a *placeholder* ``work_source_provider`` (the kernel's
    default). The OS-level ``register()`` swaps in its real
    callable in the same kernel write so the public seam
    (mathlint's ``program_providers()``) sees a single coherent
    provider set.

    Returns ``None`` when no proof program installed.
    """
    for entry_point in _program_entry_points():
        _call_program_register(entry_point)
    return _state_snapshot()


def _state_snapshot() -> ProgramProviders | None:
    """Return the kernel's current ``ProgramProviders``, or None if unset.

    Imports ``program_providers`` lazily so import-time errors
    in mathlint do not poison the OS-level entry point
    discovery (the entry point is loaded at mathlint import
    time; a lazy read happens later).
    """
    try:
        from mathlint.program_providers import program_providers as _read_state
    except ImportError:
        return None
    try:
        return _read_state()
    except RuntimeError:
        return None


def register() -> None:
    """Install the OS-level WorkSourceProvider into mathlint.

    Compose order (per @ADR-0007):

    1. The kernel's ``discover_work_selection_programs()`` runs
       first, populating the per-program work-selection callable
       registry from the ``mathlint.program_work_selection``
       entry-point group. The OS depends on this registry to
       resolve ``next_active_work`` for the supervised program.
       (This is also called from ``mathlint.cli`` at import
       time; the explicit call here keeps the OS safe when the
       mathlint CLI has not been imported first.)
    2. Each installed proof program's ``register()`` runs next,
       populating content contributions (theorem view, audit
       reports, obligation labels, identifier namespace). The
       set of programs comes from the institution catalog; the
       OS does NOT hardcode program names in source.
    3. The OS reads the merged state via ``program_providers()``
       and re-emits it with the OS-owned ``work_source_provider``
       attached, so neither side clobbers the other.
    4. Idempotency: re-calling ``register()`` re-installs the
       work-source callable (which is fresh per call so test
       monkeypatches do not leak); content contributions are
       re-populated by each program's ``register()`` and are
       idempotent at the kernel level.
    """
    # Step 1: discover per-program work-selection callables.
    # Import lazily so the entry-point discovery path is not
    # poisoned by an ImportError in a test environment.
    try:
        from mathlint.program_providers import (
            discover_work_selection_programs as _discover_ws,
        )
    except ImportError:
        _discover_ws = None
    if _discover_ws is not None:
        _discover_ws()
    composed = _compose_programs()
    provider: WorkSourceProvider = select_next_work_for_supervisor
    final = _merge_work_source(composed, provider)
    register_program_providers(final)
