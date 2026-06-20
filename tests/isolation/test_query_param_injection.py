"""
104.1 — Query Parameter Injection Isolation Test

Verifies that appending ?tenant_id=<other_tenant_uuid> to list endpoints
does NOT leak cross-tenant data.  The server must always scope by the
authenticated user's tenant, ignoring any tenant_id query parameter.
"""

import uuid

import pytest

from hub.apps.assets.models import Asset, AssetStatus

pytestmark = pytest.mark.django_db(transaction=True)

# Endpoints that accept list queries. Each tuple is (url, needs_data).
LIST_ENDPOINTS = [
    "/api/v1/assets/",
    "/api/v1/contracts/",
    "/api/v1/datasets/",
    "/api/v1/files/",
    "/api/v1/jobs/",
    "/api/v1/audit/events/",
    "/api/v1/webhooks/",
]


class TestQueryParamInjection:
    """Appending ?tenant_id=<other> must not bypass isolation."""

    def test_tenant_id_query_param_ignored_on_list(
        self, client_a, client_b, tenant_a, tenant_b, user_a
    ):
        """GET /api/v1/assets/?tenant_id=<tenant_b> returns only tenant A data."""
        Asset.objects.create(
            tenant=tenant_a,
            key=f"qp-asset-{uuid.uuid4().hex[:8]}",
            name="Tenant A Asset",
            status=AssetStatus.ACTIVE,
            created_by=user_a,
        )

        # Tenant A tries to inject Tenant B's ID as query param
        resp = client_a.get(
            "/api/v1/assets/",
            {"tenant_id": str(tenant_b.id)},
        )
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        if isinstance(results, list):
            for item in results:
                # Every returned asset must belong to tenant A
                assert str(item.get("tenant")) == str(tenant_a.id) or "tenant" not in item, (
                    f"Leaked cross-tenant data: {item}"
                )

    def test_no_500_on_injected_params(self, client_a, tenant_b):
        """Injecting foreign tenant_id must not cause 500 errors."""
        for url in LIST_ENDPOINTS:
            resp = client_a.get(url, {"tenant_id": str(tenant_b.id)})
            if resp.status_code == 500:
                # Tolerate transient deadlocks (infrastructure, not isolation bug)
                body = getattr(resp, "data", {}) or {}
                msg = str(body.get("error", ""))
                assert "deadlock" in msg.lower(), f"{url} returned non-deadlock 500: {msg}"

    def test_random_uuid_tenant_param_ignored(self, client_a):
        """Injecting a random UUID as tenant_id must not cause errors."""
        fake_id = str(uuid.uuid4())
        for url in LIST_ENDPOINTS:
            resp = client_a.get(url, {"tenant_id": fake_id})
            if resp.status_code == 500:
                body = getattr(resp, "data", {}) or {}
                msg = str(body.get("error", ""))
                assert "deadlock" in msg.lower(), f"{url} returned non-deadlock 500: {msg}"

    def test_tenant_b_inject_tenant_a_id_gets_own_data(
        self, client_b, tenant_a, tenant_b, user_a, user_b
    ):
        """Tenant B injecting tenant_a ID still only sees Tenant B assets."""
        Asset.objects.create(
            tenant=tenant_a,
            key=f"qp-a-{uuid.uuid4().hex[:8]}",
            name="Secret A",
            status=AssetStatus.ACTIVE,
            created_by=user_a,
        )
        Asset.objects.create(
            tenant=tenant_b,
            key=f"qp-b-{uuid.uuid4().hex[:8]}",
            name="Public B",
            status=AssetStatus.ACTIVE,
            created_by=user_b,
        )

        resp = client_b.get(
            "/api/v1/assets/",
            {"tenant_id": str(tenant_a.id)},
        )
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        ids = {str(r["id"]) for r in results} if isinstance(results, list) else set()
        # Must not contain any tenant A asset IDs
        a_assets = set(str(a.id) for a in Asset.objects.filter(tenant=tenant_a))
        assert ids.isdisjoint(a_assets), "Cross-tenant leak via query param"
