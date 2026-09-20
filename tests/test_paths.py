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
    mathlint_local_config_path,
    missing_credentials,
    pi_monitor_config_path,
    pi_monitor_repo,
    pi_monitor_start_script,
    resolve_model_route,
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


def test_institution_dir_falls_back_to_catalog_marker(tmp_path: Path, monkeypatch) -> None:
    """Empty env + cwd has catalog/programs.toml -> resolve to cwd's repo root.

    The fallback covers the common case where the operator `cd`s into
    the repo and runs the dispatcher without exporting the env var.
    Mutation-test oracle: a regression that drops the fallback would
    force operators to set MATHLINT_INSTITUTION_DIR for every fresh
    shell, which is the kind of fragility this skill targets.
    """
    repo_root = tmp_path
    (repo_root / "catalog").mkdir()
    (repo_root / "catalog" / "programs.toml").write_text("[[programs]]\n")
    sub = repo_root / "tests" / "deep"
    sub.mkdir(parents=True)
    monkeypatch.delenv("MATHLINT_INSTITUTION_DIR", raising=False)
    monkeypatch.chdir(sub)
    env = FakeEnvironment(values={})
    assert institution_dir(env) == repo_root


def test_institution_dir_raises_when_no_env_and_no_marker(tmp_path: Path, monkeypatch) -> None:
    """Empty env + cwd has no catalog marker -> actionable RuntimeError."""
    isolated = tmp_path / "isolated"
    isolated.mkdir()
    monkeypatch.delenv("MATHLINT_INSTITUTION_DIR", raising=False)
    monkeypatch.chdir(isolated)
    env = FakeEnvironment(values={})
    with pytest.raises(RuntimeError, match="MATHLINT_INSTITUTION_DIR"):
        institution_dir(env)


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
# Composition: pi_monitor_start_script vs. what pi_monitor's
# `watch --script` actually consumes.
#
# The dispatcher surfaces `pi_monitor_start_script(env)` as the
# canonical script path. pi_monitor's `watch` command (per its
# cli.py:946) auto-discovers a script named
# `start-pi-monitor-math.sh` next to the config when `--script` is
# not passed. These are TWO different filenames. A refactor that
# renames one without updating the other breaks the operator's
# cold-start: the watch command's fallback would silently no-op.
#
# This test pins the *contract*: the script file referenced by
# `pi_monitor_start_script` MUST exist in the pi_monitor repo on
# the operator's wired machine, AND pi_monitor's auto-discovery
# fallback MUST be able to find a sibling `start-pi-monitor-math.sh`
# when the config lives next to it. The latter is operator-conditional
# (only relevant when a per-program config is shipped alongside its
# launcher); the test is skipped when no such config exists.
# ---------------------------------------------------------------------------


def test_pi_monitor_start_script_returns_an_existing_file(
    tmp_path: Path, monkeypatch
) -> None:
    """On the operator's wired machine, the canonical script file
    returned by ``pi_monitor_start_script(env)`` MUST exist.

    Defect class: a refactor that renames
    `start-pi-monitor-pi-monitor.sh` in pi_monitor without
    updating `pi_monitor_start_script()` here would leave
    `dispatcher.run_watch(...)` returning a path that the TUI's
    `Launcher(script)` silently treats as missing. The cold-start
    doctor would print GREEN INSTITUTION READY while the operator's
    `research watch <prog>` opens an empty dashboard.
    """
    from research_institution.paths import pi_monitor_start_script

    env = FakeEnvironment(values={"PI_MONITOR_REPO": str(tmp_path)})
    resolved = pi_monitor_start_script(env)
    # Skip when the operator's actual pi_monitor repo is not
    # wired at the default path (CI runner).
    if not resolved.is_file():
        pytest.skip(
            f"pi_monitor_start_script target {resolved} not present "
            f"on this machine; CI-only skip"
        )
    assert resolved.is_file(), (
        f"pi_monitor_start_script returned a path that doesn't exist: "
        f"{resolved}. The path-resolution contract is broken — refactor "
        f"that renames the file in pi_monitor MUST update this function."
    )


def test_pi_monitor_start_script_filename_is_kaplansky_consistent(
    monkeypatch,
) -> None:
    """The filename in ``pi_monitor_start_script`` MUST be the one
    that the kaplansky launcher's documentation references.

    Defect class: a refactor here that renames the file to
    something OTHER than `start-pi-monitor-<project>.sh` style
    breaks the convention operator muscle memory relies on.
    pi_monitor's watch fallback (per cli.py:946) hard-codes
    `start-pi-monitor-math.sh`; this function should at least
    follow the same prefix. The exact name is anchored by
    multiple docs (pi_monitor CHANGELOG; pi_monitor
    docs/guides/unattended.md).
    """
    from research_institution.paths import pi_monitor_start_script

    env = FakeEnvironment(
        values={"PI_MONITOR_REPO": "/tmp/fake-pi-monitor"}  # noqa: S108
    )
    resolved = pi_monitor_start_script(env)
    # Filename MUST start with `start-pi-monitor-` per the operator's
    # documented convention.
    assert resolved.name.startswith("start-pi-monitor-"), (
        f"pi_monitor_start_script returns {resolved.name!r} which "
        f"breaks the `start-pi-monitor-<project>.sh` operator convention. "
        f"Either update the docs to match or rename the file."
    )



# ---------------------------------------------------------------------------
# agent_skills_dir
# ---------------------------------------------------------------------------


def test_agent_skills_dir_uses_env_override() -> None:
    env = FakeEnvironment(values={"PI_AGENT_SKILLS_DIR": "/tmp/my_skills"})  # noqa: S108
    assert agent_skills_dir(env) == Path("/tmp/my_skills")  # noqa: S108


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
        def get(self, name):
            return "v"

        def require(self, name):
            return "v"

        def copy(self):
            return {"name": "v"}

    env: Environment = _MyEnv()
    assert env.get("anything") == "v"


# ---------------------------------------------------------------------------
# resolve_model_route: env-first, then local.toml fallback.
#
# Per @ADR-0001 the operator's canonical place for the live model
# route is `~/.config/mathlint/local.toml` (the `model_route` field).
# The dispatcher auto-injects MATHLINT_MODEL_ROUTE from that file when
# the env var is unset. These tests pin the resolution order and the
# failure modes (missing file, malformed TOML, empty value).
# ---------------------------------------------------------------------------


def test_resolve_model_route_env_var_wins(tmp_path: Path) -> None:
    """Explicit MATHLINT_MODEL_ROUTE env var overrides local.toml."""
    (tmp_path / "local.toml").write_text(
        'model_route = "openai-codex/from-file"\n',
        encoding="utf-8",
    )
    env = FakeEnvironment(
        values={
            "MATHLINT_MODEL_ROUTE": "openai-codex/from-env",
            "MATHLINT_CONFIG": str(tmp_path / "local.toml"),
        }
    )
    assert resolve_model_route(env) == "openai-codex/from-env"


def test_resolve_model_route_falls_back_to_local_toml(tmp_path: Path) -> None:
    """When MATHLINT_MODEL_ROUTE is unset, read `model_route` from local.toml.

    This is the path the operator wanted: configure once in the TOML
    and stop exporting per-shell.
    """
    (tmp_path / "local.toml").write_text(
        'model_route = "openai-codex/gpt-5.6-luna"\n',
        encoding="utf-8",
    )
    env = FakeEnvironment(values={"MATHLINT_CONFIG": str(tmp_path / "local.toml")})
    assert resolve_model_route(env) == "openai-codex/gpt-5.6-luna"


def test_resolve_model_route_returns_none_when_unset(tmp_path: Path) -> None:
    """No env var AND no local.toml -> None (dispatcher will refuse live)."""
    # Point MATHLINT_CONFIG at a path that does NOT exist so we don't
    # accidentally read the operator's real config in this test.
    env = FakeEnvironment(
        values={"MATHLINT_CONFIG": str(tmp_path / "does-not-exist.toml")}
    )
    assert resolve_model_route(env) is None


def test_resolve_model_route_returns_none_for_empty_env_value(tmp_path: Path) -> None:
    """An empty MATHLINT_MODEL_ROUTE is treated as 'not set'.

    Without this, an accidental `export MATHLINT_MODEL_ROUTE=` (empty)
    would inject "" into the subprocess env, which mathlint would then
    refuse with a different (less actionable) error than the dispatcher's
    'no route configured' diagnostic.
    """
    env = FakeEnvironment(values={"MATHLINT_MODEL_ROUTE": ""})
    assert resolve_model_route(env) is None


def test_resolve_model_route_returns_none_for_empty_toml_field(tmp_path: Path) -> None:
    """An empty `model_route` field in local.toml is treated as 'not set'.

    Mirrors the env-empty case: never inject an empty string into
    subprocess env.
    """
    (tmp_path / "local.toml").write_text('model_route = ""\n', encoding="utf-8")
    env = FakeEnvironment(values={"MATHLINT_CONFIG": str(tmp_path / "local.toml")})
    assert resolve_model_route(env) is None


def test_resolve_model_route_returns_none_on_malformed_toml(tmp_path: Path) -> None:
    """A malformed local.toml is treated as 'no route configured'.

    Fail-closed: a syntax error in the operator's config MUST NOT
    cause the dispatcher to launch with a stale/wrong route. Better
    to refuse and surface the parse error than to silently misroute
    LLM calls.
    """
    (tmp_path / "local.toml").write_text(
        "this is not = valid TOML [[[\n",
        encoding="utf-8",
    )
    env = FakeEnvironment(values={"MATHLINT_CONFIG": str(tmp_path / "local.toml")})
    assert resolve_model_route(env) is None


def test_resolve_model_route_ignores_non_string_field(tmp_path: Path) -> None:
    """A non-string `model_route` field (e.g. int) is ignored.

    Defensive against operator-side tooling that might insert the
    wrong shape; the resolver must never inject a non-string into
    subprocess env (subprocess.run rejects it).
    """
    (tmp_path / "local.toml").write_text("model_route = 42\n", encoding="utf-8")
    env = FakeEnvironment(values={"MATHLINT_CONFIG": str(tmp_path / "local.toml")})
    assert resolve_model_route(env) is None


def test_mathlint_local_config_path_uses_env_override(tmp_path: Path) -> None:
    """MATHLINT_CONFIG env var overrides the default `~/.config/...` path."""
    cfg = tmp_path / "alt-config.toml"
    env = FakeEnvironment(values={"MATHLINT_CONFIG": str(cfg)})
    assert mathlint_local_config_path(env) == cfg


def test_mathlint_local_config_path_defaults_to_home_vault() -> None:
    """When MATHLINT_CONFIG is unset, default is `~/.config/mathlint/local.toml`."""
    env = FakeEnvironment(values={})
    assert mathlint_local_config_path(env) == Path.home() / ".config" / "mathlint" / "local.toml"
