"""Tests for the catalog entry_point parser/validator.

The catalog's `entry_point` field is one of the most common operator
typos. These tests pin:

  - The parse contract (must have `:`, both parts non-empty).
  - Whitespace is rejected.
  - Non-strings are rejected.
  - With `import_module=True`, real Python modules are checked.
"""

from __future__ import annotations

import random
import string
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


# ---------------------------------------------------------------------------
# Property tests (stdlib random; no hypothesis dependency).
#
# These exercise the parser with synthesized valid + adversarial inputs
# to catch off-by-one or whitespace-handling regressions that the
# fixed-snapshot tests above might miss. The synthesized generators
# only produce strings that the parser is supposed to accept; the
# negative tests verify rejection of malformed inputs.
#
# `random.Random` is fine here — these are property tests, not
# cryptographic use. We seed deterministically so the tests are
# reproducible across runs.
# ---------------------------------------------------------------------------


_VALID_MODULE_CHARS = string.ascii_lowercase + string.digits + "_"
_VALID_CALLABLE_CHARS = string.ascii_lowercase + string.digits + "_"


def _gen_valid_module(rng: random.Random, depth: int = 1, max_depth: int = 4) -> str:
    """Generate a dotted Python module path of `depth` segments.

    Always starts with a letter; each segment is 1-8 chars from the
    safe identifier alphabet. Avoids reserved words (none of the
    single-letter segments here are Python keywords).
    """
    if depth > max_depth or (depth > 1 and rng.random() < 0.3):
        if depth == 1:
            return _gen_valid_module(rng, depth=1, max_depth=max_depth)
        return ""
    seg = rng.choice(string.ascii_lowercase) + "".join(
        rng.choices(_VALID_MODULE_CHARS, k=rng.randint(0, 7))
    )
    rest = _gen_valid_module(rng, depth + 1, max_depth)
    return f"{seg}.{rest}" if rest else seg


def _gen_valid_callable(rng: random.Random) -> str:
    """Generate a valid Python identifier (callable name)."""
    return rng.choice(string.ascii_lowercase) + "".join(
        rng.choices(_VALID_CALLABLE_CHARS, k=rng.randint(0, 7))
    )


def test_property_round_trip_valid_inputs() -> None:
    """For every synthesized valid (module, callable) pair, parsing succeeds
    and `module_callable` reconstructs the original string.

    This is the strongest invariant the parser has: identity for
    well-formed inputs. A regression that mangles either field fails
    here.
    """
    rng = random.Random(0xC0DE_CAFE)  # deterministic seed  # noqa: S311
    for _ in range(500):
        module_path = _gen_valid_module(rng)
        callable_name = _gen_valid_callable(rng)
        s = f"{module_path}:{callable_name}"
        spec = parse_entry_point(s)
        assert spec.module_path == module_path, (
            f"module_path drift: got {spec.module_path!r}, expected {module_path!r}"
        )
        assert spec.callable_name == callable_name
        assert spec.module_callable == s


def test_property_module_callable_idempotent() -> None:
    """`parse(parse(s).module_callable) == parse(s)` for every valid s.

    Idempotence: parsing a parsed-then-reserialized entry point must
    yield an equivalent spec. Catches a class of bug where the parser
    normalizes the string in a way that round-trips incorrectly.
    """
    rng = random.Random(0xBADF_00D5)  # noqa: S311
    for _ in range(200):
        module_path = _gen_valid_module(rng)
        callable_name = _gen_valid_callable(rng)
        s1 = f"{module_path}:{callable_name}"
        spec1 = parse_entry_point(s1)
        spec2 = parse_entry_point(spec1.module_callable)
        assert spec1 == spec2, f"idempotence broken: {spec1!r} != {spec2!r}"


@pytest.mark.parametrize(
    "bad_input, expected_match",
    [
        ("", "must contain ':'"),
        ("nocolon", "must contain ':'"),
        (":", "empty module"),
        (":callable", "empty module"),
        ("module:", "empty callable"),
        ("  :callable", "whitespace"),
        ("module:  ", "whitespace"),
        ("module :callable", "whitespace"),
        ("module:call able", "whitespace"),
    ],
)
def test_property_rejects_malformed_inputs(bad_input: str, expected_match: str) -> None:
    """Every known-malformed shape is rejected with a diagnostic containing
    the operator-meaningful substring. Pins both rejection AND the
    diagnostic shape so a regression that silently accepts bad input
    (or accepts it with a different error message) surfaces.
    """
    with pytest.raises(ValueError, match=expected_match):
        parse_entry_point(bad_input)


def test_property_module_with_internal_colon_uses_last_colon() -> None:
    """`rpartition` semantic: the LAST `:` splits module from callable.

    A module name does not normally contain `:`, but if it did (e.g.
    a paste error), the parser's split must agree with the documented
    contract: leftmost-but-last for `:` in the module portion.
    """
    spec = parse_entry_point("a:b:c")
    # rpartition(':') -> ('a:b', ':', 'c'). Callable = 'c'.
    assert spec.module_path == "a:b"
    assert spec.callable_name == "c"


def test_property_deeply_nested_module_parses() -> None:
    """Modules 6+ levels deep still parse without truncation."""
    module_path = "a.b.c.d.e.f.g.h.i.j"
    spec = parse_entry_point(f"{module_path}:register")
    assert spec.module_path == module_path
    assert spec.callable_name == "register"


def test_property_arbitrary_non_string_inputs_are_rejected() -> None:
    """The parser must reject non-strings, not call into a `str` method."""
    for bad in [None, 42, 3.14, ["module:fn"], {"key": "v"}, b"bytes"]:
        with pytest.raises(ValueError, match="must be a string"):
            parse_entry_point(bad)  # type: ignore[arg-type]
