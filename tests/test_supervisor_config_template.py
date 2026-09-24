"""Canonical supervisor-config template validation.

The autonomous-research brief (Section C) requires that the
institution-owned supervisor-config template for each program
satisfies a typed autonomous-action contract:

  * rolling token + dollar caps per window (1m / 10m / 1h /
    24h) with ``on_exceeded = "wait_until_eligible"`` so
    exhaustion is self-recovering
  * NO cumulative lifetime counters (no ``max_hours`` /
    ``max_attempts`` / ``max_dollars``) that would guarantee
    eventual permanent halt for a long-running autonomous run
  * per-attempt + rolling bounds preserved
  * unknown action or invalid negative cap fails validation
  * the template path declared in the catalog must resolve to
    a real, parseable .toml file

These tests read the catalog and the per-program template via
the same paths the bootstrap / start command uses, so a
program that declares ``supervisor_config_template`` in
``catalog/programs.toml`` is automatically checked.

The validator is pure: given a parsed TOML dict and the
program name, it returns a typed verdict listing every
violation. The CLI surfaces the verdict with ``BLOCKED`` when
a violation is fatal.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from research_institution.catalog import load_catalog
from research_institution.paths import catalog_path, institution_dir


REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True, slots=True)
class TemplateVerdict:
    """Outcome of validating one supervisor-config template.

    ``violations`` carries the per-field diagnostic so the
    CLI / doctor command can show the operator exactly what
    must change. ``ok`` is True iff no fatal violations.
    """

    program: str
    template_path: Path
    parsed: dict[str, object]
    violations: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.violations

    @property
    def has_template(self) -> bool:
        return bool(self.parsed)


# ---------------------------------------------------------------------------
# Pure validator (testable in isolation)
# ---------------------------------------------------------------------------


def _get_section(parsed: dict[str, object], name: str) -> dict[str, object]:
    """Return a top-level TOML section as a dict; empty if absent."""
    value = parsed.get(name)
    return dict(value) if isinstance(value, dict) else {}


def _as_float(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _validate_template(program: str, template_path: Path) -> TemplateVerdict:
    """Pure validator: parse + assert autonomous-action contract.

    Fatal violations (the template cannot ship):

      * file missing
      * TOML parse failure
      * ``[rate_limits]`` absent or empty
      * ``on_exceeded`` absent, unrecognized, or not
        ``wait_until_eligible``
      * a missing rolling-window cap
      * a negative cap
      * presence of legacy cumulative lifetime counters
        ``[budgets].global.max_hours`` /
        ``[budgets].global.max_attempts`` /
        ``[budgets].global.max_dollars``

    Warnings (advisory): missing token / dollar caps for a
    window, missing ``[project]`` / ``[source]`` blocks.
    """
    violations: list[str] = []
    warnings: list[str] = []

    if not template_path.is_file():
        return TemplateVerdict(
            program=program,
            template_path=template_path,
            parsed={},
            violations=(f"template file missing: {template_path}",),
        )
    try:
        parsed = tomllib.loads(template_path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return TemplateVerdict(
            program=program,
            template_path=template_path,
            parsed={},
            violations=(f"TOML parse error: {exc}",),
        )

    rate_limits = _get_section(parsed, "rate_limits")
    if not rate_limits:
        violations.append("[rate_limits] section missing or empty")
    else:
        # Action with no caps is a no-op (the supervisor treats
        # it as opt-out). A template that declares the action
        # but no rolling caps is a config error: the action
        # would never trigger.
        has_any_cap = any(
            _as_float(rate_limits.get(f"max_tokens_per_{w}")) is not None
            or _as_float(rate_limits.get(f"max_dollars_per_{w}")) is not None
            for w in ("1m", "10m", "1h", "24h")
        )
        if not has_any_cap:
            violations.append(
                "[rate_limits] declares on_exceeded but no rolling caps "
                "(the action would never trigger)"
            )

    action = rate_limits.get("on_exceeded")
    if action != "wait_until_eligible":
        violations.append(
            f"[rate_limits].on_exceeded must be 'wait_until_eligible'; got {action!r}"
        )

    for window in ("1m", "10m", "1h", "24h"):
        tokens = _as_float(rate_limits.get(f"max_tokens_per_{window}"))
        dollars = _as_float(rate_limits.get(f"max_dollars_per_{window}"))
        if tokens is None:
            warnings.append(f"[rate_limits].max_tokens_per_{window} missing")
        elif tokens < 0:
            violations.append(
                f"[rate_limits].max_tokens_per_{window} is negative ({tokens})"
            )
        if dollars is None:
            warnings.append(f"[rate_limits].max_dollars_per_{window} missing")
        elif dollars < 0:
            violations.append(
                f"[rate_limits].max_dollars_per_{window} is negative ({dollars})"
            )

    budgets = _get_section(parsed, "budgets")
    global_ = _get_section(budgets, "global")
    for lifetime_key in ("max_hours", "max_attempts", "max_dollars"):
        if lifetime_key in global_:
            violations.append(
                f"[budgets].global.{lifetime_key} is a cumulative lifetime counter "
                f"that would guarantee eventual permanent halt; remove it"
            )

    if "[project]" not in parsed and "project" not in parsed:
        warnings.append("[project] section missing")
    if "[source]" not in parsed and "source" not in parsed:
        warnings.append("[source] section missing")

    return TemplateVerdict(
        program=program,
        template_path=template_path,
        parsed=parsed,
        violations=tuple(violations),
        warnings=tuple(warnings),
    )


# ---------------------------------------------------------------------------
# Catalog-driven tests
# ---------------------------------------------------------------------------


def _catalog_programs() -> list:
    return load_catalog(catalog_path())


@pytest.fixture(scope="module")
def kaplansky_template_path() -> Path:
    """Resolve the kaplansky program's canonical supervisor-config template.

    Reads the catalog, finds the kaplansky entry, resolves
    ``supervisor_config_template`` against the institution
    repo root, and returns the Path. Skips if the program does
    not declare a template (legacy programs are out of scope).
    """
    for prog in _catalog_programs():
        if prog.name == "kaplansky" and prog.supervisor_config_template:
            return institution_dir() / prog.supervisor_config_template
    pytest.skip("kaplansky program does not declare a supervisor_config_template")


class TestKaplanskyTemplate:
    """The Kaplansky canonical supervisor-config template.

    Pins Section C of the autonomous-research brief on the
    canonical template.
    """

    def test_template_file_exists(self, kaplansky_template_path: Path) -> None:
        assert kaplansky_template_path.is_file()

    def test_template_parses(self, kaplansky_template_path: Path) -> None:
        parsed = tomllib.loads(kaplansky_template_path.read_text(encoding="utf-8"))
        assert isinstance(parsed, dict)

    def test_template_satisfies_autonomous_action_contract(
        self, kaplansky_template_path: Path
    ) -> None:
        verdict = _validate_template("kaplansky", kaplansky_template_path)
        assert verdict.ok, (
            f"template violates autonomous-action contract: {verdict.violations}"
        )

    def test_no_cumulative_lifetime_counter(
        self, kaplansky_template_path: Path
    ) -> None:
        parsed = tomllib.loads(kaplansky_template_path.read_text(encoding="utf-8"))
        budgets = parsed.get("budgets", {})
        if not isinstance(budgets, dict):
            return
        global_ = budgets.get("global", {})
        if not isinstance(global_, dict):
            return
        for key in ("max_hours", "max_attempts", "max_dollars"):
            assert key not in global_, (
                f"[budgets].global.{key} is a cumulative lifetime counter "
                f"that would guarantee eventual permanent halt"
            )


# ---------------------------------------------------------------------------
# Validator unit tests (no fixture needed)
# ---------------------------------------------------------------------------


class TestValidatorUnit:
    """The validator itself, independent of any catalog entry."""

    def test_missing_template_is_fatal(self, tmp_path: Path) -> None:
        verdict = _validate_template("test", tmp_path / "missing.toml")
        assert not verdict.ok
        assert any("missing" in v for v in verdict.violations)

    def test_unknown_action_is_fatal(self, tmp_path: Path) -> None:
        p = tmp_path / "cfg.toml"
        p.write_text(
            "[rate_limits]\n"
            "max_tokens_per_1m = 1000.0\n"
            "max_dollars_per_1m = 0.1\n"
            'on_exceeded = "typo"\n',
            encoding="utf-8",
        )
        verdict = _validate_template("test", p)
        assert not verdict.ok
        assert any("on_exceeded" in v for v in verdict.violations)

    def test_negative_cap_is_fatal(self, tmp_path: Path) -> None:
        p = tmp_path / "cfg.toml"
        p.write_text(
            "[rate_limits]\n"
            "max_tokens_per_1m = -100.0\n"
            "max_dollars_per_1m = 0.1\n"
            'on_exceeded = "wait_until_eligible"\n',
            encoding="utf-8",
        )
        verdict = _validate_template("test", p)
        assert not verdict.ok
        assert any("negative" in v for v in verdict.violations)

    def test_cumulative_lifetime_counter_is_fatal(self, tmp_path: Path) -> None:
        p = tmp_path / "cfg.toml"
        p.write_text(
            "[rate_limits]\n"
            "max_tokens_per_1m = 1000.0\n"
            "max_dollars_per_1m = 0.1\n"
            'on_exceeded = "wait_until_eligible"\n'
            "[budgets]\n"
            "[budgets.global]\n"
            "max_hours = 12\n"
            "max_attempts = 30\n",
            encoding="utf-8",
        )
        verdict = _validate_template("test", p)
        assert not verdict.ok
        assert any("max_hours" in v for v in verdict.violations)
        assert any("max_attempts" in v for v in verdict.violations)

    def test_missing_action_is_fatal(self, tmp_path: Path) -> None:
        p = tmp_path / "cfg.toml"
        p.write_text(
            "[rate_limits]\n"
            "max_tokens_per_1m = 1000.0\n",
            encoding="utf-8",
        )
        verdict = _validate_template("test", p)
        assert not verdict.ok
        assert any("on_exceeded" in v for v in verdict.violations)

    def test_minimal_valid_template(self, tmp_path: Path) -> None:
        p = tmp_path / "cfg.toml"
        p.write_text(
            "[rate_limits]\n"
            "max_tokens_per_1m = 1000.0\n"
            "max_tokens_per_10m = 5000.0\n"
            "max_tokens_per_1h = 20000.0\n"
            "max_tokens_per_24h = 100000.0\n"
            "max_dollars_per_1m = 0.1\n"
            "max_dollars_per_10m = 0.5\n"
            "max_dollars_per_1h = 2.0\n"
            "max_dollars_per_24h = 10.0\n"
            'on_exceeded = "wait_until_eligible"\n',
            encoding="utf-8",
        )
        verdict = _validate_template("test", p)
        assert verdict.ok, verdict.violations

    def test_empty_rate_limits_is_fatal(self, tmp_path: Path) -> None:
        p = tmp_path / "cfg.toml"
        p.write_text(
            "[rate_limits]\n"
            'on_exceeded = "wait_until_eligible"\n',
            encoding="utf-8",
        )
        verdict = _validate_template("test", p)
        assert not verdict.ok
        assert any("no rolling caps" in v for v in verdict.violations)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
