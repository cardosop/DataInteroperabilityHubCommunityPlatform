"""
Phase 250.6.E TDD pin for the tenant feature-flags admin endpoints.

The new admin page at ``/admin/tenant-settings/`` (frontend) needs
two backend surfaces:

1. ``GET  /api/v1/tenants/me/feature-flags/`` — return the per-tenant
   capability flags + their human-readable descriptions + their
   default values. Lets the SPA render a self-describing settings
   page without a separate "schema" round-trip.

2. ``PATCH /api/v1/tenants/me/feature-flags/`` — let TENANT_ADMIN
   flip flags on / off. Each PATCH writes a
   ``TENANT_FEATURE_FLAG_UPDATED`` audit row carrying the
   before/after values so the audit-log panel below the settings
   form can render the change history.

3. ``GET  /api/v1/tenants/me/feature-flag-history/`` — return the
   audit-event rows for the calling tenant, scoped to
   ``action=TENANT_FEATURE_FLAG_UPDATED`` so the SPA can render
   "who changed what when" without scanning the full audit log.

Per Phase 250.6.E.2, all three endpoints are TENANT_ADMIN-only —
non-admin users see HTTP 403 with ``code="PERMISSION_DENIED"``. The
gate runs BEFORE the body parse so a non-admin POST can't influence
the audit emission either.

Tests use real Django ORM rows + real DRF APIClient — no mocks.
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import (
    ensure_user_has_tenant_admin_role,
)
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_tenant(*, slug_prefix: str = "t"):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{slug_prefix} {uid}",
        slug=f"{slug_prefix}-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status="UNVERIFIED",
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    return tenant, user


class FeatureFlagsGetTest(TestCase):
    """``GET`` returns the per-tenant flag values + descriptions."""

    def test_admin_can_read_flags(self):
        _tenant, user = _seed_tenant()
        ensure_user_has_tenant_admin_role(user)

        client = APIClient()
        client.force_authenticate(user=user)
        _resp = client.get("/api/v1/tenants/me/feature-flags/")
