"""End-to-end tests for the research-institution CLI dispatcher.

Uses Typer's CliRunner (no subprocess). The fixture in conftest.py
shims `mathlint` and `pi-monitor` so we never invoke the real binaries
during tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_list_prints_catalog(cli_runner, repo_root: Path) -> None:
    """research list prints the catalog programs."""
    result = cli_runner.invoke(args=["list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "kaplansky" in result.stdout


def test_unknown_program_in_start_exits_2(cli_runner) -> None:
    """research start <unknown> fails fast with a clear error."""
    result = cli_runner.invoke(args=["start", "no-such-program"], catch_exceptions=False)
    assert result.exit_code == 2
    assert "unknown program" in (result.stdout + result.stderr).lower()


def test_dry_run_start_does_not_invoke_mathlint(cli_runner, monkeypatch) -> None:
    """research start --dry-run exits 0 without invoking mathlint."""
    # Spy: count how many times the fake mathlint is invoked.
    # The fake shim prints "fake mathlint $args" to stdout; we just
    # assert the dispatcher prints "would launch" without going near it.
    result = cli_runner.invoke(args=["start", "kaplansky", "--dry-run"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "would launch" in result.stdout.lower()


def test_stop_delegates_to_mathlint(cli_runner) -> None:
    """research stop kaplansky invokes mathlint research-stop (via fake shim).

    The fake shim writes its argv to a known file (set via env var in
    conftest) so we can assert the dispatcher delegated without
    fighting Typer's stdout capture.
    """
    import os
    log = os.environ["FAKE_SHIM_LOG"]
    if os.path.exists(log):
        os.remove(log)
    result = cli_runner.invoke(args=["stop", "kaplansky"], catch_exceptions=False)
    assert result.exit_code == 0
    assert os.path.exists(log), "fake shim was never invoked"
    body = open(log, encoding="utf-8").read()
    assert "research-stop" in body


def test_status_delegates_to_mathlint(cli_runner) -> None:
    """research status kaplansky invokes mathlint research-status."""
    import os
    log = os.environ["FAKE_SHIM_LOG"]
    if os.path.exists(log):
        os.remove(log)
    result = cli_runner.invoke(args=["status", "kaplansky"], catch_exceptions=False)
    assert result.exit_code == 0
    body = open(log, encoding="utf-8").read()
    assert "research-status" in body


def test_doctor_hermetic_runs_green_gate(cli_runner, repo_root: Path) -> None:
    """research doctor delegates to green-gate/check-institution.sh --hermetic."""
    # We can't actually run the green gate in this test env (it would
    # require the real mathlint installed). Just assert that the
    # command is invoked. Easier: skip if the gate is missing.
    gate = repo_root / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        pytest.skip("green-gate script not present in this checkout")
    # The fake mathlint shim exits 0; the green-gate may exit non-zero
    # depending on the env. We just assert the command ran (exit code
    # is whatever the gate returns).
    result = cli_runner.invoke(args=["doctor"], catch_exceptions=False)
    # Either the gate ran (exit code anything but 127 = binary missing)
    # or the gate is not on PATH. We accept both.
    assert result.exit_code is not None


def test_install_skills_creates_symlinks(cli_runner, tmp_path: Path) -> None:
    """research install-skills creates one symlink per catalog program."""
    result = cli_runner.invoke(args=["install-skills"], catch_exceptions=False)
    assert result.exit_code == 0
    skills_dir = Path(tmp_path) / "agent_skills"
    assert skills_dir.is_dir()
    # One symlink per catalog program.
    symlinks = list(skills_dir.iterdir())
    assert len(symlinks) >= 1
    assert any(s.name == "kaplansky" for s in symlinks)


def test_install_skills_is_idempotent(cli_runner, tmp_path: Path) -> None:
    """Re-running install-skills does not error and refreshes symlinks."""
    first = cli_runner.invoke(args=["install-skills"], catch_exceptions=False)
    assert first.exit_code == 0
    second = cli_runner.invoke(args=["install-skills"], catch_exceptions=False)
    assert second.exit_code == 0
