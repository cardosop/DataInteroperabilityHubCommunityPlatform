"""
104.9 — Webhook Isolation Test

Verifies that webhooks subscribed by Tenant A are not visible to or
manageable by Tenant B.
"""
import uuid

import pytest

from hub.apps.webhooks.models import Webhook

pytestmark = pytest.mark.django_db(transaction=True)


class TestWebhookIsolation:
    """Webhook CRUD must be tenant-scoped."""

    @pytest.fixture(autouse=True)
    def _create_webhooks(self, tenant_a, user_a, tenant_b, user_b):
        uid = uuid.uuid4().hex[:8]
        self.webhook_a = Webhook.objects.create(
            tenant=tenant_a,
            name=f"Webhook A {uid}",
            url=f"https://hooks-a-{uid}.example.com/cb",
            secret=f"secret-a-{uid}",
            event_types=["asset.created", "contract.updated"],
            status="ACTIVE",
            created_by=user_a,
        )
        self.webhook_b = Webhook.objects.create(
            tenant=tenant_b,
            name=f"Webhook B {uid}",
            url=f"https://hooks-b-{uid}.example.com/cb",
            secret=f"secret-b-{uid}",
            event_types=["asset.created"],
            status="ACTIVE",
            created_by=user_b,
        )

    def test_webhook_list_tenant_b_excludes_tenant_a(self, client_b):
        """GET /api/v1/webhooks/ for B must not include A webhooks."""
        resp = client_b.get("/api/v1/webhooks/")
        assert resp.status_code == 200
        results = resp.data.get("results", resp.data)
        ids = {str(r["id"]) for r in results} if isinstance(results, list) else set()
        assert str(self.webhook_a.id) not in ids, (
            "Webhook list leaked Tenant A's webhook to Tenant B"
        )

    def test_webhook_detail_cross_tenant_returns_404(self, client_b):
        """Tenant B cannot read Tenant A's webhook by ID."""
        resp = client_b.get(f"/api/v1/webhooks/{self.webhook_a.id}/")
        assert resp.status_code == 404

    def test_tenant_b_cannot_update_tenant_a_webhook(self, client_b):
        """Tenant B cannot PATCH Tenant A's webhook."""
        resp = client_b.patch(
            f"/api/v1/webhooks/{self.webhook_a.id}/",
            {"url": "https://evil.example.com/steal"},
            format="json",
        )
        assert resp.status_code == 404
        self.webhook_a.refresh_from_db()
        assert "evil" not in self.webhook_a.url

    def test_tenant_b_cannot_delete_tenant_a_webhook(self, client_b):
        """Tenant B cannot DELETE Tenant A's webhook."""
        resp = client_b.delete(
            f"/api/v1/webhooks/{self.webhook_a.id}/"
        )
        assert resp.status_code == 404
        assert Webhook.objects.filter(id=self.webhook_a.id).exists()

    def test_webhook_db_scoping(self, tenant_a, tenant_b):
        """ORM confirms webhooks are tenant-scoped."""
        a_ids = set(
            str(w.id) for w in Webhook.objects.filter(tenant=tenant_a)
        )
        b_ids = set(
            str(w.id) for w in Webhook.objects.filter(tenant=tenant_b)
        )
        assert a_ids.isdisjoint(b_ids)
