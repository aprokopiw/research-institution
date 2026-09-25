"""Supported Python-version matrix (entry 08 M1 T1.2 / FR-4).

A single ``python_versions.toml`` declares the supported minimum
+ current Python versions for the research-institution's
canonical simulation. The matrix is referenced by the
``CompatMatrixRunner`` (FR-3) and the green-gate's
``verify-simulation --tier compatibility-matrix``.

The runner honors:

    * ``minimum`` — the lowest Python version still supported;
      a cell with this version is PASS / FAIL but not BLOCKED.
    * ``current`` — the version the operator runs today; the
      canonical cell.
    * ``unsupported`` (optional) — versions the runner reports
      as ``BLOCKED`` (e.g. EOL Python).

The runner does NOT install missing Python versions; the
operator's machine either has them or the cell is BLOCKED.
"""

from __future__ import annotations

import importlib.metadata
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "PythonVersionMatrix",
    "load_matrix",
    "current_python_version",
]


@dataclass(frozen=True, slots=True)
class PythonVersionMatrix:
    """The supported Python-version matrix (FR-4)."""

    minimum: str
    current: str
    unsupported: tuple[str, ...] = ()


def load_matrix(path: Path | None = None) -> PythonVersionMatrix:
    """Load the matrix from ``python_versions.toml``.

    When ``path`` is None, the runner reads
    ``<repo_root>/python_versions.toml`` (default).
    """
    if path is None:
        path = _default_matrix_path()
    if not path.exists():
        # Sensible default if the matrix file is absent (e.g.
        # a fresh checkout before entry 08 lands).
        return PythonVersionMatrix(
            minimum="3.12", current=current_python_version()
        )
    doc = tomllib.loads(path.read_text(encoding="utf-8"))
    return PythonVersionMatrix(
        minimum=str(doc["minimum"]),
        current=str(doc["current"]),
        unsupported=tuple(doc.get("unsupported", ())),
    )


def current_python_version() -> str:
    """Return the running interpreter's ``X.Y`` version."""
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _default_matrix_path() -> Path:
    # The matrix lives at the research-institution repo root.
    here = Path(__file__).resolve()
    for ancestor in [here, *here.parents]:
        if (ancestor / "pyproject.toml").exists() and (
            ancestor / "research_institution"
        ).is_dir():
            return ancestor / "python_versions.toml"
    return Path.cwd() / "python_versions.toml"


# A re-exported helper for the green-gate that wants the
# installed version of mathlint (the cross-repo compat check
# also inspects the kernel's installed version).
def installed_distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None
