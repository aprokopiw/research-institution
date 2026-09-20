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
import importlib.metadata
import logging
import time
from collections.abc import Iterable
from pathlib import Path

from mathlint.program_providers import (
    ProgramProviders,
    WorkSourceProvider,
    register_program_providers,
)

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


# Vocabulary pinned by @CTR-0094. Using a closed Literal-style set so
# the runtime values are grep-able in the mathlint consumer code.
_DISPATCH_KINDS = frozenset({"Dispatch", "Wait", "OperatorRequired", "Stop"})


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


def select_next_work_for_supervisor(repository: Path) -> dict[str, object]:
    """The OS-level WorkSourceProvider.

    Contract: @CTR-0094. Today this emits a structured ``Wait``
    envelope with the catalog-resolved program identity. The OS
    does NOT decide what math work to do; that decision belongs to
    the proof program (which fills ``ProgramProviders.roadmap_path``
    via its own plugin). When a proof program ships a roadmap
    reader, this function will compose with it by reading
    ``ProgramProviders.roadmap_path`` from the registered providers
    and converting the next item into a ``Dispatch`` envelope.

    Defect class (if regressed): a future refactor that returns
    ``kind="Dispatch"`` with an empty ``work`` list would silently
    park the supervisor with no progress. The ``reason`` field is
    the operator's only diagnostic.
    """
    fingerprint, observed = _read_revision(repository)
    program_name = _read_catalog_program_name(repository)
    label = f"{program_name or 'unknown-program'}-tick-{int(observed)}"
    return {
        "kind": "Wait",
        "reason": (
            "research-institution provider: no roadmap reader yet; "
            "the proof program must supply one via ProgramProviders. "
            "See @ADR-0007 and @CTR-0094."
        ),
        "source_revision": {
            "fingerprint": fingerprint,
            "observed_unix": observed,
            "label": label,
        },
        "work": [],
    }


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
