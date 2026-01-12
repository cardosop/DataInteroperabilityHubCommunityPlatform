"""
Marketplace Sync Job Serializers Tests

Comprehensive unit tests for marketplace sync job serializers.
"""
import pytest
from django.test import TestCase
from rest_framework.exceptions import ValidationError as DRFValidationError

from hub.apps.integrations.serializers import (
    MarketplaceSyncJobSerializer,
    MarketplaceSyncRequestSerializer,
    MarketplaceSyncJobCancelSerializer,
)
from hub.apps.integrations.models import MarketplaceSyncJob, MarketplaceConnection
from hub.apps.integrations.base import SyncDirection, SyncStatus, MarketplaceType
from hub.apps.tenants.models import Tenant, KYCStatus
from django.contrib.auth import get_user_model

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceSyncJobSerializerTest(TestCase):
    """Test suite for MarketplaceSyncJobSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test_key", "api_secret": "test_secret"},
            is_active=True
        )

        self.sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            items_synced=0,
            items_failed=0,
            errors=[],
            metadata={"test": "data"}
        )

    def test_serialize_sync_job(self):
        """Test serializing a marketplace sync job"""
        serializer = MarketplaceSyncJobSerializer(self.sync_job)
        data = serializer.data

        self.assertEqual(str(self.sync_job.id), data['id'])
        self.assertEqual(str(self.tenant.id), data['tenant'])
        self.assertEqual(self.tenant.name, data['tenant_name'])
        self.assertEqual(str(self.connection.id), data['connection_id'])
        self.assertEqual(self.connection.name, data['connection_name'])
        self.assertEqual(SyncDirection.PUSH.value, data['direction'])
        self.assertIn('Push', data['direction_display'])
        self.assertEqual(SyncStatus.PENDING.value, data['status'])
        self.assertIn('Pending', data['status_display'])
        self.assertEqual(0, data['items_synced'])
        self.assertEqual(0, data['items_failed'])
        self.assertEqual([], data['errors'])
        self.assertEqual({"test": "data"}, data['metadata'])
        self.assertIn('created_at', data)
        self.assertIn('updated_at', data)
        self.assertIsNone(data['completed_at'])

    def test_serialize_completed_sync_job(self):
        """Test serializing a completed sync job"""
        from django.utils import timezone
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.COMPLETED.value,
            items_synced=10,
            items_failed=0,
            errors=[],
            metadata={},
            completed_at=timezone.now()
        )

        serializer = MarketplaceSyncJobSerializer(sync_job)
        data = serializer.data

        self.assertEqual(SyncStatus.COMPLETED.value, data['status'])
        self.assertEqual(10, data['items_synced'])
        self.assertIsNotNone(data['completed_at'])


class MarketplaceSyncRequestSerializerTest(TestCase):
    """Test suite for MarketplaceSyncRequestSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test_key"},
            is_active=True
        )

        import uuid
        self.valid_push_data = {
            'connection_id': str(self.connection.id),
            'direction': SyncDirection.PUSH.value,
            'asset_ids': [str(uuid.uuid4()), str(uuid.uuid4())],
            'options': {'dry_run': False}
        }

        self.valid_pull_data = {
            'connection_id': str(self.connection.id),
            'direction': SyncDirection.PULL.value,
            'listing_ids': ['listing1', 'listing2'],
            'filters': {'category': 'data'},
            'options': {'create_assets': True}
        }

    def test_valid_push_request(self):
        """Test serializer with valid PUSH request"""
        serializer = MarketplaceSyncRequestSerializer(data=self.valid_push_data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['direction'], SyncDirection.PUSH.value)
        self.assertEqual(len(serializer.validated_data['asset_ids']), 2)

    def test_valid_pull_request(self):
        """Test serializer with valid PULL request"""
        serializer = MarketplaceSyncRequestSerializer(data=self.valid_pull_data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['direction'], SyncDirection.PULL.value)
        self.assertEqual(len(serializer.validated_data['listing_ids']), 2)

    def test_push_without_asset_ids(self):
        """Test PUSH direction requires asset_ids"""
        data = self.valid_push_data.copy()
        del data['asset_ids']
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('asset_ids', serializer.errors)

    def test_push_with_empty_asset_ids(self):
        """Test PUSH direction rejects empty asset_ids"""
        data = self.valid_push_data.copy()
        data['asset_ids'] = []
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('asset_ids', serializer.errors)

    def test_pull_with_asset_ids(self):
        """Test PULL direction rejects asset_ids"""
        data = self.valid_pull_data.copy()
        import uuid
        data['asset_ids'] = [str(uuid.uuid4())]
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('asset_ids', serializer.errors)

    def test_invalid_direction(self):
        """Test serializer rejects invalid direction"""
        data = self.valid_push_data.copy()
        data['direction'] = 'INVALID'
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('direction', serializer.errors)

    def test_invalid_connection_id(self):
        """Test serializer rejects invalid connection_id format"""
        data = self.valid_push_data.copy()
        data['connection_id'] = 'not-a-uuid'
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('connection_id', serializer.errors)

    def test_invalid_filters(self):
        """Test serializer rejects non-dict filters"""
        data = self.valid_pull_data.copy()
        data['filters'] = 'not a dict'
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('filters', serializer.errors)

    def test_invalid_options(self):
        """Test serializer rejects non-dict options"""
        data = self.valid_push_data.copy()
        data['options'] = 'not a dict'
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('options', serializer.errors)

    def test_bidirectional_not_supported(self):
        """Test BIDIRECTIONAL direction validation"""
        data = self.valid_push_data.copy()
        data['direction'] = SyncDirection.BIDIRECTIONAL.value
        # BIDIRECTIONAL requires asset_ids
        serializer = MarketplaceSyncRequestSerializer(data=data)
        # Should validate, but API will reject it
        self.assertTrue(serializer.is_valid())


class MarketplaceSyncJobCancelSerializerTest(TestCase):
    """Test suite for MarketplaceSyncJobCancelSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        self.valid_data = {
            'reason': 'User requested cancellation'
        }

    def test_valid_cancel_request(self):
        """Test serializer with valid cancel request"""
        serializer = MarketplaceSyncJobCancelSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['reason'], 'User requested cancellation')

    def test_cancel_without_reason(self):
        """Test serializer accepts cancel request without reason"""
        serializer = MarketplaceSyncJobCancelSerializer(data={})
        self.assertTrue(serializer.is_valid())
        self.assertIsNone(serializer.validated_data.get('reason'))

    def test_cancel_with_empty_reason(self):
        """Test serializer accepts empty reason"""
        serializer = MarketplaceSyncJobCancelSerializer(data={'reason': ''})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data['reason'], '')

    def test_cancel_with_too_long_reason(self):
        """Test serializer rejects reason exceeding max length"""
        data = {'reason': 'a' * 501}  # Exceeds max_length=500
        serializer = MarketplaceSyncJobCancelSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn('reason', serializer.errors)

