"""
104.4 — Export Isolation Test

Verifies that exporting contracts returns only the caller's tenant data.
"""

import uuid

import pytest

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract

pytestmark = pytest.mark.django_db(transaction=True)


class TestExportIsolation:
    """Contract list/export endpoints must be tenant-scoped."""

    @pytest.fixture(autouse=True)
    def _create_contracts(self, tenant_a, user_a, tenant_b, user_b):
        uid = uuid.uuid4().hex[:8]

        self.asset_a = Asset.objects.create(
            tenant=tenant_a,
            key=f"export-a-{uid}",
            name=f"Export Asset A {uid}",
            status=AssetStatus.ACTIVE,
            created_by=user_a,
        )
        self.contract_a = Contract.objects.create(
            tenant=tenant_a,
            asset=self.asset_a,
            version=1,
            status="DRAFT",
            original_spec_type="odcs",
            original_spec_version="2.2.1",
            original_format="yaml",
            original_raw="datasetName: test-a",
        )

        self.asset_b = Asset.objects.create(
            tenant=tenant_b,
            key=f"export-b-{uid}",
            name=f"Export Asset B {uid}",
            status=AssetStatus.ACTIVE,
            created_by=user_b,
        )
        self.contract_b = Contract.objects.create(
            tenant=tenant_b,
            asset=self.asset_b,
            version=1,
            status="DRAFT",
            original_spec_type="odcs",
            original_spec_version="2.2.1",
            original_format="yaml",
            original_raw="datasetName: test-b",
        )

    def test_contract_list_only_shows_own_tenant(self, client_a):
        """GET /api/v1/contracts/ returns only Tenant A contracts."""
        resp = client_a.get("/api/v1/contracts/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        ids = {str(r["id"]) for r in results} if isinstance(results, list) else set()
        assert str(self.contract_a.id) in ids
        assert str(self.contract_b.id) not in ids, (
            "Contract list leaked Tenant B contract to Tenant A"
        )

    def test_contract_list_tenant_b_excludes_tenant_a(self, client_b):
        """Tenant B cannot see Tenant A contracts in list."""
        resp = client_b.get("/api/v1/contracts/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        ids = {str(r["id"]) for r in results} if isinstance(results, list) else set()
        assert str(self.contract_b.id) in ids
        assert str(self.contract_a.id) not in ids

    def test_contract_export_isolation(self, client_b):
        """Tenant B cannot export Tenant A's contract."""
        resp = client_b.get(f"/api/v1/contracts/{self.contract_a.id}/export/")
        assert resp.status_code in (403, 404), f"Cross-tenant export returned {resp.status_code}"

    def test_contract_download_isolation(self, client_b):
        """Tenant B cannot download Tenant A's contract."""
        resp = client_b.get(f"/api/v1/contracts/{self.contract_a.id}/download/")
        assert resp.status_code in (403, 404), f"Cross-tenant download returned {resp.status_code}"

    def test_row_count_matches_tenant(self, client_a, tenant_a):
        """Contract list count matches DB count for the tenant."""
        resp = client_a.get("/api/v1/contracts/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        api_count = len(results) if isinstance(results, list) else 0
        db_count = Contract.objects.filter(tenant=tenant_a).count()
        assert api_count == db_count, f"API returned {api_count} but DB has {db_count}"
