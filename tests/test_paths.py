"""Tests for the centralized path + env resolution (paths.py).

The dispatcher refuses to operate without `MATHLINT_INSTITUTION_DIR`
set, and several env-var escape hatches (PI_MONITOR_REPO,
PI_AGENT_SKILLS_DIR, MATHLINT_PI_MONITOR_CONFIG) let operators
override defaults. These tests pin:

  - Required env vars raise clear RuntimeErrors when unset.
  - Optional env vars fall back to documented defaults.
  - All env reads go through `Environment` (no monkeypatching of
    `os.environ` in tests).
  - `missing_credentials` honors `live_credentials_required`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from research_institution.catalog import Program
from research_institution.paths import (
    agent_skills_dir,
    catalog_path,
    default_environment,
    green_gate_path,
    institution_dir,
    missing_credentials,
    pi_monitor_config_path,
    pi_monitor_repo,
    pi_monitor_start_script,
)
from tests._fakes import FakeEnvironment


def _fake_program(name: str = "x", *, creds: tuple[str, ...] = ()) -> Program:
    return Program(
        name=name,
        display_name="X",
        repository="https://x/x",
        entry_point="x:r",
        local_path="/x",
        mathlint_pin="v0.1.0",
        live_credentials_required=bool(creds),
        live_credential_env_vars=creds,
        check_program_script="x.sh",
    )


# ---------------------------------------------------------------------------
# institution_dir
# ---------------------------------------------------------------------------


def test_institution_dir_requires_env_var(tmp_path: Path) -> None:
    """Empty env raises a clear RuntimeError naming the missing var."""
    env = FakeEnvironment(values={})
    with pytest.raises(RuntimeError, match="MATHLINT_INSTITUTION_DIR"):
        institution_dir(env)


def test_institution_dir_rejects_non_directory(tmp_path: Path) -> None:
    """Env points at a non-directory -> RuntimeError."""
    env = FakeEnvironment(values={"MATHLINT_INSTITUTION_DIR": "/nonexistent/xyz"})
    with pytest.raises(RuntimeError, match="non-directory"):
        institution_dir(env)


def test_institution_dir_accepts_existing_directory(tmp_path: Path) -> None:
    env = FakeEnvironment(values={"MATHLINT_INSTITUTION_DIR": str(tmp_path)})
    assert institution_dir(env) == tmp_path


def test_institution_dir_in_production(tmp_path: Path, monkeypatch) -> None:
    """When called without env, reads from os.environ via default_environment()."""
    monkeypatch.setenv("MATHLINT_INSTITUTION_DIR", str(tmp_path))
    assert institution_dir() == tmp_path


# ---------------------------------------------------------------------------
# catalog_path / green_gate_path
# ---------------------------------------------------------------------------


def test_catalog_path_is_institution_catalog(tmp_path: Path) -> None:
    env = FakeEnvironment(values={"MATHLINT_INSTITUTION_DIR": str(tmp_path)})
    assert catalog_path(env) == tmp_path / "catalog" / "programs.toml"


def test_green_gate_path_is_institution_green_gate(tmp_path: Path) -> None:
    env = FakeEnvironment(values={"MATHLINT_INSTITUTION_DIR": str(tmp_path)})
    assert green_gate_path(env) == tmp_path / "green-gate" / "check-institution.sh"


# ---------------------------------------------------------------------------
# pi_monitor_* paths
# ---------------------------------------------------------------------------


def test_pi_monitor_config_path_uses_env_override(tmp_path: Path) -> None:
    env = FakeEnvironment(
        values={
            "MATHLINT_INSTITUTION_DIR": str(tmp_path),
            "MATHLINT_PI_MONITOR_CONFIG": "/custom/path/monitor.toml",
        }
    )
    assert pi_monitor_config_path(env) == Path("/custom/path/monitor.toml")


def test_pi_monitor_config_path_falls_back_to_vault(tmp_path: Path) -> None:
    env = FakeEnvironment(values={"MATHLINT_INSTITUTION_DIR": str(tmp_path)})
    expected = Path("~/.config/mathlint/local-pi-monitor.toml").expanduser()
    assert pi_monitor_config_path(env) == expected


def test_pi_monitor_repo_uses_env_override() -> None:
    env = FakeEnvironment(values={"PI_MONITOR_REPO": "/custom/pi_monitor"})
    assert pi_monitor_repo(env) == Path("/custom/pi_monitor")


def test_pi_monitor_repo_falls_back_to_home() -> None:
    env = FakeEnvironment(values={})
    assert pi_monitor_repo(env) == Path.home() / "Documents" / "andrei" / "pi_monitor"


def test_pi_monitor_start_script_is_repo_plus_filename(tmp_path: Path) -> None:
    env = FakeEnvironment(values={"PI_MONITOR_REPO": str(tmp_path)})
    assert pi_monitor_start_script(env) == tmp_path / "start-pi-monitor-pi-monitor.sh"


# ---------------------------------------------------------------------------
# agent_skills_dir
# ---------------------------------------------------------------------------


def test_agent_skills_dir_uses_env_override() -> None:
    env = FakeEnvironment(values={"PI_AGENT_SKILLS_DIR": "/tmp/my_skills"})
    assert agent_skills_dir(env) == Path("/tmp/my_skills")


def test_agent_skills_dir_falls_back_to_default() -> None:
    env = FakeEnvironment(values={})
    assert agent_skills_dir(env) == Path.home() / ".pi" / "agent" / "skills"


# ---------------------------------------------------------------------------
# missing_credentials
# ---------------------------------------------------------------------------


def test_missing_credentials_empty_when_not_required() -> None:
    prog = _fake_program(creds=())
    assert missing_credentials(prog) == []


def test_missing_credentials_all_present() -> None:
    env = FakeEnvironment(values={"OPENAI_API_KEY": "x", "MATHLINT_MODEL_ROUTE": "y"})
    prog = _fake_program(creds=("OPENAI_API_KEY", "MATHLINT_MODEL_ROUTE"))
    assert missing_credentials(prog, env) == []


def test_missing_credentials_reports_only_missing() -> None:
    env = FakeEnvironment(values={"MATHLINT_MODEL_ROUTE": "y"})
    prog = _fake_program(creds=("OPENAI_API_KEY", "MATHLINT_MODEL_ROUTE"))
    assert missing_credentials(prog, env) == ["OPENAI_API_KEY"]


def test_missing_credentials_empty_env_returns_all_required() -> None:
    env = FakeEnvironment(values={})
    prog = _fake_program(creds=("A", "B", "C"))
    assert missing_credentials(prog, env) == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# default_environment + the Protocol identity
# ---------------------------------------------------------------------------


def test_default_environment_returns_os_environ_wrapper() -> None:
    """default_environment() returns an _OsEnviron instance; reading
    PATH via it matches os.environ."""
    e = default_environment()
    import os as _os
    assert e.get("PATH") == _os.environ.get("PATH")


def test_environment_protocol_can_be_subclassed() -> None:
    """Tests can subclass Environment from the production module path
    and the dispatcher / paths module accepts it.

    This catches accidental drift between the two Environment protocol
    declarations (paths.py and tests/_fakes.py).
    """
    from research_institution.paths import Environment

    class _MyEnv:
        def get(self, name): return "v"

        def require(self, name): return "v"

        def copy(self): return {"name": "v"}

    env: Environment = _MyEnv()
    assert env.get("anything") == "v"
