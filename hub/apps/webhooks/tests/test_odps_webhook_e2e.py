"""
End-to-end tests for ODPS webhook delivery.

Tests the complete flow from ODPS contract operations to webhook delivery.
"""

import json
import uuid
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.webhooks.models import (
    Webhook,
    WebhookDelivery,
    WebhookEventType,
    WebhookStatus,
    DeliveryStatus,
)
from hub.apps.contracts.services import ContractService
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat, NormalizationStatus
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ODPSWebhookE2ETest(TestCase):
    """End-to-end tests for ODPS webhook delivery"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )

        # Create contract service
        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
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

    @patch('hub.apps.webhooks.service.requests.post')
    def test_odps_contract_creation_triggers_webhook_e2e(self, mock_post):
        """E2E test: Creating an ODPS contract triggers webhook delivery"""
        # Create webhook subscribed to ODPS created events
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Created Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Create unique asset for this test
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

        # Auto-generate ODPS from ODCS (this should publish odps.created event)
        odps_contract = self.contract_service.auto_generate_odps_for_odcs(
            odcs_contract_id=str(odcs_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            target_odps_version="4.1"
        )

        # Manually trigger webhook delivery for the published event
        # In production, this would be handled by the event subscriber
        from hub.apps.webhooks.odps_event_subscriber import get_odps_event_subscriber
        subscriber = get_odps_event_subscriber()

        # Simulate the event that would be published
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
            }
        }

        subscriber._handle_odps_event(event)

        # Verify webhook was triggered
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertGreaterEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.event_type, "odps.created")
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)
        self.assertIsNotNone(delivery.delivered_at)

        # Verify payload contains correct data
        payload = delivery.payload
        self.assertEqual(payload["event_type"], "odps.created")
        self.assertEqual(payload["resource_type"], "ODPS")
        self.assertEqual(payload["resource_id"], str(odps_contract.id))
        self.assertEqual(payload["data"]["contract_id"], str(odps_contract.id))

    @patch('hub.apps.webhooks.service.requests.post')
    def test_odps_contract_linking_triggers_webhook_e2e(self, mock_post):
        """E2E test: Linking ODPS to ODCS triggers webhook delivery"""
        # Create webhook subscribed to ODPS linked events
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Linked Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_LINKED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Create unique asset for this test
        asset = self._create_unique_asset("linking")

        # Create ODCS contract with hub_contract_json
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

        # Create ODPS contract with proper schema (details must be object keyed by language code)
        # Include product.contract.spec with ODCS contract for linking
        odcs_contract_data = json.loads(odcs_contract.original_raw) if odcs_contract.original_raw else {}
        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-odps",
                        "name": "Test ODPS"
                    }
                },
                "contract": {
                    "spec": odcs_contract_data  # Required for linking
                }
            }
        })

        # Link ODPS to ODCS (this should publish odps.linked event)
        linked_odps_contract = self.contract_service.link_odps_to_odcs(
            odcs_contract_id=str(odcs_contract.id),
            odps_raw=odps_raw,
            odps_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            resolve_external_refs=False
        )

        # Manually trigger webhook delivery for the published event
        from hub.apps.webhooks.odps_event_subscriber import get_odps_event_subscriber
        subscriber = get_odps_event_subscriber()

        # Simulate the odps.linked event that would be published
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
            }
        }

        subscriber._handle_odps_event(event)

        # Verify webhook was triggered
        deliveries = WebhookDelivery.objects.filter(webhook=webhook)
        self.assertGreaterEqual(deliveries.count(), 1)

        delivery = deliveries.first()
        self.assertEqual(delivery.event_type, "odps.linked")
        self.assertEqual(delivery.status, DeliveryStatus.SUCCESS)

        # Verify payload contains correct data
        payload = delivery.payload
        self.assertEqual(payload["data"]["odps_contract_id"], str(linked_odps_contract.id))
        self.assertEqual(payload["data"]["odcs_contract_id"], str(odcs_contract.id))

    @patch('hub.apps.webhooks.service.requests.post')
    def test_multiple_odps_events_trigger_multiple_webhooks_e2e(self, mock_post):
        """E2E test: Multiple ODPS events trigger multiple webhook deliveries"""
        # Create webhooks for different ODPS events
        created_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Created Webhook",
            url="https://example.com/created",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_CREATED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        linked_webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="ODPS Linked Webhook",
            url="https://example.com/linked",
            secret="test-secret",
            event_types=[WebhookEventType.ODPS_LINKED],
            status=WebhookStatus.ACTIVE,
            created_by=self.user,
        )

        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_post.return_value = mock_response

        # Create unique asset for this test
        asset = self._create_unique_asset("multiple")

        # Create ODCS contract with hub_contract_json
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

        # Auto-generate ODPS (triggers odps.created)
        odps_contract = self.contract_service.auto_generate_odps_for_odcs(
            odcs_contract_id=str(odcs_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            target_odps_version="4.1"
        )

        # Manually trigger webhook delivery for odps.created event
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
            }
        }

        subscriber._handle_odps_event(created_event)

        # Verify created webhook was triggered
        created_deliveries = WebhookDelivery.objects.filter(webhook=created_webhook)
        self.assertGreaterEqual(created_deliveries.count(), 1)

        # Verify linked webhook was not triggered yet
        linked_deliveries = WebhookDelivery.objects.filter(webhook=linked_webhook)
        self.assertEqual(linked_deliveries.count(), 0)

        # Now simulate linking (triggers odps.linked)
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
            }
        }

        subscriber._handle_odps_event(linked_event)

        # Verify linked webhook was triggered
        linked_deliveries = WebhookDelivery.objects.filter(webhook=linked_webhook)
        self.assertGreaterEqual(linked_deliveries.count(), 1)

        # Verify both webhooks have deliveries
        self.assertGreaterEqual(created_deliveries.count(), 1)
        self.assertGreaterEqual(linked_deliveries.count(), 1)

