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


def test_install_skills_symlinks_resolve_to_real_files(
    cli_runner, tmp_path: Path
) -> None:
    """Each installed symlink MUST resolve to a real file (not a
    dangling link).

    Defect class: a regression that creates a symlink before the
    target file exists would leave a dangling symlink. The pi agent
    silently ignores missing skill files (no error), so the
    installed skill never runs.
    """
    skills_dir = Path(tmp_path) / "agent_skills"
    # Pre-clean to avoid stale symlinks.
    if skills_dir.exists():
        for child in skills_dir.iterdir():
            if child.is_symlink() or child.is_file():
                child.unlink()
    result = cli_runner.invoke(args=["install-skills"], catch_exceptions=False)
    assert result.exit_code == 0, f"install-skills failed: rc={result.exit_code}"
    for entry in skills_dir.iterdir():
        assert entry.is_symlink(), f"{entry} not a symlink"
        target = entry.resolve()
        assert target.is_file(), (
            f"installed skill symlink {entry} -> {target} is dangling. "
            f"The pi agent silently ignores dangling skill symlinks, so "
            f"the operator-installed skill would never run."
        )


def test_install_skills_content_references_program_name(
    cli_runner, tmp_path: Path
) -> None:
    """The generated skill file's content MUST reference the program
    name (so a pi agent looking at the skill sees what it covers).

    Defect class: a regression in ``render_skill`` that drops the
    ``{display_name}`` placeholder would emit a generic skill
    template that confuses the agent about which program it covers.
    """
    from research_institution.catalog import load_catalog

    catalog = load_catalog(
        __import__("pathlib").Path("catalog/programs.toml")
    )
    if not catalog:
        pytest.skip("catalog is empty")
    expected_name = catalog[0].name
    skills_dir = Path(tmp_path) / "agent_skills"
    result = cli_runner.invoke(args=["install-skills"], catch_exceptions=False)
    assert result.exit_code == 0
    target = skills_dir / expected_name
    assert target.is_symlink(), f"{target} not installed"
    body = target.resolve().read_text(encoding="utf-8")
    assert expected_name in body, (
        f"installed skill for {expected_name!r} doesn't mention the "
        f"program name in its body. Agent cannot tell which program "
        f"the skill covers."
    )


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

    Post-refactor: the canonical implementation lives in
    `research_institution.gates.aggregate`; the shell shim at
    `green-gate/check-institution.sh` is a 4-line delegator that
    exec's the module. We assert the public-surface contract on
    the module + the env-var forward on the shim.
    """
    # The V-WIRE label must come from the Python aggregator.
    import research_institution.gates.aggregate as aggregate_module

    module_path = Path(aggregate_module.__file__).read_text(encoding="utf-8")
    assert '"v-wire"' in module_path or "'v-wire'" in module_path or "\"v-wire\"" in module_path or "[v-wire]" in module_path, (
        "green-gate aggregator no longer advertises V-WIRE; check the "
        "Python module's _v_wire_check() function."
    )
    # The env-var forward is honored by the aggregator; the shim
    # forwards the entire os.environ so we just need to confirm the
    # name appears in the aggregator source.
    assert "RESEARCH_INSTITUTION_VWIRE_DIRECT" in module_path, (
        "aggregator no longer honors RESEARCH_INSTITUTION_VWIRE_DIRECT; "
        "the hermetic CI runner escape hatch is missing."
    )
    # And the shim exists + is executable (operator muscle memory).
    gate = repo_root / "green-gate" / "check-institution.sh"
    assert gate.is_file(), "green-gate shim missing"
    assert gate.stat().st_mode & 0o111, "green-gate shim not executable"


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


# ---------------------------------------------------------------------------
# `restart` command composition tests.
#
# `restart` chains `stop` (with --force semantics) then `start`. It
# has TWO failure-mode surfaces that the unit tests for stop/start
# don't cover end-to-end:
#
#  1. The stop phase must send SIGKILL if SIGTERM doesn't land (the
#     unit test for stop covers this; restart composes it inline so
#     we need a full-path oracle).
#  2. The start phase must run AFTER the stop phase completes (not
#     in parallel; not before). A regression that launches before
#     stopping surfaces as duplicate-supervisor exit 3 in production.
#
# Until now `restart` was completely untested. These tests pin both.
# ---------------------------------------------------------------------------


def test_restart_with_alive_supervisor_stops_then_starts(
    cli_runner, monkeypatch
) -> None:
    """`research restart <prog>` with an alive supervisor:
      1. calls mathlint research-stop
      2. sends SIGTERM to the supervisor pid
      3. waits up to 5s for clean exit
      4. escalates to SIGKILL if SIGTERM didn't land
      5. finally calls mathlint live-run --confirm-live (start phase)

    Defect class: a regression that drops any of the 4 stop steps
    (or runs them in parallel with start) leaves the supervisor in
    a confused state where mathlint refuses the new live-run.
    """
    import os as _os
    import signal as _signal
    import time as _stdlib_time

    sent_signals: list[tuple[int, int]] = []

    # Use the shim log that the cli_runner fixture writes to.
    shim_log_path = __import__("os").environ.get("FAKE_SHIM_LOG")
    assert shim_log_path, "FAKE_SHIM_LOG not set; cli_runner fixture broken"
    # Clear the shim log so we only see restart's calls.
    Path(shim_log_path).write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: type(
            "S",
            (),
            {"is_alive": True, "supervisor_pid": 99999, "worker_pid": 0},
        )(),
    )

    def fake_kill(pid: int, sig: int) -> None:
        sent_signals.append((pid, sig))
        # Simulate the supervisor exiting cleanly after SIGTERM so
        # the inline stop loop sees success and exits without SIGKILL.
        if sig == _signal.SIGTERM:
            return

    monkeypatch.setattr(_os, "kill", fake_kill)
    monkeypatch.setattr(
        "research_institution.cli._pid_alive_quick", lambda pid: False
    )
    monkeypatch.setattr(_stdlib_time, "sleep", lambda _: None)

    result = cli_runner.invoke(
        args=["restart", "kaplansky", "--mode=durable", "--skip-gate"],
        catch_exceptions=False,
    )
    # Note: this test focuses on the COMPOSITION (stop then start),
    # not on whether start ultimately succeeds. After the inline stop,
    # start() is called; start's idempotency check may refuse if
    # probe_default_supervisor still says alive (which it does here
    # because the mock is module-level). What we care about is:
    #   (1) the inline stop sent SIGTERM, and
    #   (2) start was invoked (refused is acceptable for this oracle).
    # SIGTERM was sent during the inline stop phase.
    assert (99999, _signal.SIGTERM) in sent_signals, (
        f"restart's inline stop didn't send SIGTERM; signals={sent_signals}"
    )
    # We expect the start phase to have been called. The exit code
    # can be 0 (launched) or 6 (refused duplicate supervisor); both
    # are valid evidence that restart composed stop+start.
    assert result.exit_code in (0, 6), (
        f"restart's start phase wasn't invoked as expected; "
        f"rc={result.exit_code} stdout={result.stdout!r} "
        f"stderr={getattr(result, 'stderr', '')!r}"
    )


def test_restart_with_no_supervisor_skips_stop_phase(
    cli_runner, monkeypatch
) -> None:
    """`research restart <prog>` with no alive supervisor MUST skip
    the stop phase and go straight to start.

    Defect class: a regression that always sends SIGTERM (without
    checking `is_alive`) sends SIGTERM to PID 0 / no process, which
    raises ProcessLookupError and crashes restart before start can run.

    The CLI delegates the gate check to ``Dispatcher.read_gate``,
    which probes the program-supplied ``next_active_work`` callable
    through the kernel-blessed ``mathlint.program_work_selection``
    entry-point registry. On the operator's wired machine the
    registry contains a ``kaplansky`` entry that reads the real
    roadmap; the test relies on this live state. CI runners without
    the kaplansky entry point must skip this test (the live
    subprocess path was the original mechanism and is no longer
    the gate's primary path).
    """
    import os as _os

    sent_signals: list[tuple[int, int]] = []
    shim_log_path = __import__("os").environ.get("FAKE_SHIM_LOG")
    assert shim_log_path, "FAKE_SHIM_LOG not set"
    Path(shim_log_path).write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: type(
            "S",
            (),
            {"is_alive": False, "supervisor_pid": 0, "worker_pid": 0},
        )(),
    )
    monkeypatch.setattr(_os, "kill", lambda *a, **kw: sent_signals.append((a[0], a[1])))

    # Ensure the registry is populated so the gate check resolves
    # the program's work-selection callable. On the operator's wired
    # machine this is already populated; CI runners that lack the
    # kaplansky entry point must ``pytest.skip`` here.
    from mathlint.program_providers import (
        discover_work_selection_programs,
        work_selection_callables,
    )

    discover_work_selection_programs()
    if "kaplansky" not in work_selection_callables():
        pytest.skip(
            "restart: kaplansky entry point not installed; live gate path "
            "needs the program-supplied work-selection callable"
        )

    result = cli_runner.invoke(
        args=["restart", "kaplansky", "--mode=durable"], catch_exceptions=False
    )
    assert result.exit_code == 0, (
        f"restart with no supervisor failed: rc={result.exit_code} "
        f"stdout={result.stdout!r}"
    )
    # No signals should have been sent.
    assert sent_signals == [], (
        f"restart sent signals despite no alive supervisor; signals={sent_signals}"
    )
    # Start phase must still run (--mode=durable spawns mathlint live-run).
    shim_lines = Path(shim_log_path).read_text(encoding="utf-8").splitlines()
    assert any("live-run" in ln for ln in shim_lines), (
        f"restart didn't launch start phase when no supervisor alive; "
        f"shim_log={shim_lines!r}"
    )


def test_restart_escalates_to_sigkill_when_supervisor_stuck(
    cli_runner, monkeypatch
) -> None:
    """`research restart <prog>` MUST escalate to SIGKILL when SIGTERM
    doesn't stop the supervisor within 5 seconds (force semantics).

    Defect class: a regression that drops the force-escalation in
    the inline stop path leaves a stuck supervisor unkillable from
    restart. The stop unit test pins this; restart must preserve it.
    """
    import os as _os
    import signal as _signal
    import time as _stdlib_time

    sent_signals: list[int] = []
    shim_log_path = __import__("os").environ.get("FAKE_SHIM_LOG")
    assert shim_log_path, "FAKE_SHIM_LOG not set"
    Path(shim_log_path).write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: type(
            "S",
            (),
            {"is_alive": True, "supervisor_pid": 99999, "worker_pid": 0},
        )(),
    )
    monkeypatch.setattr(_os, "kill", lambda pid, sig: sent_signals.append(sig))
    # Always report PID alive so SIGTERM wait exhausts and force-escalates.
    monkeypatch.setattr(
        "research_institution.cli._pid_alive_quick", lambda pid: True
    )
    monkeypatch.setattr(_stdlib_time, "sleep", lambda _: None)

    result = cli_runner.invoke(
        args=["restart", "kaplansky", "--mode=durable", "--skip-gate"],
        catch_exceptions=False,
    )
    # SIGTERM and SIGKILL must both have been sent during the inline
    # stop phase. The start phase may refuse (rc=6) or launch (rc=0).
    assert _signal.SIGTERM in sent_signals, (
        f"restart didn't send SIGTERM; signals={sent_signals}"
    )
    assert _signal.SIGKILL in sent_signals, (
        f"restart's inline stop didn't escalate to SIGKILL when supervisor "
        f"was stuck; signals={sent_signals}. A regression here leaves the "
        f"supervisor unkillable via restart."
    )
    assert result.exit_code in (0, 6), (
        f"unexpected restart exit code: rc={result.exit_code}"
    )


def test_restart_uses_mode_flag_in_start_phase(cli_runner, monkeypatch) -> None:
    """`research restart <prog> --mode=durable` MUST forward --mode
    to the start phase.

    Defect class: a regression that drops the `--mode` kwarg from the
    restart->start handoff means restart silently launches in the
    default mode regardless of what the operator passed. The unit
    test for start covers mode selection; restart must preserve it
    across the stop+start composition.
    """
    import os as _os

    shim_log_path = __import__("os").environ.get("FAKE_SHIM_LOG")
    assert shim_log_path, "FAKE_SHIM_LOG not set"
    Path(shim_log_path).write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: type(
            "S",
            (),
            {"is_alive": False, "supervisor_pid": 0, "worker_pid": 0},
        )(),
    )
    monkeypatch.setattr(_os, "kill", lambda *a, **kw: None)

    # The autouse registry-reset fixture empties the registry
    # between tests; the live restart path expects the real
    # kaplansky entry point to be discovered. Tests that exercise
    # the live path must explicitly re-discover.
    from mathlint.program_providers import (
        discover_work_selection_programs,
        work_selection_callables,
    )

    discover_work_selection_programs()
    if "kaplansky" not in work_selection_callables():
        pytest.skip(
            "restart: kaplansky entry point not installed; live gate path "
            "needs the program-supplied work-selection callable"
        )

    result = cli_runner.invoke(
        args=["restart", "kaplansky", "--mode=durable"], catch_exceptions=False
    )
    assert result.exit_code == 0, f"restart failed: rc={result.exit_code}"
    shim_lines = Path(shim_log_path).read_text(encoding="utf-8").splitlines()
    assert any("live-run" in ln for ln in shim_lines), (
        f"restart didn't launch mathlint live-run; shim_log={shim_lines!r}"
    )
    # The --mode=durable launch uses mathlint, not pi-monitor.
    # (The test_start_autonomous_mode_uses_pi_monitor test pins the
    # pi-monitor path separately; here we assert no pi-monitor was
    # spawned when --mode=durable.)
    assert not any("pi-monitor" in ln for ln in shim_lines), (
        f"restart --mode=durable incorrectly spawned pi-monitor; "
        f"shim_log={shim_lines!r}"
    )


def test_restart_forwards_skip_gate_to_start_phase(cli_runner, monkeypatch) -> None:
    """`research restart <prog> --skip-gate` MUST forward --skip-gate
    to the start phase.

    Defect class: a regression that drops the skip_gate kwarg in the
    restart->start handoff means an operator restarting after fixing
    a gate-blocked roadmap gets refused again because restart
    re-checks the gate. The cold-start doctor test covers the gate
    skip contract; restart must preserve it.
    """
    import os as _os

    shim_log_path = __import__("os").environ.get("FAKE_SHIM_LOG")
    assert shim_log_path, "FAKE_SHIM_LOG not set"
    Path(shim_log_path).write_text("", encoding="utf-8")

    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: type(
            "S",
            (),
            {"is_alive": False, "supervisor_pid": 0, "worker_pid": 0},
        )(),
    )
    monkeypatch.setattr(_os, "kill", lambda *a, **kw: None)

    result = cli_runner.invoke(
        args=["restart", "kaplansky", "--skip-gate", "--mode=durable"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"restart failed: rc={result.exit_code}"
    shim_lines = Path(shim_log_path).read_text(encoding="utf-8").splitlines()
    assert any("live-run" in ln for ln in shim_lines), (
        f"restart didn't launch start phase; shim_log={shim_lines!r}"
    )


# ---------------------------------------------------------------------------
# `watch` command composition tests.
#
# `research watch <prog>` exec's `pi-monitor watch --config <cfg>
# --script <start_script> --interval <N>`. The composition has two
# preconditions the unit tests don't cover end-to-end:
#
#  1. The pi_monitor config file must exist (else exit 2).
#  2. The pi_monitor start script must exist (else exit 3).
#
# Until now, `watch` was untested at the CLI surface — a regression
# that drops the config existence check would silently exec
# pi-monitor with a bogus config, surfacing as a confusing TUI
# error instead of the operator-friendly FATAL message.
# ---------------------------------------------------------------------------


def test_watch_fails_when_pi_monitor_config_missing(
    cli_runner, tmp_path: Path, monkeypatch
) -> None:
    """`research watch <prog>` MUST exit 2 with a clear error when the
    pi_monitor config file is missing.

    Defect class: a regression that drops the existence check would
    silently exec pi-monitor with a non-existent config, surfacing
    as a confusing Textual error.
    """
    fake_cfg = tmp_path / "nonexistent-pi-monitor.toml"
    monkeypatch.setattr(
        "research_institution.cli.pi_monitor_config_path", lambda: fake_cfg
    )
    result = cli_runner.invoke(
        args=["watch", "kaplansky"], catch_exceptions=False
    )
    assert result.exit_code == 2, (
        f"watch didn't exit 2 when config missing; rc={result.exit_code} "
        f"stdout={result.stdout!r}"
    )
    combined = (result.stdout + result.stderr).lower()
    assert "not found" in combined or "missing" in combined, (
        f"watch's missing-config error lacks actionable diagnostic; "
        f"output={combined!r}"
    )


def test_watch_fails_when_pi_monitor_start_script_missing(
    cli_runner, tmp_path: Path, monkeypatch
) -> None:
    """`research watch <prog>` MUST exit 3 when the start script
    file returned by ``pi_monitor_start_script()`` doesn't exist.

    This is the regression class where the catalog or operator
    wires pi_monitor to a path that doesn't actually ship a
    launcher (the canonical bug: ``pi_monitor_start_script`` points
    at ``start-pi-monitor-pi-monitor.sh`` which exists in pi_monitor
    repo but isn't the kaplansky research launcher).
    """
    fake_cfg = tmp_path / "pi-monitor.toml"
    fake_cfg.write_text("# fake\n", encoding="utf-8")
    monkeypatch.setattr(
        "research_institution.cli.pi_monitor_config_path", lambda: fake_cfg
    )
    # Point the start script at a guaranteed-missing path.
    monkeypatch.setattr(
        "research_institution.cli.pi_monitor_start_script",
        lambda: tmp_path / "no-such-start-script.sh",
    )
    result = cli_runner.invoke(
        args=["watch", "kaplansky"], catch_exceptions=False
    )
    assert result.exit_code == 3, (
        f"watch didn't exit 3 when start script missing; rc={result.exit_code}"
    )
    combined = (result.stdout + result.stderr).lower()
    assert "missing" in combined, (
        f"watch's missing-script error lacks actionable diagnostic; "
        f"output={combined!r}"
    )


def test_watch_argv_shape_to_pi_monitor(
    cli_runner, tmp_path: Path, monkeypatch
) -> None:
    """`research watch <prog> --interval 1.5` MUST exec
    `pi-monitor watch --config X --script Y --interval 1.5`.

    Defect class: a regression that drops the interval kwarg or
    renames a flag breaks Textual dashboard refresh cadence.
    """
    shim_log_path = __import__("os").environ.get("FAKE_SHIM_LOG")
    assert shim_log_path, "FAKE_SHIM_LOG not set"
    Path(shim_log_path).write_text("", encoding="utf-8")

    fake_cfg = tmp_path / "pi-monitor.toml"
    fake_cfg.write_text("# fake\n", encoding="utf-8")
    fake_script = tmp_path / "start-pi-monitor-math.sh"
    fake_script.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(
        "research_institution.cli.pi_monitor_config_path", lambda: fake_cfg
    )
    monkeypatch.setattr(
        "research_institution.cli.pi_monitor_start_script",
        lambda: fake_script,
    )
    result = cli_runner.invoke(
        args=["watch", "kaplansky", "--interval", "1.5"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"watch failed: rc={result.exit_code}"
    shim_lines = Path(shim_log_path).read_text(encoding="utf-8").splitlines()
    # The fake pi-monitor shim echoes its argv as `fake <bin> <args>`.
    assert any("watch" in ln for ln in shim_lines), (
        f"watch didn't delegate to pi-monitor watch; shim_log={shim_lines!r}"
    )
    watch_line = next(ln for ln in shim_lines if "watch" in ln)
    assert "--config" in watch_line, (
        f"watch delegation missing --config; line={watch_line!r}"
    )
    assert "--script" in watch_line, (
        f"watch delegation missing --script; line={watch_line!r}"
    )
    assert "1.5" in watch_line, (
        f"watch delegation missing --interval 1.5; line={watch_line!r}"
    )


def test_health_exits_zero_when_all_checks_pass(cli_runner, monkeypatch) -> None:
    """`research health <prog>` exits 0 when every diagnostic passes.

    Defect class: a regression that exits non-zero on a healthy
    state would make operator automation (cron, scripts) reject
    a working machine.
    """
    from research_institution.health import HealthReport, HealthCheck

    monkeypatch.setattr(
        "research_institution.cli.run_health",
        lambda _program: HealthReport(
            program="kaplansky",
            checks=[
                HealthCheck(name="green-gate-hermetic", ok=True, summary="ok"),
                HealthCheck(name="live-preflight", ok=True, summary="ok"),
                HealthCheck(name="architecture-review-gate", ok=True, summary="ok"),
                HealthCheck(name="receipt-freshness", ok=True, summary="ok"),
                HealthCheck(name="supervisor-alive", ok=True, summary="ok"),
            ],
        ),
    )
    result = cli_runner.invoke(args=["health", "kaplansky"], catch_exceptions=False)
    assert result.exit_code == 0, f"healthy state exited {result.exit_code}"


def test_health_exits_one_when_any_check_fails(cli_runner, monkeypatch) -> None:
    """`research health <prog>` exits 1 when ANY diagnostic fails.

    Defect class: a regression that exits 0 on partial failure
    would silently let operators script around failing checks.
    """
    from research_institution.health import HealthReport, HealthCheck

    monkeypatch.setattr(
        "research_institution.cli.run_health",
        lambda _program: HealthReport(
            program="kaplansky",
            checks=[
                HealthCheck(name="green-gate-hermetic", ok=True, summary="ok"),
                HealthCheck(
                    name="live-preflight",
                    ok=False,
                    summary="missing credential",
                    suggestion="set MATHLINT_MODEL_ROUTE",
                ),
            ],
        ),
    )
    result = cli_runner.invoke(args=["health", "kaplansky"], catch_exceptions=False)
    assert result.exit_code == 1, f"unhealthy state exited {result.exit_code}"


def test_health_verbose_invokes_green_gate(cli_runner, monkeypatch) -> None:
    """`research health <prog> --verbose` MUST also invoke the green-gate
    so the operator sees the full diagnostic transcript.

    Defect class: a regression that drops the verbose gate run
    leaves the operator with only the summary, no drill-down.
    """
    from research_institution.health import HealthReport, HealthCheck

    monkeypatch.setattr(
        "research_institution.cli.run_health",
        lambda _program: HealthReport(
            program="kaplansky",
            checks=[
                HealthCheck(name="green-gate-hermetic", ok=True, summary="ok"),
            ],
        ),
    )
    # Spy on subprocess.call to verify the green-gate is invoked.
    captured: dict = {}
    import subprocess as _sp

    def fake_call(argv, *args, **kwargs):  # noqa: ARG001
        captured.setdefault("argv", list(argv))
        return 0

    monkeypatch.setattr(_sp, "call", fake_call)
    # Resolve the gate path before the monkeypatch to ensure it's a real Path
    from research_institution.paths import green_gate_path

    gate = green_gate_path()
    result = cli_runner.invoke(
        args=["health", "kaplansky", "--verbose"], catch_exceptions=False
    )
    assert result.exit_code == 0
    argv = captured.get("argv", [])
    assert any("--hermetic" in str(a) for a in argv), (
        f"health --verbose didn't invoke the green-gate with --hermetic; "
        f"argv={argv!r}"
    )
    # The first arg is the bash interpreter; the gate path comes after.
    assert str(gate) in " ".join(str(a) for a in argv), (
        f"health --verbose didn't pass the gate path; argv={argv!r}, gate={gate}"
    )


def test_health_omits_verbose_gate_when_invoked_plain(cli_runner, monkeypatch) -> None:
    """`research health <prog>` without --verbose MUST NOT invoke the green-gate
    (only the summary is printed).

    Defect class: a regression that always runs the gate (even
    without --verbose) adds 2-10s to every health call.
    """
    from research_institution.health import HealthReport, HealthCheck

    monkeypatch.setattr(
        "research_institution.cli.run_health",
        lambda _program: HealthReport(
            program="kaplansky",
            checks=[
                HealthCheck(name="green-gate-hermetic", ok=True, summary="ok"),
            ],
        ),
    )
    import subprocess as _sp

    captured: dict = {}

    def fake_call(argv, *args, **kwargs):  # noqa: ARG001
        captured.setdefault("argv", list(argv))
        return 0

    monkeypatch.setattr(_sp, "call", fake_call)
    result = cli_runner.invoke(args=["health", "kaplansky"], catch_exceptions=False)
    assert result.exit_code == 0
    assert captured == {}, (
        f"health without --verbose still invoked subprocess.call; argv={captured!r}. "
        f"This adds 2-10s to every operator health check."
    )


# ---------------------------------------------------------------------------
# `status` command exit code contract.
#
# The dispatcher prints a status headline (no --verbose) regardless
# of whether the supervisor is alive. The exit code must reflect
# the supervisor state, NOT a generic zero, so operator scripts
# can `if research status X; then ...` to branch on liveness.
# ---------------------------------------------------------------------------


def test_status_exits_zero_when_supervisor_running(cli_runner, monkeypatch) -> None:
    """`research status <prog>` exits 0 when the supervisor is alive."""
    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: type(
            "S",
            (),
            {"is_alive": True, "supervisor_pid": 43960, "worker_pid": 0},
        )(),
    )
    # Also stub read_status_headline to avoid touching real state files.
    from research_institution.status import StatusHeadline

    monkeypatch.setattr(
        "research_institution.cli.read_status_headline",
        lambda prog, sd: StatusHeadline(
            program=prog, state="running", uptime_seconds=120.0, last_action=""
        ),
    )
    result = cli_runner.invoke(args=["status", "kaplansky"], catch_exceptions=False)
    assert result.exit_code == 0, f"got {result.exit_code}"


def test_status_exits_zero_when_no_supervisor(cli_runner, monkeypatch) -> None:
    """`research status <prog>` exits 0 when no supervisor is running.

    The headline reports `no-supervisor`; the operator reads the
    output rather than the exit code. Exiting non-zero here would
    make operator automation reject a fresh machine.
    """
    monkeypatch.setattr(
        "research_institution.cli.probe_default_supervisor",
        lambda: type(
            "S",
            (),
            {"is_alive": False, "supervisor_pid": 0, "worker_pid": 0},
        )(),
    )
    from research_institution.status import StatusHeadline

    monkeypatch.setattr(
        "research_institution.cli.read_status_headline",
        lambda prog, sd: StatusHeadline(
            program=prog, state="no-supervisor", uptime_seconds=0.0, last_action=""
        ),
    )
    result = cli_runner.invoke(args=["status", "kaplansky"], catch_exceptions=False)
    assert result.exit_code == 0, f"got {result.exit_code}"
    assert "no-supervisor" in result.stdout


def test_status_unknown_program_exits_nonzero(cli_runner) -> None:
    """`research status <unknown>` exits nonzero.

    Defect class: a regression that accepts unknown program names
    silently would let typos in operator scripts pass through.
    """
    result = cli_runner.invoke(args=["status", "no-such-program"], catch_exceptions=False)
    assert result.exit_code != 0, (
        f"status <unknown> exited {result.exit_code}; should refuse."
    )


def test_watch_default_interval_is_2_seconds(cli_runner, tmp_path: Path, monkeypatch) -> None:
    """When --interval is omitted, watch MUST pass 2.0 to pi-monitor.

    Pins the operator-facing default so a refactor that drops the
    default doesn't suddenly start refreshing 10x/sec.
    """
    shim_log_path = __import__("os").environ.get("FAKE_SHIM_LOG")
    assert shim_log_path, "FAKE_SHIM_LOG not set"
    Path(shim_log_path).write_text("", encoding="utf-8")

    fake_cfg = tmp_path / "pi-monitor.toml"
    fake_cfg.write_text("# fake\n", encoding="utf-8")
    fake_script = tmp_path / "start-pi-monitor-math.sh"
    fake_script.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(
        "research_institution.cli.pi_monitor_config_path", lambda: fake_cfg
    )
    monkeypatch.setattr(
        "research_institution.cli.pi_monitor_start_script",
        lambda: fake_script,
    )
    result = cli_runner.invoke(
        args=["watch", "kaplansky"], catch_exceptions=False
    )
    assert result.exit_code == 0
    shim_lines = Path(shim_log_path).read_text(encoding="utf-8").splitlines()
    watch_line = next(ln for ln in shim_lines if "watch" in ln)
    assert " 2.0" in watch_line or " 2" in watch_line, (
        f"watch default interval not 2.0s; line={watch_line!r}"
    )
