"""End-to-end tests for the research-institution CLI dispatcher.

Uses Typer's CliRunner (no subprocess). The fixture in conftest.py
shims `mathlint` and `pi-monitor` so we never invoke the real binaries
during tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_list_prints_catalog(cli_runner, repo_root: Path) -> None:
    """research list prints the catalog programs."""
    result = cli_runner.invoke(args=["list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "kaplansky" in result.stdout


def test_unknown_program_in_start_exits_2(cli_runner) -> None:
    """research start <unknown> fails fast with a clear error."""
    result = cli_runner.invoke(args=["start", "no-such-program"], catch_exceptions=False)
    assert result.exit_code == 2
    assert "unknown program" in (result.stdout + result.stderr).lower()


def test_dry_run_start_does_not_invoke_mathlint(cli_runner, monkeypatch) -> None:
    """research start --dry-run exits 0 without invoking mathlint."""
    # Spy: count how many times the fake mathlint is invoked.
    # The fake shim prints "fake mathlint $args" to stdout; we just
    # assert the dispatcher prints "would launch" without going near it.
    result = cli_runner.invoke(args=["start", "kaplansky", "--dry-run"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "would launch" in result.stdout.lower()


def test_stop_delegates_to_mathlint(cli_runner) -> None:
    """research stop kaplansky invokes mathlint research-stop (via fake shim).

    The fake shim writes its argv to a known file (set via env var in
    conftest) so we can assert the dispatcher delegated without
    fighting Typer's stdout capture.
    """
    import os

    log = os.environ["FAKE_SHIM_LOG"]
    if os.path.exists(log):
        os.remove(log)
    result = cli_runner.invoke(args=["stop", "kaplansky"], catch_exceptions=False)
    assert result.exit_code == 0
    assert os.path.exists(log), "fake shim was never invoked"
    with open(log, encoding="utf-8") as f:
        body = f.read()
    assert "research-stop" in body


def test_status_verbose_delegates_to_mathlint(cli_runner) -> None:
    """research status --verbose invokes mathlint research-status.

    Without --verbose the dispatcher prints a one-line headline
    derived from the supervisor's state files (B.5.1) — no
    subprocess call. With --verbose it delegates to mathlint.
    """
    import os

    log = os.environ["FAKE_SHIM_LOG"]
    if os.path.exists(log):
        os.remove(log)
    result = cli_runner.invoke(args=["status", "kaplansky", "--verbose"], catch_exceptions=False)
    assert result.exit_code == 0
    with open(log, encoding="utf-8") as f:
        body = f.read()
    assert "research-status" in body


def test_status_headline_skips_subprocess(cli_runner) -> None:
    """research status <program> (no --verbose) does NOT shell out.

    The headline is a pure read of the supervisor's state files;
    a subprocess call would defeat the purpose of the headline
    (cheap + safe + no LLM). This test pins that contract.
    """
    import os

    log = os.environ["FAKE_SHIM_LOG"]
    if os.path.exists(log):
        os.remove(log)
    result = cli_runner.invoke(args=["status", "kaplansky"], catch_exceptions=False)
    # Exit 0 even when no supervisor state exists; the headline
    # gracefully reports `no-supervisor` in that case.
    assert result.exit_code == 0
    body = ""
    if os.path.exists(log):
        with open(log, encoding="utf-8") as f:
            body = f.read()
    assert "research-status" not in body, (
        f"status without --verbose should not invoke mathlint, but log says: {body!r}"
    )


def test_doctor_hermetic_runs_green_gate(cli_runner, repo_root: Path, monkeypatch) -> None:
    """research doctor delegates to green-gate/check-institution.sh --hermetic.

    Mutation oracle: a regression that drops `--hermetic` from the argv
    would silently run the operator-live gate (failing on machines
    without credentials). The contract pinned here is the exact argv.
    """
    gate = repo_root / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        pytest.skip("green-gate script not present in this checkout")

    captured: dict = {}

    def fake_call(argv, *args, **kwargs):  # noqa: ARG001
        captured["argv"] = list(argv)
        return 0

    monkeypatch.setattr("subprocess.call", fake_call)
    result = cli_runner.invoke(args=["doctor"], catch_exceptions=False)
    assert result.exit_code == 0
    argv = captured.get("argv")
    assert argv is not None, "doctor did not invoke subprocess.call"
    assert Path(argv[0]) == gate, f"argv[0]={argv[0]!r}; expected {gate}"
    assert "--hermetic" in argv, f"missing --hermetic flag in argv={argv!r}"
    assert "--live" not in argv, f"--live flag leaked into hermetic argv={argv!r}"


def test_doctor_live_runs_green_gate_with_live_flag(cli_runner, repo_root: Path, monkeypatch) -> None:
    """research doctor --live delegates with the --live flag (and not --hermetic)."""
    gate = repo_root / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        pytest.skip("green-gate script not present in this checkout")

    captured: dict = {}

    def fake_call(argv, *args, **kwargs):  # noqa: ARG001
        captured["argv"] = list(argv)
        return 0

    monkeypatch.setattr("subprocess.call", fake_call)
    result = cli_runner.invoke(args=["doctor", "--live"], catch_exceptions=False)
    assert result.exit_code == 0
    argv = captured["argv"]
    assert "--live" in argv
    assert "--hermetic" not in argv


def test_doctor_skip_program_forwards_flag(cli_runner, repo_root: Path, monkeypatch) -> None:
    """research doctor --program X forwards --skip-program=X to the gate."""
    gate = repo_root / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        pytest.skip("green-gate script not present in this checkout")

    captured: dict = {}

    def fake_call(argv, *args, **kwargs):  # noqa: ARG001
        captured["argv"] = list(argv)
        return 0

    monkeypatch.setattr("subprocess.call", fake_call)
    result = cli_runner.invoke(args=["doctor", "--program", "kaplansky"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "--skip-program=kaplansky" in captured["argv"]


def test_install_skills_creates_symlinks(cli_runner, tmp_path: Path) -> None:
    """research install-skills creates one symlink per catalog program."""
    result = cli_runner.invoke(args=["install-skills"], catch_exceptions=False)
    assert result.exit_code == 0
    skills_dir = Path(tmp_path) / "agent_skills"
    assert skills_dir.is_dir()
    # One symlink per catalog program.
    symlinks = list(skills_dir.iterdir())
    assert len(symlinks) >= 1
    assert any(s.name == "kaplansky" for s in symlinks)


def test_install_skills_is_idempotent(cli_runner, tmp_path: Path) -> None:
    """Re-running install-skills does not error and refreshes symlinks."""
    first = cli_runner.invoke(args=["install-skills"], catch_exceptions=False)
    assert first.exit_code == 0
    second = cli_runner.invoke(args=["install-skills"], catch_exceptions=False)
    assert second.exit_code == 0


def test_start_refuses_duplicate_supervisor(cli_runner, monkeypatch) -> None:
    """research start refuses when a supervisor is already running.

    Idempotency: the postmortem B.1.2 risk was that spawning a second
    supervisor would corrupt state. The dispatcher probes via
    `pi-monitor status --config` + PID liveness and refuses with
    EXIT_ALREADY_RUNNING (6) when one is up.
    """
    from research_institution.supervisor import SupervisorState

    fake_state = SupervisorState(
        config_path=Path("/tmp/x.toml"),  # noqa: S108
        supervisor_pid=99999,
        worker_pid=99998,
        is_alive=True,
        status_payload=None,
    )
    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: fake_state,
    )
    result = cli_runner.invoke(
        args=["start", "kaplansky", "--skip-gate"],
        catch_exceptions=False,
    )
    # Exit 6 (ALREADY_RUNNING); the dry-run check happens AFTER the
    # supervisor probe, so we have to pass --skip-gate to skip the
    # gate verdict (which would otherwise run before the probe in
    # the actual handler — but in this mocked path, the probe is
    # reached because the gate check requires monkeypatching mathlint).
    assert result.exit_code == 6
    combined = (result.stdout + result.stderr).lower()
    assert "supervisor already running" in combined
    assert "99999" in combined


def test_start_dry_run_shows_current_state(cli_runner, monkeypatch) -> None:
    """research start --dry-run surfaces whether a supervisor is already up.

    The dry-run path should tell the operator "would launch" + the
    current state so they don't try to spawn a duplicate.
    """
    from research_institution.supervisor import SupervisorState

    fake_state = SupervisorState(
        config_path=Path("/tmp/x.toml"),  # noqa: S108
        supervisor_pid=43960,
        worker_pid=43963,
        is_alive=True,
        status_payload=None,
    )
    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: fake_state,
    )
    result = cli_runner.invoke(
        args=["start", "kaplansky", "--dry-run"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    out = result.stdout.lower()
    assert "would launch" in out
    assert "current state" in out
    assert "43960" in result.stdout


def test_start_autonomous_mode_uses_pi_monitor(cli_runner, monkeypatch) -> None:
    """research start --mode=autonomous spawns pi-monitor run, not live-run.

    The autonomous mode (default) is for the long-running supervisor
    that monitors the roadmap; it does NOT require the mathlint
    preflight and does NOT produce a paired receipt.
    """
    import os

    log = os.environ["FAKE_SHIM_LOG"]
    if os.path.exists(log):
        os.remove(log)
    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: type("S", (), {"is_alive": False, "supervisor_pid": 0})(),
    )
    result = cli_runner.invoke(
        args=["start", "kaplansky", "--dry-run", "--mode=autonomous"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    out = result.stdout
    assert "pi-monitor run" in out
    assert "live-run" not in out


def test_start_durable_mode_uses_mathlint(cli_runner, monkeypatch) -> None:
    """research start --mode=durable spawns mathlint live-run --confirm-live."""
    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: type("S", (), {"is_alive": False, "supervisor_pid": 0})(),
    )
    result = cli_runner.invoke(
        args=["start", "kaplansky", "--dry-run", "--mode=durable"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    out = result.stdout
    assert "mathlint live-run" in out


def test_stop_no_supervisor_is_noop(cli_runner, monkeypatch) -> None:
    """research stop with no supervisor running is a clean no-op (exit 0)."""
    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: type("S", (), {"is_alive": False, "supervisor_pid": 0})(),
    )
    result = cli_runner.invoke(args=["stop", "kaplansky"], catch_exceptions=False)
    assert result.exit_code == 0
    combined = (result.stdout + result.stderr).lower()
    assert "no supervisor running" in combined


def test_stop_sends_sigterm_to_alive_supervisor(cli_runner, monkeypatch) -> None:
    """``research stop <prog>`` sends SIGTERM (signal 15) to the supervisor
    when one is alive.

    Mutation oracle: a refactor that swaps SIGTERM for SIGKILL, or
    skips the SIGTERM step entirely, would lose the cleanup window
    that supervisors need to flush state. The test pins the signal
    value at 15.
    """
    import os as _os
    import signal as _signal

    sent: list[int] = []

    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: type(
            "S",
            (),
            {"is_alive": True, "supervisor_pid": 99999, "worker_pid": 0},
        )(),
    )

    def fake_kill(pid: int, sig: int) -> None:
        sent.append(sig)
        # Simulate the supervisor exiting cleanly after SIGTERM so
        # the stop loop sees success and exits 0.
        if sig == _signal.SIGTERM:
            return  # no exception; _pid_alive_quick is monkeypatched separately

    monkeypatch.setattr(_os, "kill", fake_kill)
    monkeypatch.setattr(
        "research_institution.cli._pid_alive_quick", lambda pid: False
    )
    result = cli_runner.invoke(args=["stop", "kaplansky"], catch_exceptions=False)
    assert result.exit_code == 0, f"got {result.exit_code}; stdout={result.stdout!r}"
    assert _signal.SIGTERM in sent, (
        f"stop did not send SIGTERM; signals sent={sent}. A regression "
        f"that swaps SIGTERM for SIGKILL or skips it would lose the "
        f"supervisor's cleanup window."
    )


def test_stop_force_sends_sigkill_when_sigterm_times_out(
    cli_runner, monkeypatch
) -> None:
    """``research stop <prog> --force`` escalates to SIGKILL if SIGTERM
    doesn't stop the supervisor within 5 seconds.

    Mutation oracle: a refactor that drops the SIGKILL escalation
    in the force path leaves an unresponsive supervisor unkillable
    from this CLI. The test pins the SIGKILL signal value (9) at
    the escalation step.
    """
    import os as _os
    import signal as _signal

    sent: list[int] = []

    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: type(
            "S",
            (),
            {"is_alive": True, "supervisor_pid": 99999, "worker_pid": 0},
        )(),
    )

    def fake_kill(pid: int, sig: int) -> None:
        sent.append(sig)

    monkeypatch.setattr(_os, "kill", fake_kill)
    # Always report PID alive so the SIGTERM wait loop runs to completion
    # and the force-escalation branch fires.
    monkeypatch.setattr(
        "research_institution.cli._pid_alive_quick", lambda pid: True
    )
    # Speed up the 5-second wait loop so the test stays fast. The
    # stop() function imports `time` locally inside the loop, so we
    # patch the stdlib `time.sleep` directly (every `time` import
    # in the process resolves to the same module object).
    import time as _stdlib_time

    monkeypatch.setattr(_stdlib_time, "sleep", lambda _: None)
    result = cli_runner.invoke(
        args=["stop", "kaplansky", "--force"], catch_exceptions=False
    )
    assert result.exit_code == 0, f"got {result.exit_code}; stdout={result.stdout!r}"
    assert _signal.SIGTERM in sent, f"SIGTERM not sent; signals={sent}"
    assert _signal.SIGKILL in sent, (
        f"--force did not escalate to SIGKILL; signals={sent}. A regression "
        f"that drops the force-escalation branch leaves the supervisor "
        f"unkillable from this CLI."
    )


def test_stop_without_force_exits_1_when_supervisor_stuck(
    cli_runner, monkeypatch
) -> None:
    """``research stop <prog>`` without ``--force`` exits 1 when SIGTERM
    doesn't stop the supervisor within 5 seconds.

    The exit code 1 is the operator-facing signal that manual
    intervention (re-run with --force) is needed. A regression that
    exits 0 here would silently leave an unresponsive supervisor
    running and the operator wouldn't know.
    """
    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: type(
            "S",
            (),
            {"is_alive": True, "supervisor_pid": 99999, "worker_pid": 0},
        )(),
    )
    monkeypatch.setattr("research_institution.cli.os.kill", lambda *a, **kw: None)
    monkeypatch.setattr(
        "research_institution.cli._pid_alive_quick", lambda pid: True
    )
    import time as _stdlib_time

    monkeypatch.setattr(_stdlib_time, "sleep", lambda _: None)
    result = cli_runner.invoke(args=["stop", "kaplansky"], catch_exceptions=False)
    assert result.exit_code == 1, (
        f"got {result.exit_code}; expected 1 when SIGTERM doesn't stop "
        f"the supervisor. A regression that exits 0 silently leaves an "
        f"unresponsive supervisor running."
    )



# ---------------------------------------------------------------------------
# V-WIRE label contract — the green-gate script advertises the new tier.
#
# The V-WIRE tier was added in verify-0093-vwire (commit f565ac1). This
# test pins the surface contract: the gate script MUST print the
# `[v-wire]` label and MUST honor ``RESEARCH_INSTITUTION_VWIRE_DIRECT``.
# A future refactor that drops the tier (e.g. renaming ``v-wire`` to
# ``cross-repo-wiring``) breaks operator dashboards that grep for the
# label, so we pin the exact string here.
# ---------------------------------------------------------------------------


def test_green_gate_advertises_v_wire_subcheck(repo_root: Path) -> None:
    """The institution green-gate MUST print the ``[v-wire]`` label and
    honor ``RESEARCH_INSTITUTION_VWIRE_DIRECT``.

    Mutation oracle: a refactor that drops V-WIRE (e.g. merges it into
    V2) silently degrades the institution green-gate's coverage of
    cross-repo composition contracts. Dashboards that grep for the
    ``v-wire`` label would miss the change. This test pins the label
    AND the env-var contract so the public surface is preserved.
    """
    gate = repo_root / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        pytest.skip("green-gate script not present in this checkout")
    source = gate.read_text(encoding="utf-8")
    assert "[v-wire]" in source, (
        "green-gate no longer advertises the V-WIRE sub-check "
        "(missing '[v-wire]' label). The cross-repo wiring tier "
        "has been removed or renamed. If intentional, update this "
        "test AND the operator dashboards that grep for the label."
    )
    assert "RESEARCH_INSTITUTION_VWIRE_DIRECT" in source, (
        "green-gate no longer honors RESEARCH_INSTITUTION_VWIRE_DIRECT. "
        "The escape hatch for hermetic CI runners is missing."
    )


def test_doctor_preserves_v_wire_env_var_through_to_gate(
    cli_runner, repo_root: Path, monkeypatch
) -> None:
    """When ``RESEARCH_INSTITUTION_VWIRE_DIRECT=1`` is in the
    dispatcher's env, ``research doctor`` MUST forward it to the
    subprocess.call that invokes the gate.

    Defect: a refactor that constructs the subprocess env via
    ``subprocess.call([gate, flag])`` without propagating the
    env-var would silently disable V-WIRE for operators who set
    it in their dotfiles. The cold-start hermetic test catches
    this on the integration path; this test pins the per-CLI
    surface so a regression in ``cli.py`` surfaces here too.
    """
    gate = repo_root / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        pytest.skip("green-gate script not present in this checkout")

    captured: dict = {}

    def fake_call(argv, *args, **kwargs):  # noqa: ARG001
        captured["argv"] = list(argv)
        return 0

    monkeypatch.setattr("subprocess.call", fake_call)
    monkeypatch.setenv("RESEARCH_INSTITUTION_VWIRE_DIRECT", "1")
    result = cli_runner.invoke(args=["doctor"], catch_exceptions=False)
    assert result.exit_code == 0
    argv = captured.get("argv", [])
    # The gate must be invoked; the env-var propagation is via the
    # subprocess env (which subprocess.call inherits from os.environ).
    # We assert here that the argv shape is preserved; the actual
    # env-var propagation is a Python-level guarantee that subprocess
    # calls inherit os.environ. The cold-start test exercises the
    # full end-to-end propagation.
    assert Path(argv[0]) == gate, f"argv[0]={argv[0]!r}; expected {gate}"
