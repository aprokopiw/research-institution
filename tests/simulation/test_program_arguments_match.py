"""ProgramArguments byte-equality test (entry 07 T1.4 / FR-2)."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def test_render_program_arguments_shape() -> None:
    """The renderer returns a ProgramArguments with at least 3 args
    (program + run + --config + config_path).
    """
    from research_institution.gates.verify_simulation.deployment import (
        render_program_arguments,
    )

    args = render_program_arguments(repo_root=REPO)
    assert args.program.endswith("pi-monitor")
    assert args.args == ("run", "--config", str(REPO / "pi-monitor.cycle.toml"))


def test_render_program_arguments_argv_byte_stable() -> None:
    """Two renders produce byte-equal argv (FR-2)."""
    from research_institution.gates.verify_simulation.deployment import (
        render_program_arguments,
    )

    a = render_program_arguments(repo_root=REPO)
    b = render_program_arguments(repo_root=REPO)
    assert a.argv == b.argv


def test_render_program_arguments_with_overrides() -> None:
    """Overriding pi_monitor_bin / config_path is honored."""
    from research_institution.gates.verify_simulation.deployment import (
        render_program_arguments,
    )

    args = render_program_arguments(
        repo_root=REPO,
        pi_monitor_bin=Path("/custom/path/pi-monitor"),
        config_path=Path("/custom/path/config.toml"),
    )
    assert args.argv == (
        "/custom/path/pi-monitor",
        "run",
        "--config",
        "/custom/path/config.toml",
    )
