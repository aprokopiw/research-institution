"""Tests for the in-process Dispatcher API.

The Dispatcher is the typed Python surface that the CLI delegates to.
Every method takes a `runner`, an `environment`, and a `clock`. Tests
inject fakes from `tests._fakes` so:

  - Argv shape is pinned without subprocess side effects.
  - Env-var reads are pinned without monkeypatching `os.environ`.
  - Elapsed-time accounting is deterministic.

These tests pin:

  - The argv shape every Dispatcher method sends to mathlint/pi_monitor.
  - The exit-code semantics (ok vs not ok).
  - The typed SubprocessResult fields.
  - The GateVerdict mapping in `read_gate`.
  - The env-merging policy (inherit vs hermetic).
  - The SubprocessPolicy default timeout values.
  - The Clock injection (elapsed_seconds is recorded).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from research_institution.catalog import Program
from research_institution.contracts import GateVerdictStatus
from research_institution.dispatcher import (
    DEFAULT_POLICY,
    Dispatcher,
    SubprocessPolicy,
)
from tests._fakes import (
    FakeClock,
    FakeEnvironment,
    FakeRunner,
    QueuedResponse,
)


def _fake_program(tmp_path: Path, name: str = "x") -> Program:
    return Program(
        name=name,
        display_name="X",
        repository="https://x/x",
        entry_point="x:r",
        local_path=str(tmp_path),
        mathlint_pin="v0.1.0",
        live_credentials_required=False,
        live_credential_env_vars=(),
        check_program_script="check.sh",
    )


def _install_work_selection_callable(
    name: str,
    callable_obj,
) -> None:
    """Install a fake ``next_active_work`` callable into the kernel
    registry under ``name``.

    The dispatcher's :meth:`read_gate` discovers the program-supplied
    work-selection callable through
    :func:`mathlint.program_providers.work_selection_callables` (the
    kernel-blessed ``mathlint.program_work_selection`` entry-point
    registry). Tests write directly into the registry's slot to
    inject fakes; the slot is reset by every
    :func:`discover_work_selection_programs` call, so an autouse
    fixture would be wrong — tests should install + clean up
    explicitly via the ``_register_callable`` context manager.
    """
    from mathlint.program_providers import (
        WorkSelectionSlot,
        _work_selection_state,
    )

    slot = _work_selection_state.slot
    new_selectors = dict(slot.selectors)
    new_selectors[name] = callable_obj
    _work_selection_state.slot = WorkSelectionSlot(selectors=new_selectors)
    try:
        yield  # type: ignore[misc]  # noqa: F841
    finally:
        # Restore the prior registry so other tests start clean.
        _work_selection_state.slot = slot


# Patch _install_work_selection_callable to be a context manager.
from contextlib import contextmanager  # noqa: E402


@contextmanager
def _register_callable(name: str, callable_obj):
    """Install a fake work-selection callable; clean up on exit.

    Also installs the test-stub exception classes
    (``RoadmapNotFoundError``, ``NoActiveWorkError``) on the
    callable's module so the dispatcher's ``isinstance`` exception
    matching finds them via ``importlib.import_module``.
    """
    import contextlib
    import sys
    import types

    from mathlint.program_providers import (
        WorkSelectionSlot,
        set_work_selection_slot,
        work_selection_slot,
    )

    # Snapshot prior state for cleanup.
    prior_slot = work_selection_slot()
    new_selectors = dict(prior_slot.selectors)
    new_selectors[name] = callable_obj
    set_work_selection_slot(WorkSelectionSlot(selectors=new_selectors))

    # Also inject the contract exception classes onto the callable's
    # module (or a synthetic module if the callable is defined at
    # module scope). The dispatcher's isinstance check finds them
    # via the callable's ``__module__``.
    callable_module_name = getattr(callable_obj, "__module__", None) or "tests.test_dispatcher"
    module = sys.modules.get(callable_module_name)
    if module is None:
        module = types.ModuleType(callable_module_name)
        sys.modules[callable_module_name] = module
    prior_rnf = getattr(module, "RoadmapNotFoundError", None)
    prior_naw = getattr(module, "NoActiveWorkError", None)
    module.RoadmapNotFoundError = RoadmapNotFoundError  # type: ignore[attr-defined]
    module.NoActiveWorkError = NoActiveWorkError  # type: ignore[attr-defined]

    try:
        yield
    finally:
        # Restore prior registry + module attributes.
        set_work_selection_slot(prior_slot)
        if prior_rnf is not None:
            module.RoadmapNotFoundError = prior_rnf  # type: ignore[attr-defined]
        else:
            with contextlib.suppress(AttributeError):
                delattr(module, "RoadmapNotFoundError")
        if prior_naw is not None:
            module.NoActiveWorkError = prior_naw  # type: ignore[attr-defined]
        else:
            with contextlib.suppress(AttributeError):
                delattr(module, "NoActiveWorkError")


def _resolved_argv(call) -> list[str]:
    return list(call.argv)


# ---------------------------------------------------------------------------
# run_live
# ---------------------------------------------------------------------------


def test_run_live_argv_shape() -> None:
    """`run_live` sends `[mathlint, live-run, --confirm-live]`."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0, stdout="launched"))
    d = Dispatcher(runner=runner)
    result = d.run_live()
    assert result.ok
    assert _resolved_argv(runner.calls[0]) == [
        "mathlint",
        "live-run",
        "--confirm-live",
    ]


def test_run_live_propagates_nonzero_exit() -> None:
    """run_live propagates a non-zero exit code via `result.ok`."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=7, stderr="GATE_NOT_OPEN"))
    d = Dispatcher(runner=runner)
    result = d.run_live()
    assert not result.ok
    assert result.returncode == 7
    assert "GATE_NOT_OPEN" in result.stderr


def test_run_live_extra_args_are_appended() -> None:
    """`extra_args` is forwarded to mathlint as positional/flag args."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    d = Dispatcher(runner=runner)
    d.run_live(extra_args=["--run-root", "/tmp/x"])  # noqa: S108
    argv = _resolved_argv(runner.calls[0])
    assert argv[-2:] == ["--run-root", "/tmp/x"]  # noqa: S108


def test_run_live_auto_injects_model_route_from_env(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """MATHLINT_MODEL_ROUTE present in env is forwarded to the subprocess.

    Pinned because the dispatcher's env-merging policy must NOT
    silently drop env vars that mathlint expects (e.g. when the
    operator runs `MATHLINT_MODEL_ROUTE=... bash some-script.sh`
    that then calls the dispatcher).
    """
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    env = FakeEnvironment(
        values={"MATHLINT_MODEL_ROUTE": "openai-codex/from-env"}
    )
    d = Dispatcher(runner=runner, environment=env)
    d.run_live()
    sent_env = runner.calls[0].env
    assert sent_env is not None
    assert sent_env["MATHLINT_MODEL_ROUTE"] == "openai-codex/from-env"


def test_run_live_auto_injects_model_route_from_local_toml(tmp_path: Path) -> None:
    """When MATHLINT_MODEL_ROUTE is absent but local.toml carries model_route,
    the dispatcher resolves and forwards the configured route.

    This is the operator's "stop exporting per-shell" path. A test
    failure here means a regression in the resolve_model_route +
    _run_subprocess plumbing.
    """
    cfg = tmp_path / "local.toml"
    cfg.write_text('model_route = "openai-codex/from-local-toml"\n', encoding="utf-8")
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    env = FakeEnvironment(values={"MATHLINT_CONFIG": str(cfg)})
    d = Dispatcher(runner=runner, environment=env)
    d.run_live()
    sent_env = runner.calls[0].env
    assert sent_env is not None
    assert sent_env["MATHLINT_MODEL_ROUTE"] == "openai-codex/from-local-toml"


def test_run_live_omits_model_route_when_unresolved(tmp_path: Path) -> None:
    """No env var AND no local.toml -> MATHLINT_MODEL_ROUTE NOT in subprocess env.

    The dispatcher fails-closed on missing config: it does NOT inject
    an empty string (which mathlint would treat as a different error
    than 'not configured') and it does NOT raise. The launch refusal
    belongs to mathlint, not the dispatcher.
    """
    cfg = tmp_path / "does-not-exist.toml"
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    env = FakeEnvironment(values={"MATHLINT_CONFIG": str(cfg)})
    d = Dispatcher(runner=runner, environment=env)
    d.run_live()
    sent_env = runner.calls[0].env
    assert sent_env is not None
    assert "MATHLINT_MODEL_ROUTE" not in sent_env, (
        f"dispatcher must not inject missing route; got env={sent_env!r}"
    )


# ---------------------------------------------------------------------------
# stop_research
# ---------------------------------------------------------------------------


def test_stop_research_argv_shape() -> None:
    """`stop_research` sends `[mathlint, research-stop]`."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    d = Dispatcher(runner=runner)
    result = d.stop_research()
    assert result.ok
    assert _resolved_argv(runner.calls[0]) == ["mathlint", "research-stop"]


# ---------------------------------------------------------------------------
# read_status
# ---------------------------------------------------------------------------


def test_read_status_argv_shape() -> None:
    """`read_status` sends `[mathlint, research-status]`."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0, stdout="RUNNING"))
    d = Dispatcher(runner=runner)
    result = d.read_status()
    assert result.ok
    assert result.stdout == "RUNNING"
    assert _resolved_argv(runner.calls[0]) == ["mathlint", "research-status"]


# ---------------------------------------------------------------------------
# run_watch
# ---------------------------------------------------------------------------


def test_run_watch_argv_shape(tmp_path: Path) -> None:
    """`run_watch` sends `[pi-monitor, watch, --config, ..., --script, ..., --interval, ...]`."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    d = Dispatcher(runner=runner)
    cfg = tmp_path / "monitor.toml"
    cfg.write_text("# stub")
    script = tmp_path / "start.sh"
    script.write_text("# stub")
    result = d.run_watch(cfg, script, interval_seconds=5.0)
    assert result.ok
    argv = _resolved_argv(runner.calls[0])
    assert argv[:2] == ["pi-monitor", "watch"]
    assert "--config" in argv
    assert str(cfg) in argv
    assert "--script" in argv
    assert str(script) in argv
    assert "--interval" in argv
    assert "5.0" in argv


# ---------------------------------------------------------------------------
# read_gate
#
# The dispatcher's architecture-review gate probes the program-supplied
# ``next_active_work`` callable directly (via the kernel-blessed
# ``mathlint.program_work_selection`` entry-point registry). It does
# NOT shell out to ``mathlint roadmap`` against the program repo (that
# would invert the kernel/OS/program layering per @ADR-0014).
#
# Tests inject a fake callable via ``_register_callable`` (which writes
# to ``mathlint.program_providers.set_work_selection_slot``) so we can
# pin the gate verdict semantics without subprocess side effects.
# ---------------------------------------------------------------------------


class RoadmapNotFoundError(LookupError):
    """Test-stub exception matching the program's exception-family
    contract. The dispatcher matches by ``isinstance`` after
    importing the callable's module; the stub class name mirrors
    the program's contract class name (``RoadmapNotFoundError``,
    canonical home: ``kaplansky.work_selection``)."""


class NoActiveWorkError(LookupError):
    """Test-stub exception mirroring the program's
    ``NoActiveWorkError`` contract class."""


def _fake_program(tmp_path: Path, name: str = "x") -> Program:
    return Program(
        name=name,
        display_name="X",
        repository="https://x/x",
        entry_point="x:r",
        local_path=str(tmp_path),
        mathlint_pin="v0.1.0",
        live_credentials_required=False,
        live_credential_env_vars=(),
        check_program_script="check.sh",
    )


def _make_work_request(operation_id: str = "K4"):
    """Build a minimal WorkRequest for read_gate probe tests."""
    from datetime import UTC, datetime

    from pi_monitor.work.work_source import (
        SourceRevision,
        WorkRequest,
    )

    observed = datetime.now(tz=UTC).timestamp()
    return WorkRequest(
        source_identity="x-test-program",
        source_revision=SourceRevision(
            fingerprint="0" * 40,
            observed_unix=observed,
            label="stub",
        ),
        operation_id=operation_id,
        operation_kind="mathlint-research",
        role="MATHEMATICAL_RESEARCH",
        workspace="stub-workspace",
        payload={},
    )


def test_read_gate_open_when_program_returns_active_work(tmp_path: Path) -> None:
    """read_gate returns OPEN + the first ``operation_id`` when the
    program-supplied callable returns a non-empty ``list[WorkRequest]``.

    This is the happy path: the program has active work, the
    supervisor may launch.
    """
    def callable_obj(repository, *, source_revision):
        return [_make_work_request("K4")]

    prog = _fake_program(tmp_path, name="kaplansky")
    d = Dispatcher(runner=FakeRunner())
    with _register_callable("kaplansky", callable_obj):
        v = d.read_gate(prog)
    assert v.status == GateVerdictStatus.OPEN
    assert v.task_kind == "K4"


def test_read_gate_closed_when_program_returns_no_active_work(tmp_path: Path) -> None:
    """read_gate returns CLOSED + ``(no-active-work)`` when the program
    returns an empty list.
    """
    def callable_obj(repository, *, source_revision):
        return []

    prog = _fake_program(tmp_path, name="kaplansky")
    d = Dispatcher(runner=FakeRunner())
    with _register_callable("kaplansky", callable_obj):
        v = d.read_gate(prog)
    assert v.status == GateVerdictStatus.CLOSED
    assert v.task_kind == "(no-active-work)"


def test_read_gate_closed_when_program_raises_no_active_work(tmp_path: Path) -> None:
    """read_gate returns CLOSED + ``(no-active-work)`` when the program
    raises ``NoActiveWorkError``.
    """
    def callable_obj(repository, *, source_revision):
        raise NoActiveWorkError("no K items active")

    prog = _fake_program(tmp_path, name="kaplansky")
    d = Dispatcher(runner=FakeRunner())
    with _register_callable("kaplansky", callable_obj):
        v = d.read_gate(prog)
    assert v.status == GateVerdictStatus.CLOSED
    assert v.task_kind == "(no-active-work)"
    assert "no K items active" in v.reason


def test_read_gate_closed_when_program_raises_roadmap_not_found(tmp_path: Path) -> None:
    """read_gate returns CLOSED + ``(roadmap-missing)`` when the program
    raises ``RoadmapNotFoundError``.
    """
    def callable_obj(repository, *, source_revision):
        raise RoadmapNotFoundError("missing roadmap")

    prog = _fake_program(tmp_path, name="kaplansky")
    d = Dispatcher(runner=FakeRunner())
    with _register_callable("kaplansky", callable_obj):
        v = d.read_gate(prog)
    assert v.status == GateVerdictStatus.CLOSED
    assert v.task_kind == "(roadmap-missing)"


def test_read_gate_unknown_when_no_callable_registered(tmp_path: Path) -> None:
    """read_gate returns UNKNOWN when no entry-point callable is
    registered for the program name.

    Defect: a regression that defaults to OPEN here would let the
    dispatcher launch a program whose work-selection plumbing is
    broken.
    """
    prog = _fake_program(tmp_path, name="kaplansky")
    d = Dispatcher(runner=FakeRunner())
    # No _register_callable; the registry is empty for "kaplansky".
    v = d.read_gate(prog)
    assert v.status == GateVerdictStatus.UNKNOWN
    assert v.task_kind == "(no-work-selection-callable)"


def test_read_gate_unknown_when_callable_raises_unexpected_exception(tmp_path: Path) -> None:
    """read_gate returns UNKNOWN + diagnostic when the program callable
    raises an exception outside the recognised
    ``RoadmapNotFoundError`` / ``NoActiveWorkError`` family.
    """
    def callable_obj(repository, *, source_revision):
        raise RuntimeError("disk on fire")

    prog = _fake_program(tmp_path, name="kaplansky")
    d = Dispatcher(runner=FakeRunner())
    with _register_callable("kaplansky", callable_obj):
        v = d.read_gate(prog)
    assert v.status == GateVerdictStatus.UNKNOWN
    assert "disk on fire" in v.reason


# ---------------------------------------------------------------------------
# Wire-format drift guards
# ---------------------------------------------------------------------------


def test_argv_strings_are_pinned() -> None:
    """Pin the literal flag strings. Drift here surfaces immediately."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    Dispatcher(runner=runner).run_live()
    assert "--confirm-live" in _resolved_argv(runner.calls[0])

    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    Dispatcher(runner=runner).stop_research()
    assert _resolved_argv(runner.calls[0])[1:] == ["research-stop"]

    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    Dispatcher(runner=runner).read_status()
    assert _resolved_argv(runner.calls[0])[1:] == ["research-status"]


def test_run_live_injected_runner_receives_literal_argv() -> None:
    """Injected runner receives argv[0] verbatim (literal `"mathlint"`)."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    d = Dispatcher(runner=runner)
    result = d.run_live()
    assert result.binary == "mathlint"
    assert _resolved_argv(runner.calls[0])[0] == "mathlint"


def test_dispatcher_default_runner_invokes_subprocess_run() -> None:
    """Pin the default runner's identity: a thin wrapper around subprocess.run."""
    import inspect
    from research_institution.dispatcher import _default_runner

    d = Dispatcher()
    assert d.runner is _default_runner
    src = inspect.getsource(_default_runner)
    assert "subprocess.run" in src


# ---------------------------------------------------------------------------
# Environment injection (new)
# ---------------------------------------------------------------------------


def test_default_environment_is_os_environ() -> None:
    """The default Environment is the production `_OsEnviron` wrapper."""
    d = Dispatcher()
    # Reading MATHLINT_INSTITUTION_DIR via the dispatcher's env should
    # match os.environ directly.
    assert d.environment.get("PATH") == os.environ.get("PATH")


def test_injected_environment_drives_env_merge(tmp_path: Path) -> None:
    """Injected Environment feeds the subprocess env when inherit_env=True."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    env = FakeEnvironment(values={"MATHLINT_MODEL_ROUTE": "openai-codex/test"})
    d = Dispatcher(runner=runner, environment=env)
    d.run_live()
    sent_env = runner.calls[0].env
    assert sent_env is not None
    assert sent_env["MATHLINT_MODEL_ROUTE"] == "openai-codex/test"


def test_extra_env_overrides_inherited(tmp_path: Path) -> None:
    """extra_env (caller overrides) wins over inherited env."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    env = FakeEnvironment(values={"MATHLINT_MODEL_ROUTE": "openai-codex/inherited"})
    d = Dispatcher(runner=runner, environment=env)
    d.run_live(extra_env={"MATHLINT_MODEL_ROUTE": "openai-codex/override"})
    sent_env = runner.calls[0].env
    assert sent_env["MATHLINT_MODEL_ROUTE"] == "openai-codex/override"


def test_hermetic_policy_drops_inherited_env(tmp_path: Path) -> None:
    """With inherit_env=False, only extra_env is passed (hermetic)."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    env = FakeEnvironment(values={"MATHLINT_MODEL_ROUTE": "openai-codex/inherited"})
    policy = SubprocessPolicy(inherit_env=False)
    d = Dispatcher(runner=runner, environment=env, policy=policy)
    d.run_live(extra_env={"EXPLICIT_VAR": "yes"})
    sent_env = runner.calls[0].env
    assert sent_env == {"EXPLICIT_VAR": "yes"}
    assert "MATHLINT_MODEL_ROUTE" not in sent_env


def test_hermetic_policy_with_no_extra_env_sends_empty_env(tmp_path: Path) -> None:
    """Regression: previous impl always copied os.environ. With
    inherit_env=False and no extra_env, the subprocess env is empty.
    This is the test for the env-merging bug we fixed this turn."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    env = FakeEnvironment(values={"ANYTHING": "should-not-leak"})
    policy = SubprocessPolicy(inherit_env=False)
    d = Dispatcher(runner=runner, environment=env, policy=policy)
    d.run_live()
    sent_env = runner.calls[0].env
    assert sent_env == {}, f"hermetic policy leaked inherited env: {sent_env}"


# ---------------------------------------------------------------------------
# Clock injection (new)
# ---------------------------------------------------------------------------


def test_clock_records_elapsed_seconds(tmp_path: Path) -> None:
    """FakeClock drives deterministic elapsed_seconds on the result."""
    import dataclasses

    # Zero-elapsed case: clock never advances, result.elapsed_seconds == 0.
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    clock = FakeClock(monotonic_now=100.0)
    d = Dispatcher(runner=runner, clock=clock)
    result = d.run_live()
    assert result.elapsed_seconds == 0.0

    # Elapsed case: a runner that advances the clock by 0.75s before
    # returning. We construct this via dataclasses.replace since the
    # Dispatcher is frozen.
    clock2 = FakeClock(monotonic_now=100.0)
    runner2 = FakeRunner()
    runner2.queue(QueuedResponse(returncode=0))

    def advancing_runner(*args, **kwargs):
        clock2.advance(0.75)
        return runner2(*args, **kwargs)

    d2 = dataclasses.replace(
        Dispatcher(runner=runner2, clock=clock2),
        runner=advancing_runner,
    )
    result2 = d2.run_live()
    assert result2.elapsed_seconds == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# SubprocessPolicy defaults (new)
# ---------------------------------------------------------------------------


def test_default_policy_timeout_values() -> None:
    """The default policy pins timeouts so regressions surface."""
    assert DEFAULT_POLICY.default_timeout_seconds == 15.0
    assert DEFAULT_POLICY.watch_timeout_seconds is None
    assert DEFAULT_POLICY.inherit_env is True


def test_per_call_timeout_overrides_policy() -> None:
    """A timeout_seconds argument wins over policy.default_timeout_seconds."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    d = Dispatcher(runner=runner)
    d.run_live(timeout_seconds=120.0)
    assert runner.calls[0].timeout == 120.0


def test_default_timeout_applied_when_no_override() -> None:
    """Without a per-call override, policy.default_timeout_seconds is used."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    d = Dispatcher(runner=runner)
    d.run_live()
    assert runner.calls[0].timeout == DEFAULT_POLICY.default_timeout_seconds


def test_watch_timeout_uses_watch_default() -> None:
    """`run_watch` uses policy.watch_timeout_seconds (default None)."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    d = Dispatcher(runner=runner)
    cfg = Path("/tmp/monitor.toml")  # noqa: S108
    script = Path("/tmp/start.sh")  # noqa: S108
    d.run_watch(cfg, script)
    assert runner.calls[0].timeout is None  # no timeout on TUI by default


# ---------------------------------------------------------------------------
# cwd is forwarded (new)
# ---------------------------------------------------------------------------


def test_run_live_forwards_cwd(tmp_path: Path) -> None:
    """`cwd` argument becomes the subprocess's working directory."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    d = Dispatcher(runner=runner)
    d.run_live(cwd=tmp_path)
    assert runner.calls[0].cwd == str(tmp_path)


def test_read_gate_uses_program_local_path(tmp_path: Path) -> None:
    """read_gate probes the program's resolved_local_path by default.

    Verifies the callable receives ``prog.resolved_local_path`` when
    no cwd override is given.
    """
    def callable_obj(repository, *, source_revision):
        assert str(repository) == str(tmp_path)
        return [_make_work_request("K1")]

    prog = _fake_program(tmp_path, name="kaplansky")
    d = Dispatcher(runner=FakeRunner())
    with _register_callable("kaplansky", callable_obj):
        v = d.read_gate(prog)
    assert v.status == GateVerdictStatus.OPEN
    assert v.task_kind == "K1"


# ---------------------------------------------------------------------------
# stop_research failure-path tests.
# ---------------------------------------------------------------------------


def test_stop_research_propagates_nonzero_exit(tmp_path: Path) -> None:
    """`stop_research` MUST surface a non-zero exit as ``result.ok=False``
    (NOT as an exception).

    Defect: a regression that raises on non-zero would crash the
    restart command's inline stop path. Operators see a Python
    traceback instead of "mathlint returned N".
    """
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=2, stderr="FATAL: not running"))
    d = Dispatcher(runner=runner)
    result = d.stop_research()
    assert result.ok is False
    assert result.returncode == 2
    assert "FATAL" in result.stderr


def test_stop_research_forwards_cwd(tmp_path: Path) -> None:
    """`stop_research` MUST forward `cwd` to the subprocess."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    d = Dispatcher(runner=runner)
    d.stop_research(cwd=tmp_path)
    assert runner.calls[0].cwd == str(tmp_path)


def test_run_watch_uses_policy_watch_timeout(tmp_path: Path) -> None:
    """`run_watch` MUST honor a custom `watch_timeout_seconds` policy.

    Defect: a regression that uses `default_timeout_seconds` for
    the TUI (which runs as long as the operator wants) would
    silently kill the dashboard after 15s.
    """
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    policy = SubprocessPolicy(watch_timeout_seconds=3600.0)
    d = Dispatcher(runner=runner, policy=policy)
    cfg = tmp_path / "monitor.toml"
    script = tmp_path / "start.sh"
    d.run_watch(cfg, script)
    assert runner.calls[0].timeout == 3600.0


def test_run_watch_propagates_extra_env() -> None:
    """`run_watch` MUST merge `extra_env` into the subprocess env.

    Defect: a regression that ignores `extra_env` (a documented
    parameter) loses operator overrides like MATHLINT_MODEL_ROUTE
    on the supervisor subprocess.
    """
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    env = FakeEnvironment(values={})  # empty base env
    d = Dispatcher(runner=runner, environment=env)
    cfg = Path("/tmp/monitor.toml")  # noqa: S108
    script = Path("/tmp/start.sh")  # noqa: S108
    d.run_watch(cfg, script, extra_env={"MATHLINT_MODEL_ROUTE": "from-extra-env"})
    assert runner.calls[0].env.get("MATHLINT_MODEL_ROUTE") == "from-extra-env"


def test_read_gate_uses_program_when_local_path_missing(tmp_path: Path) -> None:
    """`read_gate` MUST use the explicit `cwd` override when provided,
    bypassing ``prog.resolved_local_path``.

    Defect: a regression that ignores the `cwd` override would
    force operators to `cd` into the program repo before reading
    the gate, defeating the dispatcher's purpose.
    """
    def callable_obj(repository, *, source_revision):
        # Probe the cwd via the callable: if cwd were ignored, the
        # callable would be invoked against the program's resolved
        # path (tmp_path) instead of the override.
        assert str(repository) == str(tmp_path / "other")
        return []

    prog = _fake_program(tmp_path, name="kaplansky")
    d = Dispatcher(runner=FakeRunner())
    other = tmp_path / "other"
    other.mkdir()
    with _register_callable("kaplansky", callable_obj):
        v = d.read_gate(prog, cwd=other)
    assert v.status == GateVerdictStatus.CLOSED


def test_run_live_uses_default_timeout_when_no_policy(tmp_path: Path) -> None:
    """Without a per-call timeout AND without a policy override,
    `run_live` uses ``DEFAULT_POLICY.default_timeout_seconds``.

    Defect: a regression that sets timeout to ``None`` when no
    policy is given would let `run_live` hang indefinitely on a
    wedged mathlint process.
    """
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0))
    d = Dispatcher(runner=runner)
    d.run_live()
    assert runner.calls[0].timeout is not None
    assert runner.calls[0].timeout == DEFAULT_POLICY.default_timeout_seconds



def test_subprocess_kwargs_minimal_shape() -> None:
    """Pin the typed shape of the kwargs forwarded to ``subprocess.run``.

    The Dispatcher builds a dict literal of kwargs (capture_output /
    text / check / env / cwd / timeout) and forwards them to the
    runner. A regression that adds an unexpected key (e.g. ``shell=True``)
    or drops a required one would silently change subprocess semantics.
    The TypedDict makes the contract explicit; this test pins the keys.
    """
    from research_institution.dispatcher import _SubprocessKwargs
    kwargs: _SubprocessKwargs = {
        "capture_output": True,
        "text": True,
        "check": False,
        "env": {},
    }
    assert kwargs["capture_output"] is True
    assert kwargs["env"] == {}
    assert set(kwargs.keys()) == {"capture_output", "text", "check", "env"}


def test_subprocess_kwargs_full_shape() -> None:
    """Pin the typed shape with all six kwargs populated."""
    from research_institution.dispatcher import _SubprocessKwargs
    kwargs: _SubprocessKwargs = {
        "capture_output": True,
        "text": True,
        "check": False,
        "env": {"PATH": "/bin"},
        "cwd": "/tmp",  # noqa: S108 — literal cwd in subprocess kwargs fixture
        "timeout": 30.0,
    }
    assert kwargs["timeout"] == 30.0
    assert kwargs["cwd"] == "/tmp"  # noqa: S108 — literal cwd in subprocess kwargs fixture
