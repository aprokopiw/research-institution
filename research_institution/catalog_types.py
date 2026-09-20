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
  - ``name`` (str): the catalog key, must match ``_PROGRAM_NAME_RE``.
  - ``display_name`` (str): human label.
  - ``repository`` (str): ``https://`` URL.
  - ``entry_point`` (str): ``\"<dotted.module>:<callable>\"``.
  - ``local_path`` (str): ``$HOME``-relative or absolute path.
  - ``mathlint_pin`` (str): git ref (branch / tag / commit).
  - ``live_credentials_required`` (bool): whether the program needs live creds.
  - ``live_credential_env_vars`` (list[str]): required env-var names.
  - ``check_program_script`` (str): path to the shell check script.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator


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

    @field_validator("live_credential_env_vars")
    @classmethod
    def _all_strs(cls, value: list[str]) -> list[str]:
        """Reject non-string env-var names (TOML coerces, but typed wire)."""
        for v in value:
            if not isinstance(v, str):
                raise ValueError(
                    f"live_credential_env_vars entries must be strings; got {type(v).__name__}"
                )
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
    "GIT_REF_RE",
    "PROGRAM_NAME_RE",
    "ProgramTomlEntry",
]
