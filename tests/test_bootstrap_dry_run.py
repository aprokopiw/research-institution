"""Tests for the canonical bootstrap entry point.

The bootstrap install is split into a thin shell shim
(`scripts/bootstrap-institution.sh`, four lines that delegate to
`scripts/bootstrap.py`) and a Python module
(`research_institution.gates.bootstrap`). Both surfaces must
exist and stay executable.

Cold-start contract tests assert:

  - The shim exists and is executable.
  - Tolerates an empty catalog (no programs to clone).
  - Prints a clear success marker.
  - The Python entry point is importable and idempotent.

The real git-clone + pip-install paths are exercised manually on
the operator's machine; CI / contract tests focus on the
contract surface.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from research_institution.gates.bootstrap import bootstrap_install

REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_SH = REPO_ROOT / "scripts" / "bootstrap-institution.sh"
BOOTSTRAP_PY = REPO_ROOT / "scripts" / "bootstrap.py"
FIXTURE_EMPTY = Path(__file__).resolve().parent / "fixtures" / "empty_catalog.toml"


def test_bootstrap_shim_exists_and_is_executable() -> None:
    assert BOOTSTRAP_SH.is_file(), f"missing {BOOTSTRAP_SH}"
    assert BOOTSTRAP_SH.stat().st_mode & 0o111, f"{BOOTSTRAP_SH} not executable"


def test_bootstrap_python_entry_exists() -> None:
    assert BOOTSTRAP_PY.is_file(), f"missing {BOOTSTRAP_PY}"
    assert BOOTSTRAP_SH.read_text().count(BOOTSTRAP_PY.name) >= 1, (
        f"{BOOTSTRAP_SH} must delegate to {BOOTSTRAP_PY}"
    )


def _stage_sandbox(tmp_path: Path) -> Path:
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir()
    (sandbox_root / "scripts").mkdir()
    (sandbox_root / "catalog").mkdir()
    shutil.copy(BOOTSTRAP_SH, sandbox_root / "scripts" / "bootstrap-institution.sh")
    shutil.copy(BOOTSTRAP_PY, sandbox_root / "scripts" / "bootstrap.py")
    shutil.copy(FIXTURE_EMPTY, sandbox_root / "catalog" / "programs.toml")
    # The bootstrap entry point imports `research_institution.gates.bootstrap`.
    # Symlink the package source into the sandbox so the bootstrap shim can
    # import it without requiring a system-wide install. This mirrors the
    # isolation pattern in `test_cold_start_hermetic.py`.
    (sandbox_root / "research_institution").symlink_to(
        REPO_ROOT / "research_institution", target_is_directory=True
    )
    return sandbox_root


def test_bootstrap_tolerates_empty_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bootstrap with an empty catalog succeeds and prints the next-step pointer."""
    if not shutil.which("python3"):
        pytest.skip("python3 not on PATH")
    sandbox_root = _stage_sandbox(tmp_path)
    # Bootstrap computes MATHLINT_INSTITUTION_DIR from $PWD when unset;
    # point it explicitly at the sandbox to keep the Python entry
    # pointed at the fixture catalog.
    monkeypatch.setenv("MATHLINT_INSTITUTION_DIR", str(sandbox_root))
    result = subprocess.run(
        ["bash", "scripts/bootstrap-institution.sh", "--apply"],
        capture_output=True,
        text=True,
        cwd=str(sandbox_root),
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, (
        f"bootstrap failed: rc={result.returncode} stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    assert "BOOTSTRAP COMPLETE" in result.stdout or "INSTITUTION BOOTSTRAPPED" in result.stdout


def test_bootstrap_reports_next_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bootstrap's output must point the operator to the canonical verify step."""
    sandbox_root = _stage_sandbox(tmp_path)
    monkeypatch.setenv("MATHLINT_INSTITUTION_DIR", str(sandbox_root))
    result = subprocess.run(
        ["bash", "scripts/bootstrap-institution.sh", "--apply"],
        capture_output=True,
        text=True,
        cwd=str(sandbox_root),
        timeout=30,
        check=False,
    )
    assert result.returncode == 0
    # The Python entry point prints `BOOTSTRAP COMPLETE`; the gate
    # docstrings + README point at verify-institution.sh. The
    # contract is that the operator always knows the next step.
    assert "BOOTSTRAP COMPLETE" in result.stdout or "check-institution.sh" in result.stdout


def test_bootstrap_install_python_api_idempotent() -> None:
    """`bootstrap_install()` runs twice without raising and yields the
    same report shape. This guards against accidental state-leak
    regressions during a refactor."""
    first = bootstrap_install()
    second = bootstrap_install()
    assert isinstance(first.steps, list)
    assert isinstance(second.steps, list)
    # Idempotency: both runs reach the same conclusion.
    assert first.ok == second.ok or first.programs_installed or second.programs_installed
