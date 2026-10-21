"""TDD pins for the Databricks DLT update-failed webhook (openspec
add-databricks-dlt-pipelines task 10.6) — the
``databricks.dlt.update.failed`` event type registration + the
best-effort notify seam the terminal transition calls on a FAILED
update (design D6: the webhook fires on terminal failures; a delivery
outage NEVER blocks the terminal transition).

No mocks: the enum pins are pure; the delivery pins use a REAL Webhook
row + a real threaded HTTP server + the production delivery service
(the mesh-delivery convention, synchronous via
``WEBHOOK_ASYNC_DELIVERY=False``) and ``wait_until`` for the delivery
state (the FIX_PLAN_FLAKY_TESTS_5_6_2 discipline — no fixed sleeps).
"""

import uuid

import pytest
from django.test import TestCase, override_settings

from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User
from hub.apps.webhooks.models import DeliveryStatus, Webhook, WebhookDelivery, WebhookStatus
from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer
from tests.utils.polling import wait_until

pytestmark = pytest.mark.django_db(transaction=True)


class TestDatabricksDltUpdateFailedEventType(TestCase):
    """The event type is registered in the canonical enum."""

    def test_the_event_type_is_registered(self):
        from hub.apps.webhooks.models import WebhookEventType

        assert WebhookEventType.DATABRICKS_DLT_UPDATE_FAILED == "databricks.dlt.update.failed"
        assert "databricks.dlt.update.failed" in [choice[0] for choice in WebhookEventType.choices]

    def test_get_databricks_event_types_lists_it(self):
        from hub.apps.webhooks.models import WebhookEventType

        event_types = WebhookEventType.get_databricks_event_types()
        assert WebhookEventType.DATABRICKS_DLT_UPDATE_FAILED in event_types
        assert WebhookEventType.DATABRICKS_JOB_RUN_FAILED in event_types


@override_settings(WEBHOOK_ASYNC_DELIVERY=False)
class TestDltUpdateFailedWebhookDelivery(TestCase):
    """The notify seam triggers deliveries for subscribed webhooks."""

    reset_sequences = False
    serialized_rollback = False

    def _fixture_teardown(self):
        pass

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"DLT Webhook Tenant {uid}",
            slug=f"dlt-webhook-{uid}",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"dlt-wh-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

    def _make_webhook(self, event_types, url):
        return Webhook.objects.create(
            tenant=self.tenant,
            name="DLT Webhook",
            url=url,
            secret="test-secret-key",
            event_types=event_types,
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

    def test_a_subscribed_webhook_receives_the_update_failed_delivery(self):
        try:
            from hub.apps.databricks_admin.dlt_webhooks import notify_dlt_update_failed
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

        with TestWebhookServer(response_status=200) as server:
            webhook = self._make_webhook(["databricks.dlt.update.failed"], server.get_url())
            update_id = str(uuid.uuid4())
            notify_dlt_update_failed(
                tenant_id=str(self.tenant.id),
                workspace_id=str(uuid.uuid4()),
                pipeline_id="dlp-1",
                update_id=update_id,
                state="FAILED",
                error_message="cluster lost",
            )
            wait_until(
                lambda: (
                    WebhookDelivery.objects.filter(
                        webhook=webhook, event_type="databricks.dlt.update.failed"
                    ).count()
                    >= 1
                ),
                timeout=5.0,
                message="databricks.dlt.update.failed delivery not recorded",
            )
            deliveries = WebhookDelivery.objects.filter(
                webhook=webhook, event_type="databricks.dlt.update.failed"
            )
            assert deliveries.count() == 1
            assert deliveries.first().status == DeliveryStatus.SUCCESS
            # The delivery envelope carries the event type + resource
            # id, and the reported failure attribution inside ``data``
            # (the delivery service's payload contract).
            payload = deliveries.first().payload or {}
            assert payload.get("event_type") == "databricks.dlt.update.failed"
            assert payload.get("resource_id") == update_id
            data = payload.get("data") or {}
            assert data.get("pipeline_id") == "dlp-1"
            assert data.get("update_id") == update_id
            assert data.get("state") == "FAILED"
            assert data.get("error_message") == "cluster lost"

    def test_an_unsubscribed_webhook_gets_zero_deliveries(self):
        try:
            from hub.apps.databricks_admin.dlt_webhooks import notify_dlt_update_failed
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

        with TestWebhookServer(response_status=200) as server:
            webhook = self._make_webhook(["asset.created"], server.get_url())
            notify_dlt_update_failed(
                tenant_id=str(self.tenant.id),
                workspace_id=str(uuid.uuid4()),
                pipeline_id="dlp-1",
                update_id=str(uuid.uuid4()),
                state="FAILED",
                error_message="boom",
            )
            wait_until(
                lambda: (
                    WebhookDelivery.objects.filter(
                        webhook=webhook, event_type="databricks.dlt.update.failed"
                    ).count()
                    == 0
                ),
                timeout=2.0,
                message="delivery must not exist for an unsubscribed webhook",
            )
            assert not WebhookDelivery.objects.filter(webhook=webhook).exists()

    def test_the_notify_seam_is_best_effort_never_blocks(self):
        # D6: a delivery failure must NEVER block the terminal
        # transition — a malformed tenant id (a real caller bug) makes
        # the delivery service raise a real DB-layer error; the seam
        # swallows it and reports zero triggered, never a raise.
        try:
            from hub.apps.databricks_admin.dlt_webhooks import notify_dlt_update_failed
        except (RuntimeError, ModuleNotFoundError):
            pytest.skip("hub.apps.apps (paid layer not installed in core-only mode)")

        result = notify_dlt_update_failed(
            tenant_id="not-a-uuid",
            workspace_id=str(uuid.uuid4()),
            pipeline_id="dlp-1",
            update_id=str(uuid.uuid4()),
            state="FAILED",
            error_message="cluster lost",
        )
        assert result == 0, "the seam swallows delivery failures and reports zero triggered"
