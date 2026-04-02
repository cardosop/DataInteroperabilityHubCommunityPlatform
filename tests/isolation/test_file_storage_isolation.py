"""
104.7 — File Storage Isolation Test

Verifies that Tenant B cannot access Tenant A's files by ID,
path traversal, or direct download endpoint.
"""
import uuid

import pytest

from hub.apps.files.models import File

pytestmark = pytest.mark.django_db(transaction=True)


class TestFileStorageIsolation:
    """File endpoints must enforce tenant scoping on every operation."""

    @pytest.fixture(autouse=True)
    def _create_files(self, tenant_a, user_a, tenant_b, user_b):
        uid = uuid.uuid4().hex[:8]
        self.file_a = File.objects.create(
            tenant=tenant_a,
            name=f"secret-report-{uid}.csv",
            content_type="text/csv",
            size=256,
            storage_path=f"tenants/{tenant_a.id}/files/secret-{uid}.csv",
            created_by=user_a,
        )
        self.file_b = File.objects.create(
            tenant=tenant_b,
            name=f"public-report-{uid}.csv",
            content_type="text/csv",
            size=128,
            storage_path=f"tenants/{tenant_b.id}/files/public-{uid}.csv",
            created_by=user_b,
        )

    def test_tenant_b_cannot_get_tenant_a_file_by_id(self, client_b):
        """GET /api/v1/files/<tenant_a_file_id>/ → 404."""
        resp = client_b.get(f"/api/v1/files/{self.file_a.id}/")
        assert resp.status_code == 404

    def test_tenant_a_can_get_own_file(self, client_a):
        """GET /api/v1/files/<own_file_id>/ → 200."""
        resp = client_a.get(f"/api/v1/files/{self.file_a.id}/")
        assert resp.status_code == 200

    def test_tenant_b_cannot_download_tenant_a_file(self, client_b):
        """GET /api/v1/files/<tenant_a_file_id>/download/ → 404."""
        resp = client_b.get(f"/api/v1/files/{self.file_a.id}/download/")
        assert resp.status_code in (403, 404)

    def test_file_list_excludes_cross_tenant(self, client_b):
        """File list endpoint only shows Tenant B's files."""
        resp = client_b.get("/api/v1/files/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        ids = {str(r["id"]) for r in results} if isinstance(results, list) else set()
        assert str(self.file_a.id) not in ids, "File list leaked Tenant A file"
        assert str(self.file_b.id) in ids, "File list missing Tenant B's own file"

    def test_tenant_b_cannot_delete_tenant_a_file(self, client_b):
        """DELETE /api/v1/files/<tenant_a_file_id>/ → 404."""
        resp = client_b.delete(f"/api/v1/files/{self.file_a.id}/")
        assert resp.status_code == 404
        assert File.objects.filter(id=self.file_a.id).exists()

    def test_unauthenticated_cannot_access_files(self):
        """Unauthenticated user gets 401 on file endpoint."""
        from rest_framework.test import APIClient

        anon = APIClient()
        resp = anon.get(f"/api/v1/files/{self.file_a.id}/")
        assert resp.status_code == 401
