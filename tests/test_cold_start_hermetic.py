"""Cold-start workflow test.

Exercises the AGENTS.md cold-start recipe against the real repo on this
machine:

  1. Read the catalog.
  2. Run the green gate (hermetic).
  3. Run `python -m research_institution list`.
  4. Run `python -m research_institution doctor`.

This is the contract the AGENTS.md prescribes. A fresh agent that runs
the cold prompt must succeed at all four steps.

Skipped when mathlint / pi-monitor are not installed, or when the
pi_monitor supervisor is currently holding the state lock (which
makes the live-mode sub-check block; see
`test_cold_start_doctor_live_passes_when_credentials_valid`).
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

# The pi_monitor supervisor holds a lock at this path while running.
# Live-mode mathlint system-readiness can block waiting for this lock;
# we skip those tests when a supervisor is active to avoid hanging.
PI_MONITOR_LOCK = Path.home() / ".local" / "state" / "mathlint" / "pi-monitor" / "supervisor.lock"


def _supervisor_running() -> bool:
    """True iff a pi_monitor supervisor holds the state lock."""
    if not PI_MONITOR_LOCK.exists():
        return False
    try:
        pid_text = PI_MONITOR_LOCK.read_text(encoding="utf-8").strip()
        pid = int(pid_text)
        # POSIX kill(pid, 0) succeeds iff the process exists.
        os.kill(pid, 0)
        return True
    except (ValueError, ProcessLookupError, PermissionError, OSError):
        return False


@pytest.fixture(scope="module")
def _has_mathlint() -> bool:
    return shutil.which("mathlint") is not None


@pytest.fixture(scope="module")
def _has_pi_monitor() -> bool:
    return shutil.which("pi-monitor") is not None


def test_cold_start_list(cli_runner) -> None:
    """Step 1: `python -m research_institution list` prints the catalog."""
    result = cli_runner.invoke(args=["list"], catch_exceptions=False)
    assert result.exit_code == 0
    assert "kaplansky" in result.stdout


def test_cold_start_doctor_hermetic() -> None:
    """Step 2: green gate --hermetic returns GREEN INSTITUTION READY.

    V-WIRE is opt-in for this test (set
    RESEARCH_INSTITUTION_RUN_VWIRE=1 to include it). By default the
    cold-start doctor asserts V0+V2 are green and leaves V-WIRE for
    the dedicated cross-repo wiring tests in
    `tests/local_readiness/test_cross_repo_wiring.py` (run separately
    via the math-engine venv). This separation matches the
    `@ADR-0006` boundary: the dispatcher is not the canonical
    authority on cross-repo composition contracts.
    """
    gate = REPO / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        pytest.skip("green gate missing")
    env = os.environ.copy()
    if os.environ.get("RESEARCH_INSTITUTION_RUN_VWIRE") == "1":
        env["RESEARCH_INSTITUTION_VWIRE_DIRECT"] = "1"
    else:
        env["MATHLINT_AUTONOMY_SKIP_G7"] = "1"
    result = subprocess.run(
        ["bash", str(gate), "--hermetic"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )
    assert result.returncode == 0, (
        f"green gate failed: rc={result.returncode} stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )
    assert "GREEN INSTITUTION READY" in result.stdout


def test_cold_start_doctor_hermetic_with_vwire() -> None:
    """Step 2 (strict): green gate --hermetic + V-WIRE returns GREEN INSTITUTION READY.

    Opt-in variant of `test_cold_start_doctor_hermetic` that runs the
    full cross-repo wiring tier. This test fails fast when the
    institution is wired but a cross-repo composition contract is
    broken (e.g. an installed program plugin fails to populate the
    work_source_provider slot). The diagnostic points directly at the
    boundary that needs fixing. Skipped by default to keep the
    cold-start workflow decoupled from the cross-repo contract tier
    per @ADR-0006; run with RESEARCH_INSTITUTION_RUN_VWIRE=1 to
    exercise it in CI.
    """
    if os.environ.get("RESEARCH_INSTITUTION_RUN_VWIRE") != "1":
        pytest.skip("RESEARCH_INSTITUTION_RUN_VWIRE not set; cross-repo wiring skipped")
    gate = REPO / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        pytest.skip("green gate missing")
    env = os.environ.copy()
    env["RESEARCH_INSTITUTION_VWIRE_DIRECT"] = "1"
    result = subprocess.run(
        ["bash", str(gate), "--hermetic"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        env=env,
    )
    assert result.returncode == 0, (
        f"green gate (with V-WIRE) failed: rc={result.returncode} "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "v-wire" in result.stdout, (
        f"V-WIRE sub-check did not appear in gate output: {result.stdout!r}"
    )


@pytest.mark.skipif(
    _supervisor_running(),
    reason=(
        "pi_monitor supervisor is currently running and holds the state lock; "
        "the live-mode sub-check blocks waiting for it. Stop the supervisor "
        "(`pi-monitor stop --config ~/.config/mathlint/local-pi-monitor.toml`) "
        "and re-run to exercise this gate."
    ),
)
def test_cold_start_doctor_live_passes_when_credentials_valid() -> None:
    """Step 3: green gate --live exits 0 when the institution is wired.

    On a fully wired machine, --hermetic and --live MUST both exit 0
    (the only difference is which program provider the engine
    sub-check uses). This test pins the contract: a regression that
    breaks the live gate while the hermetic gate stays GREEN is a
    real defect worth catching here.

    Skipped when the pi_monitor supervisor is active; see the
    skipif condition above. The skip is BLOCKED-class behavior per
    the verification skill: required evidence is unobtainable in
    this run because the operator's environment has a competing
    supervisor.
    """
    gate = REPO / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        pytest.skip("green gate missing")
    # Skip if the operator has no live credentials — the live gate
    # legitimately fails-closed without them, and that's not a defect.
    if not os.environ.get("MATHLINT_MODEL_ROUTE"):
        pytest.skip("MATHLINT_MODEL_ROUTE not set; live gate not exercised")
    result = subprocess.run(
        ["bash", str(gate), "--live"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, (
        f"live gate failed: rc={result.returncode} "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "GREEN INSTITUTION READY" in result.stdout


@pytest.mark.skipif(
    _supervisor_running(),
    reason=(
        "Supervisor holds the state lock; the live engine sub-check "
        "would block. The --no-model --no-write variant below exercises "
        "the same code path without locking."
    ),
)
def test_cold_start_doctor_live_no_model_subcheck_is_nonblocking() -> None:
    """Step 3 (faster oracle): the live-mode engine sub-check is non-blocking.

    The full `bash green-gate --live` path can hang when the pi_monitor
    supervisor is running. This test exercises the SAME live-mode mathlint
    code path (system-readiness with the live provider flags) but with
    `--no-model` and `--no-write`, which:

      - Skip the agent-smoke LLM call (no network, no cost).
      - Skip state-file writes (no lock contention with the supervisor).
      - Still run all engine wiring checks (config, postgres, mathlint).

    A regression that breaks the live-mode code path (the dispatcher
    calls `mathlint system-readiness` before delegating to live-run)
    will surface here even when the full gate is blocked by a
    competing supervisor.
    """
    if not shutil.which("mathlint"):
        pytest.skip("mathlint not on PATH")
    if not os.environ.get("MATHLINT_MODEL_ROUTE"):
        pytest.skip("MATHLINT_MODEL_ROUTE not set; live subcheck not exercised")
    result = subprocess.run(
        [
            "mathlint",
            "system-readiness",
            "--no-model",
            "--no-write",
            "--json",
            "--config",
            os.environ.get("MATHLINT_CONFIG", str(Path.home() / ".config/mathlint" / "local.toml")),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
        cwd=str(REPO / "catalog" if (REPO / "catalog").exists() else str(REPO)),
    )
    # system-readiness with --no-model returns 0 if config loaded
    # (its per-check verdicts are in the JSON, not the exit code).
    assert result.returncode == 0, (
        f"live-mode subcheck failed: rc={result.returncode} stderr={result.stderr[:600]!r}"
    )
    # The JSON output must contain at least one structured check
    # verdict. This is the strongest non-flaky oracle we can use
    # for "live mode can run without hanging".
    import json as _json

    payload = _json.loads(result.stdout)
    assert "checks" in payload, (
        f"system-readiness --json did not return a `checks` list: {payload!r}"
    )
    assert isinstance(payload["checks"], list)
    assert len(payload["checks"]) >= 1, "no check entries in system-readiness verdict"


def test_green_gate_live_with_fake_mathlint(tmp_path: Path) -> None:
    """Hermetic live-mode oracle: green-gate --live runs end-to-end with
    fake mathlint + fake pi-monitor shims that simulate the live-mode
    sub-checks passing.

    This is the strongest non-flaky oracle we have for the live-mode
    gate WITHOUT requiring operator credentials. It exercises:

      - green-gate --live argv parsing
      - the engine sub-check (delegated to mathlint) with a fake shim
      - the supervisor sub-check (skipped — pi-monitor not on PATH
        in this isolated env, just like the operator's PATH)
      - per-program sub-checks (delegated to the kaplansky check
        script)

    The fake mathlint returns rc=0 in live mode when
    MATHLINT_MODEL_ROUTE is set. The fake pi-monitor is absent, so
    the supervisor sub-check is skipped (matching operator envs that
    don't have pi-monitor installed yet).

    This test catches the same regressions as
    test_cold_start_doctor_live_passes_when_credentials_valid but
    runs without depending on operator credentials. It runs even
    when the real pi_monitor supervisor is up (no lock contention).

    Pinned in response to the verification-skill audit: the live gate
    had no hermetic oracle, so a regression that broke --live while
    --hermetic stayed green would slip through CI.
    """
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    log_path = tmp_path / "shim.log"

    # Fake mathlint: succeeds when MATHLINT_MODEL_ROUTE is set; logs
    # the argv so the test can assert delegation happened.
    mathlint_shim = shim_dir / "mathlint"
    mathlint_shim.write_text(
        "#!/bin/sh\n"
        f'echo "MATHLINT_CALLED: $*" >> "{log_path}"\n'
        'if [ -n "$MATHLINT_MODEL_ROUTE" ]; then\n'
        '    exit 0\n'
        "else\n"
        '    echo "FATAL: no MATHLINT_MODEL_ROUTE" >&2\n'
        '    exit 3\n'
        "fi\n",
        encoding="utf-8",
    )
    mathlint_shim.chmod(0o755)

    # Fake engine script: the gate's `ENGINE_SCRIPT` resolves to
    # $HOME/Documents/andrei/math/scripts/check-local-system-readiness.sh
    # by default. We override via RESEARCH_INSTITUTION_ENGINE_SCRIPT so
    # no real mathlint wiring is exercised.
    fake_engine = shim_dir / "fake-engine.sh"
    fake_engine.write_text(
        f"#!/bin/sh\n"
        f'echo "ENGINE_CALLED: $*" >> "{log_path}"\n'
        'exec mathlint "$@"\n',
        encoding="utf-8",
    )
    fake_engine.chmod(0o755)

    # Fake program check-script: also succeeds (the gate's per-program
    # iteration will invoke the resolved `check_program_script`).
    # We pre-populate a tmp katamari project that the gate resolves to.
    fake_program_dir = tmp_path / "kaplansky_fake"
    fake_program_dir.mkdir()
    (fake_program_dir / "scripts").mkdir()
    (fake_program_dir / "scripts" / "check-program-institution.sh").write_text(
        "#!/bin/sh\nexit 0\n",
        encoding="utf-8",
    )
    (fake_program_dir / "scripts" / "check-program-institution.sh").chmod(0o755)

    # Build an isolated catalog pointing at the fake program dir.
    fake_catalog = tmp_path / "catalog"
    fake_catalog.mkdir()
    (fake_catalog / "programs.toml").write_text(
        "[[programs]]\n"
        'name = "kaplansky"\n'
        'display_name = "Kaplansky Research Program (test stub)"\n'
        'repository = "https://github.com/aprokopiw/math-kaplansky"\n'
        'entry_point = "kaplansky.mathlint_plugin:register"\n'
        f'local_path = "{fake_program_dir}"\n'
        'mathlint_pin = "v0.1.0"\n'
        "live_credentials_required = true\n"
        'live_credential_env_vars = ["MATHLINT_MODEL_ROUTE"]\n'
        'check_program_script = "scripts/check-program-institution.sh"\n',
        encoding="utf-8",
    )

    # Run the green gate with --live, isolated PATH (shims only +
    # system PATH for awk/tail/git), and MATHLINT_MODEL_ROUTE set.
    gate = REPO / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        pytest.skip("green gate missing")

    # The gate resolves ROOT from its own location; for an isolated
    # run we cd into the fake catalog directory and symlink the gate
    # so its `ROOT` resolution points at our fake catalog.
    isolated_repo = tmp_path / "isolated_repo"
    isolated_repo.mkdir()
    (isolated_repo / "catalog").symlink_to(fake_catalog, target_is_directory=True)
    gate_in_isolated = isolated_repo / "green-gate"
    gate_in_isolated.symlink_to(REPO / "green-gate", target_is_directory=True)

    env = os.environ.copy()
    env["PATH"] = f"{shim_dir}:{env.get('PATH', '/usr/bin:/bin')}"
    env["MATHLINT_MODEL_ROUTE"] = "openai-codex/test-fake-route"
    env["RESEARCH_INSTITUTION_ENGINE_SCRIPT"] = str(fake_engine)
    env["RESEARCH_INSTITUTION_HERMETIC"] = "1"  # skip v0-ruff
    # Force the gate's `ROOT` resolution by cd-ing; the gate uses
    # `$(dirname "$0")/..` so symlinking it into isolated_repo makes
    # ROOT = isolated_repo.
    result = subprocess.run(
        ["bash", str(gate_in_isolated / "check-institution.sh"), "--live"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
        cwd=str(isolated_repo),
    )
    assert result.returncode == 0, (
        f"live gate failed hermetically: rc={result.returncode} "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "GREEN INSTITUTION READY" in result.stdout, (
        f"gate did not declare ready: stdout={result.stdout!r}"
    )
    # All three sub-checks should appear in the passed list.
    assert "engine" in result.stdout, (
        f"engine sub-check did not pass; stdout={result.stdout!r}"
    )
    assert "program=kaplansky" in result.stdout, (
        f"per-program sub-check did not pass; stdout={result.stdout!r}"
    )

    # The fake mathlint should have been invoked by the gate (the
    # engine sub-check delegates to mathlint under the hood). The
    # per-program check may NOT delegate to mathlint; that's the
    # fake program-script's job. We assert that mathlint was called
    # AT LEAST ONCE (engine sub-check).
    log_text = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    assert "MATHLINT_CALLED" in log_text, (
        f"fake mathlint was never invoked; gate may have bypassed the engine "
        f"sub-check. log={log_text!r}"
    )


def test_green_gate_live_fails_closed_without_credentials(tmp_path: Path) -> None:
    """Hermetic oracle for the failure path: --live MUST fail-closed when
    no MATHLINT_MODEL_ROUTE is set.

    Symmetry with the happy-path oracle above. A regression that lets
    the live gate pass without credentials would surface here.
    """
    shim_dir = tmp_path / "shims"
    shim_dir.mkdir()
    fake_program_dir = tmp_path / "kaplansky_fake"
    fake_program_dir.mkdir()
    (fake_program_dir / "scripts").mkdir()
    (fake_program_dir / "scripts" / "check-program-institution.sh").write_text(
        "#!/bin/sh\nexit 0\n",
        encoding="utf-8",
    )
    (fake_program_dir / "scripts" / "check-program-institution.sh").chmod(0o755)

    fake_catalog = tmp_path / "catalog"
    fake_catalog.mkdir()
    (fake_catalog / "programs.toml").write_text(
        "[[programs]]\n"
        'name = "kaplansky"\n'
        'display_name = "Kaplansky Research Program (test stub)"\n'
        'repository = "https://github.com/aprokopiw/math-kaplansky"\n'
        'entry_point = "kaplansky.mathlint_plugin:register"\n'
        f'local_path = "{fake_program_dir}"\n'
        'mathlint_pin = "v0.1.0"\n'
        "live_credentials_required = true\n"
        'live_credential_env_vars = ["MATHLINT_MODEL_ROUTE"]\n'
        'check_program_script = "scripts/check-program-institution.sh"\n',
        encoding="utf-8",
    )

    gate = REPO / "green-gate" / "check-institution.sh"
    if not gate.is_file():
        pytest.skip("green gate missing")

    isolated_repo = tmp_path / "isolated_repo"
    isolated_repo.mkdir()
    (isolated_repo / "catalog").symlink_to(fake_catalog, target_is_directory=True)
    gate_in_isolated = isolated_repo / "green-gate"
    gate_in_isolated.symlink_to(REPO / "green-gate", target_is_directory=True)

    # Fake mathlint that exits 3 (FAILED) when MATHLINT_MODEL_ROUTE is unset.
    (shim_dir / "mathlint").write_text(
        "#!/bin/sh\n"
        'if [ -n "$MATHLINT_MODEL_ROUTE" ]; then exit 0; else exit 3; fi\n',
        encoding="utf-8",
    )
    (shim_dir / "mathlint").chmod(0o755)

    # Fake engine script: thin wrapper that delegates to mathlint.
    fake_engine = shim_dir / "fake-engine.sh"
    fake_engine.write_text(
        "#!/bin/sh\nexec mathlint \"$@\"\n",
        encoding="utf-8",
    )
    fake_engine.chmod(0o755)

    env = os.environ.copy()
    # Ensure MATHLINT_MODEL_ROUTE is unset (pop if present).
    env.pop("MATHLINT_MODEL_ROUTE", None)
    env["PATH"] = f"{shim_dir}:{env.get('PATH', '/usr/bin:/bin')}"
    env["RESEARCH_INSTITUTION_ENGINE_SCRIPT"] = str(fake_engine)
    env["RESEARCH_INSTITUTION_HERMETIC"] = "1"

    result = subprocess.run(
        ["bash", str(gate_in_isolated / "check-institution.sh"), "--live"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env=env,
        cwd=str(isolated_repo),
    )
    assert result.returncode != 0, (
        "live gate should have failed without MATHLINT_MODEL_ROUTE; "
        f"got rc=0 with stdout={result.stdout!r}"
    )
    assert "RED:" in result.stdout, (
        f"expected RED verdict; got stdout={result.stdout!r}"
    )
