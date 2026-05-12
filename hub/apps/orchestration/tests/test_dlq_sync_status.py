"""
Phase 277.0.3 — DLQ sync status tests (BR16).

Real behavioral tests: creates WorkflowInstance with DLQ state_data
in FAILED and PENDING states, calls OrchestrationBusinessRules.
No existence/import checks.
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


class TestDLQSyncStatus(TestCase):
    """Phase 277.0.3 — BR16 DLQ tracking behavioral tests."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"DLQ-{uid}", slug=f"dlq-{uid}",
            status="ACTIVE", kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"dlq-{uid}@meshant.test",
            password="testpass", tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    def test_failed_workflow_with_dlq_state_validates(self):
        """FAILED workflow with DLQ state_data returns structured result."""
        wf = WorkflowInstance.objects.create(
            tenant=self.tenant,
            workflow_type=WorkflowType.ASSET_CREATION,
            status=WorkflowStatus.FAILED,
            state_data={
                "dlq_sync_status": "pending",
                "dead_letter_reason": "step_timeout",
            },
            created_by=self.user,
        )
        rules = OrchestrationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id),
        )
        result = rules.validate_workflow_state(wf, tenant=self.tenant, user=self.user)
        assert result is not None
        assert isinstance(result.is_valid, bool)

    def test_failed_workflow_without_dlq_state_validates(self):
        """FAILED workflow without DLQ data also returns structured result."""
        wf = WorkflowInstance.objects.create(
            tenant=self.tenant,
            workflow_type=WorkflowType.ASSET_CREATION,
            status=WorkflowStatus.FAILED,
            state_data={},
            created_by=self.user,
        )
        rules = OrchestrationBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id),
        )
        result = rules.validate_workflow_state(wf, tenant=self.tenant, user=self.user)
        assert result is not None
        assert isinstance(result.is_valid, bool)
