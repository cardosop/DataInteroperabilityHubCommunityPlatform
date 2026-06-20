"""
End-to-end tests for ODPS webhook delivery.

Tests the complete flow from ODPS contract operations to webhook delivery.
Uses real TestWebhookServer (no mocks).
Uses wait_until for delivery state (no fixed time.sleep) per FIX_PLAN_FLAKY_TESTS_5_6_2.
"""

import json
import uuid

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.django_db(transaction=True)]
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import (
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.services import ContractService
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus
from hub.apps.webhooks.models import (
    DeliveryStatus,
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
)
from hub.apps.webhooks.tests.test_odps_webhook_integration import TestWebhookServer
from tests.utils.polling import wait_until


User = get_user_model()


class ODPSWebhookE2ETest(TransactionTestCase):
    """End-to-end tests for ODPS webhook delivery"""

    reset_sequences = False
    serialized_rollback = False

    def _fixture_teardown(self):
        """Skip TRUNCATE CASCADE to avoid timeout."""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )

        # Create contract service
        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def _create_unique_asset(self, name_suffix: str = "") -> Asset:
        """Create a unique asset for each test to avoid duplicate key violations"""
        return Asset.objects.create(
            tenant=self.tenant,
            name=f"Test Asset {name_suffix}",
            domain="test",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def test_odps_contract_creation_triggers_webhook_e2e(self):
        """E2E test: Creating an ODPS contract triggers webhook delivery (real server)."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Created Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            asset = self._create_unique_asset("creation")

            # Create ODCS contract with hub_contract_json (required for ODPS generation)
            # Use factory to ensure proper setup
            odcs_contract = ContractFactoryEnhanced.create_contract(
                tenant=self.tenant,
                created_by=self.user,
                asset=asset,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.2",
                original_format=OriginalFormat.JSON,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                status=ContractStatus.DRAFT,
                name="Test ODCS Contract",
            )

            odps_contract = self.contract_service.auto_generate_odps_for_odcs(
                odcs_contract_id=str(odcs_contract.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                target_odps_version="4.1",
            )

            from hub.apps.webhooks.odps_event_subscriber import get_odps_event_subscriber

            subscriber = get_odps_event_subscriber()

            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "odps.created",
                "data": {
                    "contract_id": str(odps_contract.id),
                    "asset_id": str(asset.id) if asset else None,
                    "status": str(odps_contract.status),
                    "odps_version": "4.1",
                    "original_format": str(odps_contract.original_format),
                },
                "source": {
                    "service": "contract_service",
                    "tenant_id": str(self.tenant.id),
                    "user_id": str(self.user.id),
                },
            }

            subscriber._handle_odps_event(event)

            def has_success_delivery():
                d = WebhookDelivery.objects.filter(webhook=webhook).first()
                return d is not None and d.status == DeliveryStatus.SUCCESS

            wait_until(
                has_success_delivery, timeout=5.0, message="ODPS created delivery not SUCCESS"
            )
            deliveries = WebhookDelivery.objects.filter(webhook=webhook)
            self.assertEqual(deliveries.count(), 1,
                             f"Expected exactly 1 delivery, got {deliveries.count()}")

            delivery = deliveries.first()
            self.assertEqual(delivery.event_type, "odps.created")
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
            self.assertIsNotNone(delivery.delivered_at)

            payload = delivery.payload
            self.assertEqual(payload["event_type"], "odps.created")
            self.assertEqual(payload["resource_type"], "ODPS")
            self.assertEqual(payload["resource_id"], str(odps_contract.id))
            self.assertEqual(payload["data"]["contract_id"], str(odps_contract.id))

            requests_received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(requests_received), 1,
                            f"Expected exactly 1 received request, got {len(requests_received)}")

    def test_odps_contract_linking_triggers_webhook_e2e(self):
        """E2E test: Linking ODPS to ODCS triggers webhook delivery (real server)."""
        with TestWebhookServer(response_status=200) as server:
            webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Linked Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_LINKED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            asset = self._create_unique_asset("linking")

            odcs_contract = ContractFactoryEnhanced.create_contract(
                tenant=self.tenant,
                created_by=self.user,
                asset=asset,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.2",
                original_format=OriginalFormat.JSON,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                status=ContractStatus.DRAFT,
                name="Test ODCS Contract",
            )

            odcs_contract_data = (
                json.loads(odcs_contract.original_raw) if odcs_contract.original_raw else {}
            )
            odps_raw = json.dumps(
                {
                    "schema": "https://opendataproducts.org/schema/v4.1",
                    "version": "4.1",
                    "product": {
                        "details": {"en": {"productID": "test-odps", "name": "Test ODPS"}},
                        "contract": {"spec": odcs_contract_data},
                    },
                }
            )

            linked_odps_contract = self.contract_service.link_odps_to_odcs(
                odcs_contract_id=str(odcs_contract.id),
                odps_raw=odps_raw,
                odps_format="JSON",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                resolve_external_refs=False,
            )

            from hub.apps.webhooks.odps_event_subscriber import get_odps_event_subscriber

            subscriber = get_odps_event_subscriber()

            event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "odps.linked",
                "data": {
                    "odps_contract_id": str(linked_odps_contract.id),
                    "odcs_contract_id": str(odcs_contract.id),
                    "link_type": "bidirectional",
                },
                "source": {
                    "service": "contract_service",
                    "tenant_id": str(self.tenant.id),
                    "user_id": str(self.user.id),
                },
            }

            subscriber._handle_odps_event(event)

            def has_linked_delivery():
                d = WebhookDelivery.objects.filter(webhook=webhook).first()
                return d is not None and d.status == DeliveryStatus.SUCCESS

            wait_until(has_linked_delivery, timeout=5.0, message="ODPS linked delivery not SUCCESS")
            deliveries = WebhookDelivery.objects.filter(webhook=webhook)
            self.assertEqual(deliveries.count(), 1,
                             f"Expected exactly 1 delivery, got {deliveries.count()}")

            delivery = deliveries.first()
            self.assertEqual(delivery.event_type, "odps.linked")
            self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)

            payload = delivery.payload
            self.assertEqual(payload["data"]["odps_contract_id"], str(linked_odps_contract.id))
            self.assertEqual(payload["data"]["odcs_contract_id"], str(odcs_contract.id))

            requests_received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(requests_received), 1,
                            f"Expected exactly 1 received request, got {len(requests_received)}")

    def test_multiple_odps_events_trigger_multiple_webhooks_e2e(self):
        """E2E test: Multiple ODPS events trigger multiple webhook deliveries (real server)."""
        with TestWebhookServer(response_status=200) as server:
            created_webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Created Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_CREATED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            linked_webhook = Webhook.objects.create(
                tenant=self.tenant,
                name="ODPS Linked Webhook",
                url=server.get_url(),
                secret="test-secret",
                event_types=[WebhookEventType.ODPS_LINKED],
                status=WebhookStatus.ACTIVE,
                created_by=self.user,
            )

            asset = self._create_unique_asset("multiple")

            odcs_contract = ContractFactoryEnhanced.create_contract(
                tenant=self.tenant,
                created_by=self.user,
                asset=asset,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.2",
                original_format=OriginalFormat.JSON,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
                status=ContractStatus.DRAFT,
                name="Test ODCS Contract",
            )

            odps_contract = self.contract_service.auto_generate_odps_for_odcs(
                odcs_contract_id=str(odcs_contract.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                target_odps_version="4.1",
            )

            from hub.apps.webhooks.odps_event_subscriber import get_odps_event_subscriber

            subscriber = get_odps_event_subscriber()

            created_event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "odps.created",
                "data": {
                    "contract_id": str(odps_contract.id),
                    "asset_id": str(odps_contract.asset.id) if odps_contract.asset else None,
                    "status": str(odps_contract.status),
                    "odps_version": "4.1",
                    "original_format": str(odps_contract.original_format),
                },
                "source": {
                    "service": "contract_service",
                    "tenant_id": str(self.tenant.id),
                    "user_id": str(self.user.id),
                },
            }

            subscriber._handle_odps_event(created_event)

            def has_created_delivery():
                return WebhookDelivery.objects.filter(webhook=created_webhook).count() >= 1

            wait_until(
                has_created_delivery, timeout=5.0, message="Created webhook delivery not recorded"
            )
            created_deliveries = WebhookDelivery.objects.filter(webhook=created_webhook)
            self.assertEqual(created_deliveries.count(), 1,
                             f"Expected exactly 1 created delivery, got {created_deliveries.count()}")

            linked_deliveries = WebhookDelivery.objects.filter(webhook=linked_webhook)
            self.assertEqual(linked_deliveries.count(), 0)

            linked_event = {
                "event_id": str(uuid.uuid4()),
                "event_type": "odps.linked",
                "data": {
                    "odps_contract_id": str(odps_contract.id),
                    "odcs_contract_id": str(odcs_contract.id),
                    "link_type": "bidirectional",
                },
                "source": {
                    "service": "contract_service",
                    "tenant_id": str(self.tenant.id),
                    "user_id": str(self.user.id),
                },
            }

            subscriber._handle_odps_event(linked_event)

            def has_linked_delivery_count():
                return WebhookDelivery.objects.filter(webhook=linked_webhook).count() >= 1

            wait_until(
                has_linked_delivery_count,
                timeout=5.0,
                message="Linked webhook delivery not recorded",
            )
            linked_deliveries = WebhookDelivery.objects.filter(webhook=linked_webhook)
            self.assertEqual(linked_deliveries.count(), 1,
                             f"Expected exactly 1 linked delivery, got {linked_deliveries.count()}")

            requests_received = server.get_received_requests(timeout=2.0)
            self.assertEqual(len(requests_received), 2,
                            f"Expected exactly 2 received requests, got {len(requests_received)}")
