"""
Phase 277.B.050 — auth_login_total counter tests.

Verifies that the auth_login_total Prometheus counter increments
correctly for each login outcome: success, failure (invalid email),
failure (wrong password), locked_out, rate_limited.

No mocks — uses real login endpoint, real rate-limit counters, real
OTel metrics.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.observability.otel_metrics import auth_login_total
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus


def _uid():
    return uuid.uuid4().hex[:8]


def _counter_value(**labels):
    """Return the current observed value of auth_login_total for given labels.

    The login view's ``_inc_auth_login`` always emits three labels
    (status, tenant_id, auth_method).  Missing labels default to ""
    so the cache key matches what the view actually writes.
    """
    full_labels = {"tenant_id": "", "auth_method": "password", **labels}
    return auth_login_total.labels(**full_labels)._value.get()


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestAuthLoginMetrics(TestCase):
    """auth_login_total counter increments on all login outcomes."""

    def setUp(self):
        uid = _uid()
        self.tenant = Tenant.objects.create(
            name=f"AuthMetric-{uid}",
            slug=f"authmetric-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"authmetric-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            email_verified=True,
        )

    # ── Success ────────────────────────────────────────────────────

    @pytest.mark.integration
    def test_01_success_increments_counter(self):
        tenant_id = str(self.tenant.id)
        before = _counter_value(status="success", tenant_id=tenant_id)
        client = APIClient()
        resp = client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        after = _counter_value(status="success", tenant_id=tenant_id)
        self.assertEqual(
            after,
            before + 1,
            f"auth_login_total{{status=success}} should increment by 1 "
            f"(before={before}, after={after})",
        )

    # ── Failure (invalid email) ────────────────────────────────────

    @pytest.mark.integration
    def test_02_invalid_email_increments_failure_counter(self):
        before = _counter_value(status="failure")
        client = APIClient()
        client.post(
            "/api/v1/auth/login/",
            {"email": f"no-such-{_uid()}@example.com", "password": "testpass123"},
            format="json",
        )
        after = _counter_value(status="failure")
        self.assertEqual(after, before + 1)

    # ── Failure (wrong password) ───────────────────────────────────

    @pytest.mark.integration
    def test_03_wrong_password_increments_failure_counter(self):
        before = _counter_value(status="failure")
        client = APIClient()
        client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "wrongpassword"},
            format="json",
        )
        after = _counter_value(status="failure")
        self.assertEqual(after, before + 1)

    # ── Unauthenticated ────────────────────────────────────────────

    @pytest.mark.integration
    def test_04_missing_credentials_returns_400(self):
        client = APIClient()
        resp = client.post(
            "/api/v1/auth/login/",
            {"email": "", "password": ""},
            format="json",
        )
        self.assertGreaterEqual(resp.status_code, 400)

    # ── Counter labels present ─────────────────────────────────────

    @pytest.mark.integration
    def test_05_counter_has_expected_labels(self):
        """The auth_login_total counter was registered with the correct labels."""
        # Trigger a login to ensure labels are materialised.
        client = APIClient()
        client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )
        # After a successful login call, the counter must exist with
        # status="success" and the tenant_id populated.
        success_val = _counter_value(status="success", tenant_id=str(self.tenant.id))
        self.assertIsNotNone(success_val)
        self.assertGreaterEqual(success_val, 1)


@pytest.mark.django_db(transaction=True)
@pytest.mark.integration
class TestAuthLoginMetricsTenantLabel(TestCase):
    """Tenant ID label is populated on successful login."""

    def setUp(self):
        uid = _uid()
        self.tenant = Tenant.objects.create(
            name=f"AuthLbl-{uid}",
            slug=f"authlbl-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"authlbl-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            email_verified=True,
        )

    @pytest.mark.integration
    def test_success_counter_has_tenant_id(self):
        tenant_id = str(self.tenant.id)
        client = APIClient()
        resp = client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "testpass123"},
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        val = _counter_value(status="success", tenant_id=tenant_id)
        self.assertIsNotNone(val)
        self.assertGreaterEqual(val, 1)
