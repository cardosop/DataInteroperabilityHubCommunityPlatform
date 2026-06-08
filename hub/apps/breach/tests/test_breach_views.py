"""
285.12.3.1 — Breach notification ViewSet tests (real DB, no mocks).
"""
from __future__ import annotations
import pytest

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.breach.models import BreachIncidentStatus, BreachNotification, BreachNotificationStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole

User = get_user_model()


class BreachNotificationViewSetTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test-{uid}", slug=f"t-{uid}", status="ACTIVE",
            compliance_breach_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"user_{uid}@test.local", password="Pass1234!",
            tenant=self.tenant,
        )
        # IsBreachResponder requires TENANT_ADMIN, DPO, or SECURITY_ADMIN
        role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN", tenant=self.tenant,
            defaults={"description": "Tenant Administrator"},
        )
        UserRole.objects.get_or_create(
            user=self.user, tenant=self.tenant, role=role,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    @pytest.mark.integration
    def test_list_notifications_empty(self):
        resp = self.client.get("/api/v1/breach/notifications/")
        self.assertEqual(resp.status_code, 200)

    @pytest.mark.integration
    def test_create_breach_notification(self):
        # BreachNotificationViewSet is ReadOnlyModelViewSet — POST goes to incidents endpoint.
        payload = {
            "title": "Test breach incident",
            "summary": "Test breach notification",
            "regimes": ["GDPR"],
            "discovered_at": "2026-05-20T10:00:00Z",
        }
        resp = self.client.post("/api/v1/breach/incidents/", payload, format="json")
        self.assertEqual(resp.status_code, 201)

    @pytest.mark.integration
    def test_unauthenticated_rejected(self):
        client = APIClient()
        resp = client.get("/api/v1/breach/notifications/")
        self.assertEqual(resp.status_code, 401)
