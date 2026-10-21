"""
close-test-coverage-gaps 3.0 — ``POST /api/v1/tenants/onboarding/`` permission contract.

Checkpoint 3.0 verified the ``admin/tenants/`` estate and found it
PLATFORM_ADMIN-only everywhere (``IsAuthenticated + IsPlatformAdmin`` on every
admin view) — routes.tsx's "org creation is now a Platform Admin function in
/admin" comment is accurate. During that verification THIS endpoint surfaced a
contract INCOHERENCE: ``TenantConfigViewSet.get_permissions()`` returned
``AllowAny`` for the ``onboarding`` action, silently overriding the
``@action(permission_classes=[permissions.IsAuthenticated])`` decorator (dead
code), while the view body hand-rolled a PLATFORM_ADMIN check that returned a
non-DRF ``{"error": ...}`` 403. Net: anonymous requests reached the view and
got a 403 from the BODY instead of a 401 from the permission LAYER.

This suite pins the coherent contract:

1.  Permission enforcement lives at the DRF layer — ``get_permissions()``
    resolves the action to ``IsAuthenticated + IsPlatformAdmin`` (same
    pairing as ``AdminTenantCreateView``). Unauthenticated → 401;
    authenticated non-platform-admin → 403 with the platform's DRF 3.16
    envelope (``error.code=AUTH_FORBIDDEN``) — NOT the old hand-rolled
    ``{"error": "Organization creation requires ..."}`` body check.
2.  The provisioning capability is unchanged: a PLATFORM_ADMIN with a
    valid payload still creates the tenant + first user (201 + the
    documented ``{tenant, user, subscription_id, plan}`` response shape).
3.  Serializer validation still runs after the permission layer (bad
    payload → 400, not a 5xx or a permission response).
"""

from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework import permissions, status
from rest_framework.test import APIClient

from hub.apps.tenants.models import PlanTier, Tenant, TenantPlan
from hub.apps.tenants.permissions import IsPlatformAdmin
from hub.apps.tenants.views import TenantConfigViewSet

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()

ONBOARDING_URL = "/api/v1/tenants/onboarding/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tenant(*, slug_suffix: str | None = None) -> Tenant:
    uid = slug_suffix or uuid.uuid4().hex[:8]
    return Tenant.objects.create(name=f"Tenant {uid}", slug=f"tenant-{uid}")


def _ensure_free_plan() -> TenantPlan:
    """Hermetic free plan — mirrors the seed_default_plans row."""
    plan, _ = TenantPlan.objects.get_or_create(
        slug="free",
        defaults={
            "name": "Free",
            "tier": PlanTier.FREE,
            "is_active": True,
        },
    )
    return plan


def _make_platform_admin(*, tenant: Tenant | None = None) -> User:
    uid = uuid.uuid4().hex[:8]
    home_tenant = tenant or _make_tenant(slug_suffix=f"pa-home-{uid}")
    user = User.objects.create_user(
        email=f"pa-{uid}@example.com", password="testpass123", tenant=home_tenant
    )
    user.is_platform_admin = True
    user.save(update_fields=["is_platform_admin"])
    return user


def _make_regular_user(tenant: Tenant) -> User:
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"u-{uid}@example.com", password="testpass123", tenant=tenant
    )


def _valid_payload() -> dict:
    uid = uuid.uuid4().hex[:8]
    return {
        "name": f"Acme {uid}",
        "slug": f"acme-{uid}",
        "plan_slug": "free",
        "first_user": {
            "email": f"admin-{uid}@example.com",
            "password": "securepass123",
            "display_name": "Acme Admin",
        },
        "region": "us-east-1",
    }


# ---------------------------------------------------------------------------
# Tier 1 — the permission LAYER is the enforcement point
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.journey("JOURNEY-TENANT-ONBOARDING")
class TestOnboardingPermissionLayer:
    @pytest.mark.integration
    def test_get_permissions_resolves_platform_admin_for_onboarding(self):
        """``get_permissions()`` resolves the onboarding action to
        IsAuthenticated + IsPlatformAdmin.

        DRF 3.16 trap: ``ViewSetMixin.as_view`` does NOT apply
        ``@action(permission_classes=...)`` kwargs to the view — branching
        in ``get_permissions()`` on ``self.action`` is the supported
        mechanism. Guards against both the previous incoherence (AllowAny)
        and a regression that drops IsPlatformAdmin from the branch.
        """
        view = TenantConfigViewSet()
        view.action = "onboarding"
        resolved = [type(p) for p in view.get_permissions()]
        assert IsPlatformAdmin in resolved
        assert permissions.IsAuthenticated in resolved
        # Every OTHER action stays IsAuthenticated-only.
        view.action = "list"
        resolved_other = [type(p) for p in view.get_permissions()]
        assert resolved_other == [permissions.IsAuthenticated]

    @pytest.mark.integration
    def test_unauthenticated_returns_401(self):
        """Anon requests are rejected at the layer: 401, not a body-403."""
        client = APIClient()
        resp = client.post(ONBOARDING_URL, _valid_payload(), format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED, resp.content

    @pytest.mark.integration
    def test_authenticated_non_platform_admin_returns_drf_403(self):
        """Non-platform-admins get 403 with the platform's DRF 3.16
        envelope (error.code=AUTH_FORBIDDEN from the custom exception
        handler) — NOT the old hand-rolled
        {"error": "Organization creation requires PLATFORM_ADMIN role."}."""
        tenant = _make_tenant()
        regular = _make_regular_user(tenant)
        client = APIClient()
        client.force_authenticate(regular)
        resp = client.post(ONBOARDING_URL, _valid_payload(), format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN, resp.content
        body = resp.json()
        assert body.get("error", {}).get("code") == "AUTH_FORBIDDEN", body

    @pytest.mark.integration
    def test_no_tenant_created_by_blocked_caller(self):
        """A blocked caller must not mutate anything."""
        tenant = _make_tenant()
        regular = _make_regular_user(tenant)
        payload = _valid_payload()
        client = APIClient()
        client.force_authenticate(regular)
        resp = client.post(ONBOARDING_URL, payload, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN, resp.content
        assert not Tenant.objects.filter(slug=payload["slug"]).exists()


# ---------------------------------------------------------------------------
# Tier 2 — the provisioning capability is unchanged
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestOnboardingPlatformAdminHappyPath:
    @pytest.fixture(autouse=True)
    def _setup(self):
        _ensure_free_plan()
        self.admin = _make_platform_admin()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @pytest.mark.integration
    def test_platform_admin_provisions_tenant_with_first_user(self):
        payload = _valid_payload()
        resp = self.client.post(ONBOARDING_URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED, resp.content
        body = resp.json()
        assert body["tenant"]["slug"] == payload["slug"]
        assert body["tenant"]["name"] == payload["name"]
        assert body["user"]["email"] == payload["first_user"]["email"]
        assert body["plan"]["slug"] == "free"
        assert Tenant.objects.filter(slug=payload["slug"]).exists()

    @pytest.mark.integration
    def test_invalid_payload_returns_400_after_permission_layer(self):
        """Serializer validation still applies to admitted callers."""
        payload = _valid_payload()
        del payload["first_user"]
        resp = self.client.post(ONBOARDING_URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, resp.content
