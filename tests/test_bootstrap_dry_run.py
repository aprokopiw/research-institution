"""Tests for `scripts/bootstrap-institution.sh`.

The bootstrap script is the cold-start entrypoint documented in
AGENTS.md. It must:

  - Exist and be executable.
  - Tolerate an empty catalog (no programs to clone).
  - Print a clear success marker (`INSTITUTION BOOTSTRAPPED`).
  - Read the catalog from a configurable path (default: repo root).

We test in `--dry-run` mode by running the script's TOML-parsing +
catalog-iteration phase against a fixture catalog in tmp_path. The
real git-clone + pip-install paths are exercised manually on the
operator's machine; CI / contract tests focus on the contract surface.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP = REPO_ROOT / "scripts" / "bootstrap-institution.sh"
FIXTURE_EMPTY = Path(__file__).resolve().parent / "fixtures" / "empty_catalog.toml"


def test_bootstrap_script_exists_and_is_executable() -> None:
    assert BOOTSTRAP.is_file(), f"missing {BOOTSTRAP}"
    assert BOOTSTRAP.stat().st_mode & 0o111, f"{BOOTSTRAP} not executable"


def test_bootstrap_tolerates_empty_catalog(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bootstrap with an empty catalog prints INSTITUTION BOOTSTRAPPED."""
    if not shutil.which("python3"):
        pytest.skip("python3 not on PATH")
    # The bootstrap script reads catalog/programs.toml at a hardcoded
    # path. To test with an empty catalog without mutating the repo,
    # we make a sandbox copy of the script + an empty catalog.
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir()
    (sandbox_root / "scripts").mkdir()
    (sandbox_root / "catalog").mkdir()
    shutil.copy(BOOTSTRAP, sandbox_root / "scripts" / "bootstrap-institution.sh")
    shutil.copy(FIXTURE_EMPTY, sandbox_root / "catalog" / "programs.toml")

    # Run from the sandbox; bootstrap computes ROOT from its own location.
    result = subprocess.run(
        ["bash", "scripts/bootstrap-institution.sh"],
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
    assert "INSTITUTION BOOTSTRAPPED" in result.stdout


def test_bootstrap_reports_root_and_next_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bootstrap's output tells the operator what to run next."""
    sandbox_root = tmp_path / "sandbox"
    sandbox_root.mkdir()
    (sandbox_root / "scripts").mkdir()
    (sandbox_root / "catalog").mkdir()
    shutil.copy(BOOTSTRAP, sandbox_root / "scripts" / "bootstrap-institution.sh")
    shutil.copy(FIXTURE_EMPTY, sandbox_root / "catalog" / "programs.toml")
    result = subprocess.run(
        ["bash", "scripts/bootstrap-institution.sh"],
        capture_output=True,
        text=True,
        cwd=str(sandbox_root),
        timeout=30,
        check=False,
    )
    assert result.returncode == 0
    # The bootstrap script must print the green-gate path so the
    # operator can copy-paste the next step.
    assert "check-institution.sh" in result.stdout or "green-gate" in result.stdout
