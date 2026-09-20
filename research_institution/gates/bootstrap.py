"""Bootstrap the institution: clone + pip-install every catalog entry.

Idempotent. Safe to re-run after partial success.

Replaces the previous `scripts/bootstrap-institution.sh`. Behavior:

  1. Install the two dev-dep packages (mathlint, pi-monitor) when
     a `uv` is available; tolerate failure (operators may already
     have these in their own venv — see @ADR-0006).
  2. For each catalog program:
       - git clone <repository> <local_path>  (skip if present)
       - pip install -e <local_path>           (skip if importable)
  3. Purge transient GLLA/build state from each program's checkout
     so the next run starts clean (per @INV-0093).

Every step is testable: `bootstrap_install()` returns a
`BootstrapReport` whose `steps` list carries the per-step outcome.
"""

from __future__ import annotations

import contextlib
import importlib.util
import shutil
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from research_institution.catalog import Program, load_catalog
from research_institution.gates.runner import RunResult, run
from research_institution.paths import catalog_path


TRANSIENT_DIRS: tuple[str, ...] = (
    ".pi-glla",
    "build",
    "dist",
    ".pytest_cache",
    ".ruff_cache",
)


@dataclass(frozen=True, slots=True)
class BootstrapStep:
    """One stage of the bootstrap with its captured outcome."""

    name: str
    detail: str
    result: RunResult | None = None
    skipped: bool = False

    @property
    def ok(self) -> bool:
        if self.skipped:
            return True
        return self.result is not None and self.result.ok


@dataclass(frozen=True, slots=True)
class BootstrapReport:
    """Aggregated outcome of `bootstrap_install`."""

    steps: list[BootstrapStep] = field(default_factory=list)
    programs_installed: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return all(s.ok for s in self.steps)

    @property
    def failures(self) -> list[BootstrapStep]:
        return [s for s in self.steps if not s.ok]


def _is_importable(module_name: str) -> bool:
    """True iff `module_name` resolves in the active Python env.

    Used to skip a `pip install -e` step that has already happened
    (idempotency).
    """
    return importlib.util.find_spec(module_name) is not None


def _dev_dep_argv() -> tuple[str, ...]:
    """Build the pip-install command for the two dev-dep packages.

    The previous shell script installed
    `git+https://github.com/aprokopiw/math-kaplansky-research-program.git@v0.1.0`
    which 404s (the repo was renamed to math-kaplansky). The
    mathlint package is installed locally from
    `~/Documents/andrei/math`; pi-monitor from
    `~/Documents/andrei/pi_monitor`. When those local checkouts are
    absent (e.g. CI runner), the dev-dep step is skipped with a
    WARN — operators are expected to have provided mathlint
    another way (per @ADR-0006, the mathlint dependency is a
    soft convenience, not a hard dep).
    """
    mathlint_local = Path.home() / "Documents" / "andrei" / "math"
    pi_monitor_local = Path.home() / "Documents" / "andrei" / "pi_monitor"
    targets: list[Path] = []
    if mathlint_local.is_dir():
        targets.append(mathlint_local)
    if pi_monitor_local.is_dir():
        targets.append(pi_monitor_local)
    if not targets:
        return ()  # signal: nothing to install locally
    argv: list[str] = ["uv", "pip", "install"]
    argv.extend(f"-e{t}" for t in targets)
    return tuple(argv)


def _dev_dep_step() -> BootstrapStep:
    """Probe for `uv` and run the local dev-dep install. Tolerate failure."""
    import shutil as _sh

    if not _sh.which("uv"):
        return BootstrapStep(
            name="dev-deps",
            detail="uv not on PATH; skipping (mathlint/pi-monitor must already be installed)",
            skipped=True,
        )
    argv = _dev_dep_argv()
    if not argv:
        return BootstrapStep(
            name="dev-deps",
            detail=(
                "no local math/pi_monitor checkouts to install from; "
                "skipping (mathlint/pi-monitor must already be installed)"
            ),
            skipped=True,
        )
    result = run(argv)
    return BootstrapStep(
        name="dev-deps",
        detail=f"uv pip install {' '.join(argv[3:])}",
        result=result,
    )


def _clone_step(program: Program) -> BootstrapStep:
    """Clone a program repo to its `local_path` when absent."""
    local = program.resolved_local_path
    if local.is_dir():
        return BootstrapStep(
            name=f"clone:{program.name}",
            detail=f"already present at {local}",
            skipped=True,
        )
    result = run(("git", "clone", program.repository, str(local)))
    return BootstrapStep(
        name=f"clone:{program.name}",
        detail=f"git clone {program.repository} -> {local}",
        result=result,
    )


def _import_name_for(program: Program) -> str:
    """Best-effort: derive the importable Python module name from
    `entry_point` (e.g. `kaplansky.mathlint_plugin:register` ->
    `kaplansky`). Falls back to the program name.
    """
    ep = program.entry_point
    return ep.split(".", 1)[0] if ep else program.name


def _install_step(program: Program) -> BootstrapStep:
    """`pip install -e` for a catalog program; skip when already importable."""
    module_name = _import_name_for(program)
    if _is_importable(module_name):
        return BootstrapStep(
            name=f"install:{program.name}",
            detail=f"module {module_name!r} already importable; skipping",
            skipped=True,
        )
    local = program.resolved_local_path
    if not local.is_dir():
        return BootstrapStep(
            name=f"install:{program.name}",
            detail=f"local_path missing: {local}; cannot install",
            result=RunResult(
                command=("pip", "install", "-e", str(local)),
                returncode=1,
                stdout="",
                stderr=f"local_path does not exist: {local}",
            ),
        )
    result = run(("pip", "install", "-e", str(local)))
    return BootstrapStep(
        name=f"install:{program.name}",
        detail=f"pip install -e {local}",
        result=result,
    )


def _purge_step(program: Program) -> BootstrapStep:
    """Remove transient state (`TRANSIENT_DIRS`) from a program's checkout."""
    local = program.resolved_local_path
    if not local.is_dir():
        return BootstrapStep(
            name=f"purge:{program.name}",
            detail=f"local_path missing: {local}; nothing to purge",
            skipped=True,
        )
    purged: list[str] = []
    for sub in TRANSIENT_DIRS:
        target = local / sub
        if target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            purged.append(str(target))
        elif target.exists() or target.is_symlink():
            with contextlib.suppress(OSError):
                target.unlink()
            purged.append(str(target))
    detail = f"purged {', '.join(purged)}" if purged else "nothing to purge"
    return BootstrapStep(name=f"purge:{program.name}", detail=detail, skipped=True)


def _iter_programs() -> list[Program]:
    """Read the institution catalog; tolerate absence by returning []."""
    try:
        return list(load_catalog(catalog_path()))
    except (OSError, ValueError, tomllib.TOMLDecodeError):
        return []


def bootstrap_install(
    *,
    skip_dev_deps: bool = False,
    skip_clone: bool = False,
    skip_install: bool = False,
    skip_purge: bool = False,
) -> BootstrapReport:
    """Run the institution bootstrap and return a structured report.

    All flags default to False (every stage runs). Each is a
    testing + recovery escape hatch — operators rarely need to
    set them.

    Idempotent: re-running with default flags is safe and fast
    (every step short-circuits when its precondition is met).
    """
    steps: list[BootstrapStep] = []
    if not skip_dev_deps:
        steps.append(_dev_dep_step())
    programs = _iter_programs()
    for program in programs:
        if not skip_clone:
            steps.append(_clone_step(program))
        if not skip_install:
            steps.append(_install_step(program))
        if not skip_purge:
            steps.append(_purge_step(program))
    installed = tuple(
        step.name.removeprefix("install:")
        for step in steps
        if step.name.startswith("install:") and step.ok and not step.skipped
    )
    return BootstrapReport(steps=steps, programs_installed=installed)


__all__ = [
    "BootstrapReport",
    "BootstrapStep",
    "bootstrap_install",
]
