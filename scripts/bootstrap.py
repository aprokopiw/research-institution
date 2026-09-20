"""Bootstrap the institution. CLI entry point.

Replaces the previous `scripts/bootstrap-institution.sh` shell
script. Reads the catalog, installs every program + the dev-dep
packages (mathlint, pi-monitor), and returns a structured
report. Idempotent.

Usage::

    python -m research_institution.gates.bootstrap [--apply]
"""

from __future__ import annotations

from research_institution.gates.bootstrap import bootstrap_install


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="bootstrap-institution",
        description=(
            "Clone + install every catalog entry + dev deps. Idempotent. "
            "Replaces scripts/bootstrap-institution.sh."
        ),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Run pip install / clone mutations (default: dry-run, print only).",
    )
    parser.add_argument(
        "--skip-dev-deps",
        action="store_true",
        help="Skip the mathlint + pi-monitor install step.",
    )
    ns = parser.parse_args()
    if ns.apply:
        report = bootstrap_install(skip_dev_deps=ns.skip_dev_deps)
        verb = "BOOTSTRAP COMPLETE" if report.ok else "BOOTSTRAP INCOMPLETE"
        print(verb)
        for step in report.steps:
            flag = "ok" if step.ok else "FAIL"
            detail = f" - {step.detail}" if step.detail else ""
            print(f"  [{flag}] {step.name}{detail}")
        if report.programs_installed:
            print(f"installed: {' '.join(report.programs_installed)}")
        return 0 if report.ok else 1
    print("dry-run: would run bootstrap (use --apply to mutate)")
    return 0


if __name__ == "__main__":  # pragma: no cover — entry point
    raise SystemExit(main())
