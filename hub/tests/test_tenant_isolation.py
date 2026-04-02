"""
Phase 14 – Tenant Isolation Tests (14.8)

Uses *real* JWT tokens (no force_authenticate) to prove that tenant isolation
is enforced at the authentication/authorisation layer, not just at the ORM
filter layer.

Tenants are kept intentionally simple (no billing/KYC set-up) because the
tests only exercise READ operations (GET), which do not require an active
subscription.

Token generation uses JWTTokenGenerator.generate_access_token() directly, which
avoids any HTTP round-trip and is consistent with the pattern used in the Phase
11 tests (test_auth_security.py::TestGetUserFromTokenQueryCount).
"""

import uuid

import pytest
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.role_support import ensure_user_has_tenant_admin_role
from hub.apps.users.models import User, UserStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tenant(name_suffix: str = "") -> Tenant:
    suffix = name_suffix or uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"Tenant-{suffix}",
        slug=f"tenant-{suffix}",
        status="ACTIVE",
    )


def _make_user(tenant: Tenant, email: str | None = None, is_platform_admin: bool = False) -> User:
    email = email or f"user-{uuid.uuid4().hex[:8]}@test.local"
    user = User.objects.create_user(
        email=email,
        password="Pass1234!",
        tenant=tenant,
        is_platform_admin=is_platform_admin,
    )
    user.status = UserStatus.ACTIVE
    user.save(update_fields=["status"])
    return user


def _bearer_client(user: User) -> APIClient:
    """Return an APIClient with a real JWT Bearer token for *user*."""
    token = JWTTokenGenerator.generate_access_token(user)
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return client


def _make_asset(tenant: Tenant, created_by: User, key_suffix: str = "") -> Asset:
    key = key_suffix or uuid.uuid4().hex[:8]
    return Asset.objects.create(
        tenant=tenant,
        key=f"asset-{key}",
        name=f"Asset {key}",
        status=AssetStatus.ACTIVE,
        created_by=created_by,
    )


def _make_contract(tenant: Tenant, asset: Asset, created_by: User) -> Contract:
    return Contract.objects.create(
        tenant=tenant,
        asset=asset,
        version=1,
        status=ContractStatus.DRAFT,
        original_spec_type="ODCS",
        original_format="JSON",
        original_raw='{"id": "test"}',
        created_by=created_by,
    )


# ---------------------------------------------------------------------------
# 14.8  Tenant isolation tests with real JWT auth
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256")
class TestTenantIsolationAssets(TestCase):
    """
    Verify that asset endpoints respect tenant boundaries using real JWT tokens.
    """

    def setUp(self):
        # Tenant A + user + asset
        self.tenant_a = _make_tenant("a")
        self.user_a = _make_user(self.tenant_a, "user-a@test.local")
        self.asset_a = _make_asset(self.tenant_a, self.user_a)

        # Tenant B + user
        self.tenant_b = _make_tenant("b")
        self.user_b = _make_user(self.tenant_b, "user-b@test.local")

        # Authenticated clients with real JWT tokens
        self.client_a = _bearer_client(self.user_a)
        self.client_b = _bearer_client(self.user_b)

    # ------------------------------------------------------------------
    # Tenant A can read its own asset
    # ------------------------------------------------------------------

    def test_tenant_a_can_read_own_asset(self):
        resp = self.client_a.get(f"/api/v1/assets/{self.asset_a.id}/")
        self.assertEqual(resp.status_code, 200, resp.data)

    # ------------------------------------------------------------------
    # Tenant B cannot read Tenant A's asset (must return 404)
    # ------------------------------------------------------------------

    def test_cross_tenant_asset_returns_404(self):
        """Tenant-B user GET /api/v1/assets/{tenant_A_asset_id}/ must return 404."""
        resp = self.client_b.get(f"/api/v1/assets/{self.asset_a.id}/")
        self.assertEqual(
            resp.status_code,
            404,
            f"Expected 404 for cross-tenant asset access, got {resp.status_code}: {resp.data}",
        )

    def test_cross_tenant_asset_list_excludes_other_tenant(self):
        """Tenant B's asset list must not contain tenant A's asset."""
        resp = self.client_b.get("/api/v1/assets/")
        self.assertEqual(resp.status_code, 200, resp.data)
        # Support paginated and non-paginated responses
        results = resp.data.get("results", resp.data) if isinstance(resp.data, dict) else resp.data
        ids = [str(item.get("id")) for item in (results if isinstance(results, list) else [])]
        self.assertNotIn(str(self.asset_a.id), ids)

    # ------------------------------------------------------------------
    # Unauthenticated request → 401
    # ------------------------------------------------------------------

    def test_unauthenticated_asset_access_returns_401(self):
        anon_client = APIClient()
        resp = anon_client.get(f"/api/v1/assets/{self.asset_a.id}/")
        self.assertEqual(resp.status_code, 401, resp.data)


@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256")
class TestTenantIsolationContracts(TestCase):
    """
    Verify that contract endpoints respect tenant boundaries using real JWT tokens.
    """

    def setUp(self):
        self.tenant_a = _make_tenant("ca")
        self.user_a = _make_user(self.tenant_a, "user-ca@test.local")
        self.asset_a = _make_asset(self.tenant_a, self.user_a, "contract-asset")
        self.contract_a = _make_contract(self.tenant_a, self.asset_a, self.user_a)

        self.tenant_b = _make_tenant("cb")
        self.user_b = _make_user(self.tenant_b, "user-cb@test.local")

        self.client_a = _bearer_client(self.user_a)
        self.client_b = _bearer_client(self.user_b)

    def test_tenant_a_can_read_own_contract(self):
        resp = self.client_a.get(f"/api/v1/contracts/{self.contract_a.id}/")
        self.assertEqual(resp.status_code, 200, resp.data)

    def test_cross_tenant_contract_returns_404(self):
        resp = self.client_b.get(f"/api/v1/contracts/{self.contract_a.id}/")
        self.assertEqual(
            resp.status_code,
            404,
            f"Expected 404 for cross-tenant contract access, got {resp.status_code}: {resp.data}",
        )

    def test_unauthenticated_contract_access_returns_401(self):
        anon_client = APIClient()
        resp = anon_client.get(f"/api/v1/contracts/{self.contract_a.id}/")
        self.assertEqual(resp.status_code, 401, resp.data)


@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256")
class TestPlatformAdminCrossTenantAccess(TestCase):
    """
    Platform admins must be able to read assets from any tenant.
    """

    def setUp(self):
        # Regular tenant with an asset
        self.tenant_a = _make_tenant("pa")
        self.user_a = _make_user(self.tenant_a, "user-pa@test.local")
        self.asset_a = _make_asset(self.tenant_a, self.user_a, "admin-asset")

        # Platform admin (no specific tenant required)
        admin_tenant = _make_tenant("admin")
        self.platform_admin = _make_user(
            admin_tenant, "admin@test.local", is_platform_admin=True
        )
        self.admin_client = _bearer_client(self.platform_admin)

    def test_platform_admin_can_read_any_tenant_asset(self):
        resp = self.admin_client.get(f"/api/v1/assets/{self.asset_a.id}/")
        # Platform admin should get 200 (not 404)
        self.assertEqual(
            resp.status_code,
            200,
            f"Platform admin should access any asset; got {resp.status_code}: {resp.data}",
        )


# ---------------------------------------------------------------------------
# 14.8 (extension) — Tenant isolation: WRITE / MUTATE operations
#
# Read-only isolation is necessary but not sufficient.  An attacker who can
# enumerate a resource id from a public listing or a leaked URL must not be
# able to PATCH, PUT, or DELETE a resource owned by another tenant.
# ---------------------------------------------------------------------------

@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256")
class TestTenantIsolationAssetsMutation(TestCase):
    """
    Cross-tenant PATCH / DELETE on assets must return 404, not 403.

    Returning 404 (rather than 403) prevents leaking the existence of a
    resource to a foreign tenant — a necessary complement to the read
    isolation tests in TestTenantIsolationAssets.
    """

    def setUp(self):
        # Tenant A owns an asset
        self.tenant_a = _make_tenant("mut-a")
        ensure_tenant_has_active_subscription(self.tenant_a)
        self.user_a = _make_user(self.tenant_a, "user-mut-a@test.local")
        self.asset_a = _make_asset(self.tenant_a, self.user_a, "mut")

        # Tenant B is the attacker
        self.tenant_b = _make_tenant("mut-b")
        ensure_tenant_has_active_subscription(self.tenant_b)
        self.user_b = _make_user(self.tenant_b, "user-mut-b@test.local")

        self.client_a = _bearer_client(self.user_a)
        self.client_b = _bearer_client(self.user_b)

    # ── PATCH ─────────────────────────────────────────────────────────────

    def test_cross_tenant_asset_patch_returns_404(self):
        """Tenant B PATCH on tenant A's asset must return 404."""
        resp = self.client_b.patch(
            f"/api/v1/assets/{self.asset_a.id}/",
            {"name": "hacked"},
            format="json",
        )
        self.assertEqual(
            resp.status_code,
            404,
            f"Cross-tenant PATCH must return 404, got {resp.status_code}: {resp.json()}",
        )

    # ── PUT ───────────────────────────────────────────────────────────────

    def test_cross_tenant_asset_put_returns_404(self):
        """Tenant B PUT on tenant A's asset must return 404."""
        resp = self.client_b.put(
            f"/api/v1/assets/{self.asset_a.id}/",
            {
                "name": "hacked",
                "key": "hacked-key",
                "status": "ACTIVE",
            },
            format="json",
        )
        self.assertEqual(
            resp.status_code,
            404,
            f"Cross-tenant PUT must return 404, got {resp.status_code}: {resp.json()}",
        )

    # ── DELETE ────────────────────────────────────────────────────────────

    def test_cross_tenant_asset_delete_returns_404(self):
        """Tenant B DELETE on tenant A's asset must return 404."""
        resp = self.client_b.delete(f"/api/v1/assets/{self.asset_a.id}/")
        self.assertEqual(
            resp.status_code,
            404,
            f"Cross-tenant DELETE must return 404, got {resp.status_code}: {resp.json()}",
        )
        # Confirm the asset still exists (was not deleted)
        self.assertTrue(
            Asset.objects.filter(id=self.asset_a.id).exists(),
            "Asset must not have been deleted by a cross-tenant request",
        )

    # ── Positive case: own-tenant PATCH succeeds ──────────────────────────

    def test_own_tenant_asset_patch_returns_success(self):
        """Tenant A PATCH on its own DRAFT asset must return 200."""
        ensure_user_has_tenant_admin_role(self.user_a)
        # Use a DRAFT asset to avoid business rule requiring ACTIVE contract
        draft_asset = Asset.objects.create(
            tenant=self.tenant_a,
            key=f"mut-draft-{uuid.uuid4().hex[:8]}",
            name="Draft Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user_a,
        )
        resp = self.client_a.patch(
            f"/api/v1/assets/{draft_asset.id}/",
            {"name": "updated name"},
            format="json",
        )
        self.assertEqual(
            resp.status_code,
            200,
            f"Own-tenant PATCH must return 200; got {resp.status_code}: {resp.data}",
        )


@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256")
class TestTenantIsolationContractsMutation(TestCase):
    """
    Cross-tenant PATCH / DELETE on contracts must return 404.
    """

    def setUp(self):
        self.tenant_a = _make_tenant("cmut-a")
        ensure_tenant_has_active_subscription(self.tenant_a)
        self.user_a = _make_user(self.tenant_a, "user-cmut-a@test.local")
        self.asset_a = _make_asset(self.tenant_a, self.user_a, "cmut-asset")
        self.contract_a = _make_contract(self.tenant_a, self.asset_a, self.user_a)

        self.tenant_b = _make_tenant("cmut-b")
        ensure_tenant_has_active_subscription(self.tenant_b)
        self.user_b = _make_user(self.tenant_b, "user-cmut-b@test.local")

        self.client_a = _bearer_client(self.user_a)
        self.client_b = _bearer_client(self.user_b)

    def test_cross_tenant_contract_patch_returns_404(self):
        resp = self.client_b.patch(
            f"/api/v1/contracts/{self.contract_a.id}/",
            {"version": 99},
            format="json",
        )
        self.assertEqual(
            resp.status_code,
            404,
            f"Cross-tenant contract PATCH must return 404, got {resp.status_code}: {resp.json()}",
        )

    def test_cross_tenant_contract_delete_returns_404(self):
        resp = self.client_b.delete(f"/api/v1/contracts/{self.contract_a.id}/")
        self.assertEqual(
            resp.status_code,
            404,
            f"Cross-tenant contract DELETE must return 404, got {resp.status_code}: {resp.json()}",
        )
        self.assertTrue(
            Contract.objects.filter(id=self.contract_a.id).exists(),
            "Contract must not have been deleted by a cross-tenant request",
        )
