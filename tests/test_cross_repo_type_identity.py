"""Cross-repo type-identity contract.

The research-institution side imports the typed wire shapes from
pi_monitor by identity (per @ADR-0006, @ADR-0007, @ADR-0009). This
test pins the identity contract: a drift in pi-monitor's wire shape
surfaces here as a class-identity change that pyright flags at
every import site.

Identity pairs (ri-side name = pi-monitor canonical):

  - DecisionKind            == pi_monitor.work_source.DecisionKind
  - CanonicalReasonCode     == pi_monitor.work_source.CanonicalReasonCode
  - OperationKind           == pi_monitor.work_source.OperationKind
  - RoleName                == pi_monitor.work_source.RoleName
  - SourceIdentity          == pi_monitor.work_source.SourceIdentity
  - WorkspaceName           == pi_monitor.work_source.WorkspaceName
  - SupervisorStatusPayload == pi_monitor.supervisor_status.SupervisorStatusPayload

Each pair MUST be ``assertIs``-identical: a single source of truth
means one class, not two mirrored copies.
"""

from __future__ import annotations

import unittest

from pi_monitor import supervisor_status, work_source
from research_institution.contracts import source_decision
from research_institution.supervisor import SupervisorStatusPayload


class CrossRepoTypeIdentityTests(unittest.TestCase):
    """The OS side sees the same class identity as pi-monitor."""

    def test_decision_kind_identity(self) -> None:
        self.assertIs(source_decision.DecisionKind, work_source.DecisionKind)

    def test_canonical_reason_code_identity(self) -> None:
        self.assertIs(source_decision.CanonicalReasonCode, work_source.CanonicalReasonCode)

    def test_operation_kind_identity(self) -> None:
        self.assertIs(source_decision.OperationKind, work_source.OperationKind)

    def test_role_name_identity(self) -> None:
        self.assertIs(source_decision.RoleName, work_source.RoleName)

    def test_source_identity_identity(self) -> None:
        self.assertIs(source_decision.SourceIdentity, work_source.SourceIdentity)

    def test_workspace_name_identity(self) -> None:
        self.assertIs(source_decision.WorkspaceName, work_source.WorkspaceName)

    def test_supervisor_status_payload_identity(self) -> None:
        self.assertIs(
            SupervisorStatusPayload,
            supervisor_status.SupervisorStatusPayload,
        )


class CrossRepoCanonicalReasonCodesTests(unittest.TestCase):
    """The OS-side canonical set matches pi-monitor's."""

    def test_canonical_reason_code_set_matches(self) -> None:
        # The two frozensets must contain the same wire strings.
        self.assertEqual(
            source_decision.CANONICAL_REASON_CODES,
            set(work_source.CANONICAL_REASON_CODES),
        )


class CrossRepoDecisionKindMembersTests(unittest.TestCase):
    """Both sides see the same enum members."""

    def test_decision_kind_members_match(self) -> None:
        pm_members = {m.value for m in work_source.DecisionKind}
        ri_members = {m.value for m in source_decision.DecisionKind}
        self.assertEqual(pm_members, ri_members)


if __name__ == "__main__":
    unittest.main()
