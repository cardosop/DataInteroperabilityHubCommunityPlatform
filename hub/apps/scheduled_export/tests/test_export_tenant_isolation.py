"""
285.12.3.3 — Scheduled export tenant isolation + RLS enforcement tests.
"""
from __future__ import annotations
import pytest

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.tenants.models import Tenant

User = get_user_model()


class ExportTenantIsolationTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tenant_a = Tenant.objects.create(
            name="Tenant-A", slug=f"ta-{uuid.uuid4().hex[:8]}", status="ACTIVE",
        )
        cls.tenant_b = Tenant.objects.create(
            name="Tenant-B", slug=f"tb-{uuid.uuid4().hex[:8]}", status="ACTIVE",
        )
        cls.user_a = User.objects.create_user(
            email=f"ua_{uuid.uuid4().hex[:8]}@test.local", password="Pass1234!",
            tenant=cls.tenant_a,
        )
        cls.user_b = User.objects.create_user(
            email=f"ub_{uuid.uuid4().hex[:8]}@test.local", password="Pass1234!",
            tenant=cls.tenant_b,
        )

    def setUp(self):
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
