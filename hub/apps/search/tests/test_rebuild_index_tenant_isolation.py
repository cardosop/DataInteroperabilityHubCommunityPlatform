from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from hub.apps.audit import event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _make_tenant(prefix: str) -> Tenant:
    suffix = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{prefix}-{suffix}",
        slug=f"{prefix}-{suffix}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
    )
    return cast("Tenant", tenant)


def _make_auditor_user(tenant: Tenant):
    suffix = uuid.uuid4().hex[:8]
    user = User.objects.create(
        email=f"auditor-{suffix}@example.com",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name="AUDITOR",
        defaults={"description": "Auditor"},
    )
    UserRole.objects.get_or_create(
        user=user,
        tenant=tenant,
        role=role,
    )
    return user


class RebuildIndexTenantIsolationTests(TestCase):
    def setUp(self) -> None:
        self.tenant_a = _make_tenant("search-a")
        self.tenant_b = _make_tenant("search-b")
        ensure_tenant_has_active_subscription(self.tenant_a)
        self.user_a = _make_auditor_user(self.tenant_a)
        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user_a)
        self.url = reverse("search-rebuild-index")

    @staticmethod
    def _counter_value() -> float:
        from hub.apps.observability.cross_tenant_metrics import (
            cross_tenant_denied_total,
        )

        labeled = cross_tenant_denied_total.labels(
            endpoint="search.rebuild_index",
            reason="body_tenant_mismatch",
        )
        value = getattr(labeled, "_value", None)
        if value is None or not hasattr(value, "get"):
            return 0.0
        return float(value.get())

    def test_auditor_cannot_trigger_cross_tenant_rebuild(self) -> None:
        before_audit = AuditEvent.objects.filter(
            tenant=self.tenant_a,
            action=event_types.CROSS_TENANT_DENIED,
        ).count()
        before_counter = self._counter_value()

        response: Any = self.api_client.post(
            self.url,
            {"tenant_id": str(self.tenant_b.id)},
            format="json",
        )

        self.assertEqual(response.status_code, 403, response.content)
        self.assertEqual(
            response.json(),
            {
                "code": "CROSS_TENANT_FORBIDDEN",
                "detail": "tenant_id must not be set in request body",
            },
        )

        after_audit = AuditEvent.objects.filter(
            tenant=self.tenant_a,
            action=event_types.CROSS_TENANT_DENIED,
        ).count()
        self.assertEqual(after_audit - before_audit, 1)

        latest = AuditEvent.objects.filter(
            tenant=self.tenant_a,
            action=event_types.CROSS_TENANT_DENIED,
        ).latest("timestamp")
        self.assertEqual(latest.result, "FAILURE")
        self.assertEqual(
            latest.details_json.get("requested_tenant_id"),
            str(self.tenant_b.id),
        )
        self.assertEqual(
            latest.details_json.get("actual_tenant_id"),
            str(self.tenant_a.id),
        )

        after_counter = self._counter_value()
        self.assertGreaterEqual(after_counter - before_counter, 1.0)

    def test_auditor_can_rebuild_own_tenant(self) -> None:
        response: Any = self.api_client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body.get("status"), "index rebuild started")
        self.assertTrue(body.get("success"), "Response must include 'success' key")

    def test_matching_body_tenant_id_is_transitionally_accepted(self) -> None:
        response: Any = self.api_client.post(
            self.url,
            {"tenant_id": str(self.tenant_a.id)},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.content)
        body = response.json()
        self.assertEqual(body.get("status"), "index rebuild started")
        self.assertTrue(body.get("success"), "Response must include 'success' key")
