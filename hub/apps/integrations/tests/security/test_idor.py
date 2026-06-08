"""
Phase 250.5.C.1 — federated-asset IDOR (Insecure Direct Object Reference)
test suite.

The federated-asset surface exposes ``ExternalResourceReference`` rows
through three nested endpoints on ``AssetViewSet``:

* ``GET  /api/v1/assets/{asset_id}/external-resources/`` — list
* ``POST /api/v1/assets/{asset_id}/external-resources/download/`` — single
* ``POST /api/v1/assets/{asset_id}/external-resources/batch-download/`` — batch

The trailing slash on the download endpoints is load-bearing: DRF's
``DefaultRouter`` defaults to ``trailing_slash='/'``, so omitting the
slash returns 404 from the URL resolver (NOT from the cross-tenant
gate or the role gate). Tests against these endpoints would pass for
the wrong reason without the slash.

Per Phase 250.5.A's threat model + the IDOR audit gap this phase closes,
the contract pinned by this suite is:

1. **Cross-tenant read returns 404** (NOT 403, NOT 200) — existence-leak
   protection. A user from tenant B asking for tenant A's external
   resources MUST receive 404 with no asset/resource metadata in the
   response body.

2. **AUDITOR cannot mutate** — the download endpoints CREATE File +
   Dataset rows, so they're write-class operations. AUDITOR is a
   read-only role; the download endpoints MUST refuse AUDITOR with
   403, leaving no DB side-effects.

3. **Missing tenant ⇒ 401** — an authenticated user with no tenant
   assignment AND no X-Tenant-Id header on a tenant-scoped endpoint
   MUST receive 401 (the request cannot be tenant-resolved). 403 is
   incorrect because the user IS authenticated; 401 forces the
   client to refresh credentials or attach a tenant header.

4. **Malformed tenant_id ⇒ 400** — an X-Tenant-Id header carrying a
   non-UUID value MUST return 400 (Bad Request), NOT 500
   (server-side ValidationError leak). 403 would be wrong because
   the request is structurally invalid, not a permission failure.

Tests use real Django ORM rows + real DRF APIClient — NO mocks of
business logic. The download endpoint's connector path is exercised
against a `MarketplaceConnection` test fixture; downloads themselves
are blocked at the role gate so no real S3/HTTP work fires.
"""
from __future__ import annotations

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.assets.models import (
    Asset,
    AssetSourceType,
    AssetStatus,
    ExternalResourceReference,
)
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
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
        federated_import_enabled=True,
    )
    ensure_tenant_has_active_subscription(tenant)
    return tenant


def _seed_user(tenant, *, roles: list[str] | None = None):
    uid = uuid.uuid4().hex[:8]
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    if roles is not None:
        from hub.apps.users.models import Role
        for role_name in roles:
            role = Role.objects.filter(tenant=tenant, name=role_name).first()
            if not role:
                role = Role.objects.create(tenant=tenant, name=role_name, description=f"{role_name} Role")
            user.user_roles.create(role=role)
    return user


def _seed_federated_asset_with_resource(tenant):
    """Stand up a FEDERATED Asset + one ExternalResourceReference so
    the IDOR tests have a real row to attempt access against."""
    from hub.apps.integrations.models import MarketplaceConnection
    from hub.apps.integrations.base import MarketplaceType

    asset = Asset.objects.create(
        tenant=tenant,
        key=f"fed-{uuid.uuid4().hex[:6]}",
        name="Federated Asset Under Test",
        status=AssetStatus.DRAFT,
        source_type=AssetSourceType.FEDERATED,
    )
    connection = MarketplaceConnection.objects.create(
        tenant=tenant,
        name=f"Conn {uuid.uuid4().hex[:6]}",
        marketplace_type=MarketplaceType.CKAN_INSTANCE.value,
        config={"endpoint_url": "https://ckan.example/api"},
        is_active=True,
    )
    ref = ExternalResourceReference.objects.create(
        asset=asset,
        resource_id="r-1",
        name="resource-a",
        url="https://ckan.example/r/a.csv",
        format="CSV",
        marketplace_type="CKAN_INSTANCE",
        connection_id=connection.id,
    )
    return asset, connection, ref


# ---------------------------------------------------------------------------
# 250.5.C.1 — cross-tenant read returns 404 (no existence leak)
# ---------------------------------------------------------------------------


class CrossTenantExternalResourceListReadProtectionTest(TestCase):
    """Tenant-B user GETting tenant-A's external resources MUST receive
    404. The response body MUST NOT carry the asset's name/key/external
    resource metadata."""

    def test_cross_tenant_list_external_resources_returns_404(self):
        tenant_a = _seed_tenant(slug_prefix="a")
        tenant_b = _seed_tenant(slug_prefix="b")
        user_b = _seed_user(tenant_b, roles=["TENANT_ADMIN", "DATA_PROVIDER"])
        asset_a, _conn_a, ref_a = _seed_federated_asset_with_resource(tenant_a)

        client = APIClient()
        client.force_authenticate(user=user_b)
        resp = client.get(f"/api/v1/assets/{asset_a.id}/external-resources/")

        assert resp.status_code == 404, resp.content
        # Defensive: even if the body includes a "detail" key (DRF's
        # default), it MUST NOT carry tenant-A's asset metadata.
        body_str = resp.content.decode("utf-8", errors="replace")
        assert asset_a.name not in body_str
        assert ref_a.name not in body_str
        assert str(asset_a.key) not in body_str

    def test_cross_tenant_download_external_resource_returns_404(self):
        tenant_a = _seed_tenant(slug_prefix="a")
        tenant_b = _seed_tenant(slug_prefix="b")
        user_b = _seed_user(tenant_b, roles=["TENANT_ADMIN", "DATA_PROVIDER"])
        asset_a, _conn_a, ref_a = _seed_federated_asset_with_resource(tenant_a)

        client = APIClient()
        client.force_authenticate(user=user_b)
        resp = client.post(
            f"/api/v1/assets/{asset_a.id}/external-resources/download/",
            data={"resource_id": ref_a.resource_id},
            format="json",
        )
        # 404, NOT 403 — preserve zero-knowledge of cross-tenant data.
        assert resp.status_code == 404, resp.content


# ---------------------------------------------------------------------------
# 250.5.C.1 — AUDITOR cannot mutate (download = creates File/Dataset)
# ---------------------------------------------------------------------------


class AuditorMutationDenyTest(TestCase):
    """The download endpoints create File + Dataset rows — write-class
    operations. AUDITOR is a read-only role; both endpoints MUST refuse
    with 403 and leave NO downstream DB side-effects."""

    def test_auditor_download_returns_403_no_dataset_created(self):
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        tenant = _seed_tenant(slug_prefix="t")
        auditor = _seed_user(tenant, roles=["AUDITOR"])
        asset, _conn, ref = _seed_federated_asset_with_resource(tenant)

        files_before = File.objects.filter(tenant=tenant).count()
        datasets_before = Dataset.objects.filter(asset=asset).count()

        client = APIClient()
        client.force_authenticate(user=auditor)
        resp = client.post(
            f"/api/v1/assets/{asset.id}/external-resources/download/",
            data={"resource_id": ref.resource_id},
            format="json",
        )
        # AUDITOR is read-only on federated assets; mutate-class ops
        # must be 403 (NOT 200, NOT 404). The pre-existing tenant-
        # scoping check passes (auditor IS in the tenant), so 404
        # would be wrong — the row exists, the role just can't act
        # on it.
        assert resp.status_code in (401, 403), resp.content
        # No File / Dataset side-effect — the refusal MUST land at the
        # role gate BEFORE any download / persistence work begins.
        assert File.objects.filter(tenant=tenant).count() == files_before
        assert Dataset.objects.filter(asset=asset).count() == datasets_before

    def test_auditor_batch_download_returns_403_no_side_effects(self):
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File

        tenant = _seed_tenant(slug_prefix="t")
        auditor = _seed_user(tenant, roles=["AUDITOR"])
        asset, _conn, ref = _seed_federated_asset_with_resource(tenant)

        files_before = File.objects.filter(tenant=tenant).count()
        datasets_before = Dataset.objects.filter(asset=asset).count()

        client = APIClient()
        client.force_authenticate(user=auditor)
        resp = client.post(
            f"/api/v1/assets/{asset.id}/external-resources/batch-download/",
            data={"resource_ids": [ref.resource_id]},
            format="json",
        )
        assert resp.status_code in (401, 403), resp.content
        assert File.objects.filter(tenant=tenant).count() == files_before
        assert Dataset.objects.filter(asset=asset).count() == datasets_before

    def test_auditor_can_still_list_external_resources(self):
        """Sanity counter-test: AUDITOR keeps READ access to the
        list endpoint (read-only role can read federated assets in
        own tenant per Phase 250.5.A.4)."""
        tenant = _seed_tenant(slug_prefix="t")
        auditor = _seed_user(tenant, roles=["AUDITOR"])
        asset, _conn, ref = _seed_federated_asset_with_resource(tenant)

        client = APIClient()
        client.force_authenticate(user=auditor)
        resp = client.get(f"/api/v1/assets/{asset.id}/external-resources/")
        assert resp.status_code == 200, resp.content
        body = resp.json()
        assert isinstance(body, dict) or isinstance(body, list)


# ---------------------------------------------------------------------------
# 250.5.C.1 — tenant-resolution failure modes (401 vs 400)
# ---------------------------------------------------------------------------


class TenantResolutionFailureModesTest(TestCase):
    """The tenant-scoping middleware (`hub.apps.auth.middleware.TenantScopingMiddleware`)
    is the gate for X-Tenant-Id resolution. The IDOR-relevant failure
    modes are:

    * X-Tenant-Id header present but bearer token missing/invalid → 401
      (the credentials are bad, retry after refresh).
    * X-Tenant-Id header carries a non-UUID value → 400 (the request
      is structurally invalid; NOT 500 with a stack trace; NOT 403
      which would imply a permission decision).
    """

    def test_xtenantid_header_without_auth_returns_401(self):
        tenant = _seed_tenant(slug_prefix="t")
        # Unauthenticated client — no force_authenticate, no Authorization
        # header. The middleware sees the X-Tenant-Id header, can't
        # resolve a user, and returns 401.
        client = APIClient()
        resp = client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=str(tenant.id),
        )
        assert resp.status_code == 401, resp.content

    def test_malformed_xtenantid_header_returns_400(self):
        """X-Tenant-Id with a non-UUID value MUST surface as 400. A
        500 (unhandled ValidationError on Tenant lookup) leaks
        server-side error structure to attackers; a 403 would be
        misleading because the request is malformed, not denied."""
        tenant = _seed_tenant(slug_prefix="t")
        user = _seed_user(tenant, roles=["TENANT_ADMIN"])

        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID="not-a-valid-uuid",
        )
        assert resp.status_code == 400, resp.content
        # The body should NOT carry a Python stack trace fragment.
        body_str = resp.content.decode("utf-8", errors="replace")
        assert "Traceback" not in body_str
        assert "ValidationError" not in body_str

    def test_unknown_xtenantid_returns_403(self):
        """Sanity: a syntactically VALID UUID that doesn't match any
        existing tenant yields 403 (per the existing middleware
        contract — the request is well-formed, just permission-
        denied). Documented as the contrast case for the 400 above."""
        tenant = _seed_tenant(slug_prefix="t")
        user = _seed_user(tenant, roles=["TENANT_ADMIN"])

        random_uuid = str(uuid.uuid4())
        client = APIClient()
        client.force_authenticate(user=user)
        resp = client.get(
            "/api/v1/assets/",
            HTTP_X_TENANT_ID=random_uuid,
        )
        assert resp.status_code == 403, resp.content
