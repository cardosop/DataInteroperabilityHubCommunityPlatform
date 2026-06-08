"""
285.12.3.1 — DSAR handler ViewSet + public portal tests (real DB, no mocks).
"""
from __future__ import annotations
import pytest

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.dsar.models import DSARRequest, DSARRequestType, DSARStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

User = get_user_model()


class DSARViewSetTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test-{uid}", slug=f"t-{uid}", status="ACTIVE",
        )
        self.user = User.objects.create_user(
            email=f"user_{uid}@test.local", password="Pass1234!",
            tenant=self.tenant,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        # IsDsarHandler requires TENANT_ADMIN, DPO, or LEGAL_ADMIN
        role = Role.objects.get_or_create(tenant=self.tenant, name="TENANT_ADMIN")[0]
        UserRole.objects.get_or_create(user=self.user, tenant=self.tenant, role=role)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @pytest.mark.integration
    def test_list_dsar_requests(self):
        resp = self.client.get("/api/v1/dsar/requests/")
        self.assertEqual(resp.status_code, 200)

    @pytest.mark.integration
    def test_create_dsar_request(self):
        payload = {
            "request_type": DSARRequestType.ACCESS,
            "subject_email": "subject@example.com",
            "description": "Test DSAR request",
        }
        resp = self.client.post("/api/v1/dsar/requests/", payload, format="json")
        self.assertEqual(resp.status_code, 201)

    @pytest.mark.integration
    def test_unauthenticated_rejected(self):
        client = APIClient()
        resp = client.get("/api/v1/dsar/requests/")
        self.assertEqual(resp.status_code, 401)
