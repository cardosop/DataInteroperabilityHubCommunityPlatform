"""
104.3 — Search Isolation Test

Verifies that Tenant A's searchable resources are invisible to Tenant B's
search queries, even when searching by exact name or keyword.
"""
import uuid
import time

import pytest

from hub.apps.assets.models import Asset, AssetStatus

pytestmark = pytest.mark.django_db(transaction=True)


class TestSearchIsolation:
    """Search must be tenant-scoped — no cross-tenant result leakage."""

    @pytest.fixture(autouse=True)
    def _create_searchable_assets(self, tenant_a, user_a, tenant_b, user_b):
        uid = uuid.uuid4().hex[:8]
        self.unique_keyword = f"UniqueSearchTerm{uid}"

        self.asset_a = Asset.objects.create(
            tenant=tenant_a,
            key=f"search-a-{uid}",
            name=f"Asset {self.unique_keyword} Alpha",
            status=AssetStatus.ACTIVE,
            created_by=user_a,
        )
        self.asset_b = Asset.objects.create(
            tenant=tenant_b,
            key=f"search-b-{uid}",
            name=f"Asset Bravo {uid}",
            status=AssetStatus.ACTIVE,
            created_by=user_b,
        )

    def test_tenant_b_search_cannot_find_tenant_a_asset(self, client_b):
        """Tenant B searching exact keyword finds 0 results from Tenant A."""
        resp = client_b.get(
            "/api/v1/assets/",
            {"search": self.unique_keyword},
        )
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        ids = [str(r["id"]) for r in results] if isinstance(results, list) else []
        assert str(self.asset_a.id) not in ids, (
            f"Search leaked Tenant A asset to Tenant B"
        )

    def test_tenant_a_search_finds_own_asset(self, client_a):
        """Tenant A searching own keyword finds its asset."""
        resp = client_a.get(
            "/api/v1/assets/",
            {"search": self.unique_keyword},
        )
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        ids = [str(r["id"]) for r in results] if isinstance(results, list) else []
        assert str(self.asset_a.id) in ids, (
            "Tenant A cannot find its own asset via search"
        )

    def test_tenant_b_search_excludes_tenant_a_from_results(self, client_b):
        """Even broad search returns only Tenant B's own assets."""
        resp = client_b.get("/api/v1/assets/", {"search": "Asset"})
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        if isinstance(results, list):
            for item in results:
                assert str(item["id"]) != str(self.asset_a.id), (
                    "Broad search leaked Tenant A asset"
                )
