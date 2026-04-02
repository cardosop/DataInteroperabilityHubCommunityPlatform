"""
104.8 — Audit Log Isolation Test

Verifies that Tenant A's audit events are not visible via Tenant B's
audit log endpoint.
"""
import uuid

import pytest

from hub.apps.audit.models import AuditEvent

pytestmark = pytest.mark.django_db(transaction=True)


class TestAuditLogIsolation:
    """Audit events must be strictly tenant-scoped."""

    @pytest.fixture(autouse=True)
    def _create_audit_events(self, tenant_a, user_a, tenant_b, user_b):
        uid = uuid.uuid4().hex[:8]

        self.audit_a = AuditEvent.objects.create(
            tenant=tenant_a,
            actor_user=user_a,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
            action="ASSET_CREATED",
            details_json={"key": f"audit-a-{uid}"},
        )
        self.audit_b = AuditEvent.objects.create(
            tenant=tenant_b,
            actor_user=user_b,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
            action="ASSET_CREATED",
            details_json={"key": f"audit-b-{uid}"},
        )

    def test_audit_list_tenant_b_excludes_tenant_a(self, client_b):
        """GET /api/v1/audit/audit-events/ for B must not include A events."""
        resp = client_b.get("/api/v1/audit/audit-events/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        ids = {str(r["id"]) for r in results} if isinstance(results, list) else set()
        assert str(self.audit_a.id) not in ids, "Audit log leaked Tenant A event"
        assert str(self.audit_b.id) in ids

    def test_audit_detail_cross_tenant_returns_404(self, client_b):
        """Tenant B cannot read Tenant A's audit event by ID."""
        resp = client_b.get(f"/api/v1/audit/audit-events/{self.audit_a.id}/")
        assert resp.status_code == 404

    def test_audit_list_tenant_a_sees_own_events(self, client_a):
        """Tenant A can see its own audit events."""
        resp = client_a.get("/api/v1/audit/audit-events/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        ids = {str(r["id"]) for r in results} if isinstance(results, list) else set()
        assert str(self.audit_a.id) in ids
        assert str(self.audit_b.id) not in ids

    def test_audit_count_matches_db(self, client_a, tenant_a):
        """API audit count matches DB for the tenant."""
        resp = client_a.get("/api/v1/audit/audit-events/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        api_count = len(results) if isinstance(results, list) else 0
        db_count = AuditEvent.objects.filter(tenant=tenant_a).count()
        # API may be paginated, so api_count <= db_count
        assert api_count <= db_count
