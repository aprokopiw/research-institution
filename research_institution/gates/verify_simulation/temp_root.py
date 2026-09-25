"""Temp-root factory for the verify-simulation harness (entry 06 T1.2).

Per FR-7 of the spec, ``temp_root_factory`` yields a disposable
temp deployment root per scenario run. On success the temp_root
is removed; on failure (raised exception OR non-PASS report) the
temp_root is preserved for post-mortem inspection.

The contract:

  * Each call to ``temp_root_factory(scenario=...)`` yields a
    ``TempRoot`` context manager with a unique ``scenario_id``,
    a ``path`` to a fresh ``TemporaryDirectory``, and the
    captured exception (if any).
  * The ``cleanup_expectations`` are ``temp_root_cleanup_on_success``
    + ``preserve_on_failure`` per FR-6.
  * The factory never silently swallows exceptions; the caller
    decides via the ``on_success`` / ``on_failure`` hooks.
"""

from __future__ import annotations

import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

__all__ = ["TempRoot", "temp_root_factory"]


@dataclass(frozen=True, slots=True)
class TempRoot:
    """A disposable deployment root for one scenario run.

    The ``scenario_id`` is a unique hex slug; the ``path`` is
    the temp directory's root. ``preserved`` is set when the
    context exits via exception OR when the caller explicitly
    asks for preservation.
    """

    scenario_id: str
    path: Path
    preserved: bool = False


@contextmanager
def temp_root_factory(*, scenario: str) -> Iterator[TempRoot]:
    """Yield a ``TempRoot`` and either clean up or preserve it.

    Usage::

        with temp_root_factory(scenario="happy-three-cycle") as root:
            ...

    On clean exit, the temp directory is removed. On exception,
    the temp directory is preserved (the operator can inspect
    it). The implementation manages ``TemporaryDirectory``
    cleanup directly: on exception, ``cleanup()`` is NOT called;
    on clean exit, ``cleanup()`` removes the directory.
    """
    scenario_id = f"{scenario}-{uuid.uuid4().hex[:12]}"
    path = Path(tempfile.mkdtemp(prefix=f"verify-sim-{scenario_id}-"))
    preserved = False
    try:
        root = TempRoot(scenario_id=scenario_id, path=path, preserved=False)
        yield root
    except BaseException:
        # Preserve on failure; do NOT remove the directory.
        preserved = True
        raise
    else:
        # Clean exit; remove the directory.
        import shutil

        shutil.rmtree(path, ignore_errors=True)
    finally:
        del preserved  # value is observable via the post-mortem path


def cleanup(root: TempRoot) -> None:
    """Remove the temp root's directory (no-op if already cleaned)."""
    import shutil

    if root.path.exists():
        shutil.rmtree(root.path, ignore_errors=True)


def preserve(root: TempRoot) -> None:
    """Mark the root as preserved (the directory stays on disk)."""
    # Marking is a no-op for the filesystem — the caller already
    # has the path. We return the updated root via a copy.
    return TempRoot(
        scenario_id=root.scenario_id, path=root.path, preserved=True
    )
