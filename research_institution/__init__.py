"""research-institution: catalog-driven dispatcher over mathlint + pi_monitor.

Per @ADR-0006, this package owns only:
- catalog (declarative program registry)
- bootstrap (clone + install)
- green gate (canonical wiring evidence)
- this dispatcher CLI (catalog-driven delegation)

No application logic. No data parsing. No persistence boundary crossings.
Every command is a thin subprocess wrapper around a sibling-repo CLI.

Public surface
--------------

The recommended imports for external callers (tests, scripts, future
extensions) are:

* :class:`Program` / :func:`load_catalog` — the catalog model + loader.
* :class:`Dispatcher` — the in-process API (runner/env/clock-injectable).
* :class:`GateVerdict` / :class:`GateVerdictStatus` — the
  architecture-review gate verdict type + enum.
* :class:`TaskKind` — the parsed `TASK KIND:` enum from mathlint.
* :class:`ExitCode` — the dispatcher's documented exit codes.
* :class:`DispatcherVerb` — the canonical CLI verb names.

Deep imports are allowed but discouraged: a generic agent should
be able to write `from research_institution import Dispatcher` and
have it work without knowing the package's internal layout.
"""

from research_institution.catalog import Program, load_catalog
from research_institution.contracts import (
    DispatcherVerb,
    ExitCode,
    GateVerdict,
    GateVerdictStatus,
    TaskKind,
    gate_verdict_from_task_kind,
)
from research_institution.dispatcher import (
    DEFAULT_POLICY,
    Dispatcher,
    SubprocessPolicy,
    SubprocessResult,
)

__all__ = [
    "DEFAULT_POLICY",
    "Dispatcher",
    "DispatcherVerb",
    "ExitCode",
    "GateVerdict",
    "GateVerdictStatus",
    "Program",
    "SubprocessPolicy",
    "SubprocessResult",
    "TaskKind",
    "gate_verdict_from_task_kind",
    "load_catalog",
]
__version__ = "0.1.0"
