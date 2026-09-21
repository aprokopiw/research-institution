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
from pathlib import Path
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol
from collections.abc import Callable, Mapping


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
    def from_args(cls, args: tuple[Any, ...], kwargs: Mapping[str, Any]) -> FakeCall:
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


# ---------------------------------------------------------------------------
# F-1: FakeMathResearchProgram — in-process research-program double
# ---------------------------------------------------------------------------


class RoadmapNotFoundError(FileNotFoundError):
    """Fake's "no roadmap found" exception.

    The OS catches by attribute lookup on the callable's module;
    because ``FakeMathResearchProgram.next_active_work`` lives in
    this module, the OS will recognize this class as the canonical
    "no roadmap" signal. Mirrors kaplansky.work_selection.
    """


class RoadmapParseError(ValueError):
    """Fake's "malformed roadmap" exception. Mirrors kaplansky.work_selection.

    The OS re-raises this (does not emit Wait) so a parse defect
    surfaces as a crash in the supervisor's catch-all.
    """


class NoActiveWorkError(LookupError):
    """Fake's "no active work" exception. Mirrors kaplansky.work_selection.

    The OS catches by attribute lookup and emits a Wait envelope
    with ``reason_code = "no_eligible_work"``.
    """


@dataclass(frozen=True, slots=True)
class FakeProgramItem:
    """One synthesized WorkRequest for FakeMathResearchProgram.

    Mirrors the shape a real research program (kaplansky, etc.)
    feeds into the dispatch envelope. Tests pass a list of these
    to :class:`FakeMathResearchProgram` to script what the program
    "decides" to dispatch on each call.
    """

    operation_id: str
    operation_kind: str = "mathlint-research"
    role: str = "research"
    workspace: str = "default"
    schema_name: str = "test.program_item/v1"
    source_identity: str = "test-research-program"


class FakeMathResearchProgram:
    """A research-program double that scripts its ``next_active_work``.

    Substitutes for a real program (e.g. kaplansky) in COMPOSE
    tests. The composition seam is the entry-point-resolved
    callable (per `@ADR-0007`): the OS looks the program up by
    catalog name in the ``mathlint.program_work_selection`` entry
    registry; this fake installs a callable under the catalog
    name the OS is asked to resolve.

    ## Behavior contract

    - ``scripted_items`` is the FIFO queue of items the callable
      returns on each call. When the queue is empty, the callable
      raises :class:`NoActiveWorkError` (matching kaplansky's
      contract) so the OS emits a ``Wait`` envelope.
    - ``fail_with`` (optional) replaces the queue: the callable
      raises whatever exception is configured. Tests use this
      to drill the ``RoadmapParseError`` -> crash path
      (COMPOSE-4) or the ``RoadmapNotFoundError`` -> wait path.
    - ``call_count`` increments on every call; tests use it to
      assert the OS retried the right number of times.
    - ``install(into, name)`` registers the fake's ``next_active_work``
      into the ``mathlint.program_work_selection`` registry under
      ``name`` so the OS can resolve it by catalog name.
    - ``register()`` is a no-op for the fake (it owns no content
      contributions; tests inject those separately if needed).

    ## Why not a real kaplansky fake?

    Per @ADR-0007 + the test-hardening plan §13 Q2: a fake
    ``kaplansky`` would couple research-institution tests to
    kaplansky's roadmap TOML shape. ``FakeMathResearchProgram``
    is program-agnostic — a future second program uses the same
    fake unchanged.
    """

    def __init__(
        self,
        scripted_items: list[FakeProgramItem] | None = None,
        *,
        fail_with: BaseException | None = None,
    ) -> None:
        self._items: list[FakeProgramItem] = list(scripted_items or [])
        self._fail_with: BaseException | None = fail_with
        self.call_count: int = 0
        self.last_repository: Path | None = None

    @property
    def scripted_items(self) -> tuple[FakeProgramItem, ...]:
        """Read-only view of remaining items (tests assert queue state)."""
        return tuple(self._items)

    def next_active_work(
        self,
        repository: Path,
        *,
        source_revision: Any,
    ) -> list[Any]:
        """The program-supplied callable. Match kaplansky's signature.

        On call:

        1. If ``fail_with`` is set, raise it (COMPOSE error drill).
        2. If queue is non-empty, pop one item, wrap it as a
           ``WorkRequest`` (re-exported via the contracts module),
           and return ``[request]``.
        3. If queue is empty, raise ``NoActiveWorkError`` (the
           OS catches this and emits a ``Wait`` envelope).
        """
        from research_institution.contracts.source_decision import WorkRequest

        self.call_count += 1
        self.last_repository = repository
        if self._fail_with is not None:
            raise self._fail_with
        if not self._items:
            # The OS catches by attribute lookup on the callable's
            # module (see _ask_program_for_work); tests._fakes must
            # expose NoActiveWorkError for the OS to recognize this
            # as a "no active work" signal (vs an unhandled crash).
            raise NoActiveWorkError("fake: queue exhausted; no active item")
        item = self._items.pop(0)
        return [
            WorkRequest(
                source_identity=item.source_identity,
                source_revision=source_revision,
                operation_id=item.operation_id,
                operation_kind=item.operation_kind,
                role=item.role,
                workspace=item.workspace,
                payload={
                    "schema_name": item.schema_name,
                    "id": item.operation_id,
                    "kind": item.operation_kind,
                },
            )
        ]

    def install(self, name: str) -> None:
        """Register this fake's callable into the work-selection registry.

        Tests call this BEFORE invoking the OS so
        ``work_selection_callables().get(name)`` returns
        ``self.next_active_work``. The registry is in
        ``mathlint.program_providers`` (kernel code); the public
        seam is :func:`set_work_selection_slot`.
        """
        try:
            from mathlint.program_providers import (
                WorkSelectionSlot,
                set_work_selection_slot,
                work_selection_callables,
            )
        except ImportError as exc:  # pragma: no cover — mathlint absent
            raise RuntimeError(
                "mathlint.program_providers not importable; install math "
                "before using FakeMathResearchProgram.install()"
            ) from exc
        # Preserve any existing entries so tests can compose multiple
        # fakes. The slot is the single seam per @ADR-0007.
        existing = dict(work_selection_callables())
        existing[name] = self.next_active_work
        set_work_selection_slot(WorkSelectionSlot(selectors=existing))

    def register(self) -> None:
        """No-op content-contribution hook. Kept for API parity.

        Intentionally empty: the fake owns no content contributions;
        tests inject those separately if needed. The docstring is
        the only body so ruff does not flag an unnecessary ``pass``.
        """


# ---------------------------------------------------------------------------
# F-4: FaultInjector — typed exception injection at boundary ports
# ---------------------------------------------------------------------------


class FaultInjector:
    """Inject a typed exception at a named boundary port.

    Used by COMPOSE tests to drill the recovery paths. The
    injector attaches to a port name (e.g. ``"work_source"``,
    ``"audit_chain"``, ``"mathlint_source"``) and a callable
    that wraps the real port call. On ``inject_once(port, exc)``
    the next call through the wrapper raises ``exc``; subsequent
    calls delegate to the real callable.

    ## Usage

        runner = FakeRunner()
        runner.queue(QueuedResponse(returncode=0, stdout="ok"))
        injector = FaultInjector()
        wrapped = injector.wrap_runner(runner)

        # First call: returns "ok"
        wrapped(("mathlint", "status"))
        # Second call: raises
        with pytest.raises(RuntimeError):
            injector.inject_once("runner", RuntimeError("simulated"))
            wrapped(("mathlint", "status"))

    The fault scope is per-instance, not global, so parallel
    tests do not collide. Tests reset the injector between
    invocations via :meth:`reset`.
    """

    def __init__(self) -> None:
        self._armed: dict[str, BaseException] = {}

    def inject_once(self, port: str, exc: BaseException) -> None:
        """Arm the injector to raise ``exc`` on the next call through ``port``."""
        self._armed[port] = exc

    def reset(self, port: str | None = None) -> None:
        """Clear armed faults. ``port=None`` clears every port."""
        if port is None:
            self._armed.clear()
        else:
            self._armed.pop(port, None)

    def consume(self, port: str) -> BaseException | None:
        """Return and clear the armed fault for ``port``, or None."""
        return self._armed.pop(port, None)

    def wrap_runner(self, runner: FakeRunner) -> FakeRunner:
        """Return a wrapper around ``runner`` that consults ``self`` first.

        The wrapper is a :class:`FakeRunner` subclass; tests that
        hold a reference to the original see no change. The
        wrapper's ``__call__`` checks ``self._armed['runner']``
        before delegating.
        """

        class _FaultedRunner(FakeRunner):
            def __init__(self, injector: FaultInjector, inner: FakeRunner) -> None:
                super().__init__()
                # Move the inner's queue into the wrapper so the
                # parent's ``__call__`` sees the queued responses.
                self._queue.extend(inner._queue)
                self._injector = injector

            def __call__(self, *args: Any, **kwargs: Any) -> Any:
                armed = self._injector.consume("runner")
                if armed is not None:
                    raise armed
                return super().__call__(*args, **kwargs)

        return _FaultedRunner(self, runner)


# ---------------------------------------------------------------------------
# F-6: InMemoryAuditChain — minimal chain recorder for research-institution
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AuditEventRecord:
    """One recorded audit-chain event.

    Mirrors math's :class:`tests.support.audit_chain_double.AuditEvent`
    shape but kept in research-institution (per the no-shared-fakes
    rule). Tests that need a chain across both repos use each
    repo's recorder; the cross-repo invariant is the
    ``prev_hash == prior.hash`` link, which is identical in both.
    """

    seq: int
    name: str
    payload: dict[str, object]
    prev_hash: str
    hash: str
    emitted_at: float


class InMemoryAuditChain:
    """Append-only, hash-linked, in-memory audit-chain double.

    Same semantics as math's :class:`AuditChainDouble`:

    - genesis ``prev_hash`` is the well-known sentinel ``"GENESIS"``;
    - every emitted event links ``prev_hash`` to the prior tail;
    - the chain is order-independent on the wall clock; the
      ``emitted_at`` field is informational only.

    Tests assert chain-validity via :meth:`assert_chain_valid`;
    if the linking breaks, the assertion names the broken
    ``seq`` so the regression is easy to localise.
    """

    GENESIS_PREV_HASH = "GENESIS"

    def __init__(self) -> None:
        self.events: list[AuditEventRecord] = []
        self._counter = 0

    def emit(self, name: str, payload: dict[str, object] | None = None) -> AuditEventRecord:
        import hashlib

        if not isinstance(name, str) or not name:
            raise ValueError("audit event name must be a non-empty string")
        body: dict[str, object] = dict(payload) if payload is not None else {}
        self._counter += 1
        prev_hash = self.events[-1].hash if self.events else self.GENESIS_PREV_HASH
        payload_bytes = repr(sorted(body.items())).encode("utf-8")
        digest = hashlib.sha256(
            f"{self._counter}|{name}|{prev_hash}|".encode() + payload_bytes
        ).hexdigest()
        event = AuditEventRecord(
            seq=self._counter,
            name=name,
            payload=body,
            prev_hash=prev_hash,
            hash=digest,
            emitted_at=0.0,
        )
        self.events.append(event)
        return event

    def assert_chain_valid(self) -> None:
        expected_prev = self.GENESIS_PREV_HASH
        for event in self.events:
            if event.prev_hash != expected_prev:
                raise AssertionError(
                    f"audit-chain break at seq={event.seq}: "
                    f"prev_hash={event.prev_hash!r} != expected={expected_prev!r}"
                )
            expected_prev = event.hash


# ---------------------------------------------------------------------------
# F-7: BoundarySpy — record every call through a port for assertion
# ---------------------------------------------------------------------------


class BoundarySpy:
    """Wrap a callable to record every call (port-name, args, kwargs, return).

    Used to assert that the OS invokes a port the expected
    number of times with the expected arguments. The spy is
    passive (it records; it does not inject), so it composes
    cleanly with :class:`FaultInjector`.

    ## Usage

        spy = BoundarySpy()
        runner = FakeRunner()
        runner.queue(QueuedResponse(returncode=0, stdout="ok"))
        wrapped = spy.wrap("runner", runner)
        wrapped(("mathlint", "status"))

        assert spy.call_count("runner") == 1
        assert spy.calls("runner")[0].args == (("mathlint", "status"),)
    """

    @dataclass(frozen=True, slots=True)
    class Call:
        args: tuple[Any, ...]
        kwargs: dict[str, Any]
        result: Any

    def __init__(self) -> None:
        self._calls: dict[str, list[BoundarySpy.Call]] = {}

    def wrap(self, port: str, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Return a wrapper around ``fn`` that records every call under ``port``."""
        calls = self._calls.setdefault(port, [])

        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            result = fn(*args, **kwargs)
            calls.append(BoundarySpy.Call(args=args, kwargs=dict(kwargs), result=result))
            return result

        # Preserve __name__ so debug logs are readable.
        import contextlib
        with contextlib.suppress(AttributeError):
            _wrapped.__name__ = getattr(fn, "__name__", port)  # type: ignore[attr-defined]
        return _wrapped

    def call_count(self, port: str) -> int:
        return len(self._calls.get(port, []))

    def calls(self, port: str) -> tuple[BoundarySpy.Call, ...]:
        return tuple(self._calls.get(port, []))

    def reset(self, port: str | None = None) -> None:
        if port is None:
            self._calls.clear()
        else:
            self._calls.pop(port, None)


# ---------------------------------------------------------------------------
# F-2: FakeCatalog — construct a Program directly without writing TOML


def make_fake_program(
    name: str = "test-research-program",
    *,
    local_path: str | None = None,
    entry_point: str | None = None,
    program_markers: tuple[str, ...] = ("programs/test-research-program-roadmap.toml",),
) -> Any:
    """Construct a :class:`Program` for tests without writing TOML.

    The OS resolves the supervised program's identity from the
    catalog. Tests that exercise the OS's catalog-driven
    resolution need a :class:`Program` whose ``local_path`` (or
    whose ``program_markers``) point at a tmp-path repo, NOT at
    the operator's wired kaplansky checkout. This helper skips
    the TOML round-trip and returns the dataclass directly.

    Field defaults are calibrated to the
    research-institution/tests contract:

    - ``name`` defaults to ``"test-research-program"`` so it
      matches the :class:`FakeMathResearchProgram` default and the
      institution's repo-boundary check.
    - ``local_path`` defaults to ``"/tmp/<name>"``; the caller
      is responsible for creating that directory and writing the
      marker file before the OS runs.
    - ``entry_point`` defaults to ``f"{name}.mathlint_plugin:register"``
      so it's a valid module:attr spec without naming a real
      program.
    - ``program_markers`` defaults to a single roadmap TOML inside
      a ``programs/`` directory — the OS's secondary match path.

    Tests that need a *full* catalog list (e.g. green-gate tests)
    should construct each entry with this helper and pass them to
    the green-gate driver.
    """
    from research_institution.catalog import Program

    if local_path is None:
        # Use tempfile under ``/tmp``-equivalent; the OS resolves
        # ``$HOME`` so a per-test home directory works. Test code
        # always passes an explicit ``local_path`` (pytest tmp_path),
        # so this default only matters for sanity-check scripts.
        import tempfile
        local_path = str(Path(tempfile.gettempdir()) / name)
    if entry_point is None:
        entry_point = f"{name}.mathlint_plugin:register"
    return Program(
        name=name,
        display_name=f"Test Program ({name})",
        repository=f"https://example.com/{name}.git",
        entry_point=entry_point,
        local_path=local_path,
        mathlint_pin="main",
        live_credentials_required=False,
        live_credential_env_vars=(),
        check_program_script="scripts/check-program-institution.sh",
        program_markers=program_markers,
    )


# ---------------------------------------------------------------------------
# F-5: ScriptedSource — generic external-source double (probe shape)
# ---------------------------------------------------------------------------


class ScriptedSource:
    """A queue-driven external-source double.

    Used by COMPOSE-1 + COMPOSE-2 to script the WorkSourceProvider's
    sequence of ``Dispatch`` / ``Wait`` envelopes without spinning
    up a real subprocess. Each ``ScriptedSource.feed(envelope)``
    queues one envelope; :meth:`pull` dequeues in FIFO order.

    Falls back to ``raise AssertionError`` when the queue is empty
    so test-setup mistakes fail loudly instead of returning a
    stale default that masks the real bug (per the prime
    directive: surfaces fail loud, not silently GREEN).
    """

    def __init__(self) -> None:
        self._queue: list[Any] = []
        self.pull_count: int = 0

    def feed(self, envelope: Any) -> None:
        """Queue one envelope (Dispatch, Wait, OperatorRequired, Stop)."""
        self._queue.append(envelope)

    def feed_many(self, envelopes: list[Any]) -> None:
        for env in envelopes:
            self.feed(env)

    def pull(self) -> Any:
        """Pop and return the next queued envelope. Raises if empty."""
        self.pull_count += 1
        if not self._queue:
            raise AssertionError(
                f"ScriptedSource: pull #{self.pull_count} but queue empty"
            )
        return self._queue.pop(0)

    @property
    def queued(self) -> int:
        return len(self._queue)


__all__ = [
    "AuditEventRecord",
    "BoundarySpy",
    "Clock",
    "Environment",
    "FakeCall",
    "FakeClock",
    "FakeEnvironment",
    "FakeMathResearchProgram",
    "FakeProgramItem",
    "FakeRunner",
    "FaultInjector",
    "InMemoryAuditChain",
    "NoActiveWorkError",
    "OsEnviron",
    "QueuedResponse",
    "RecordingEnvironment",
    "RoadmapNotFoundError",
    "RoadmapParseError",
    "ScriptedSource",
    "SystemClock",
    "is_executable",
    "make_fake_program",
    "scoped_env",
]
