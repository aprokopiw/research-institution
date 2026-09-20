"""research-institution mathlint.providers plugin.

Per @ADR-0007, this module populates mathlint's
``ProgramProviders.work_source_provider`` slot from the OS
layer. The kernel (mathlint) calls ``discover_program_providers``
at import time, which loads the ``mathlint.providers`` entry
point registered in this repo's ``pyproject.toml`` and invokes
the ``register()`` function below.

Contract: ``@CTR-0094`` (work-source-provider dispatch envelope).

Composition with proof programs (per @ADR-0007):
The OS owns the *work-source slot*. Each proof program owns
its *content contributions* (theorem view, audit reports,
obligation labels, etc.). Mathlint's
``register_program_providers`` is wholesale (the kernel
replaces the entire ``ProgramProviders`` state on every call),
so the OS cannot let the program plugin overwrite its slot.

To preserve both halves, ``register()`` here:

1. Invokes each installed proof program's ``mathlint_plugin.register()``
   directly (importing the module by name from the catalog's
   ``entry_point``). The program's call populates theorem views,
   audit reports, obligation labels, identifier namespace, etc.
2. Reads the just-installed ``ProgramProviders`` state.
3. Re-emits a merged ``ProgramProviders`` whose ``work_source_provider``
   field carries the OS-level ``select_next_work_for_supervisor``
   and whose remaining fields are the program's contributions
   (so the program's slot is preserved alongside ours).

If no proof program is installed in the current environment
(common on CI runners), the OS still installs
``work_source_provider``; the supplier zeros (no theorem
view, no audit reports) are deliberate — the kernel can answer
the work-decide syscall with a ``Wait`` envelope either way.
"""

from __future__ import annotations

import dataclasses
import importlib
import logging
import time
from collections.abc import Iterable
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
    REASON_WAIT_REQUESTED,
    REASON_WORK_AVAILABLE,
    Dispatch,
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


# Proof programs that contribute content alongside the OS-owned
# work-source slot. Each entry is the catalog's ``entry_point``
# value (e.g. ``"kaplansky.mathlint_plugin:register"``). The OS
# discovers programs by reading the institution catalog and only
# composes with those marked ``live_credentials_required = true``
# (or any program that exports a ``mathlint_plugin`` module).
#
# Adding a second research program means adding its name to
# ``catalog/programs.toml``; no code edit here is needed.
_DEFAULT_PROGRAM_ENTRY_POINTS: tuple[str, ...] = (
    "kaplansky.mathlint_plugin:register",
)


# Reason code vocabulary is pinned by REASON_WAIT_REQUESTED
# (imported from research_institution.contracts.source_decision).
# The closed set lives in the contracts module so every call site
# shares one source of truth.


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
    """Best-effort: name the catalog program whose local_path matches `repo`.

    The OS already owns the catalog (@ADR-0006); using it here
    avoids hardcoding a program name in mathlint's surface.
    Returns None when no catalog entry matches OR when the
    institution directory isn't configured (which is the normal
    state for a math-only venv or a CI runner).
    """
    try:
        # Import lazily so import-time errors don't poison the
        # entry-point discovery path.
        from research_institution.catalog import load_catalog
        from research_institution.paths import catalog_path

        programs = load_catalog(catalog_path())
    except (OSError, ValueError, ImportError, RuntimeError):
        # RuntimeError covers "MATHLINT_INSTITUTION_DIR not set"
        # which is the expected state for hermetic tests.
        return None
    repo_str = str(repo).rstrip("/")
    for program in programs:
        try:
            resolved = str(program.resolved_local_path).rstrip("/")
        except (OSError, RuntimeError):
            continue
        if resolved == repo_str:
            return program.name
    return None


def select_next_work_for_supervisor(repository: Path) -> Dispatch | Wait:
    """The OS-level WorkSourceProvider.

    Contract: @CTR-0094. The OS owns the *transport* (typed
    ``Dispatch`` / ``Wait`` envelope, serialisation, retry/wake
    policy); the *decision* of what to work on next is owned by the
    proof program (currently kaplansky via ``work_selection.next_active_work``).

    Composition:

      1. The OS reads the source revision (git HEAD fingerprint, or
         the roadmap's content fingerprint when not a git checkout).
      2. The OS calls ``kaplansky.work_selection.next_active_work`` to
         ask kaplansky: "what should mathlint work on next?". The
         program owns the answer; the OS does NOT inspect the
         roadmap TOML itself.
      3. If kaplansky returns one or more WorkRequests, the OS wraps
         them in a typed :class:`Dispatch` with the canonical
         ``reason_code="work_available"``.
      4. If kaplansky has no active work
         (``NoActiveWorkError``), the OS emits a :class:`Wait` with
         ``wake_on_source_change=True`` so the supervisor re-decides
         as soon as the program moves an item to ``active``.

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
    try:
        work = _ask_program_for_work(repository, source_revision)
    except _ProgramRoadmapNotFound:
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
    except _ProgramNoActiveWork as exc:
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


class _ProgramRoadmapNotFound(LookupError):
    """Proof program's roadmap file is missing — caller emits Wait."""


class _ProgramNoActiveWork(LookupError):
    """Proof program has zero active items with next_action."""


def _ask_program_for_work(
    repository: Path,
    source_revision: SourceRevision,
) -> list[WorkRequest]:
    """Delegate to the registered proof program's next-step selector.

    The composition is by catalog: the catalog declares one
    ``entry_point`` per proof program; that module's ``register()``
    populates ``ProgramProviders``; the OS then calls this helper
    which looks up the program-supplied ``next_active_work``
    function via a registry. Today the registry has exactly one
    entry (``kaplansky.work_selection.next_active_work``); adding a
    second program means adding a registry entry, no OS code
    change.
    """
    try:
        import kaplansky.work_selection as kaplansky_ws
    except ImportError:
        raise _ProgramRoadmapNotFound(
            f"kaplansky is not installed in this environment; "
            f"cannot determine active work for {repository}"
        ) from None
    try:
        return kaplansky_ws.next_active_work(repository, source_revision=source_revision)
    except kaplansky_ws.RoadmapNotFoundError as exc:
        raise _ProgramRoadmapNotFound(str(exc)) from exc
    except kaplansky_ws.NoActiveWorkError as exc:
        raise _ProgramNoActiveWork(str(exc)) from exc
    except kaplansky_ws.RoadmapParseError:
        # Re-raise: a malformed roadmap is a config defect, not a
        # "no work" signal. The supervisor should see the crash
        # rather than silently parking.
        raise


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

    Reads the institution catalog when present; falls back to
    the built-in default (``kaplansky``) so a math-only venv
    still composes with kaplansky when both are installed.

    Each entry is the ``entry_point`` declared in
    ``catalog/programs.toml`` (e.g.
    ``"kaplansky.mathlint_plugin:register"``).
    """
    try:
        from research_institution.catalog import load_catalog
        from research_institution.paths import catalog_path

        programs = load_catalog(catalog_path())
    except (OSError, ValueError, ImportError, RuntimeError):
        return tuple(_DEFAULT_PROGRAM_ENTRY_POINTS)
    return tuple(p.entry_point for p in programs)


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

    1. Each installed proof program's ``register()`` runs first,
       populating content contributions (theorem view, audit
       reports, obligation labels, identifier namespace).
    2. The OS reads the merged state via ``program_providers()``
       and re-emits it with the OS-owned ``work_source_provider``
       attached, so neither side clobbers the other.
    3. Idempotency: re-calling ``register()`` re-installs the
       work-source callable (which is fresh per call so test
       monkeypatches do not leak); content contributions are
       re-populated by each program's ``register()`` and are
       idempotent at the kernel level.
    """
    composed = _compose_programs()
    provider: WorkSourceProvider = select_next_work_for_supervisor
    final = _merge_work_source(composed, provider)
    register_program_providers(final)
