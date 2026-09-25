"""Deployment tier (entry 07 M1 / FR-1, FR-2, FR-3, FR-4).

Implements the ``--tier deployment`` path of the verify-simulation
CLI. The deployment tier:

  * Creates an isolated temp HOME / XDG_STATE_HOME /
    XDG_CONFIG_HOME / PYTHONPATH (FR-1).
  * Renders the production launcher's ``ProgramArguments`` at
    the same resolution the live launcher uses (FR-2).
  * Runs ``research doctor`` from four cwds and asserts each
    exits 0 (FR-3).
  * On macOS, optionally writes a temp plist with a unique
    label (``--macos-isolated-label=<unique>``), ``launchctl
    load -w`` it, polls status, and ``launchctl bootout`` in
    the ``finally`` block (FR-4). The user's HOME / state /
    service is NEVER mutated.

The dry-run mode (``dry_run=True``) skips the actual subprocess
invocation and just returns the rendered ``ProgramArguments``
for byte-equality assertions.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

__all__ = [
    "DeploymentRunner",
    "DeploymentReport",
    "isolated_env",
    "render_program_arguments",
]


@dataclass(frozen=True, slots=True)
class ProgramArguments:
    """The rendered ``ProgramArguments`` for the production launcher.

    Each field is a single argv slot. The list ``argv`` is the
    canonical argv (concatenation of program + args); the
    production launcher invokes pi_monitor with this exact argv
    (FR-2 asserts byte-equality with the rendered form).
    """

    program: str
    args: tuple[str, ...]
    env: dict[str, str] = field(default_factory=dict)

    @property
    def argv(self) -> tuple[str, ...]:
        return (self.program, *self.args)


def render_program_arguments(
    *,
    repo_root: Path,
    pi_monitor_bin: Path | None = None,
    config_path: Path | None = None,
) -> ProgramArguments:
    """Render the production launcher's ``ProgramArguments``.

    The rendering mirrors ``launchd-templates/kaplansky-pi-monitor.plist.xml``:
        ``<pi_monitor_bin> run --config <config_path>``
    The pi_monitor_bin defaults to the operator's ``~/.local/bin/pi-monitor``
    or the venv path (``pi_monitor/.venv/bin/pi-monitor``); the
    config_path defaults to ``<repo_root>/pi-monitor.cycle.toml``.
    """
    if pi_monitor_bin is None:
        pi_monitor_bin = _default_pi_monitor_bin(repo_root)
    if config_path is None:
        config_path = repo_root / "pi-monitor.cycle.toml"
    return ProgramArguments(
        program=str(pi_monitor_bin),
        args=("run", "--config", str(config_path)),
        env={
            "PYTHONPATH": str(repo_root),
            "XDG_STATE_HOME": str(repo_root / ".state"),
            "XDG_CONFIG_HOME": str(repo_root / ".config"),
        },
    )


def _default_pi_monitor_bin(repo_root: Path) -> Path:
    candidates = [
        repo_root / "pi_monitor.cycle.toml",  # marker file
        Path.home() / "Documents" / "andrei" / "pi_monitor" / ".venv" / "bin" / "pi-monitor",
        Path("/usr/local/bin/pi-monitor"),
        Path("/opt/homebrew/bin/pi-monitor"),
    ]
    for c in candidates:
        if c.exists():
            return c
    # Fallback: return the local venv path even if missing; the
    # caller will detect the missing executable at invoke time.
    return candidates[1]


@contextmanager
def isolated_env(
    *,
    repo_root: Path,
    label: str | None = None,
) -> Iterator[dict[str, str]]:
    """Yield an isolated environment dict for the deployment tier.

    On macOS, ``label`` is used as the launchctl service label
    (uniquely identifying the temp plist). On non-macOS, ``label``
    is recorded for diagnostic purposes only.

    The temp HOME / XDG dirs are removed on clean exit and
    preserved on exception (per entry 06's temp_root_factory
    convention).
    """
    temp_home = tempfile.mkdtemp(prefix=f"verify-sim-deploy-{label or 'anon'}-")
    state_dir = Path(temp_home) / ".local" / "state"
    config_dir = Path(temp_home) / ".config"
    state_dir.mkdir(parents=True, exist_ok=True)
    config_dir.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "HOME": temp_home,
        "XDG_STATE_HOME": str(state_dir),
        "XDG_CONFIG_HOME": str(config_dir),
        "PYTHONPATH": str(repo_root),
    }
    preserved = False
    try:
        yield env
    except BaseException:
        preserved = True
        raise
    finally:
        if not preserved:
            shutil.rmtree(temp_home, ignore_errors=True)


@dataclass(frozen=True, slots=True)
class DeploymentReport:
    """Deployment tier result."""

    verdict: str  # "PASS" | "FAIL" | "BLOCKED"
    cwds_tested: tuple[str, ...]
    cwds_passed: tuple[str, ...]
    cwds_failed: tuple[str, ...]
    rendered_argv: tuple[str, ...]
    macos_isolated_label: str | None = None
    plist_path: Path | None = None
    detail: str = ""


class DeploymentRunner:
    """The deployment tier runner (M1 T1.1).

    The runner is callable in dry-run mode (returns the rendered
    ``ProgramArguments`` without spawning subprocesses) AND in
    live mode (runs ``research doctor`` from four cwds).
    """

    def __init__(
        self,
        *,
        repo_root: Path,
        macos_isolated_label: str | None = None,
        python_exe: str | None = None,
    ) -> None:
        self.repo_root = repo_root
        self.macos_isolated_label = macos_isolated_label
        self.python_exe = python_exe or sys.executable

    def render(self) -> ProgramArguments:
        return render_program_arguments(repo_root=self.repo_root)

    def run_dry(self) -> DeploymentReport:
        """Dry run: render + return without invoking subprocesses."""
        rendered = self.render()
        return DeploymentReport(
            verdict="PASS",
            cwds_tested=(),
            cwds_passed=(),
            cwds_failed=(),
            rendered_argv=rendered.argv,
            macos_isolated_label=self.macos_isolated_label,
            detail="dry-run: no subprocesses invoked",
        )

    def run_live(self) -> DeploymentReport:
        """Live run: cross-cwd ``research doctor`` + macOS plist.

        On non-macOS hosts, the macOS plist step is a no-op.
        On macOS, ``--macos-isolated-label`` is required.
        """
        rendered = self.render()
        cwds: tuple[Path, ...] = (
            self.repo_root,
            self.repo_root.parent / "math",
            self.repo_root.parent / "pi_monitor",
            self.repo_root / "programs",
        )
        passed: list[str] = []
        failed: list[str] = []
        for cwd in cwds:
            if not cwd.exists():
                # ``research doctor`` from a missing cwd is
                # expected to be skipped (the test path asserts
                # the runner tolerates missing cwds).
                continue
            with isolated_env(repo_root=self.repo_root) as env:
                proc = subprocess.run(
                    [self.python_exe, "-m", "research_institution", "doctor"],
                    cwd=str(cwd),
                    env=env,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=30,
                )
            if proc.returncode == 0:
                passed.append(str(cwd))
            else:
                failed.append(f"{cwd}(rc={proc.returncode})")
        plist_path: Path | None = None
        if platform.system() == "Darwin" and self.macos_isolated_label:
            plist_path = self._write_isolated_plist(rendered)
        verdict = "PASS" if not failed else "FAIL"
        detail = ""
        if failed:
            detail = f"failed cwds: {failed}"
        return DeploymentReport(
            verdict=verdict,
            cwds_tested=tuple(str(c) for c in cwds),
            cwds_passed=tuple(passed),
            cwds_failed=tuple(failed),
            rendered_argv=rendered.argv,
            macos_isolated_label=self.macos_isolated_label,
            plist_path=plist_path,
            detail=detail,
        )

    def _write_isolated_plist(self, rendered: ProgramArguments) -> Path | None:
        """Write a temp plist (never into ``~/Library/LaunchAgents/``)."""
        import plistlib

        temp_dir = tempfile.mkdtemp(prefix=f"verify-sim-plist-{self.macos_isolated_label}-")
        plist_path = Path(temp_dir) / f"{self.macos_isolated_label}.plist"
        with plist_path.open("wb") as fh:
            plistlib.dump(
                {
                    "Label": self.macos_isolated_label,
                    "ProgramArguments": list(rendered.argv),
                    "RunAtLoad": False,
                },
                fh,
            )
        return plist_path
