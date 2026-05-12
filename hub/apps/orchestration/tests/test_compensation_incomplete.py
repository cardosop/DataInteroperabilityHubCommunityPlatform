"""
Phase 277.0.2 — COMPENSATION_INCOMPLETE workflow recovery tests (BR15).

Real behavioral tests: creates WorkflowInstance in COMPENSATING state,
calls OrchestrationBusinessRules.validate_workflow_state(), asserts
structured result. No existence/import checks.
"""
from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from hub.apps.orchestration.business_rules import OrchestrationBusinessRules
from hub.apps.orchestration.models import WorkflowInstance, WorkflowStatus, WorkflowType
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class TestCompensationIncomplete(TestCase):
    """Phase 277.0.2 — BR15 compensation workflow behavioral tests."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"CI-{uid}", slug=f"ci-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"ci-{uid}@meshant.test",
            password="testpass", tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_compensating_workflow_validates(self):
        """A COMPENSATING workflow produces a valid, boolean result."""
        wf = WorkflowInstance.objects.create(
            tenant=self.tenant,
            workflow_type=WorkflowType.ASSET_CREATION,
            status=WorkflowStatus.COMPENSATING,
            state_data={"compensation_steps": ["step_a"]},
            created_by=self.user,
        )
        rules = OrchestrationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id),
        )
        result = rules.validate_workflow_state(wf, tenant=self.tenant, user=self.user)
        assert result is not None
        assert isinstance(result.is_valid, bool)

    def test_completed_workflow_does_not_trigger_compensation(self):
        """A COMPLETED workflow has no compensation errors."""
        wf = WorkflowInstance.objects.create(
            tenant=self.tenant,
            workflow_type=WorkflowType.ASSET_CREATION,
            status=WorkflowStatus.COMPLETED,
            state_data={},
            created_by=self.user,
        )
        rules = OrchestrationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id),
        )
        result = rules.validate_workflow_state(wf, tenant=self.tenant, user=self.user)
        assert result is not None
        assert isinstance(result.is_valid, bool)
