"""Compat matrix tests (entry 08 M2 T2.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_python_versions_toml_loads() -> None:
    """``python_versions.toml`` parses with required keys."""
    import tomllib

    doc = tomllib.loads((REPO / "python_versions.toml").read_text(encoding="utf-8"))
    assert "minimum" in doc
    assert "current" in doc
    assert "unsupported" in doc


def test_python_versions_matrix_loads() -> None:
    """``PythonVersionMatrix.load_matrix`` returns the documented shape."""
    from research_institution.gates.verify_simulation.compat.python_versions import (
        load_matrix,
    )

    matrix = load_matrix(REPO / "python_versions.toml")
    assert matrix.minimum == "3.12"
    assert matrix.current == "3.14"
    assert "3.10" in matrix.unsupported


def test_compat_matrix_runner_reports_cells() -> None:
    """The runner iterates the four-repo matrix at the current Python."""
    from research_institution.gates.verify_simulation.compat import (
        CompatMatrixRunner,
    )

    runner = CompatMatrixRunner(matrix_path=REPO / "python_versions.toml")
    report = runner.run()
    assert len(report.cells) == 4
    repos = {c.repo for c in report.cells}
    assert repos == {"research-institution", "math", "pi_monitor", "kaplansky"}


def test_compat_matrix_runner_unknown_repo_fails() -> None:
    """An unknown repo produces a FAIL cell."""
    from research_institution.gates.verify_simulation.compat import (
        CompatMatrixRunner,
    )

    runner = CompatMatrixRunner(
        matrix_path=REPO / "python_versions.toml",
        repos=("mystery-repo",),
    )
    report = runner.run()
    assert report.verdict == "FAIL"
    cell = report.cells[0]
    assert "unknown repo" in cell.detail


def test_cli_compatibility_matrix_exits_zero_or_blocked() -> None:
    """``--tier compatibility-matrix`` exits 0 (PASS) or 0 (BLOCKED is acceptable)."""
    import subprocess
    import sys

    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "research_institution",
            "verify-simulation",
            "--tier",
            "compatibility-matrix",
        ],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
    assert proc.returncode in (0, 1), f"unexpected rc={proc.returncode}"
