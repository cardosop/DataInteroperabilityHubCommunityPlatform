"""
285.12.3.1 — DPIA ViewSet + assessment wizard tests (real DB, no mocks).
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

pytestmark = [pytest.mark.journey("JOURNEY-CPO-012")]

from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole

User = get_user_model()


class DPIAViewSetTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test-{uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
            compliance_dpia_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"user_{uid}@test.local",
            password="Pass1234!",
            tenant=self.tenant,
        )
        # IsDpiaParticipant requires TENANT_ADMIN, DPO, or LEGAL_ADMIN
        role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN",
            tenant=self.tenant,
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(
            user=self.user,
            tenant=self.tenant,
            role=role,
        )
        self.user.is_platform_admin = True
        self.user.save(update_fields=["is_platform_admin"])
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @pytest.mark.integration
    def test_list_dpia_records(self):
        resp = self.client.get("/api/v1/dpia/records/")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("results", resp.data, "Paginated response must include 'results' key")

    @pytest.mark.integration
    def test_create_dpia_record(self):
        payload = {
            "title": "Test DPIA",
            "description": "Test assessment",
            "processing_purpose": "testing",
        }
        resp = self.client.post("/api/v1/dpia/records/", payload, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.data["title"], "Test DPIA")
        self.assertIn("id", resp.data)

    @pytest.mark.integration
    def test_unauthenticated_rejected(self):
        client = APIClient()
        resp = client.get("/api/v1/dpia/records/")
        self.assertEqual(resp.status_code, 401)
