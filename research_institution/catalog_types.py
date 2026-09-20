"""Typed Pydantic models for catalog entries.

The catalog (``catalog/programs.toml``) is operator-edited; the
loader :func:`research_institution.catalog.load_catalog` parses
each ``[[programs]]`` entry through :class:`ProgramTomlEntry` for
typed-shape validation at the parse boundary.

Why a Pydantic model and not the existing ``Program`` dataclass:
the dataclass owns the *semantic* shape (post-validation invariants
like \"``mathlint_pin`` matches the git-ref regex\"); the Pydantic
model owns the *wire* shape (the TOML keys the operator actually
writes). Conflating them would force the operator to learn about
internal invariants; separating them keeps the wire format loose
(``extra=\"allow\"`` for forward-compat) and the post-validation
shape strict.

Wire format (one ``[[programs]]`` entry):
  - ``name`` (str): the catalog key, must match ``PROGRAM_NAME_RE``.
  - ``display_name`` (str): human label.
  - ``repository`` (str): ``https://`` URL.
  - ``entry_point`` (str): ``\"<dotted.module>:<callable>\"``.
  - ``local_path`` (str): ``$HOME``-relative or absolute path.
  - ``mathlint_pin`` (str): git ref (branch / tag / commit).
  - ``live_credentials_required`` (bool): whether the program needs live creds.
  - ``live_credential_env_vars`` (list[str]): required env-var names.
  - ``check_program_script`` (str): path to the shell check script.

Catalog schema invariants are owned here (canonical regexes);
:mod:`research_institution.catalog` re-uses them in the legacy
``Program.__post_init__`` check so the typed wire parse and the
post-validation dataclass share one source of truth.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, field_validator


#: Catalog schema invariants. Mirrored from catalog/schema.toml; tests
#: enforce both stay in sync via tests/test_catalog.py. These are the
#: canonical regex objects for the catalog wire format; the
#: :class:`Program` dataclass in :mod:`research_institution.catalog`
#: uses them for its post-validation invariants.
PROGRAM_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
GIT_REF_RE = re.compile(r"^[A-Za-z0-9._/-]+$")


class ProgramTomlEntry(BaseModel):
    """Wire shape of one ``[[programs]]`` TOML entry.

    All required fields are typed; ``extra=\"allow\"`` keeps
    forward-compat with future operator-added keys. Validation is
    intentionally loose here (``str`` everywhere); the
    ``Program`` dataclass applies the schema invariants
    (regex matches, ``repository`` starts with ``https://``).
    """

    model_config = ConfigDict(extra="allow")

    name: str
    display_name: str
    repository: str
    entry_point: str
    local_path: str
    mathlint_pin: str
    live_credentials_required: bool
    live_credential_env_vars: list[str]
    check_program_script: str

    @field_validator("name")
    @classmethod
    def _name_matches_re(cls, value: str) -> str:
        """Reject program names that don't match the canonical regex.

        The Pydantic wire parse boundary is the typed home for the
        ``program-name`` constraint; the :class:`Program` dataclass
        in :mod:`research_institution.catalog` uses the same regex
        for its post-validation invariant (single source of truth).
        """
        if not PROGRAM_NAME_RE.match(value):
            raise ValueError(
                f"program name {value!r} does not match {PROGRAM_NAME_RE.pattern}"
            )
        return value

    @field_validator("mathlint_pin")
    @classmethod
    def _mathlint_pin_matches_re(cls, value: str) -> str:
        """Reject mathlint_pin that doesn't match the canonical git-ref regex."""
        if not GIT_REF_RE.match(value):
            raise ValueError(
                f"mathlint_pin {value!r} does not match {GIT_REF_RE.pattern}"
            )
        return value

    @field_validator("repository")
    @classmethod
    def _repository_is_https(cls, value: str) -> str:
        """Reject non-https repository URLs."""
        if not value.startswith("https://"):
            raise ValueError(f"repository {value!r} must be an https:// URL")
        return value

    @field_validator("live_credential_env_vars")
    @classmethod
    def _all_strs(cls, value: list[str]) -> list[str]:
        """Reject non-string env-var names (TOML coerces, but typed wire).

        The list is declared ``list[str]`` so a non-string entry fails
        at the Pydantic parse boundary (typed view). This validator
        returns the value unchanged — it exists to pin the typed
        contract in the wire model (defensive: TOML parsers may
        coerce non-string env-var names to strings silently).
        """
        return list(value)

    @field_validator("entry_point")
    @classmethod
    def _entry_point_shape(cls, value: str) -> str:
        """Validate the ``<module>:<callable>`` shape at parse time.

        The full validation (importability) is the green gate's
        job; here we only enforce the string shape so a malformed
        entry fails fast with a precise diagnostic.
        """
        from research_institution.contracts.entry_point import parse_entry_point
        parse_entry_point(value)
        return value


__all__ = [
    "ProgramTomlEntry",
]
