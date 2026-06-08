"""
Phase 277.B.032 — Admin onboarding-state endpoint tests.
"""
from __future__ import annotations
import pytest

import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.users.models import Role, User, UserRole, UserStatus


def _uid():
    return uuid.uuid4().hex[:8]


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestAdminTenantOnboardingState(TestCase):
    """GET /api/v1/admin/tenants/{id}/onboarding-state/"""

    @classmethod
    def setUpTestData(cls):
        uid = _uid()
        cls.tenant = Tenant.objects.create(
            name=f"Onb-{uid}", slug=f"onb-{uid}",
            status="ACTIVE", kyc_status=KYCStatus.UNVERIFIED,
        )
        cls.platform_admin = User.objects.create_user(
            email=f"pa-onb-{uid}@example.com",
            password="testpass", tenant=None,
            status=UserStatus.ACTIVE,
        )
        cls.platform_admin.is_platform_admin = True
        cls.platform_admin.save(update_fields=["is_platform_admin"])

        cls.regular_user = User.objects.create_user(
            email=f"regular-onb-{uid}@example.com",
            password="testpass", tenant=cls.tenant,
            status=UserStatus.ACTIVE,
        )

    # ── Happy path ─────────────────────────────────────────────────

    @pytest.mark.integration
    def test_01_platform_admin_gets_onboarding_state(self):
        client = APIClient()
        client.force_authenticate(user=self.platform_admin)
        resp = client.get(
            f"/api/v1/admin/tenants/{self.tenant.id}/onboarding-state/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("onboarding_state", resp.data)
        state = resp.data["onboarding_state"]
        # All three signals are False for a fresh tenant with no
        # TENANT_ADMIN, UNVERIFIED KYC, and no subscription.
        self.assertFalse(state["tenant_admin_invited"])
        self.assertFalse(state["kyc_submitted"])
        self.assertFalse(state["billing_setup"])
        self.assertFalse(state["all_complete"])

    @pytest.mark.integration
    def test_02_tenant_admin_invitation_detected(self):
        admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN",
            defaults={"description": "Admin"},
        )
        UserRole.objects.create(user=self.regular_user, role=admin_role, tenant=self.tenant)

        client = APIClient()
        client.force_authenticate(user=self.platform_admin)
        resp = client.get(
            f"/api/v1/admin/tenants/{self.tenant.id}/onboarding-state/"
        )
        state = resp.data["onboarding_state"]
        self.assertTrue(state["tenant_admin_invited"])

    @pytest.mark.integration
    def test_03_kyc_submitted_detected(self):
        self.tenant.kyc_status = KYCStatus.PENDING_REVIEW
        self.tenant.save()

        client = APIClient()
        client.force_authenticate(user=self.platform_admin)
        resp = client.get(
            f"/api/v1/admin/tenants/{self.tenant.id}/onboarding-state/"
        )
        state = resp.data["onboarding_state"]
        self.assertTrue(state["kyc_submitted"])

    @pytest.mark.integration
    def test_04_all_complete_when_signals_satisfied(self):
        from hub.apps.billing.models import Subscription
        from hub.apps.tenants.models import TenantPlan
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        # Satisfy all three signals
        admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN",
            defaults={"description": "Admin"},
        )
        UserRole.objects.create(user=self.regular_user, role=admin_role, tenant=self.tenant)
        self.tenant.kyc_status = KYCStatus.VERIFIED
        self.tenant.save()
        ensure_tenant_has_active_subscription(self.tenant)

        client = APIClient()
        client.force_authenticate(user=self.platform_admin)
        resp = client.get(
            f"/api/v1/admin/tenants/{self.tenant.id}/onboarding-state/"
        )
        state = resp.data["onboarding_state"]
        self.assertTrue(state["all_complete"])

    # ── Auth / permissions ─────────────────────────────────────────

    @pytest.mark.integration
    def test_05_unauthenticated_is_rejected(self):
        client = APIClient()
        resp = client.get(
            f"/api/v1/admin/tenants/{self.tenant.id}/onboarding-state/"
        )
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    @pytest.mark.integration
    def test_06_non_platform_admin_is_rejected(self):
        client = APIClient()
        client.force_authenticate(user=self.regular_user)
        resp = client.get(
            f"/api/v1/admin/tenants/{self.tenant.id}/onboarding-state/"
        )
        self.assertIn(resp.status_code, [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND,
        ])

    @pytest.mark.integration
    def test_07_non_existent_tenant_returns_404(self):
        client = APIClient()
        client.force_authenticate(user=self.platform_admin)
        resp = client.get(
            f"/api/v1/admin/tenants/{uuid.uuid4()}/onboarding-state/"
        )
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    # ── Audit event ────────────────────────────────────────────────

    @pytest.mark.integration
    def test_08_audit_event_emitted_on_view(self):
        client = APIClient()
        client.force_authenticate(user=self.platform_admin)
        resp = client.get(
            f"/api/v1/admin/tenants/{self.tenant.id}/onboarding-state/"
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        event = AuditEvent.objects.filter(
            action="TENANT_ONBOARDING_STATE_VIEWED",
        ).order_by("-timestamp").first()
        self.assertIsNotNone(event)
        self.assertEqual(str(event.resource_id), str(self.tenant.id))
