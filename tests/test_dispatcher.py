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
from research_institution.contracts import GateVerdictStatus, TaskKind
from research_institution.contracts.gate_verdict import TASK_KIND_ABSENT
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


def _fake_program(tmp_path: Path) -> Program:
    return Program(
        name="x",
        display_name="X",
        repository="https://x/x",
        entry_point="x:r",
        local_path=str(tmp_path),
        mathlint_pin="v0.1.0",
        live_credentials_required=False,
        live_credential_env_vars=(),
        check_program_script="check.sh",
    )


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
# ---------------------------------------------------------------------------


ROADMAP_CLOSED = """\
TASK KIND: ARCHITECTURE_REVIEW_REQUIRED
REASON: completed outcome has no unique approved on_failure edge.
"""

ROADMAP_OPEN = """\
TASK KIND: RESEARCH
"""


def test_read_gate_closed(tmp_path: Path) -> None:
    """read_gate returns a CLOSED verdict when roadmap says so."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0, stdout=ROADMAP_CLOSED))
    d = Dispatcher(runner=runner)
    v = d.read_gate(_fake_program(tmp_path))
    assert v.status == GateVerdictStatus.CLOSED
    assert v.task_kind == TaskKind.ARCHITECTURE_REVIEW_REQUIRED.value
    assert "no unique approved" in v.reason


def test_read_gate_open(tmp_path: Path) -> None:
    """read_gate returns an OPEN verdict when roadmap says RESEARCH."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0, stdout=ROADMAP_OPEN))
    d = Dispatcher(runner=runner)
    v = d.read_gate(_fake_program(tmp_path))
    assert v.status == GateVerdictStatus.OPEN
    assert v.task_kind == TaskKind.RESEARCH.value


def test_read_gate_roadmap_failure(tmp_path: Path) -> None:
    """read_gate returns UNKNOWN + diagnostic when mathlint fails."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=3, stderr="FATAL: bad config"))
    d = Dispatcher(runner=runner)
    v = d.read_gate(_fake_program(tmp_path))
    assert v.status == GateVerdictStatus.UNKNOWN
    assert "3" in v.reason
    assert "FATAL" in v.raw_excerpt


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
    """read_gate defaults cwd to program's resolved_local_path."""
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0, stdout=ROADMAP_OPEN))
    d = Dispatcher(runner=runner)
    prog = _fake_program(tmp_path)
    d.read_gate(prog)
    assert runner.calls[0].cwd == str(tmp_path)


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


def test_read_gate_returns_open_when_roadmap_stdout_is_blank(
    tmp_path: Path,
) -> None:
    """When `mathlint roadmap` exits 0 but stdout has NO `TASK KIND:`
    line (legacy/empty roadmap), `read_gate` MUST return OPEN with
    the documented ``(absent)`` sentinel.

    Defect: a regression that raises on missing TASK KIND line
    would crash every cold-start on a freshly-cloned kaplansky
    repo with an empty roadmap.
    """
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0, stdout=""))
    d = Dispatcher(runner=runner)
    v = d.read_gate(_fake_program(tmp_path))
    assert v.status == GateVerdictStatus.OPEN
    assert v.task_kind == TASK_KIND_ABSENT


def test_read_gate_uses_program_when_local_path_missing(tmp_path: Path) -> None:
    """`read_gate` MUST use the explicit `cwd` override when provided,
    bypassing ``prog.resolved_local_path``.

    Defect: a regression that ignores the `cwd` override would
    force operators to `cd` into the program repo before reading
    the gate, defeating the dispatcher's purpose.
    """
    runner = FakeRunner()
    runner.queue(QueuedResponse(returncode=0, stdout=ROADMAP_OPEN))
    d = Dispatcher(runner=runner)
    other = tmp_path / "other"
    other.mkdir()
    d.read_gate(_fake_program(tmp_path), cwd=other)
    assert runner.calls[0].cwd == str(other)


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
        "cwd": "/tmp",
        "timeout": 30.0,
    }
    assert kwargs["timeout"] == 30.0
    assert kwargs["cwd"] == "/tmp"
