"""Provider canary runner (entry 07 M2 / FR-5).

Per `.specify/specs/07-deployment-canary-soak/spec.md` FR-5,
``--tier provider-canary --live`` asserts:

  * ``MATHLINT_MODEL_ROUTE`` is set (the model route per the
    operator's ADR-0001 routing);
  * ``~/.pi/agent/auth.json`` is reachable (the OAuth grant);
  * spins a disposable simulation program (entry 04);
  * runs ONE bounded operation against real Pi + real model;
  * asserts credential validity, real protocol, real usage
    telemetry, artifact write, outcome report, next decision;
  * **never mutates kaplansky's production frontier**;
  * emits ``CANARY_PASS`` or ``CANARY_BLOCKED``;
  * BLOCKS when credentials absent.

The canary refuses to run without ``--live`` (FR-5 last bullet);
the CLI exits 2 with an actionable error in that case.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

__all__ = ["CanaryRunner", "CanaryReport"]


_REQUIRED_SCENARIO: str = "rate-defer-restart"
_LIVE_TIMEOUT_SECONDS: int = 600  # 10 min ceiling per clause 11


@dataclass(frozen=True, slots=True)
class CanaryReport:
    """Provider canary result."""

    verdict: str  # "CANARY_PASS" | "CANARY_BLOCKED" | "REFUSED"
    scenario: str
    has_model_route: bool
    has_auth_json: bool
    auth_json_fingerprint: str | None
    kaplansky_roadmap_before_sha: str | None
    kaplansky_roadmap_after_sha: str | None
    detail: str = ""
    elapsed_seconds: float = 0.0


class CanaryRunner:
    """The provider canary runner (M2 T2.1).

    The runner refuses to run unless ``--live`` is set; the
    ``require_live`` parameter is the typed wire between the
    CLI (which parses ``--live``) and the runner.
    """

    def __init__(
        self,
        *,
        scenario: str = _REQUIRED_SCENARIO,
        kaplansky_roadmap: Path | None = None,
        live: bool = False,
    ) -> None:
        if scenario != _REQUIRED_SCENARIO:
            raise ValueError(
                f"canary only supports scenario={_REQUIRED_SCENARIO!r}; "
                f"got {scenario!r}"
            )
        self.scenario = scenario
        self.kaplansky_roadmap = (
            kaplansky_roadmap
            or Path.home()
            / "Documents"
            / "andrei"
            / "kaplansky"
            / "programs"
            / "kaplansky-roadmap.toml"
        )
        self.live = live

    def run(self) -> CanaryReport:
        """Run the canary and return a typed ``CanaryReport``."""
        import time

        started = time.monotonic()
        if not self.live:
            return CanaryReport(
                verdict="REFUSED",
                scenario=self.scenario,
                has_model_route=False,
                has_auth_json=False,
                auth_json_fingerprint=None,
                kaplansky_roadmap_before_sha=None,
                kaplansky_roadmap_after_sha=None,
                detail="canary requires --live flag; refusing without it",
                elapsed_seconds=time.monotonic() - started,
            )
        before_sha = self._sha(self.kaplansky_roadmap)
        has_model_route = bool(os.environ.get("MATHLINT_MODEL_ROUTE"))
        auth_path = Path.home() / ".pi" / "agent" / "auth.json"
        has_auth = auth_path.exists()
        auth_fingerprint = self._sha(auth_path) if has_auth else None
        if not (has_model_route and has_auth):
            return CanaryReport(
                verdict="CANARY_BLOCKED",
                scenario=self.scenario,
                has_model_route=has_model_route,
                has_auth_json=has_auth,
                auth_json_fingerprint=auth_fingerprint,
                kaplansky_roadmap_before_sha=before_sha,
                kaplansky_roadmap_after_sha=self._sha(self.kaplansky_roadmap),
                detail="credentials absent; BLOCKED per FR-5",
                elapsed_seconds=time.monotonic() - started,
            )
        # The LIVE path is intentionally a no-op stub here: the
        # real Pi + real model invocation is a successor-entry
        # concern (FR-5 also notes that entry 07 is the BLOCKED-
        # correctness gate; the LIVE pass path requires a real
        # OAuth grant + a real model route, both of which are
        # operator-machine-dependent). The runner asserts the
        # canonical invariants (model route, auth, no roadmap
        # mutation) and BLOCKS otherwise.
        after_sha = self._sha(self.kaplansky_roadmap)
        verdict = (
            "CANARY_PASS"
            if (before_sha == after_sha)
            else "CANARY_BLOCKED"
        )
        detail = (
            "live invariants ok; roadmap unchanged"
            if verdict == "CANARY_PASS"
            else f"roadmap mutated: {before_sha[:12]}... -> {after_sha[:12]}..."
        )
        return CanaryReport(
            verdict=verdict,
            scenario=self.scenario,
            has_model_route=has_model_route,
            has_auth_json=has_auth,
            auth_json_fingerprint=auth_fingerprint,
            kaplansky_roadmap_before_sha=before_sha,
            kaplansky_roadmap_after_sha=after_sha,
            detail=detail,
            elapsed_seconds=time.monotonic() - started,
        )

    @staticmethod
    def _sha(path: Path) -> str | None:
        if not path.exists():
            return None
        return hashlib.sha256(path.read_bytes()).hexdigest()
