from __future__ import annotations

import uuid
from typing import Any, cast

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

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

    def _assert_sunset(self, response: Any) -> None:
        """P3-1 (sunset 2026-08-10): the rebuild-index action died with
        the deprecated search surface — APIVersionMiddleware 410s it
        BEFORE any view code (the pre-sunset tenant-isolation behaviors
        are dead with the surface; the rebuild capability's migration
        to the live surface is recorded for the search owning lane)."""
        self.assertEqual(response.status_code, 410, response.content)
        body = response.json()
        self.assertEqual(body.get("code"), "ENDPOINT_SUNSET", response.content)
        self.assertEqual(
            body.get("details", {}).get("replacement"), "/api/search/",
            response.content,
        )

    def test_rebuild_sunset_contract(self) -> None:
        response: Any = self.api_client.post(self.url, {}, format="json")
        self._assert_sunset(response)

    def test_rebuild_sunset_contract_with_body(self) -> None:
        response: Any = self.api_client.post(
            self.url,
            {"tenant_id": str(self.tenant_b.id)},
            format="json",
        )
        self._assert_sunset(response)

    def test_rebuild_sunset_contract_for_matching_tenant(self) -> None:
        response: Any = self.api_client.post(
            self.url,
            {"tenant_id": str(self.tenant_a.id)},
            format="json",
        )
        self._assert_sunset(response)
