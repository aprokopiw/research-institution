"""macOS isolated-label deployment test (entry 07 T1.5 / FR-4)."""

from __future__ import annotations

import os
import platform
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


@pytest.mark.skipif(
    platform.system() != "Darwin", reason="macOS-only deployment test"
)
def test_macos_isolated_label_writes_temp_plist() -> None:
    """On Darwin, ``--macos-isolated-label=<unique>`` writes a temp
    plist (NOT into ``~/Library/LaunchAgents/``). The runner's
    ``finally`` removes the temp plist.
    """
    from research_institution.gates.verify_simulation.deployment import (
        DeploymentRunner,
    )

    label = f"verify-sim-isolated-{os.getpid()}"
    runner = DeploymentRunner(
        repo_root=REPO, macos_isolated_label=label
    )
    rendered = runner.render()
    plist_path = runner._write_isolated_plist(rendered)
    try:
        assert plist_path is not None
        assert plist_path.exists()
        # The plist is in a temp dir, NOT in the user's HOME.
        home = Path.home()
        assert home not in plist_path.parents
        # The plist's content includes the rendered argv.
        import plistlib

        with plist_path.open("rb") as fh:
            doc = plistlib.load(fh)
        assert doc["Label"] == label
        assert doc["ProgramArguments"] == list(rendered.argv)
    finally:
        if plist_path is not None:
            import shutil

            if plist_path.exists():
                plist_path.unlink()
            if plist_path.parent.exists():
                shutil.rmtree(plist_path.parent, ignore_errors=True)


def test_macos_isolated_label_skipped_on_non_darwin() -> None:
    """On non-Darwin, the macOS plist step is a no-op."""
    from research_institution.gates.verify_simulation.deployment import (
        DeploymentRunner,
    )

    if platform.system() == "Darwin":
        pytest.skip("darwin-specific test")
    runner = DeploymentRunner(repo_root=REPO, macos_isolated_label="any")
    report = runner.run_dry()
    assert report.macos_isolated_label == "any"
    assert report.plist_path is None
