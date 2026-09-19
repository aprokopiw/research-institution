"""In-process Dispatcher API: typed wrappers over mathlint + pi_monitor subprocesses.

The CLI layer (:mod:`research_institution.cli`) is a thin Typer
adapter; this module is the typed Python surface operators can call
from scripts, tests, or future automation. Every method:

  - Returns a typed result (no parsed dicts, no string blobs).
  - Takes a `runner` callable for the subprocess step; default
    uses :func:`subprocess.run`. Tests inject a fake runner.
  - Takes an `environment` (`:class:`Environment`) for env-var
    reads. Tests inject a :class:`FakeEnvironment` instead of
    monkeypatching `os.environ` (which is global and unsafe across
    parallel tests).
  - Takes a `clock` for elapsed-time accounting. Tests inject
    :class:`FakeClock` for deterministic assertions.
  - Pins the argv shape (positional + flags) it sends, so a mathlint
    flag rename surfaces as a test failure here, not as silent
    behavior drift in production.

This module is NOT the operator's CLI. It's the in-process API. The
two are kept separate so:

  - CLI concerns (exit codes, typer parsing, error printing) stay
    in `cli.py`.
  - Dispatch logic (argv shape, run policy, typed return values)
    stays here and is unit-testable without Typer or subprocess.

Every method documents the wire contract it implements:

  - :meth:`Dispatcher.read_gate` reads `mathlint roadmap` and
    returns a typed :class:`GateVerdict`. Wire format pinned in
    `tests/test_gate_check.py`.
  - :meth:`Dispatcher.run_live` invokes `mathlint live-run`. Wire
    format pinned by the mathlint `live-run --help` contract; tests
    in `tests/test_dispatcher.py`.
  - :meth:`Dispatcher.stop_research` invokes `mathlint research-stop`.
  - :meth:`Dispatcher.read_status` invokes `mathlint research-status`.
  - :meth:`Dispatcher.run_watch` invokes `pi-monitor watch`.

All `*_live` / `*_research` methods return :class:`SubprocessResult`
which carries the typed outcome + raw stdout/stderr for diagnostics.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Protocol

from research_institution.catalog import Program
from research_institution.contracts import GateVerdict, GateVerdictStatus

# A runner is anything with the signature of subprocess.run.
# Tests inject fakes; production uses subprocess.run.
Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class Environment(Protocol):
    """Typed env-var provider. Production wraps `os.environ`.

    Defined here as well as in `tests/_fakes.py` so production code
    can declare the dependency without importing test code. The two
    definitions are structurally identical; the duplication is the
    cost of keeping tests out of the production import graph.
    """

    def get(self, name: str) -> str | None: ...
    def require(self, name: str) -> str: ...
    def copy(self) -> dict[str, str]: ...


class _OsEnviron:
    """Production Environment: wraps `os.environ`."""

    def get(self, name: str) -> str | None:
        return os.environ.get(name)

    def require(self, name: str) -> str:
        v = os.environ.get(name)
        if v is None:
            raise KeyError(f"required env var not set: {name}")
        return v

    def copy(self) -> dict[str, str]:
        return dict(os.environ)


class Clock(Protocol):
    """Wall + monotonic clock. Production uses real time."""

    def time(self) -> float: ...
    def monotonic(self) -> float: ...


class _SystemClock:
    def time(self) -> float:
        return time.time()

    def monotonic(self) -> float:
        return time.monotonic()


def _default_runner(*args: object, **kwargs: object) -> "subprocess.CompletedProcess[str]":
    """Default subprocess runner. Type-annotated loosely to allow
    test fakes with arbitrary signatures."""
    return subprocess.run(*args, **kwargs)  # type: ignore[arg-type]


@dataclass(frozen=True, slots=True)
class SubprocessResult:
    """The typed outcome of one subprocess invocation.

    Mirrors `subprocess.CompletedProcess` but typed: the dispatcher's
    callers don't have to reach into a Python-stdlib dataclass.

    `binary` is the resolved path to the binary that ran (post-`which`).
    `argv` is the literal argv list (resolved binary first).
    `returncode` is the subprocess's exit code.
    `stdout`, `stderr` are captured text streams.
    `elapsed_seconds` is wall time; 0.0 if the runner doesn't measure.
    """

    binary: str
    argv: tuple[str, ...]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    elapsed_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        """True iff the subprocess exited 0."""
        return self.returncode == 0


@dataclass(frozen=True, slots=True)
class SubprocessPolicy:
    """Per-verb subprocess policy: timeouts, cwd default, env-merging.

    Centralizes the dispatcher's "how do I run one subprocess" rules.
    Methods accept a :class:`SubprocessPolicy` override so tests can
    pin timeout behavior without subclassing the Dispatcher.

    Fields:
      - `default_timeout_seconds`: timeout for non-watch verbs
        (15s for gate, 30s for stop, 60s for status).
      - `watch_timeout_seconds`: TUI verbs run as long as the
        operator wants; default None (no timeout).
      - `inherit_env`: when True, merge the caller's environment
        into the subprocess's env. When False, only the explicit
        `extra_env` dict is passed. Default True (operator-friendly).
    """

    default_timeout_seconds: float = 15.0
    watch_timeout_seconds: Optional[float] = None
    inherit_env: bool = True


DEFAULT_POLICY = SubprocessPolicy()


@dataclass(frozen=True, slots=True)
class Dispatcher:
    """The in-process dispatcher surface.

    Constructed with optional `runner` / `environment` / `clock` /
    `policy`. Default values are production (real subprocess.run,
    real os.environ, real time). Tests inject fakes via the public
    keyword args.

    The Dispatcher does NOT do its own catalog lookup; the caller
    passes a :class:`Program` (or the program name + a catalog loader).
    This keeps the Dispatcher free of file-I/O concerns.
    """

    runner: Runner = field(default=_default_runner)
    environment: Environment = field(default=_OsEnviron())
    clock: Clock = field(default=_SystemClock())
    policy: SubprocessPolicy = field(default=DEFAULT_POLICY)

    # -----------------------------------------------------------------------
    # mathlint roadmap -> GateVerdict
    # -----------------------------------------------------------------------
    def read_gate(
        self,
        prog: Program,
        mathlint_bin: str = "mathlint",
        cwd: Optional[Path] = None,
        timeout_seconds: Optional[float] = None,
    ) -> GateVerdict:
        """Read `mathlint roadmap` and return the architecture-review gate verdict.

        Wire contract (mathlint roadmap):
          - argv: [mathlint, "roadmap"]
          - cwd: program's resolved_local_path (or override)
          - exit 0 + stdout contains `TASK KIND: <value>` -> parsed
          - exit 0 + no TASK KIND line -> status=OPEN, task_kind="(absent)"
          - exit != 0 -> status=UNKNOWN, task_kind="(roadmap-failed)"

        Raises FileNotFoundError if mathlint is not on PATH (the
        subprocess.run raises it natively; we don't catch).
        """
        workdir = cwd or prog.resolved_local_path
        result = self._run_subprocess(
            argv=[mathlint_bin, "roadmap"],
            cwd=workdir,
            timeout_seconds=timeout_seconds or self.policy.default_timeout_seconds,
        )
        if result.returncode != 0:
            return GateVerdict(
                task_kind="(roadmap-failed)",
                status=GateVerdictStatus.UNKNOWN,
                reason=f"mathlint roadmap exited {result.returncode}",
                raw_excerpt=(result.stderr or result.stdout)[-400:],
            )
        return GateVerdict.from_text(result.stdout)

    # -----------------------------------------------------------------------
    # mathlint live-run
    # -----------------------------------------------------------------------
    def run_live(
        self,
        mathlint_bin: str = "mathlint",
        cwd: Optional[Path] = None,
        extra_args: Sequence[str] = (),
        extra_env: Optional[dict[str, str]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> SubprocessResult:
        """Invoke `mathlint live-run --confirm-live`.

        Wire contract (mathlint live-run):
          - argv: [mathlint, "live-run", "--confirm-live", *extra_args]
          - exit 0 -> launched; the supervisor takes over.
          - exit != 0 -> refused; stderr explains why.

        `extra_args` is for forward-compat (mathlint flags this repo
        doesn't synthesize yet). Don't use it to bypass the gate
        check — that's what `GateVerdict` is for.
        """
        argv = [mathlint_bin, "live-run", "--confirm-live", *extra_args]
        return self._run_subprocess(
            argv=argv,
            cwd=cwd,
            extra_env=extra_env,
            timeout_seconds=timeout_seconds or self.policy.default_timeout_seconds,
        )

    # -----------------------------------------------------------------------
    # mathlint research-stop
    # -----------------------------------------------------------------------
    def stop_research(
        self,
        mathlint_bin: str = "mathlint",
        cwd: Optional[Path] = None,
        timeout_seconds: Optional[float] = None,
    ) -> SubprocessResult:
        """Invoke `mathlint research-stop`.

        Wire contract:
          - argv: [mathlint, "research-stop"]
          - exit 0 -> stop recorded; subsequent live-run is gated.
          - exit != 0 -> mathlint-side error; stderr is the diagnostic.
        """
        argv = [mathlint_bin, "research-stop"]
        return self._run_subprocess(
            argv=argv,
            cwd=cwd,
            timeout_seconds=timeout_seconds or self.policy.default_timeout_seconds,
        )

    # -----------------------------------------------------------------------
    # mathlint research-status
    # -----------------------------------------------------------------------
    def read_status(
        self,
        mathlint_bin: str = "mathlint",
        cwd: Optional[Path] = None,
        timeout_seconds: Optional[float] = None,
    ) -> SubprocessResult:
        """Invoke `mathlint research-status`.

        Wire contract:
          - argv: [mathlint, "research-status"]
          - exit 0 -> stdout is the status report (currently plain text).
          - exit != 0 -> mathlint-side error.

        NOTE: the dispatcher does NOT parse the status report; that
        belongs to mathlint's own reporter (`@ADR-0006`). This method
        returns the raw SubprocessResult so callers can decide.
        """
        argv = [mathlint_bin, "research-status"]
        return self._run_subprocess(
            argv=argv,
            cwd=cwd,
            timeout_seconds=timeout_seconds or self.policy.default_timeout_seconds,
        )

    # -----------------------------------------------------------------------
    # pi-monitor watch
    # -----------------------------------------------------------------------
    def run_watch(
        self,
        config_path: Path,
        start_script: Path,
        pi_monitor_bin: str = "pi-monitor",
        interval_seconds: float = 2.0,
        extra_env: Optional[dict[str, str]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> SubprocessResult:
        """Invoke `pi-monitor watch --config <cfg> --script <script> --interval N`.

        Wire contract (pi-monitor watch):
          - argv: [pi-monitor, "watch",
                    "--config", str(config_path),
                    "--script", str(start_script),
                    "--interval", str(interval_seconds)]
          - Requires a real TTY (Textual).
          - exit 0 -> TUI exited normally (operator hit q).
          - exit != 0 -> pi-monitor error; stderr is the diagnostic.
        """
        argv = [
            pi_monitor_bin,
            "watch",
            "--config",
            str(config_path),
            "--script",
            str(start_script),
            "--interval",
            str(interval_seconds),
        ]
        return self._run_subprocess(
            argv=argv,
            extra_env=extra_env,
            timeout_seconds=timeout_seconds or self.policy.watch_timeout_seconds,
        )

    # -----------------------------------------------------------------------
    # private helpers
    # -----------------------------------------------------------------------
    def _run_subprocess(
        self,
        argv: list[str],
        cwd: Optional[Path] = None,
        extra_env: Optional[dict[str, str]] = None,
        timeout_seconds: Optional[float] = None,
    ) -> SubprocessResult:
        """Run one subprocess; return a typed SubprocessResult.

        Env-merging policy:
          - If `policy.inherit_env` is True (default), start from
            `self.environment.copy()` and apply `extra_env` overrides.
          - If `policy.inherit_env` is False, ONLY `extra_env` is
            passed (operator opted into a hermetic env). This fixes
            a subtle bug where the previous implementation always
            copied `os.environ` even when the caller passed an
            empty dict.

        PATH resolution is delegated to the runner; this method does
        NOT pre-resolve `argv[0]`, so tests using an injected runner
        receive the literal argv and can assert its shape verbatim.
        """
        if self.policy.inherit_env:
            run_env = self.environment.copy()
        else:
            run_env = dict(extra_env) if extra_env else {}
        if extra_env:
            run_env.update(extra_env)

        kwargs: dict[str, Any] = {
            "capture_output": True,
            "text": True,
            "check": False,
            "env": run_env,
        }
        if cwd is not None:
            kwargs["cwd"] = str(cwd)
        if timeout_seconds is not None:
            kwargs["timeout"] = timeout_seconds

        t0 = self.clock.monotonic()
        completed = self.runner(argv, **kwargs)
        elapsed = self.clock.monotonic() - t0
        # For the default runner, subprocess.run resolved argv[0]
        # via PATH internally; we can re-resolve to fill the `binary`
        # field for diagnostics. For injected runners, `binary` is
        # argv[0] verbatim (the runner decides what to do with it).
        if self.runner is _default_runner:
            binary = argv[0] if Path(argv[0]).is_absolute() else (shutil.which(argv[0]) or argv[0])
        else:
            binary = argv[0]
        return SubprocessResult(
            binary=binary,
            argv=tuple(argv),
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
            elapsed_seconds=elapsed,
        )


__all__ = [
    "DEFAULT_POLICY",
    "Dispatcher",
    "Runner",
    "SubprocessPolicy",
    "SubprocessResult",
]
