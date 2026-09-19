"""Tests for the catalog entry_point parser/validator.

The catalog's `entry_point` field is one of the most common operator
typos. These tests pin:

  - The parse contract (must have `:`, both parts non-empty).
  - Whitespace is rejected.
  - Non-strings are rejected.
  - With `import_module=True`, real Python modules are checked.
"""

from __future__ import annotations

import sys
import types

import pytest

from research_institution.contracts.entry_point import (
    parse_entry_point,
    validate_entry_point,
)


def test_parse_basic() -> None:
    """Standard `module:callable` parses cleanly."""
    s = parse_entry_point("kaplansky.mathlint_plugin:register")
    assert s.module_path == "kaplansky.mathlint_plugin"
    assert s.callable_name == "register"
    assert s.module_callable == "kaplansky.mathlint_plugin:register"


def test_parse_dotted_module() -> None:
    """Deep dotted module paths are preserved."""
    s = parse_entry_point("a.b.c.d.e:foo")
    assert s.module_path == "a.b.c.d.e"
    assert s.callable_name == "foo"


def test_parse_no_colon_rejected() -> None:
    with pytest.raises(ValueError, match="must contain ':'"):
        parse_entry_point("kaplansky.mathlint_plugin")


def test_parse_empty_module_rejected() -> None:
    with pytest.raises(ValueError, match="empty module"):
        parse_entry_point(":register")


def test_parse_empty_callable_rejected() -> None:
    with pytest.raises(ValueError, match="empty callable"):
        parse_entry_point("kaplansky.mathlint_plugin:")


def test_parse_whitespace_module_rejected() -> None:
    with pytest.raises(ValueError, match="whitespace"):
        parse_entry_point("kaplansky .mathlint_plugin:register")


def test_parse_whitespace_callable_rejected() -> None:
    with pytest.raises(ValueError, match="whitespace"):
        parse_entry_point("kaplansky.mathlint_plugin:reg ister")


def test_parse_non_string_rejected() -> None:
    with pytest.raises(ValueError, match="must be a string"):
        parse_entry_point(42)  # type: ignore[arg-type]


def test_validate_skips_import_when_disabled() -> None:
    """Default validator does NOT import; only checks shape."""
    spec = parse_entry_point("nonexistent.module:foo")
    ok, reason = validate_entry_point(spec, import_module=False)
    assert ok is True
    assert reason is None


def test_validate_imports_real_module() -> None:
    """With import_module=True, real modules are checked."""
    # Inject a fake module into sys.modules.
    fake = types.ModuleType("research_institution_test_fake_module")
    fake.register = lambda: None  # type: ignore[attr-defined]
    sys.modules["research_institution_test_fake_module"] = fake
    try:
        spec = parse_entry_point("research_institution_test_fake_module:register")
        ok, reason = validate_entry_point(spec, import_module=True)
        assert ok is True
        assert reason is None
    finally:
        del sys.modules["research_institution_test_fake_module"]


def test_validate_rejects_unimportable_module() -> None:
    spec = parse_entry_point("definitely_not_a_real_module_xyz:foo")
    ok, reason = validate_entry_point(spec, import_module=True)
    assert ok is False
    assert reason is not None
    assert "definitely_not_a_real_module_xyz" in reason


def test_validate_rejects_missing_callable() -> None:
    """Module exists but callable doesn't."""
    fake = types.ModuleType("research_institution_test_no_register")
    sys.modules["research_institution_test_no_register"] = fake
    try:
        spec = parse_entry_point("research_institution_test_no_register:register")
        ok, reason = validate_entry_point(spec, import_module=True)
        assert ok is False
        assert "no attribute 'register'" in reason
    finally:
        del sys.modules["research_institution_test_no_register"]


def test_real_catalog_entry_points_parse() -> None:
    """Every real catalog entry's entry_point parses successfully."""
    from pathlib import Path
    from research_institution.catalog import load_catalog

    catalog = Path(__file__).resolve().parents[1] / "catalog" / "programs.toml"
    programs = load_catalog(catalog)
    for prog in programs:
        # Must not raise.
        spec = parse_entry_point(prog.entry_point)
        assert spec.module_path
        assert spec.callable_name
