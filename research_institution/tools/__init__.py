"""One-shot operator + maintenance tools for research-institution.

This subpackage contains small, idempotent scripts an operator runs
once (or rarely) to repair, migrate, or inspect a local checkout.
None of these tools are part of the dispatcher CLI surface; they
are intentionally isolated so the dispatcher can stay pure
delegation per ``@ADR-0006``.

Responsibilities:
- Provide standalone entry-point scripts invoked via
  ``python -m research_institution.tools.<name>``.
- Be fail-closed on dry-run; never silently mutate state.

Non-responsibilities:
- Production hot-path logic: anything the dispatcher CLI invokes on
  every command belongs in ``research_institution.gates`` or the
  CLI itself, not here.

Contracts:
- ``@ADR-0006`` (research-institution scope — no application logic
  beyond delegation)
"""
