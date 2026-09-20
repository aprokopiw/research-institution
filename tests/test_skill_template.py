"""Tests for the per-program pi skill template (B.1.5).

These tests pin the wire format of the generated skill markdown. If
the template changes in a way that breaks the operator's pi sessions,
these tests catch it.

Invariants:

  - Frontmatter (`name`, `description`) is present and uses the
    catalog program's `name`.
  - Every verb in SKILL_VERBS gets a documented `sh` code-block.
  - The cross-reference section names @ADR-0006 (the canonical
    scope ADR).
  - The dispatcher is referenced as `research <verb> <name>`.
"""

from __future__ import annotations

from research_institution.catalog import Program
from research_institution.contracts.skill_template import (
    SKILL_TEMPLATE,
    SKILL_VERBS,
    render_skill,
)


def _fake_program(name: str = "kaplansky") -> Program:
    return Program(
        name=name,
        display_name="Kaplansky Research Program",
        repository="https://github.com/aprokopiw/math-kaplansky",
        entry_point="kaplansky.mathlint_plugin:register",
        local_path="$HOME/Documents/andrei/kaplansky",
        mathlint_pin="v0.1.0",
        live_credentials_required=True,
        live_credential_env_vars=("MATHLINT_MODEL_ROUTE",),
        check_program_script="scripts/check-program-institution.sh",
    )


def test_render_skill_returns_string() -> None:
    p = _fake_program()
    out = render_skill(p)
    assert isinstance(out, str)
    assert len(out) > 200  # not a stub


def test_skill_includes_frontmatter_with_program_name() -> None:
    p = _fake_program()
    out = render_skill(p)
    assert "name: kaplansky" in out
    assert "description:" in out


def test_skill_description_includes_display_name() -> None:
    """The frontmatter `description` carries the catalog display_name.

    Mutation-test oracle: a regression that hardcodes a generic
    description (or the wrong program's name) would break operator
    skill discovery silently. This test pins the description's
    catalog-derived content.
    """
    p = _fake_program()
    out = render_skill(p)
    # The display_name appears in the description (frontmatter + body).
    assert p.display_name in out
    # The description field specifically is the catalog-derived one.
    # Find the description line and assert it's not a generic stub.
    import re as _re

    desc_match = _re.search(r"description:\s*(.+)", out)
    assert desc_match is not None, "no description: field in frontmatter"
    desc = desc_match.group(1)
    assert p.display_name in desc, f"description missing display_name; got: {desc!r}"
    assert "WRONG" not in desc, "description contains literal 'WRONG'"


def test_skill_lists_every_documented_verb() -> None:
    """Every verb in SKILL_VERBS appears in the rendered skill as a code-block line."""
    p = _fake_program()
    out = render_skill(p)
    for verb in SKILL_VERBS:
        assert f"research {verb.value} {p.name}" in out, (
            f"verb {verb.value!r} not in rendered skill"
        )


def test_skill_cites_adr_0006() -> None:
    """The cross-reference section must name @ADR-0006 (scope ADR)."""
    p = _fake_program()
    out = render_skill(p)
    assert "@ADR-0006" in out


def test_skill_documents_start_with_dry_run_flag() -> None:
    """The `start` block documents `--dry-run` so operators discover it."""
    p = _fake_program()
    out = render_skill(p)
    assert "start" in out
    assert "--dry-run" in out


def test_skill_template_uses_format_map_placeholders() -> None:
    """The template is a format string with explicit placeholder names.

    If a new field is added to Program, the template should be
    updated to use it; this test pins the placeholder set.
    """
    expected_placeholders = {
        "program_name",
        "display_name",
        "local_path",
        "entry_point",
        "verb_blocks",
        "verb_invocation_summary",
    }
    # Crude but effective: format_map requires every key.
    p = _fake_program()
    out = render_skill(p)
    # If a placeholder is missing, render_skill raises KeyError. Pass.
    assert out
    # And the template's `.format_map` keys must all be in the set.
    # Extract placeholders via a quick parse.
    import re as _re

    found = set(_re.findall(r"\{([a-z_]+)\}", SKILL_TEMPLATE))
    assert found == expected_placeholders, (
        f"template placeholders drift: {found - expected_placeholders} "
        f"missing; {expected_placeholders - found} absent"
    )


def test_skill_template_is_not_empty_for_unknown_program() -> None:
    """Rendering never raises; the template accepts any Program."""
    p = _fake_program(name="some-future-program")
    out = render_skill(p)
    assert "some-future-program" in out
    assert "research start some-future-program" in out


def test_skill_template_drift_guard_for_verb_enum() -> None:
    """Adding a verb to SKILL_VERBS automatically updates the rendered skill.

    This test enumerates the verbs the template currently supports and
    asserts each appears in the rendered output. A new verb added to
    SKILL_VERBS appears automatically; a verb removed drops out.
    """
    p = _fake_program()
    out = render_skill(p)
    for verb in SKILL_VERBS:
        assert verb.value in out
