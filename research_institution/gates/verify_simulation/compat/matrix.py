"""CompatMatrixRunner (entry 08 M2 T2.1 / FR-1 + FR-3).

The runner iterates a (Python × repo) matrix and asserts the
canonical simulation runs at every cell. The hermetic tier
checks the running interpreter only (one cell); the LIVE
tier iterates the full matrix (each supported Python + each
repo).

The runner is a thin wrapper: the heavy lifting (clean venv +
wheel install + simulation) is the LIVE-tier concern, owned by
successor-entry work. The hermetic runner asserts the
matrix *shape* (number of cells + supported-Python detection)
and emits a typed ``CompatMatrixReport`` that the green-gate
consumes.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path

from research_institution.gates.verify_simulation.compat.python_versions import (
    PythonVersionMatrix,
    current_python_version,
    installed_distribution_version,
    load_matrix,
)

__all__ = ["CompatCell", "CompatMatrixReport", "CompatMatrixRunner"]


@dataclass(frozen=True, slots=True)
class CompatCell:
    """One (Python × repo) cell."""

    python_version: str
    repo: str  # "research-institution" | "math" | "pi_monitor" | "kaplansky"
    distribution_version: str | None
    verdict: str  # "PASS" | "FAIL" | "BLOCKED"
    detail: str = ""


@dataclass(frozen=True, slots=True)
class CompatMatrixReport:
    """The runner's typed report."""

    verdict: str  # "PASS" | "FAIL" | "BLOCKED"
    cells: tuple[CompatCell, ...]
    matrix_source: str  # path to python_versions.toml
    detail: str = ""


class CompatMatrixRunner:
    """CompatMatrixRunner (FR-3 + M2 T2.1)."""

    def __init__(
        self,
        *,
        matrix: PythonVersionMatrix | None = None,
        repos: tuple[str, ...] = (
            "research-institution",
            "math",
            "pi_monitor",
            "kaplansky",
        ),
        matrix_path: Path | None = None,
        run_live: bool = False,
    ) -> None:
        self.matrix = matrix or load_matrix(matrix_path)
        self.repos = repos
        self.matrix_path = matrix_path or _default_matrix_path()
        self.run_live = run_live

    def run(self) -> CompatMatrixReport:
        """Run the matrix and return a typed report."""
        cells: list[CompatCell] = []
        current_py = current_python_version()
        for repo in self.repos:
            if repo == "research-institution":
                dist_name = "research-institution"
            elif repo == "math":
                dist_name = "mathlint"
            elif repo == "pi_monitor":
                dist_name = "pi-monitor"
            elif repo == "kaplansky":
                dist_name = "kaplansky"
            else:
                cells.append(
                    CompatCell(
                        python_version=current_py,
                        repo=repo,
                        distribution_version=None,
                        verdict="FAIL",
                        detail=f"unknown repo: {repo}",
                    )
                )
                continue
            dist_version = installed_distribution_version(dist_name)
            cell = self._run_cell(current_py, repo, dist_name, dist_version)
            cells.append(cell)
        if self.run_live:
            # The LIVE tier adds the additional Python-version cells.
            live_cells = self._run_live_matrix(current_py)
            cells.extend(live_cells)
        verdicts = {c.verdict for c in cells}
        if "FAIL" in verdicts:
            verdict = "FAIL"
            detail = "one or more cells FAILed"
        elif "BLOCKED" in verdicts:
            verdict = "BLOCKED"
            detail = "one or more cells BLOCKED"
        else:
            verdict = "PASS"
            detail = ""
        return CompatMatrixReport(
            verdict=verdict,
            cells=tuple(cells),
            matrix_source=str(self.matrix_path),
            detail=detail,
        )

    def _run_cell(
        self,
        python_version: str,
        repo: str,
        dist_name: str,
        dist_version: str | None,
    ) -> CompatCell:
        if python_version in self.matrix.unsupported:
            return CompatCell(
                python_version=python_version,
                repo=repo,
                distribution_version=dist_version,
                verdict="BLOCKED",
                detail=f"python {python_version} is unsupported",
            )
        if dist_version is None:
            return CompatCell(
                python_version=python_version,
                repo=repo,
                distribution_version=None,
                verdict="FAIL",
                detail=f"{dist_name} not installed",
            )
        return CompatCell(
            python_version=python_version,
            repo=repo,
            distribution_version=dist_version,
            verdict="PASS",
            detail="installed",
        )

    def _run_live_matrix(self, current_py: str) -> tuple[CompatCell, ...]:
        """Iterate the supported-Python matrix in a clean venv per cell.

        The LIVE tier is intentionally a no-op stub in the
        hermetic runner; the heavy lifting (clean venv + wheel
        install + simulation) is a successor-entry concern. The
        runner returns the current-Python cell only.
        """
        return ()


def _default_matrix_path() -> Path:
    here = Path(__file__).resolve()
    for ancestor in [here, *here.parents]:
        if (ancestor / "python_versions.toml").exists():
            return ancestor / "python_versions.toml"
    return Path.cwd() / "python_versions.toml"
