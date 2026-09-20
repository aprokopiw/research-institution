"""Typed parse path for ``pi-monitor status`` on the OS side.

The dispatcher calls :func:`research_institution.supervisor.probe_supervisor`
and gets back a :class:`SupervisorState` whose ``status_payload`` is
the typed :class:`pi_monitor.supervisor_status.SupervisorStatusPayload`
(re-exported as :data:`research_institution.supervisor.SupervisorStatusPayload`).

These tests pin the typed boundary so a drift in pi-monitor's wire
shape surfaces here as a Pydantic ValidationError, not as a
silent ``dict`` mismatch deep in a downstream consumer.
"""

from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from research_institution.supervisor import (
    SupervisorStatusPayload,
    probe_supervisor,
)
from tests._fakes import FakeRunner  # type: ignore[import-not-found]


class SupervisorStatusTypedContractTests(unittest.TestCase):
    """Probe path returns the typed ``SupervisorStatusPayload``."""

    def test_probe_supervisor_returns_typed_payload(self) -> None:
        from tests._fakes import QueuedResponse
        runner = FakeRunner()
        payload = json.dumps(
            {
                "schema_name": "pi-monitor-status-payload/v1",
                "project": "kaplansky",
                "supervisor_pid": os.getpid(),
                "worker_pid": 0,
            }
        )
        runner.queue(
            QueuedResponse(returncode=0, stdout=payload, stderr="")
        )
        state = probe_supervisor(Path("/tmp/cfg.toml"), runner=runner)
        assert state.status_payload is not None
        # The typed view is the canonical Pydantic model; the
        # dispatcher reads ``payload.project`` not ``payload["project"]``.
        self.assertIsInstance(state.status_payload, SupervisorStatusPayload)
        self.assertEqual(state.status_payload.project, "kaplansky")
        self.assertEqual(state.status_payload.supervisor_pid, os.getpid())

    def test_probe_supervisor_re_exports_canonical_model(self) -> None:
        # The dispatcher must see the same class identity as pi-monitor;
        # a drift in pi-monitor's wire shape surfaces at the
        # import boundary (pyright flags the re-export change).
        from pi_monitor.supervisor_status import (
            SupervisorStatusPayload as PM_SSP,
        )
        self.assertIs(SupervisorStatusPayload, PM_SSP)

    def test_malformed_wire_falls_back_to_clean_state(self) -> None:
        # A wire-format drift (e.g. a supervisor from a future
        # version that drops ``supervisor_pid``) must NOT crash
        # the dispatcher; the probe falls back to the clean
        # "no data" state and ``is_alive`` is False.
        from tests._fakes import QueuedResponse
        runner = FakeRunner()
        runner.queue(
            QueuedResponse(returncode=0, stdout="this is not json", stderr=""),
        )
        state = probe_supervisor(Path("/tmp/cfg.toml"), runner=runner)
        self.assertIsNone(state.status_payload)
        self.assertEqual(state.supervisor_pid, 0)
        self.assertEqual(state.worker_pid, 0)
        self.assertFalse(state.is_alive)


if __name__ == "__main__":
    unittest.main()
