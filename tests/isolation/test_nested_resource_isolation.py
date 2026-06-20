"""
104.2 — Nested Resource Isolation Test

Verifies that Tenant B cannot access any level of a nested resource
hierarchy belonging to Tenant A: asset → dataset → file.
"""

import uuid

import pytest

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File

pytestmark = pytest.mark.django_db(transaction=True)


class TestNestedResourceIsolation:
    """Tenant B cannot traverse Tenant A's asset → dataset → file chain."""

    @pytest.fixture(autouse=True)
    def _create_hierarchy(self, tenant_a, user_a, tenant_b, user_b):
        uid = uuid.uuid4().hex[:8]

        # Tenant A hierarchy
        self.asset_a = Asset.objects.create(
            tenant=tenant_a,
            key=f"nested-a-{uid}",
            name=f"Nested Asset A {uid}",
            status=AssetStatus.ACTIVE,
            created_by=user_a,
        )
        self.file_a = File.objects.create(
            tenant=tenant_a,
            name=f"nested-file-{uid}.csv",
            content_type="text/csv",
            size=100,
            storage_path=f"tenants/{tenant_a.id}/files/nested-{uid}.csv",
            created_by=user_a,
        )
        self.dataset_a = Dataset.objects.create(
            tenant=tenant_a,
            asset=self.asset_a,
            file=self.file_a,
            format="CSV",
        )

        # Tenant B hierarchy (to confirm B can access its own)
        self.asset_b = Asset.objects.create(
            tenant=tenant_b,
            key=f"nested-b-{uid}",
            name=f"Nested Asset B {uid}",
            status=AssetStatus.ACTIVE,
            created_by=user_b,
        )

    def test_tenant_b_cannot_read_tenant_a_asset(self, client_b):
        resp = client_b.get(f"/api/v1/assets/{self.asset_a.id}/")
        assert resp.status_code == 404

    def test_tenant_b_cannot_read_tenant_a_dataset(self, client_b):
        resp = client_b.get(f"/api/v1/datasets/{self.dataset_a.id}/")
        assert resp.status_code == 404

    def test_tenant_b_cannot_read_tenant_a_file(self, client_b):
        resp = client_b.get(f"/api/v1/files/{self.file_a.id}/")
        assert resp.status_code == 404

    def test_tenant_a_can_read_own_hierarchy(self, client_a):
        for url in [
            f"/api/v1/assets/{self.asset_a.id}/",
            f"/api/v1/datasets/{self.dataset_a.id}/",
            f"/api/v1/files/{self.file_a.id}/",
        ]:
            resp = client_a.get(url)
            assert resp.status_code == 200, f"Tenant A cannot read own: {url}"

    def test_tenant_b_cannot_update_tenant_a_asset(self, client_b):
        resp = client_b.patch(
            f"/api/v1/assets/{self.asset_a.id}/",
            {"name": "Hacked"},
            format="json",
        )
        assert resp.status_code == 404
        self.asset_a.refresh_from_db()
        assert "Hacked" not in self.asset_a.name

    def test_tenant_b_cannot_delete_tenant_a_asset(self, client_b):
        resp = client_b.delete(f"/api/v1/assets/{self.asset_a.id}/")
        assert resp.status_code == 404
        assert Asset.objects.filter(id=self.asset_a.id).exists()

    def test_tenant_b_list_excludes_tenant_a_resources(self, client_b):
        """List endpoints must not leak Tenant A's IDs."""
        for url, model_a_id in [
            ("/api/v1/assets/", self.asset_a.id),
            ("/api/v1/datasets/", self.dataset_a.id),
            ("/api/v1/files/", self.file_a.id),
        ]:
            resp = client_b.get(url)
            assert resp.status_code == 200
            results = resp.data.get("results", resp.data)
            ids = [str(r["id"]) for r in results] if isinstance(results, list) else []
            assert str(model_a_id) not in ids, f"Leaked {url} ID {model_a_id}"
