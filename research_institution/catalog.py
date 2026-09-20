"""Catalog loader: TOML -> typed Program dataclasses.

The catalog is the single source of truth for "which math research
programs are in flight". This module parses it once, validates each
entry against `catalog/schema.toml` invariants, and exposes a frozen
list of `Program` objects the dispatcher consumes.

Per @ADR-0006, the dispatcher does not own the catalog semantics; this
loader is the only place TOML structure is touched. Tests inject
fixtures from `tests/fixtures/catalog.toml`.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

# Catalog schema invariants. Mirrored from catalog/schema.toml; tests
# enforce both stay in sync via tests/test_catalog.py.

_PROGRAM_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_GIT_REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


@dataclass(frozen=True, slots=True)
class Program:
    """One catalog entry. Mirrors `[[programs]]` in catalog/programs.toml.

    Fields map 1:1 to the TOML keys. Derived helpers (resolved_local_path,
    launch_command_path, etc.) are properties so the catalog stays flat.
    """

    name: str
    display_name: str
    repository: str
    entry_point: str
    local_path: str  # raw, $HOME-expanded at resolve time
    mathlint_pin: str
    live_credentials_required: bool
    live_credential_env_vars: tuple[str, ...]
    check_program_script: str

    @property
    def resolved_local_path(self) -> Path:
        """$HOME-expand the local_path field; do not assert existence here."""
        if self.local_path.startswith("$HOME"):
            return Path(self.local_path.replace("$HOME", str(Path.home()), 1))
        return Path(self.local_path)

    @property
    def check_script_path(self) -> Path:
        """Path to the program's local check script (relative to its repo)."""
        return self.resolved_local_path / self.check_program_script

    def __post_init__(self) -> None:
        if not _PROGRAM_NAME_RE.match(self.name):
            raise ValueError(
                f"program name {self.name!r} does not match {_PROGRAM_NAME_RE.pattern}"
            )
        if not _GIT_REF_RE.match(self.mathlint_pin):
            raise ValueError(
                f"mathlint_pin {self.mathlint_pin!r} does not match {_GIT_REF_RE.pattern}"
            )
        if not self.repository.startswith("https://"):
            raise ValueError(f"repository {self.repository!r} must be an https:// URL")
        if not self.entry_point:
            raise ValueError(f"entry_point is required for {self.name}")
        if not self.check_program_script.endswith(".sh"):
            raise ValueError(f"check_program_script {self.check_program_script!r} must end in .sh")
        if not self.local_path.startswith(("/", "$HOME")):
            raise ValueError(f"local_path {self.local_path!r} must start with / or $HOME")
        # Cross-field invariant: entry_point final segment uniqueness is
        # enforced by load_catalog() across the full list.


def load_catalog(path: Path) -> list[Program]:
    """Parse the catalog TOML and return validated, deduplicated Programs.

    Raises ValueError on schema violation. Returns a list (not a dict)
    because catalog order is the operator's declaration order and is
    semantically meaningful (the green gate runs programs in catalog
    order).
    """
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    raw_entries = data.get("programs")
    if not isinstance(raw_entries, list) or not raw_entries:
        raise ValueError(f"catalog at {path} must contain a non-empty [[programs]] table")

    programs: list[Program] = []
    seen_names: set[str] = set()
    seen_entry_segments: set[str] = set()
    for idx, entry in enumerate(raw_entries):
        try:
            prog = _parse_one(entry, idx)
        except ValueError as exc:
            raise ValueError(f"catalog entry #{idx} invalid: {exc}") from exc
        if prog.name in seen_names:
            raise ValueError(f"duplicate program name {prog.name!r}")
        seen_names.add(prog.name)
        segment = prog.entry_point.rsplit(".", 1)[-1]
        if segment in seen_entry_segments:
            raise ValueError(f"duplicate entry_point final segment {segment!r}")
        seen_entry_segments.add(segment)
        programs.append(prog)

    return programs


def _parse_one(entry: dict, idx: int) -> Program:
    """Parse one [[programs]] entry into a Program dataclass."""
    required = (
        "name",
        "display_name",
        "repository",
        "entry_point",
        "local_path",
        "mathlint_pin",
        "live_credentials_required",
        "live_credential_env_vars",
        "check_program_script",
    )
    missing = [k for k in required if k not in entry]
    if missing:
        raise ValueError(f"missing keys: {missing}")

    creds_raw = entry["live_credential_env_vars"]
    if not isinstance(creds_raw, list):
        raise ValueError(f"live_credential_env_vars must be a list, got {type(creds_raw).__name__}")

    # Validate entry_point shape at load time (per @ADR-0006 +
    # contracts/entry_point.py). Shape-only; import-time validation
    # is the green gate's job, not the catalog loader's.
    from research_institution.contracts.entry_point import parse_entry_point

    parse_entry_point(entry["entry_point"])

    return Program(
        name=entry["name"],
        display_name=entry["display_name"],
        repository=entry["repository"],
        entry_point=entry["entry_point"],
        local_path=entry["local_path"],
        mathlint_pin=entry["mathlint_pin"],
        live_credentials_required=bool(entry["live_credentials_required"]),
        live_credential_env_vars=tuple(creds_raw),
        check_program_script=entry["check_program_script"],
    )
