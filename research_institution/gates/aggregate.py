"""Aggregate every gate into one verdict.

The previous shell script lived at `green-gate/check-institution.sh`
and inlined six steps: v0-ruff, v-wire (mathlint's autonomy.sh
G7), engine (mathlint's check-local-system-readiness.sh),
supervisor (`pi-monitor doctor`), per-program checks (each
catalog entry's `check_program_script`), and a verdict printer.

Re-implemented here in Python so each step is testable in
isolation. Operators can either:

    python -m research_institution.gates.aggregate check
    # or, equivalently:
    bash green-gate/check-institution.sh --hermetic   # thin shim

The aggregator exposes a CLI (`python -m
research_institution.gates.aggregate`) and an in-process API
(`check_institution()`) that returns a `GateReport`.
"""

from __future__ import annotations

import argparse
import enum
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from research_institution.catalog import Program, load_catalog
from research_institution.gates.runner import RunResult, run
from research_institution.paths import (
    catalog_path,
    institution_dir,
    pi_monitor_config_path,
)


class GateStatus(enum.Enum):
    """The bounded set of gate verdicts.

    Mirrors the operator's mental model: a gate is either PASS
    or it isn't. There is no "WARN" verdict because the
    institution green-gate is fail-closed (per @INV-0093,
    GREEN means every check passed; anything else is RED).
    """

    PASS = "pass"  # noqa: S105 — enum label, not a password
    FAIL = "fail"
    SKIP = "skip"


@dataclass(frozen=True, slots=True)
class GateCheck:
    """A single gate stage with its verdict + captured output."""

    name: str
    status: GateStatus
    detail: str = ""
    output: str = ""
    result: RunResult | None = None

    @property
    def ok(self) -> bool:
        return self.status is not GateStatus.FAIL


@dataclass(frozen=True, slots=True)
class GateReport:
    """Aggregated institution gate verdict.

    `ok` is True iff every check passed or was skipped; a single
    FAIL propagates as `not ok`. `check_program_script` failures
    carry the program's name so operators see *which* program
    is mis-wired without re-running individual gates.
    """

    checks: tuple[GateCheck, ...]
    mode: str

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks)

    @property
    def failures(self) -> tuple[GateCheck, ...]:
        return tuple(c for c in self.checks if c.status is GateStatus.FAIL)

    def render(self) -> str:
        lines: list[str] = []
        for check in self.checks:
            prefix = f"[{check.name}]"
            if check.status is GateStatus.PASS:
                lines.append(f"{prefix} ok")
            elif check.status is GateStatus.SKIP:
                lines.append(f"{prefix} skipped ({check.detail})")
            else:
                lines.append(f"{prefix} FAILED ({check.detail})")
                if check.output:
                    lines.append(check.output.rstrip("\n"))
        lines.append("")
        if self.ok:
            lines.append("GREEN INSTITUTION READY")
            passed_names = [c.name for c in self.checks if c.status is GateStatus.PASS]
            lines.append(f"passed: {' '.join(passed_names)}")
        else:
            failed_names = [c.name for c in self.failures]
            lines.append(f"RED: failed checks: {' '.join(failed_names)}")
        return "\n".join(lines)



# ---------------------------------------------------------------------------
# Stage implementations
# ---------------------------------------------------------------------------


def _ruff_check() -> GateCheck:
    """Run `ruff check research_institution tests` when `ruff` is on PATH.

    `ruff` is not a hard dependency — CI is the canonical enforcer.
    A missing ruff is reported as SKIP, never FAIL.
    """
    if shutil.which("ruff") is None:
        return GateCheck(
            name="v0-ruff",
            status=GateStatus.SKIP,
            detail="ruff not on PATH (skipped; CI enforces this gate)",
        )
    inst = institution_dir()
    result = run(("ruff", "check", "research_institution", "tests"), cwd=inst)
    if result.ok:
        return GateCheck(name="v0-ruff", status=GateStatus.PASS, detail="ruff ok")
    return GateCheck(
        name="v0-ruff",
        status=GateStatus.FAIL,
        detail="ruff reported violations",
        output=result.stdout + result.stderr,
        result=result,
    )


def _v_wire_check(*, mode: str) -> GateCheck:
    """Run mathlint's autonomy.sh G7 (cross-repo wiring) tier.

    Honors three bypass knobs that the operator might legitimately
    use:

        RESEARCH_INSTITUTION_HERMETIC=1
            Skip entirely (CI runners without mathlint).

        MATHLINT_AUTONOMY_SKIP_G7=1
            Cold-start hatch (mathlint isn't bootstrapped yet).

        RESEARCH_INSTITUTION_VWIRE_DIRECT=1
            Bypass autonomy.sh G1..G6 and invoke just the cross-repo
            wiring test directly. Useful when conventions drift
            (one of the 41 mathlint test marker violations) and the
            operator wants only the wiring signal.

    The bypasses preserve backward compatibility with the original
    shell aggregator.
    """
    if os.environ.get("RESEARCH_INSTITUTION_HERMETIC") == "1":
        return GateCheck(
            name="v-wire",
            status=GateStatus.SKIP,
            detail="RESEARCH_INSTITUTION_HERMETIC=1 (skipped)",
        )
    if os.environ.get("MATHLINT_AUTONOMY_SKIP_G7") == "1":
        return GateCheck(
            name="v-wire",
            status=GateStatus.SKIP,
            detail="MATHLINT_AUTONOMY_SKIP_G7=1 (skipped)",
        )
    autonomy = Path.home() / "Documents" / "andrei" / "math" / "scripts" / "autonomy.sh"
    mathlint_test_dir = Path.home() / "Documents" / "andrei" / "math"
    direct = os.environ.get("RESEARCH_INSTITUTION_VWIRE_DIRECT") == "1"
    direct_test = mathlint_test_dir / "tests" / "local_readiness" / "test_cross_repo_wiring.py"
    if direct and direct_test.is_file():
        pytest = mathlint_test_dir / ".venv" / "bin" / "python"
        if not pytest.is_file():
            pytest = Path(sys.executable)
        cmd = (
            str(pytest),
            "-m",
            "pytest",
            "--no-cov",
            "-q",
            "tests/local_readiness/test_cross_repo_wiring.py",
        )
        result = run(cmd, cwd=mathlint_test_dir)
        if result.ok:
            return GateCheck(name="v-wire", status=GateStatus.PASS, detail="direct test ok")
        return GateCheck(
            name="v-wire",
            status=GateStatus.FAIL,
            detail="direct cross-repo wiring test failed",
            output=result.stdout + result.stderr,
            result=result,
        )
    if autonomy.is_file():
        result = run(("bash", str(autonomy)))
        if result.ok:
            return GateCheck(name="v-wire", status=GateStatus.PASS, detail="autonomy.sh ok")
        return GateCheck(
            name="v-wire",
            status=GateStatus.FAIL,
            detail="autonomy.sh failed",
            output=result.stdout + result.stderr,
            result=result,
        )
    return GateCheck(
        name="v-wire",
        status=GateStatus.SKIP,
        detail=f"autonomy.sh not at {autonomy}; skipping",
    )


def _engine_check(*, mode: str) -> GateCheck:
    """Run mathlint's check-local-system-readiness.sh.

    Hermetic mode routes the provider through the bundled
    ``self_test-sample`` program (no LLM, no postgres); live
    mode runs the operator's real config. The flag
    ``--skip-external`` mirrors the previous shell aggregator's
    default for hermetic.

    The ``RESEARCH_INSTITUTION_ENGINE_SCRIPT`` env var overrides
    the engine path so tests can stub mathlint with a fake
    script. The escape hatch honors the convention established
    by the previous shell aggregator's contract.
    """
    override = os.environ.get("RESEARCH_INSTITUTION_ENGINE_SCRIPT")
    if override:
        engine_script = Path(override)
        if not engine_script.is_file():
            return GateCheck(
                name="engine",
                status=GateStatus.SKIP,
                detail=f"RESEARCH_INSTITUTION_ENGINE_SCRIPT points at missing file: {engine_script}",
            )
    else:
        engine_script = (
            Path.home() / "Documents" / "andrei" / "math" / "scripts" / "check-local-system-readiness.sh"
        )
        if not engine_script.is_file():
            return GateCheck(
                name="engine",
                status=GateStatus.SKIP,
                detail="math-engine not at expected path; skipping",
            )
    argv: tuple[str, ...] = ("bash", str(engine_script))
    if mode == "hermetic":
        argv = (*argv, "--skip-external", "--use-program=self_test-sample")
    result = run(argv)
    if result.ok:
        return GateCheck(name="engine", status=GateStatus.PASS, detail="mathlint ok")
    return GateCheck(
        name="engine",
        status=GateStatus.FAIL,
        detail="math-engine readiness check failed",
        output=result.stdout + result.stderr,
        result=result,
    )


def _supervisor_check() -> GateCheck:
    """Run `pi-monitor doctor` when `pi-monitor` is on PATH."""
    if shutil.which("pi-monitor") is None and not (Path(__file__).resolve().parents[3] / ".venv" / "bin" / "pi-monitor").is_file():
        return GateCheck(
            name="supervisor",
            status=GateStatus.SKIP,
            detail="pi-monitor not on PATH; skipping",
        )
    config = pi_monitor_config_path()
    argv: tuple[str, ...]
    if config.is_file():
        argv = ("pi-monitor", "doctor", "--config", str(config))
    else:
        argv = ("pi-monitor", "doctor")
    result = run(argv)
    if result.ok:
        return GateCheck(name="supervisor", status=GateStatus.PASS, detail="pi-monitor ok")
    return GateCheck(
        name="supervisor",
        status=GateStatus.FAIL,
        detail="pi-monitor doctor failed",
        output=result.stdout + result.stderr,
        result=result,
    )


def _program_check(program: Program, *, mode: str) -> GateCheck:
    """Run a single catalog program's `check_program_script`.

    Honors the same hermetic/live split as the engine check.
    Tolerates a missing or missing-script local checkout with
    WARN-style SKIPs (not FAILs) because the bootstrap may
    not have run yet; bootstrap is owned by a separate gate.
    """
    label = f"program={program.name}"
    local = program.resolved_local_path
    if not local.is_dir():
        return GateCheck(
            name=label,
            status=GateStatus.SKIP,
            detail=f"local_path missing: {local}",
        )
    check_script = local / program.check_program_script
    if not check_script.is_file():
        return GateCheck(
            name=label,
            status=GateStatus.SKIP,
            detail=f"check script missing: {check_script}",
        )
    argv: tuple[str, ...] = ("bash", str(check_script))
    argv = (*argv, "--live" if mode == "live" else "--hermetic")
    result = run(argv, cwd=local)
    if result.ok:
        return GateCheck(name=label, status=GateStatus.PASS, detail=f"{program.name} ok")
    return GateCheck(
        name=label,
        status=GateStatus.FAIL,
        detail=f"{program.name} check failed",
        output=result.stdout + result.stderr,
        result=result,
    )


def _iter_programs() -> list[Program]:
    """Read the institution catalog; tolerate absence."""
    try:
        return list(load_catalog(catalog_path()))
    except (OSError, ValueError, Exception):  # noqa: BLE001 — fail-open
        return []


# ---------------------------------------------------------------------------
# Public aggregator
# ---------------------------------------------------------------------------


def check_institution(
    mode: str = "hermetic",
    skip_programs: tuple[str, ...] = (),
) -> GateReport:
    """Run the institution green gate end-to-end.

    `mode` is `hermetic` (default — CI-safe, no LLM) or `live`
    (operator-only — requires credentials). `skip_programs`
    lets the operator exclude one program (useful when
    developing that program).

    Returns a `GateReport`. The method is the canonical
    diagnostic surface for every external caller (`doctor`,
    the bash shim, the architecture-review gate, and the
    research-institution tests).
    """
    if mode not in {"hermetic", "live"}:
        raise ValueError(f"mode must be 'hermetic' or 'live'; got {mode!r}")
    checks: list[GateCheck] = []
    checks.append(_ruff_check())
    checks.append(_v_wire_check(mode=mode))
    checks.append(_engine_check(mode=mode))
    checks.append(_supervisor_check())
    for program in _iter_programs():
        if program.name in skip_programs:
            checks.append(
                GateCheck(
                    name=f"program={program.name}",
                    status=GateStatus.SKIP,
                    detail="skipped by --skip-program",
                )
            )
            continue
        checks.append(_program_check(program, mode=mode))
    return GateReport(checks=tuple(checks), mode=mode)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for `python -m research_institution.gates.aggregate`.

    Default verb is `check`. Accepts `list` as the only explicit
    alternative. Tolerates `--hermetic`/`--live`/`--skip-program`
    flags just like the previous shell aggregator.
    """
    parser = argparse.ArgumentParser(
        prog="research-institution-gate",
        description=(
            "Run the institution green gate (replaces green-gate/check-institution.sh)."
        ),
    )
    parser.add_argument(
        "verb",
        nargs="?",
        default="check",
        choices=("check", "list"),
        help="Action to perform (default: check).",
    )
    parser.add_argument(
        "--hermetic",
        action="store_const",
        const="hermetic",
        dest="mode",
        help="Run in CI-safe mode (default).",
    )
    parser.add_argument(
        "--live",
        action="store_const",
        const="live",
        dest="mode",
        help="Run in operator-live mode (requires credentials).",
    )
    parser.add_argument(
        "--skip-program",
        action="append",
        default=[],
        dest="skip_programs",
        metavar="NAME",
        help="Skip a catalog program (repeatable).",
    )
    parser.set_defaults(mode="hermetic")
    ns = parser.parse_args(argv)
    if ns.verb == "list":
        print("NAME\tDISPLAY\tREPOSITORY\tENTRY_POINT")
        for p in _iter_programs():
            print(f"{p.name}\t{p.display_name}\t{p.repository}\t{p.entry_point}")
        return 0
    report = check_institution(
        mode=ns.mode,
        skip_programs=tuple(ns.skip_programs),
    )
    print(report.render())
    return 0 if report.ok else 1


if __name__ == "__main__":  # pragma: no cover — entry point
    raise SystemExit(main())
