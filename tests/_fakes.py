"""Shared test infrastructure: fakes, fixtures, env injection.

Every test in this repo that touches subprocess or env vars should
use the helpers here. Centralizing prevents the "every test
re-implements FakeRunner" pattern that caused the conftest-PATH-strip
bug earlier.

Public surface:

  - :class:`FakeRunner` -- a queue-driven `subprocess.run` double
    that records every call and returns queued responses. The same
    class can drive every Dispatcher method.

  - :class:`FakeClock` -- monotonic + wall-clock injection. Tests
    can advance time deterministically instead of sleeping.

  - :class:`FakeEnvironment` -- typed env-var provider. Tests
    construct one with a dict; production wraps `os.environ`.

  - :class:`RecordingEnv` -- like FakeEnvironment but records every
    lookup, so tests can assert which env vars the dispatcher read.

Import path note: this module is in `tests/` and is NOT shipped.
Production code never imports it. The dispatcher uses real
`subprocess.run` + `os.environ`; tests inject fakes via the
public `runner=` and `env=` keyword args.
"""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


# ---------------------------------------------------------------------------
# Environment protocol + fakes
# ---------------------------------------------------------------------------


class Environment(Protocol):
    """Typed env-var provider. Production wraps `os.environ`.

    Tests implement this with a dict-backed fake. The protocol lets
    the dispatcher's path/env code be unit-tested without monkeypatching
    `os.environ` (which is global and unsafe across parallel tests).
    """

    def get(self, name: str) -> str | None: ...
    def require(self, name: str) -> str: ...
    def copy(self) -> dict[str, str]: ...


class OsEnviron:
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


@dataclass(frozen=True, slots=True)
class FakeEnvironment:
    """Dict-backed Environment. Tests construct with a literal dict."""

    values: Mapping[str, str]

    def get(self, name: str) -> str | None:
        return self.values.get(name)

    def require(self, name: str) -> str:
        if name not in self.values:
            raise KeyError(f"required env var not set: {name}")
        return self.values[name]

    def copy(self) -> dict[str, str]:
        return dict(self.values)


@dataclass
class RecordingEnvironment:
    """Wraps another Environment and records every lookup.

    Use to assert "the dispatcher read MATHLINT_MODEL_ROUTE but not
    PI_MONITOR_REPO" without coupling to monkeypatch order.
    """

    inner: Environment
    reads: list[str] = field(default_factory=list)

    def get(self, name: str) -> str | None:
        self.reads.append(name)
        return self.inner.get(name)

    def require(self, name: str) -> str:
        self.reads.append(name)
        return self.inner.require(name)

    def copy(self) -> dict[str, str]:
        return self.inner.copy()


@contextmanager
def scoped_env(values: Mapping[str, str]) -> Iterator[FakeEnvironment]:
    """Yield a FakeEnvironment pre-populated with the given values.

    Tests use this instead of `monkeypatch.setenv` so the dispatcher's
    Environment-injected code path is exercised. monkeypatch is fine
    for code that reads `os.environ` directly (today's cli.py), but
    new code should accept an `Environment` and use this context.
    """
    yield FakeEnvironment(values=values)


class _IterableProtocol(Protocol):
    """Iterable protocol marker for type annotations.

    Defined locally so we don't import `collections.abc.Iterable`
    separately from the imports above; keeps the file self-contained.
    """

    def __iter__(self) -> Iterator[object]: ...


# ---------------------------------------------------------------------------
# Subprocess runner fakes
# ---------------------------------------------------------------------------


@dataclass
class QueuedResponse:
    """One canned response for the FakeRunner queue."""

    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class FakeRunner:
    """A test double for `subprocess.run`.

    Records every call; returns queued responses in FIFO order. If a
    call is made with no queued response, raises AssertionError so
    test-setup mistakes fail loudly downstream (instead of returning
    a generic rc=0 that masks the real bug).

    Usage:

        runner = FakeRunner()
        runner.queue(QueuedResponse(returncode=0, stdout="ok"))
        result = Dispatcher(runner=runner).run_live()
        assert runner.calls[0].argv == ["mathlint", "live-run", ...]
    """

    def __init__(self) -> None:
        self.calls: list[FakeCall] = []
        self._queue: list[QueuedResponse] = []

    def queue(self, response: QueuedResponse) -> None:
        """Append one canned response to the queue."""
        self._queue.append(response)

    def queue_many(self, responses: Iterable[QueuedResponse]) -> None:
        for r in responses:
            self.queue(r)

    def __call__(self, *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        call = FakeCall.from_args(args, kwargs)
        self.calls.append(call)
        if not self._queue:
            raise AssertionError(
                f"FakeRunner: no queued response for call #{len(self.calls)} "
                f"argv={call.argv} kwargs={list(kwargs)}"
            )
        response = self._queue.pop(0)
        # Use the actual argv that was passed (so result.args matches).
        return subprocess.CompletedProcess(
            call.argv,
            response.returncode,
            stdout=response.stdout,
            stderr=response.stderr,
        )


@dataclass(frozen=True, slots=True)
class FakeCall:
    """One recorded call to the FakeRunner."""

    argv: tuple[str, ...]
    cwd: str | None
    env: Mapping[str, str] | None
    timeout: float | None
    kwargs: Mapping[str, Any]

    @classmethod
    def from_args(cls, args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> "FakeCall":
        argv = tuple(args[0]) if args else ()
        return cls(
            argv=argv,
            cwd=kwargs.get("cwd"),
            env=kwargs.get("env"),
            timeout=kwargs.get("timeout"),
            kwargs={k: v for k, v in kwargs.items() if k not in {"cwd", "env", "timeout"}},
        )


# ---------------------------------------------------------------------------
# Clock injection
# ---------------------------------------------------------------------------


class Clock(Protocol):
    """Wall + monotonic clock. Production uses time.time / time.monotonic."""

    def time(self) -> float: ...
    def monotonic(self) -> float: ...


class SystemClock:
    """Production clock: real time.time / time.monotonic."""

    def time(self) -> float:
        return time.time()

    def monotonic(self) -> float:
        return time.monotonic()


@dataclass
class FakeClock:
    """Deterministic clock. Tests advance `now` explicitly."""

    now: float = 0.0
    monotonic_now: float = 0.0

    def time(self) -> float:
        return self.now

    def monotonic(self) -> float:
        return self.monotonic_now

    def advance(self, seconds: float) -> None:
        """Move both clocks forward by `seconds`."""
        self.now += seconds
        self.monotonic_now += seconds

    def set(self, unix: float) -> None:
        """Set the wall clock to a specific Unix timestamp."""
        self.now = unix


# ---------------------------------------------------------------------------
# Path resolution helpers
# ---------------------------------------------------------------------------


def is_executable(path: str | os.PathLike[str]) -> bool:
    """Cross-platform executable check. Tests use this to verify shims."""
    import stat as _stat

    try:
        st = os.stat(path)
    except (OSError, TypeError):
        return False
    return bool(st.st_mode & _stat.S_IXUSR)


__all__ = [
    "Clock",
    "Environment",
    "FakeCall",
    "FakeClock",
    "FakeEnvironment",
    "FakeRunner",
    "OsEnviron",
    "QueuedResponse",
    "RecordingEnvironment",
    "SystemClock",
    "is_executable",
    "scoped_env",
]
