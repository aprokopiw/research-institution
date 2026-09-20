"""Subprocess helper for gate stages.

The gates package delegates to external CLIs (mathlint,
pi_monitor, mathlint-kaplansky) only when they are the
genuine system seam. This module centralizes:

  - Capturing exit status, stdout, and stderr with a uniform
    shape (`RunResult`).
  - A small `run()` helper that:
      * Captures output safely (no pipe-buffer stalls).
      * Resolves the executable via the project's own `.venv/bin`
        first when one exists, so operators running tests get
        the same tools the bundle installs.
      * Honors the canonical env conventions (e.g. PATH so the
        bash fallback in mathlint's scripts keeps working).
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RunResult:
    """The deterministic outcome of a subprocess stage.

    `ok` is True iff the command exited with status 0. `command`
    is the argv that was executed; `cwd` is the working directory
    (may be None to inherit the parent's cwd). `stdout` and
    `stderr` are the captured bytes decoded as UTF-8 with
    `errors="replace"` so a malformed log line cannot crash the
    aggregator.

    Tests assert on `ok`, the boolean fields, and substrings of
    `stdout`/`stderr`; they do not depend on the exact wording of
    operator-facing diagnostics.
    """

    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    cwd: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _project_bin() -> Path | None:
    """The canonical venv `bin/` if the operator is using the
    institution's venv. Used to prepend tools like `mathlint`,
    `pi-monitor`, `mathlint-kaplansky` to PATH so subprocess
    invocations never depend on the operator's interactive
    shell environment.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / ".venv" / "bin"
        if candidate.is_dir():
            return candidate
    return None


def _resolve_argv(argv: tuple[str, ...]) -> tuple[str, ...]:
    """If the first token is a bare name that lives in the
    project's `.venv/bin/`, expand it to an absolute path. This
    makes subprocess invocations deterministic when the operator
    hasn't sourced the venv.
    """
    if not argv:
        return argv
    head = argv[0]
    if "/" in head or head == "":
        return argv
    bin_dir = _project_bin()
    if bin_dir is None:
        return argv
    candidate = bin_dir / head
    if candidate.is_file() and os.access(candidate, os.X_OK):
        return (str(candidate), *argv[1:])
    return argv


def run(
    argv: tuple[str, ...] | list[str],
    *,
    cwd: Path | str | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    check: bool = False,
) -> RunResult:
    """Run a command and return a RunResult.

    Args:
        argv: command + args. Bare names (no "/") are resolved
            against the project venv before exec.
        cwd: working directory; default inherits parent.
        env: environment dict; merged on top of os.environ so
            callers can override a single var.
        timeout: seconds; None disables.
        check: when True, raise CalledProcessError on failure.

    Returns:
        RunResult with returncode, stdout, stderr, and the
        resolved argv actually executed (useful for "what did I
        just run?" debugging).
    """
    argv_t = tuple(argv)
    resolved = _resolve_argv(argv_t)
    full_env = dict(os.environ)
    bin_dir = _project_bin()
    if bin_dir is not None:
        # Prepend (project venv first) so dispatched tools
        # (mathlint, pi-monitor, ruff) match the operator's
        # expected resolution — but keep system PATH so bash and
        # uv remain reachable even when the operator's shell
        # doesn't include them yet.
        full_env["PATH"] = f"{bin_dir}{os.pathsep}{full_env.get('PATH', '')}"
    if env:
        full_env.update(env)
    completed = subprocess.run(
        resolved,
        cwd=str(cwd) if cwd is not None else None,
        env=full_env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=check,
    )
    return RunResult(
        command=resolved,
        returncode=completed.returncode,
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
        cwd=str(cwd) if cwd is not None else None,
    )


__all__ = ["RunResult", "run"]
