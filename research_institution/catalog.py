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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .catalog_types import ProgramTomlEntry

# Catalog schema invariants. Mirrored from catalog/schema.toml; tests
# enforce both stay in sync via tests/test_catalog.py. The Pydantic
# wire model (:class:`catalog_types.ProgramTomlEntry`) is loaded
# lazily by :func:`_parse_one`; importing it at module top would
# force pydantic on every catalog import (and the green-gate bash
# shim invokes the catalog via system Python where pydantic may
# not be installed).
_PROGRAM_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
_GIT_REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
#: Lazy handle to :class:`catalog_types.ProgramTomlEntry`. Loaded
#: on first :func:`_parse_one` call.
_ProgramTomlEntry: type | None = None


def _get_program_toml_entry() -> type:
    global _ProgramTomlEntry
    if _ProgramTomlEntry is None:
        from .catalog_types import ProgramTomlEntry
        _ProgramTomlEntry = ProgramTomlEntry
    return _ProgramTomlEntry


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
    # tomllib returns list[dict[str, Any]]; we re-type as
    # list[dict[str, object]] because that's what the legacy
    # ``_parse_one`` signature accepts (and matches the wire-model
    # contract — ``ProgramTomlEntry.model_validate`` does the real
    # shape check inside ``_parse_one``).
    typed_entries: list[dict[str, object]] = list(raw_entries)  # type: ignore[assignment]

    programs: list[Program] = []
    seen_names: set[str] = set()
    seen_entry_segments: set[str] = set()
    for idx, entry in enumerate(typed_entries):
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


def _parse_one(entry: dict[str, object], idx: int) -> Program:
    """Parse one [[programs]] entry into a Program dataclass.

    Validates the wire shape through :class:`ProgramTomlEntry`
    so a missing required field, a non-list
    ``live_credential_env_vars``, or a malformed ``entry_point``
    fails fast at the typed parse boundary (not deep in the
    dataclass's ``__post_init__`` or a downstream consumer).

    Falls back to the legacy hand-rolled validation path when
    Pydantic is not available (e.g. system-Python invocations via
    the green-gate bash shim where pydantic may not be installed).
    The legacy path keeps the catalog loader functional in that
    environment; typed validation is the canonical path when
    Pydantic is present.
    """
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
        # Preserve the legacy \"missing keys\" error message so the
        # catalog loader's contract (and existing tests) stay stable;
        # the Pydantic ValidationError below catches type mismatches.
        raise ValueError(f"missing keys: {missing}")
    try:
        ProgramTomlEntry_cls = _get_program_toml_entry()
    except ImportError:
        # Pydantic not available (system Python via the green-gate
        # bash shim). Fall back to the legacy hand-rolled path so
        # the catalog still loads.
        return _parse_one_legacy(entry)

    try:
        typed = ProgramTomlEntry_cls.model_validate(entry)
    except Exception as exc:
        # Re-raise with a stable diagnostic; Pydantic's default
        # ``ValidationError`` lists each malformed field but uses
        # different surface wording than the legacy helper.
        raise ValueError(f"entry failed validation: {exc}") from exc

    return Program(
        name=typed.name,
        display_name=typed.display_name,
        repository=typed.repository,
        entry_point=typed.entry_point,
        local_path=typed.local_path,
        mathlint_pin=typed.mathlint_pin,
        live_credentials_required=typed.live_credentials_required,
        live_credential_env_vars=tuple(typed.live_credential_env_vars),
        check_program_script=typed.check_program_script,
    )


def _parse_one_legacy(entry: dict[str, object]) -> Program:
    """Legacy fallback when Pydantic is unavailable.

    Used by the green-gate bash shim which runs via system
    Python where pydantic may not be installed. The typed
    Pydantic path (``_parse_one``) is the canonical entry
    validator when Pydantic is present.
    """
    creds_raw = entry["live_credential_env_vars"]
    creds_list: list[str] = []
    if isinstance(creds_raw, list):
        for v in creds_raw:
            if isinstance(v, str):
                creds_list.append(v)
            else:
                raise ValueError(
                    "live_credential_env_vars entries must be strings"
                )
    else:
        raise ValueError("live_credential_env_vars must be a list")

    from research_institution.contracts.entry_point import parse_entry_point

    entry_point = str(entry["entry_point"])
    parse_entry_point(entry_point)

    return Program(
        name=str(entry["name"]),
        display_name=str(entry["display_name"]),
        repository=str(entry["repository"]),
        entry_point=entry_point,
        local_path=str(entry["local_path"]),
        mathlint_pin=str(entry["mathlint_pin"]),
        live_credentials_required=bool(entry["live_credentials_required"]),
        live_credential_env_vars=tuple(creds_list),
        check_program_script=str(entry["check_program_script"]),
    )
