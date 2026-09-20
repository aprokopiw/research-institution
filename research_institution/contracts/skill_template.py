"""Typed rendering of per-program pi skill markdown.

The dispatcher CLI exposes `research install-skills` (B.1.5). It
generates one skill markdown per catalog entry, symlinked into
`$PI_AGENT_SKILLS_DIR`. This module owns the template + the rendering
logic so:

  - The template is version-controlled and unit-testable (no string
    concat in `cli.py`).
  - The `DispatcherVerb` enum drives the verb list (B.1.5 in
    ADR-0006); renaming a verb here updates the template
    and the tests automatically.
  - Drift tests in `tests/test_skill_template.py` pin the wire format
    so a future change to `claude-code`'s skill loader surfaces
    immediately.
"""

from __future__ import annotations

from research_institution.catalog import Program
from research_institution.contracts import DispatcherVerb

# The skill markdown template. Uses str.format_map for explicit
# variable names; if a new field is added to Program, this template
# will fail-fast at the test layer.
SKILL_TEMPLATE = """\
---
name: {program_name}
description: {verb_invocation_summary} Thin wrapper over `research {program_name} ...` (the catalog-driven dispatcher in research-institution). Use when the operator says "{program_name} start", "{program_name} stop", "@{program_name}", or asks to interact with this program.
---

# {display_name}

Catalog entry: `{program_name}`. Local path: `{local_path}`. Entry point: `{entry_point}`.

## Invoke

```sh
{verb_blocks}
```

All commands are thin subprocess wrappers around mathlint + pi_monitor. See
`docs/operations/research-institution-quickstart.md` for the operator
one-pager.

## Cross-references

- `@ADR-0006` — research-institution owns only catalog + bootstrap + green gate + dispatcher.
- `{local_path}/docs/ROADMAP.md` — program-specific roadmap.
"""


# Verbs surfaced in the skill template, in display order.
SKILL_VERBS: tuple[DispatcherVerb, ...] = (
    DispatcherVerb.START,
    DispatcherVerb.STOP,
    DispatcherVerb.STATUS,
    DispatcherVerb.WATCH,
)


def _verb_block(verb: DispatcherVerb, program_name: str) -> str:
    """One 'sh' code-block line per verb, with the documented flags."""
    if verb == DispatcherVerb.START:
        return f"# {verb.value.capitalize()} (refused if architecture-review gate is closed; --dry-run bypasses).\nresearch {verb.value} {program_name} [--dry-run]"
    if verb == DispatcherVerb.WATCH:
        return f"# {verb.value.capitalize()} (TUI; needs a real TTY).\nresearch {verb.value} {program_name}"
    return f"# {verb.value.capitalize()}\nresearch {verb.value} {program_name}"


def render_skill(prog: Program) -> str:
    """Render the skill markdown for one catalog program.

    Pure function: no I/O, no filesystem. The CLI layer writes the
    rendered string to disk and symlinks it.
    """
    verb_blocks = "\n\n".join(_verb_block(v, prog.name) for v in SKILL_VERBS)
    description = (
        f"Start, stop, status, and watch the {prog.display_name} program. "
        "Thin wrapper over `research " + prog.name + " ...` (the catalog-driven "
        "dispatcher in research-institution). Use when the operator says "
        f'"{prog.name} start", "{prog.name} stop", "@{prog.name}", or asks '
        "to interact with this program."
    )
    return SKILL_TEMPLATE.format_map(
        {
            "program_name": prog.name,
            "display_name": prog.display_name,
            "local_path": prog.local_path,
            "entry_point": prog.entry_point,
            "verb_blocks": verb_blocks,
            "verb_invocation_summary": description,
        }
    )


__all__ = [
    "SKILL_TEMPLATE",
    "SKILL_VERBS",
    "render_skill",
]
