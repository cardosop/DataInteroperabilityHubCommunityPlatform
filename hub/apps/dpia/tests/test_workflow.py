"""Workflow transitions — real ORM."""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from hub.apps.dpia.models import Dpia, DpiaStatus, ResidualRiskLevel
from hub.apps.dpia.workflow import (
    complete_consultation,
    create_follow_on_version,
    diff_wizard_payloads,
    review_dpia,
    submit_dpia,
)
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DpiaWorkflowTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"dpia-wf-{uid}",
            slug=f"dpia-wf-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_dpia_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.actor = User.objects.create_user(
            email=f"dpo-{uid}@example.com",
            password="pw",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_submit_and_review_approve_sets_next_review(self):
        dpia = Dpia.objects.create(
            tenant=self.tenant,
            title="Test",
            created_by=self.actor,
            status=DpiaStatus.DRAFT,
        )
        submit_dpia(dpia=dpia, actor=self.actor)
        dpia.refresh_from_db()
        self.assertEqual(dpia.status, DpiaStatus.IN_REVIEW)

        review_dpia(
            dpia=dpia,
            actor=self.actor,
            outcome=DpiaStatus.APPROVED,
            risk_residual=ResidualRiskLevel.LOW,
            dpo_summary="ok",
        )
        dpia.refresh_from_db()
        self.assertEqual(dpia.status, DpiaStatus.APPROVED)
        self.assertIsNotNone(dpia.next_review_due_at)

    @pytest.mark.integration
    def test_approve_with_high_residual_requires_consultation(self):
        dpia = Dpia.objects.create(
            tenant=self.tenant,
            title="High risk",
            created_by=self.actor,
            status=DpiaStatus.DRAFT,
        )
        submit_dpia(dpia=dpia, actor=self.actor)
        review_dpia(
            dpia=dpia,
            actor=self.actor,
            outcome=DpiaStatus.APPROVED,
            risk_residual=ResidualRiskLevel.HIGH,
            dpo_summary="escalate",
        )
        dpia.refresh_from_db()
        self.assertEqual(dpia.status, DpiaStatus.REQUIRES_CONSULTATION)

    @pytest.mark.integration
    def test_consultation_complete_approves(self):
        dpia = Dpia.objects.create(
            tenant=self.tenant,
            title="Consult",
            created_by=self.actor,
            status=DpiaStatus.REQUIRES_CONSULTATION,
        )
        complete_consultation(dpia=dpia, actor=self.actor, approve=True)
        dpia.refresh_from_db()
        self.assertEqual(dpia.status, DpiaStatus.APPROVED)

    @pytest.mark.integration
    def test_follow_on_version_and_diff(self):
        first = Dpia.objects.create(
            tenant=self.tenant,
            title="V1",
            created_by=self.actor,
            status=DpiaStatus.APPROVED,
            wizard_payload={"a": 1},
        )
        second = create_follow_on_version(dpia=first, actor=self.actor, title="V2")
        self.assertEqual(second.previous_version_id, first.id)
        second.wizard_payload = {"a": 2, "b": 3}
        second.save(update_fields=["wizard_payload"])
        d = diff_wizard_payloads(second.wizard_payload, first.wizard_payload)
        self.assertTrue(any(c["field"] == "a" for c in d["changed_keys"]))

    @pytest.mark.integration
    def test_cannot_submit_non_draft(self):
        dpia = Dpia.objects.create(
            tenant=self.tenant,
            title="x",
            created_by=self.actor,
            status=DpiaStatus.IN_REVIEW,
        )
        with self.assertRaises(ValidationError):
            submit_dpia(dpia=dpia, actor=self.actor)
