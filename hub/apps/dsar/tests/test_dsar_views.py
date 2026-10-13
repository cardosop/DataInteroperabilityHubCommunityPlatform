"""
285.12.3.1 — DSAR handler ViewSet + public portal tests (real DB, no mocks).
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

pytestmark = [pytest.mark.journey("JOURNEY-CPO-015")]

from hub.apps.dsar.models import DSARRequestType
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole

User = get_user_model()


class DSARViewSetTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test-{uid}",
            slug=f"t-{uid}",
            status="ACTIVE",
        )
        self.user = User.objects.create_user(
            email=f"user_{uid}@test.local",
            password="Pass1234!",
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
        self.assertIn("results", resp.data, "Paginated response must include 'results' key")

    @pytest.mark.integration
    def test_create_dsar_request(self):
        payload = {
            "request_type": DSARRequestType.ACCESS,
            "subject_email": "subject@example.com",
            "description": "Test DSAR request",
        }
        resp = self.client.post("/api/v1/dsar/requests/", payload, format="json")
        self.assertEqual(resp.status_code, 201)
        self.assertIn("id", resp.data, "Response must include the created request id")
        self.assertEqual(resp.data.get("status"), "SUBMITTED")
        # Verify persistence
        from hub.apps.dsar.models import DSARRequest

        self.assertTrue(
            DSARRequest.objects.filter(id=resp.data["id"]).exists(),
            "DSARRequest must be persisted in the database",
        )

    @pytest.mark.integration
    def test_unauthenticated_rejected(self):
        client = APIClient()
        resp = client.get("/api/v1/dsar/requests/")
        self.assertEqual(resp.status_code, 401)


@override_settings(DSAR_SKIP_HCAPTCHA_VERIFICATION=True)
class PublicDsarSubmitSecurityTests(TestCase):
    """W1.2b: the public ingress scopes by the tenant's PUBLIC slug —
    a client-supplied raw tenant UUID was a scoping capability (the
    cross-tenant leak class)."""

    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="DSAR Public Co",
            slug=f"dsar-public-{uuid.uuid4().hex[:8]}",
            compliance_dsar_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)

    def _payload(self, **overrides):
        payload = {
            "tenant_slug": self.tenant.slug,
            "request_type": DSARRequestType.ACCESS,
            "subject_email": f"subject-{uuid.uuid4().hex[:8]}@example.com",
            "regimes": ["GDPR"],
            "hcaptcha_response": "test-token",
        }
        payload.update(overrides)
        return payload

    def test_known_slug_creates_a_request_for_that_tenant(self):
        resp = self.client.post(
            reverse("public-dsar-submit"), self._payload(), format="json"
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        from hub.apps.dsar.models import DSARRequest

        row = DSARRequest.objects.get(tenant_id=self.tenant.id)
        self.assertIsNotNone(row)

    def test_unknown_slug_is_rejected(self):
        resp = self.client.post(
            reverse("public-dsar-submit"),
            self._payload(tenant_slug="no-such-tenant"),
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_raw_tenant_uuid_is_no_longer_a_scoping_capability(self):
        # The OLD contract was a raw tenant UUID in the payload; the field
        # is now a slug — a payload in the old shape is rejected by the
        # serializer (tenant_slug missing → 400).
        resp = self.client.post(
            reverse("public-dsar-submit"),
            {
                "tenant_id": str(self.tenant.id),
                "request_type": DSARRequestType.ACCESS,
                "subject_email": f"old-{uuid.uuid4().hex[:8]}@example.com",
                "regimes": ["GDPR"],
                "hcaptcha_response": "test-token",
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
