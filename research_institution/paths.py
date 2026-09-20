"""Canonical path + env resolution. The single source of truth.

All `os.environ.get(...)` reads in production code go through this
module. Centralization lets tests inject deterministic path fixtures
without monkeypatching `os.environ` (which is global and unsafe
across parallel tests).

Why this module exists:

  - `MATHLINT_INSTITUTION_DIR` must be set or the dispatcher refuses
    to operate. Centralized validation means callers don't have to
    re-implement the "is this directory?" check.
  - `PI_MONITOR_REPO`, `PI_AGENT_SKILLS_DIR`, `MATHLINT_PI_MONITOR_CONFIG`
    are operator escape hatches. The defaults match the operator's
    `~/.zshrc` wiring, but tests can override.
  - The `Environment` protocol (defined here too, mirroring the
    dispatcher) lets the CLI's path code be unit-tested with a
    `FakeEnvironment` from `tests/_fakes.py`.

Per `@ADR-0006`: no `$HOME` defaults baked into source code. The
catalog carries absolute paths; tests inject fixtures; operators
configure the env vars.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Protocol


class Environment(Protocol):
    """Typed env-var provider. Mirrors `tests/_fakes.Environment`.

    Duplicated here so production code can declare the dependency
    without importing test code. The two definitions are
    structurally identical.
    """

    def get(self, name: str) -> str | None: ...
    def require(self, name: str) -> str: ...
    def copy(self) -> dict[str, str]: ...


class _OsEnviron:
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


def default_environment() -> Environment:
    """Return the production Environment (os.environ wrapper).

    Tests inject a FakeEnvironment; production code calls this once
    at startup and threads the returned Environment through the
    dispatcher's dependencies.
    """
    return _OsEnviron()


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def institution_dir(env: Optional[Environment] = None) -> Path:
    """Return the research-institution repo root, or raise if unset.

    Resolution order:

    1. The ``MATHLINT_INSTITUTION_DIR`` env var (set by the operator's
       dotfiles; the canonical override).
    2. The current working directory or any ancestor that contains
       ``catalog/programs.toml`` (covers the common case where the
       operator `cd`s into the repo and runs the dispatcher directly
       from there, e.g. in a fresh test or recovery scenario).

    Raises RuntimeError when neither path resolves, with an actionable
    fix that names the env var and the canonical repo path.
    """
    e = env or _OsEnviron()
    raw = e.get("MATHLINT_INSTITUTION_DIR")
    if raw:
        p = Path(raw)
        if not p.is_dir():
            raise RuntimeError(f"MATHLINT_INSTITUTION_DIR points at non-directory: {p}")
        return p
    # Fallback: walk up from cwd looking for the catalog marker.
    import os as _os
    cwd = Path(_os.getcwd())
    for candidate in (cwd, *cwd.parents):
        if (candidate / "catalog" / "programs.toml").is_file():
            return candidate
    raise RuntimeError(
        "MATHLINT_INSTITUTION_DIR is not set AND no ancestor of cwd contains "
        "catalog/programs.toml. Either `cd` into the research-institution repo "
        "first, or export MATHLINT_INSTITUTION_DIR=/path/to/research-institution"
    )


def mathlint_vault(env: Optional[Environment] = None) -> Path:
    """Default location for the mathlint config the dispatcher uses."""
    return Path("~/.config/mathlint").expanduser()


def pi_monitor_config_path(env: Optional[Environment] = None) -> Path:
    """Path to the pi_monitor config the dispatcher uses.

    Catalog-driven: each program declares its supervisor config path.
    Falls back to the operator-shared config for backward compat.
    """
    e = env or _OsEnviron()
    raw = e.get("MATHLINT_PI_MONITOR_CONFIG")
    if raw:
        return Path(raw)
    return mathlint_vault(env) / "local-pi-monitor.toml"


def catalog_path(env: Optional[Environment] = None) -> Path:
    """Default location for the catalog TOML."""
    return institution_dir(env) / "catalog" / "programs.toml"


def green_gate_path(env: Optional[Environment] = None) -> Path:
    """Path to the canonical green-gate script."""
    return institution_dir(env) / "green-gate" / "check-institution.sh"


def pi_monitor_repo(env: Optional[Environment] = None) -> Path:
    """Path to the pi_monitor repo, for locating `start-*.sh` scripts.

    Defaults to `~/Documents/andrei/pi_monitor` per the operator's
    documented wiring. Tests override via the env.
    """
    e = env or _OsEnviron()
    raw = e.get("PI_MONITOR_REPO")
    if raw:
        return Path(raw)
    return Path.home() / "Documents" / "andrei" / "pi_monitor"


def pi_monitor_start_script(env: Optional[Environment] = None) -> Path:
    """The canonical pi_monitor supervisor start script."""
    return pi_monitor_repo(env) / "start-pi-monitor-pi-monitor.sh"


def pi_monitor_state_dir(env: Optional[Environment] = None) -> Path:
    """Directory where the pi_monitor supervisor writes runtime state.

    Hardcoded in pi_monitor as ``~/.local/state/mathlint/pi-monitor/``.
    Surfaced here so the dispatcher's `status` headline reader can
    import it from a single source of truth rather than hardcoding
    the same path.
    """
    e = env or _OsEnviron()
    raw = e.get("PI_MONITOR_STATE_DIR")
    if raw:
        return Path(raw)
    return Path.home() / ".local" / "state" / "mathlint" / "pi-monitor"


def agent_skills_dir(env: Optional[Environment] = None) -> Path:
    """The pi agent's skill discovery root (default `~/.pi/agent/skills`)."""
    e = env or _OsEnviron()
    raw = e.get("PI_AGENT_SKILLS_DIR")
    if raw:
        return Path(raw)
    return Path.home() / ".pi" / "agent" / "skills"


def missing_credentials(prog, env: Optional[Environment] = None) -> list[str]:
    """Return the list of credential env vars the program requires but
    the environment does not provide.

    A program requires credentials iff `live_credentials_required` is
    True (catalog invariant). If required, every name in
    `live_credential_env_vars` must be present in `env`.
    """
    e = env or _OsEnviron()
    if not prog.live_credentials_required:
        return []
    return [v for v in prog.live_credential_env_vars if not e.get(v)]


__all__ = [
    "Environment",
    "agent_skills_dir",
    "catalog_path",
    "default_environment",
    "green_gate_path",
    "institution_dir",
    "mathlint_vault",
    "missing_credentials",
    "pi_monitor_config_path",
    "pi_monitor_repo",
    "pi_monitor_start_script",
    "pi_monitor_state_dir",
]
