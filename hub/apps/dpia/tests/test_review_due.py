"""Periodic review sweep — RLS-disabled transaction local to connection."""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.audit import event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.dpia.models import Dpia, DpiaStatus
from hub.apps.dpia.services.review_due import run_dpia_review_due_scan
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class DpiaReviewDueTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"dpia-rd-{uid}",
            slug=f"dpia-rd-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            compliance_dpia_enabled=True,
        )

    @pytest.mark.integration
    def test_reopens_past_due(self):
        past = timezone.now() - timedelta(days=1)
        dpia = Dpia.objects.create(
            tenant=self.tenant,
            title="Annual",
            status=DpiaStatus.APPROVED,
            next_review_due_at=past,
        )
        c = run_dpia_review_due_scan()
        self.assertGreaterEqual(c["rows_reopened"], 1)
        dpia.refresh_from_db()
        self.assertEqual(dpia.status, DpiaStatus.IN_REVIEW)
        self.assertTrue(
            AuditEvent.objects.filter(
                resource_id=dpia.id,
                action=event_types.DPIA_PERIODIC_REVIEW_OPENED,
            ).exists()
        )

    @pytest.mark.integration
    def test_skips_disabled_tenant(self):
        self.tenant.compliance_dpia_enabled = False
        self.tenant.save(update_fields=["compliance_dpia_enabled"])
        Dpia.objects.create(
            tenant=self.tenant,
            title="x",
            status=DpiaStatus.APPROVED,
            next_review_due_at=timezone.now() - timedelta(days=2),
        )
        c = run_dpia_review_due_scan()
        self.assertEqual(c["rows_reopened"], 0)
