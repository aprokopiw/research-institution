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
    d.run_live(extra_args=["--run-root", "/tmp/x"])
    argv = _resolved_argv(runner.calls[0])
    assert argv[-2:] == ["--run-root", "/tmp/x"]


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
    assert sent_env == {}, (
        f"hermetic policy leaked inherited env: {sent_env}"
    )


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
    cfg = Path("/tmp/monitor.toml")
    script = Path("/tmp/start.sh")
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
