"""research-institution mathlint.providers plugin.

Per @ADR-0007, this module populates mathlint's
``ProgramProviders.work_source_provider`` slot from the OS
layer. The kernel (mathlint) calls ``discover_program_providers``
at import time, which loads the ``mathlint.providers`` entry
point registered in this repo's ``pyproject.toml`` and invokes
the ``register()`` function below.

Contract: ``@CTR-0094`` (work-source-provider dispatch envelope).

The dispatch envelope shape is fixed by mathlint (the kernel).
This module decides only what to put *inside* the envelope.
Today the OS emits a structured ``Wait`` envelope with the
catalog-resolved program identity and the supervisor's current
revision fingerprint. As proof programs ship roadmap readers,
the OS composes with them via ``ProgramProviders.roadmap_path``
(filled by each program's own ``register()`` call).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from mathlint.program_providers import (
    ProgramProviders,
    WorkSourceProvider,
    register_program_providers,
)

__all__ = ["register", "select_next_work_for_supervisor"]


# Vocabulary pinned by @CTR-0094. Using a closed Literal-style set so
# the runtime values are grep-able in the mathlint consumer code.
_DISPATCH_KINDS = frozenset({"Dispatch", "Wait", "OperatorRequired", "Stop"})


def _read_repository() -> Path:
    """Return the supervised program's repository, or raise.

    Resolution order matches mathlint's ``real_source.configured_provider``
    so the same env-var contract is honored on both sides of the
    kernel/OS boundary.
    """
    raw = os.environ.get("TARGET_REPOSITORY") or os.environ.get(
        "KAPLANSKY_REPOSITORY", ""
    )
    if not raw:
        msg = (
            "research-institution provider: target repository is not configured. "
            "Set TARGET_REPOSITORY (preferred) or KAPLANSKY_REPOSITORY."
        )
        raise RuntimeError(msg)
    return Path(raw)


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


def register() -> None:
    """Install the OS-level WorkSourceProvider into mathlint.

    Idempotent: calling ``register()`` twice with no other plugin
    between calls is safe. The slot is set to a fresh
    ``select_next_work_for_supervisor`` callable each time so a
    test that mutates the function (e.g. via monkeypatch) does
    not leak across test boundaries.
    """
    provider: WorkSourceProvider = select_next_work_for_supervisor
    register_program_providers(ProgramProviders(work_source_provider=provider))
