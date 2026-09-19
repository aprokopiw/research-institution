"""Shared test fixtures.

The dispatcher CLI is exercised end-to-end with Typer's CliRunner
(no subprocess), so the tests are fast and deterministic. The catalog
fixture is the canonical TOML from the repo; alternative fixtures
live in tests/fixtures/catalog-*.toml.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path("/Users/erinprokopiw/Documents/andrei/research-institution")


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Make tests deterministic: redirect env vars; leave PATH alone.

    Scope: tests that exercise the dispatcher CLI. Pre-existing shell-
    script tests inherit the system PATH (which they need for awk,
    tail, git).
    """
    monkeypatch.setenv("MATHLINT_INSTITUTION_DIR", str(REPO))
    monkeypatch.setenv("PI_AGENT_SKILLS_DIR", str(tmp_path / "agent_skills"))
    monkeypatch.setenv("PI_MONITOR_REPO", str(tmp_path / "pi_monitor_repo"))


@pytest.fixture
def cli_runner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A Typer CliRunner instance bound to the dispatcher app.

    Builds a per-test PATH with fake mathlint + pi-monitor shims so the
    dispatcher delegates without invoking the real binaries. Logs each
    invocation to $FAKE_SHIM_LOG so tests can assert delegation.
    """
    from research_institution.cli import app
    from typer.testing import CliRunner

    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    shim_log = tmp_path / "shim.log"
    monkeypatch.setenv("FAKE_SHIM_LOG", str(shim_log))
    for name in ("mathlint", "pi-monitor"):
        (shim_dir / name).write_text(
            f"#!/bin/sh\necho \"fake $0 $*\" >> \"{shim_log}\"\nexit 0\n",
            encoding="utf-8",
        )
        (shim_dir / name).chmod(0o755)
    # Prepend shim dir so fake binaries win name resolution.
    current = __import__("os").environ.get("PATH") or "/usr/bin:/bin"
    monkeypatch.setenv("PATH", f"{shim_dir}:{current}")

    runner = CliRunner()

    def _invoke(args=None, **kwargs):
        return runner.invoke(app, args=args, **kwargs)

    return type("CliRunnerFacade", (), {"invoke": staticmethod(_invoke)})()


@pytest.fixture
def repo_root() -> Path:
    return REPO
