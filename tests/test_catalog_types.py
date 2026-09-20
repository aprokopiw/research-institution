"""Typed Pydantic wire-model tests for catalog entries.

The catalog loader :mod:`research_institution.catalog` parses
each ``[[programs]]`` entry through :class:`ProgramTomlEntry`
(defined in :mod:`research_institution.catalog_types`) for
typed-shape validation at the parse boundary.

Why Pydantic and not the legacy dict-loop:
- A missing required field is caught at ``model_validate`` (one
  raise) rather than the legacy hand-rolled missing-key scan.
- The wire shape is typed; ``extra=\"allow\"`` keeps forward-compat.
- ``field_validator`` checks (``live_credential_env_vars`` are
  strings, ``entry_point`` has ``module:callable`` shape) are
  declarative instead of imperative.

The legacy hand-rolled fallback (``_parse_one_legacy``) is the
fallback for system-Python invocations (green-gate bash shim) where
pydantic may not be installed.
"""

from __future__ import annotations

import unittest

from pydantic import ValidationError

from research_institution.catalog_types import ProgramTomlEntry


class ProgramTomlEntryTests(unittest.TestCase):
    def test_valid_entry_passes(self) -> None:
        entry = {
            "name": "kaplansky",
            "display_name": "Kaplansky Research Program",
            "repository": "https://github.com/example/math-kaplansky",
            "entry_point": "kaplansky.mathlint_plugin:register",
            "local_path": "$HOME/src/math-kaplansky",
            "mathlint_pin": "v1.0.0",
            "live_credentials_required": True,
            "live_credential_env_vars": ["OPENAI_API_KEY"],
            "check_program_script": "scripts/check.sh",
        }
        typed = ProgramTomlEntry.model_validate(entry)
        self.assertEqual(typed.name, "kaplansky")
        self.assertEqual(typed.live_credential_env_vars, ["OPENAI_API_KEY"])

    def test_missing_required_field_rejected(self) -> None:
        entry = {
            "name": "x",
            "display_name": "x",
            "repository": "https://x",
            "entry_point": "x:r",
            "local_path": "/x",
            "mathlint_pin": "v1",
            # ``live_credentials_required`` missing
            "live_credential_env_vars": [],
            "check_program_script": "x.sh",
        }
        with self.assertRaises(ValidationError):
            ProgramTomlEntry.model_validate(entry)

    def test_non_string_credential_rejected(self) -> None:
        entry = {
            "name": "x",
            "display_name": "x",
            "repository": "https://x",
            "entry_point": "x:r",
            "local_path": "/x",
            "mathlint_pin": "v1",
            "live_credentials_required": True,
            "live_credential_env_vars": ["OK", 42],  # int in the list
            "check_program_script": "x.sh",
        }
        with self.assertRaises(ValidationError):
            ProgramTomlEntry.model_validate(entry)

    def test_malformed_entry_point_rejected(self) -> None:
        entry = {
            "name": "x",
            "display_name": "x",
            "repository": "https://x",
            "entry_point": "no-colon-here",  # missing ``:``
            "local_path": "/x",
            "mathlint_pin": "v1",
            "live_credentials_required": True,
            "live_credential_env_vars": [],
            "check_program_script": "x.sh",
        }
        with self.assertRaises(ValidationError):
            ProgramTomlEntry.model_validate(entry)

    def test_extra_fields_pass_through(self) -> None:
        """``extra=\"allow\"`` keeps forward-compat with future operator-added keys."""
        entry = {
            "name": "x",
            "display_name": "x",
            "repository": "https://x",
            "entry_point": "x:r",
            "local_path": "/x",
            "mathlint_pin": "v1",
            "live_credentials_required": False,
            "live_credential_env_vars": [],
            "check_program_script": "x.sh",
            "future_operator_field": "y",
        }
        typed = ProgramTomlEntry.model_validate(entry)
        self.assertEqual(typed.model_extra, {"future_operator_field": "y"})


if __name__ == "__main__":
    unittest.main()
