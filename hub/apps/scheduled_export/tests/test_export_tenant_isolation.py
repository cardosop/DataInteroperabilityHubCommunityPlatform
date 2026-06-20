"""
285.12.3.3 — Scheduled export tenant isolation + RLS enforcement tests.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportStatus,
)
from hub.apps.tenants.models import Tenant

User = get_user_model()


class ExportTenantIsolationTests(TestCase):
    def setUp(self):
        super().setUp()
        _suffix = uuid.uuid4().hex[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"Tenant-A-{_suffix}",
            slug=f"ta-{_suffix}",
            status="ACTIVE",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"Tenant-B-{_suffix}",
            slug=f"tb-{_suffix}",
            status="ACTIVE",
        )
        self.user_a = User.objects.create_user(
            email=f"ua_{_suffix}@test.local",
            password="Pass1234!",
            tenant=self.tenant_a,
        )
        self.user_b = User.objects.create_user(
            email=f"ub_{_suffix}@test.local",
            password="Pass1234!",
            tenant=self.tenant_b,
        )
        self.client = APIClient()

    @pytest.mark.integration
    def test_tenant_a_cannot_see_tenant_b_export(self):
        export = ScheduledExport.objects.create(
            tenant=self.tenant_b,
            name="B-export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test"},
            schedule_config={"cron": "0 0 * * *"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
            status=ScheduledExportStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user_a)
        resp = self.client.get(f"/api/v1/scheduled-exports/{export.id}/")
        self.assertEqual(resp.status_code, 404)

    @pytest.mark.integration
    def test_tenant_b_can_see_own_export(self):
        export = ScheduledExport.objects.create(
            tenant=self.tenant_b,
            name="B-export-own",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test"},
            schedule_config={"cron": "0 0 * * *"},
            source_scope={"asset_ids": [str(uuid.uuid4())]},
            status=ScheduledExportStatus.ACTIVE,
        )
        self.client.force_authenticate(user=self.user_b)
        resp = self.client.get(f"/api/v1/scheduled-exports/{export.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["id"], str(export.id))
