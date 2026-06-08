"""
285.12.3.2 — Consent management ViewSet tests.
"""
from __future__ import annotations
import pytest

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole
from hub.apps.consent.models import ConsentPurpose

User = get_user_model()


def _consent_signing_keys() -> dict:
    return {"__default__": ["a" * 64]}


class ConsentViewSetTests(TestCase):
    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test-{uid}", slug=f"t-{uid}", status="ACTIVE",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"user_{uid}@test.local", password="Pass1234!",
            tenant=self.tenant,
        )
        # ConsentRecordViewSet: list requires IsAuthenticated + IsTenantScoped;
        # create requires IsTenantAdmin.
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
    def test_list_consent_records(self):
        resp = self.client.get("/api/v1/consent/consent-records/")
        self.assertEqual(resp.status_code, 200)

    @override_settings(CONSENT_SIGNING_KEYS_JSON=_consent_signing_keys())
    @pytest.mark.integration
    def test_record_consent(self):
        # Create a valid ConsentPurpose first so the create succeeds.
        purpose = ConsentPurpose.objects.create(
            tenant=self.tenant,
            key=f"test-purpose-{uuid.uuid4().hex[:8]}",
            name="Test Purpose",
            description="Purpose for consent record test",
            is_active=True,
        )
        payload = {
            "purpose_id": str(purpose.id),
            "granted": True,
            "data_subject_id": str(uuid.uuid4()),
        }
        resp = self.client.post("/api/v1/consent/consent-records/", payload, format="json")
        self.assertEqual(resp.status_code, 201)

    @pytest.mark.integration
    def test_unauthenticated_rejected(self):
        client = APIClient()
        resp = client.get("/api/v1/consent/consent-records/")
        self.assertEqual(resp.status_code, 401)
