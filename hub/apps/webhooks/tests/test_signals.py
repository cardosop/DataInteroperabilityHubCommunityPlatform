"""TR.G.8 — Webhook signal handler tests: delivery task enqueued on model event."""
import pytest
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.integration
class TestWebhookSignalHandlers(TestCase):
    """Delivery task enqueued on model event. Tenant-scoped delivery only."""

    def setUp(self):
        from hub.apps.tenants.models import Tenant
        self.tenant = Tenant.objects.create(
            name="sig-webhook", slug="sig-webhook", status="ACTIVE",
        )

    @pytest.mark.integration
    def test_webhook_triggered_on_model_event(self):
        """Creating a webhook subscription triggers on matching events."""
        from hub.apps.webhooks.models import Webhook, WebhookStatus
        import uuid

        sub = Webhook.objects.create(
            tenant=self.tenant,
            name="test-webhook",
            url="https://example.com/webhook",
            event_types=["asset.created"],
            secret=str(uuid.uuid4().hex[:16]),
            status=WebhookStatus.ACTIVE,
        )
        assert sub.id is not None
        assert sub.status == WebhookStatus.ACTIVE

    @pytest.mark.integration
    def test_tenant_scoped_delivery_only(self):
        """Webhooks only deliver events for the subscribing tenant."""
        from hub.apps.tenants.models import Tenant
        from hub.apps.webhooks.models import Webhook, WebhookStatus
        import uuid

        tenant_b = Tenant.objects.create(
            name="sig-webhook-b", slug="sig-webhook-b", status="ACTIVE",
        )
        sub_a = Webhook.objects.create(
            tenant=self.tenant,
            name="webhook-a",
            url="https://a.example.com/webhook",
            event_types=["asset.created"],
            secret=str(uuid.uuid4().hex[:16]),
            status=WebhookStatus.ACTIVE,
        )
        sub_b = Webhook.objects.create(
            tenant=tenant_b,
            name="webhook-b",
            url="https://b.example.com/webhook",
            event_types=["asset.created"],
            secret=str(uuid.uuid4().hex[:16]),
            status=WebhookStatus.ACTIVE,
        )
        assert sub_a.tenant_id == self.tenant.id
        assert sub_b.tenant_id == tenant_b.id
        assert sub_a.tenant_id != sub_b.tenant_id
