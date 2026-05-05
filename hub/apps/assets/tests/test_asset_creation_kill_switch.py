"""
Phase 250.6.A — TDD pin for the per-tenant ``asset_creation`` kill switch.

Per D250.17, the kill switch lets ops freeze new-asset creation on a
per-tenant basis without touching code: a flipped flag stops the
``POST /api/v1/assets/`` and ``POST /api/v1/assets/data-first/`` paths
from accepting any new work, returning 403 + ``ASSET_CREATION_DISABLED``.
The flag also propagates to the SPA via ``/api/v1/capabilities/`` so
the frontend can render the "disabled capability" page (not a 403
toast inside the create form, which would be confusing).

The test pins all four flag combinations:

1. Existing tenant (default True) + flag True ⇒ create succeeds.
2. Tenant flag flipped to False ⇒ create returns 403 with code.
3. Existing tenant + data-first endpoint when flag is False ⇒ same 403.
4. Capability response carries ``asset_creation`` mirror of the flag.

Tests use real Django ORM rows + real DRF APIClient — no mocks. The
data-first endpoint's downstream workflow path is NOT exercised
because the kill switch fires at the view boundary BEFORE serializer
parsing — this is the load-bearing contract (no side-effects on
rejection).
"""
from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import (
    ensure_user_has_data_provider_role,
    ensure_user_has_tenant_admin_role,
)
from hub.apps.users.models import UserStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed_tenant(*, asset_creation_enabled: bool = True, slug_prefix: str = "t"):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"{slug_prefix} {uid}",
        slug=f"{slug_prefix}-{uid}",
        status=TenantStatus.ACTIVE,
        kyc_status="UNVERIFIED",
        asset_creation_enabled=asset_creation_enabled,
    )
    ensure_tenant_has_active_subscription(tenant)
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    # Use the canonical role-setup helpers (NOT ``user.roles = [...]``,
    # which is a no-op — there is no ``roles`` JSONField on User; role
    # checks at ``user.has_role(...)`` query the ``UserRole`` related
    # manager, not an instance attribute). Without these helpers the
    # downstream role check (``has_role("DATA_PROVIDER", "TENANT_ADMIN")``)
    # in ``AssetViewSet.create`` returns False and the counter-test
    # would 403 BEFORE the kill switch even fires.
    ensure_user_has_data_provider_role(user)
    ensure_user_has_tenant_admin_role(user)
    return tenant, user


# ---------------------------------------------------------------------------
# 250.6.A.1 — default True on existing tenants per D250.17
# ---------------------------------------------------------------------------


class TenantAssetCreationFlagDefaultTest(TestCase):
    """Existing tenants get ``asset_creation_enabled=True`` so the
    kill-switch deploy doesn't accidentally freeze every customer's
    asset creation. New tenants (created via the onboarding flow)
    can opt in to the False default for the onboarding-incomplete
    state — that's a separate code path."""

    def test_default_true_on_new_tenant(self):
        tenant = Tenant.objects.create(
            name=f"T {uuid.uuid4().hex[:6]}",
            slug=f"t-{uuid.uuid4().hex[:6]}",
            status=TenantStatus.ACTIVE,
            kyc_status="UNVERIFIED",
        )
        assert tenant.asset_creation_enabled is True


# ---------------------------------------------------------------------------
# 250.6.A.3 — backend views return 403 + ASSET_CREATION_DISABLED
# ---------------------------------------------------------------------------


class AssetCreationKillSwitchViewTest(TestCase):
    """When `tenant.asset_creation_enabled = False` the backend
    blocks both creation paths (POST /assets/ + POST /assets/data-first/)
    with HTTP 403 + ``code="ASSET_CREATION_DISABLED"`` BEFORE any
    serializer / workflow / persistence work begins."""

    def test_post_assets_returns_403_when_disabled(self):
        tenant, user = _seed_tenant(asset_creation_enabled=False)
        client = APIClient()
        client.force_authenticate(user=user)

        before = Asset.objects.filter(tenant=tenant).count()
        resp = client.post(
            "/api/v1/assets/",
            data={
                "key": f"a-{uuid.uuid4().hex[:6]}",
                "name": "Should be blocked",
            },
            format="json",
        )
        assert resp.status_code == 403, resp.content
        body = resp.json()
        assert body.get("code") == "ASSET_CREATION_DISABLED"
        # No side-effect: no Asset row landed.
        assert Asset.objects.filter(tenant=tenant).count() == before

    def test_post_data_first_returns_403_when_disabled(self):
        tenant, user = _seed_tenant(asset_creation_enabled=False)
        client = APIClient()
        client.force_authenticate(user=user)

        before = Asset.objects.filter(tenant=tenant).count()
        # Django's test client computes ``CONTENT_LENGTH`` automatically
        # from the request body — no need to set ``HTTP_CONTENT_LENGTH``
        # explicitly (and ``HTTP_CONTENT_LENGTH`` would set the wrong
        # WSGI meta key anyway: the data-first body-size guard at
        # views.py:511 reads ``CONTENT_LENGTH`` (no ``HTTP_`` prefix —
        # WSGI convention), not ``HTTP_CONTENT_LENGTH``).
        resp = client.post(
            "/api/v1/assets/data-first/",
            data={
                "file_id": str(uuid.uuid4()),
                "key": f"a-{uuid.uuid4().hex[:6]}",
                "name": "Should be blocked",
            },
            format="json",
        )
        assert resp.status_code == 403, resp.content
        body = resp.json()
        assert body.get("code") == "ASSET_CREATION_DISABLED"
        assert Asset.objects.filter(tenant=tenant).count() == before

    def test_post_assets_succeeds_when_enabled(self):
        """Counter-test: with the flag at default True, the POST path
        works as it did pre-Phase. Pins that the gate is opt-in
        (False breaks creation) not fail-closed (True still works)."""
        tenant, user = _seed_tenant(asset_creation_enabled=True)
        client = APIClient()
        client.force_authenticate(user=user)

        resp = client.post(
            "/api/v1/assets/",
            data={
                "key": f"a-{uuid.uuid4().hex[:6]}",
                "name": "Allowed",
            },
            format="json",
        )
        assert resp.status_code == 201, resp.content
        body = resp.json()
        assert body["status"] == AssetStatus.DRAFT


# ---------------------------------------------------------------------------
# 250.6.A.4 — capability mirrored on /api/v1/capabilities/
# ---------------------------------------------------------------------------


class AssetCreationCapabilityResponseTest(TestCase):
    """``GET /api/v1/capabilities/`` MUST include ``asset_creation``
    mirroring the tenant's flag value. The SPA reads this to decide
    whether to render the create button / form vs the disabled page."""

    def test_capabilities_carries_asset_creation_true(self):
        tenant, user = _seed_tenant(asset_creation_enabled=True)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/capabilities/")
        assert resp.status_code == 200
        caps = resp.json().get("capabilities", {})
        assert "asset_creation" in caps, list(caps.keys())
        assert caps["asset_creation"] is True

    def test_capabilities_carries_asset_creation_false(self):
        tenant, user = _seed_tenant(asset_creation_enabled=False)
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get("/api/v1/capabilities/")
        caps = resp.json().get("capabilities", {})
        assert caps.get("asset_creation") is False
