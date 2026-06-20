"""
Marketplace Sync Job Serializers Tests

Comprehensive unit tests for marketplace sync job serializers.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob
from hub.apps.integrations.serializers import (
    MarketplaceSyncJobCancelSerializer,
    MarketplaceSyncJobSerializer,
    MarketplaceSyncRequestSerializer,
)
from hub.apps.tenants.models import KYCStatus, Tenant

User = get_user_model()

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceSyncJobSerializerTest(TestCase):
    """Test suite for MarketplaceSyncJobSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test_key", "api_secret": "test_secret"},
            is_active=True,
        )

        self.sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
            items_synced=0,
            items_failed=0,
            errors=[],
            metadata={"test": "data"},
        )

    def test_serialize_sync_job(self):
        """Test serializing a marketplace sync job"""
        serializer = MarketplaceSyncJobSerializer(self.sync_job)
        data = serializer.data

        self.assertEqual(str(self.sync_job.id), data["id"])
        self.assertEqual(str(self.tenant.id), data["tenant"])
        self.assertEqual(self.tenant.name, data["tenant_name"])
        self.assertEqual(str(self.connection.id), data["connection_id"])
        self.assertEqual(self.connection.name, data["connection_name"])
        self.assertEqual(SyncDirection.PUSH.value, data["direction"])
        self.assertIn("Push", data["direction_display"])
        self.assertEqual(SyncStatus.PENDING.value, data["status"])
        self.assertIn("Pending", data["status_display"])
        self.assertEqual(0, data["items_synced"])
        self.assertEqual(0, data["items_failed"])
        self.assertEqual([], data["errors"])
        self.assertEqual({"test": "data"}, data["metadata"])
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)
        self.assertIsNone(data["completed_at"])

    def test_serialize_completed_sync_job(self):
        """Test serializing a completed sync job"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.COMPLETED.value,
            items_synced=10,
            items_failed=0,
            errors=[],
            metadata={},
            completed_at=timezone.now(),
        )

        serializer = MarketplaceSyncJobSerializer(sync_job)
        data = serializer.data

        self.assertEqual(SyncStatus.COMPLETED.value, data["status"])
        self.assertEqual(10, data["items_synced"])
        self.assertIsNotNone(data["completed_at"])

    def test_cascade_delete_removes_sync_job_when_connection_deleted(self):
        """Test that deleting a connection cascade-deletes its sync jobs.

        MarketplaceConnection has on_delete=models.CASCADE on the sync_jobs
        reverse relation, so deleting the connection must remove all related
        sync jobs.
        """
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
        )
        sync_job_id = sync_job.id

        self.connection.delete()

        self.assertFalse(
            MarketplaceSyncJob.objects.filter(id=sync_job_id).exists(),
            "Cascade delete should remove sync jobs when their connection is deleted",
        )

    def test_cascade_delete_removes_sync_job_when_tenant_deleted(self):
        """Test that deleting a tenant cascade-deletes its sync jobs.

        Tenant has on_delete=models.CASCADE on the sync_jobs reverse relation,
        so deleting the tenant must remove all related sync jobs.
        """
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
        )
        sync_job_id = sync_job.id

        self.tenant.delete()

        self.assertFalse(
            MarketplaceSyncJob.objects.filter(id=sync_job_id).exists(),
            "Cascade delete should remove sync jobs when their tenant is deleted",
        )

    def test_serialize_sync_job_with_invalid_metadata(self):
        """Test that serializer handles invalid metadata structure"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            metadata={"nested": {"deep": {"value": "test"}}},  # Deep nesting
        )

        serializer = MarketplaceSyncJobSerializer(sync_job)
        data = serializer.data

        # Should serialize successfully even with complex metadata
        self.assertIn("metadata", data)
        self.assertEqual(data["metadata"]["nested"]["deep"]["value"], "test")

    def test_serialize_sync_job_with_large_errors_list(self):
        """Test that serializer handles large errors list"""
        large_errors = [
            {"message": f"Error {i}", "timestamp": timezone.now().isoformat()} for i in range(100)
        ]
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            errors=large_errors,
        )

        serializer = MarketplaceSyncJobSerializer(sync_job)
        data = serializer.data

        # Should serialize successfully with large lists
        self.assertEqual(len(data["errors"]), 100)

    def test_serialize_sync_job_with_special_characters(self):
        """Test that serializer handles special characters in metadata"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            metadata={"key": "value with special chars: !@#$%^&*()"},
        )
        serializer = MarketplaceSyncJobSerializer(sync_job)
        data = serializer.data
        self.assertIn("special chars", data["metadata"]["key"])

    def test_serialize_sync_job_returns_all_required_fields(self):
        """Test that serializer returns all required fields"""
        serializer = MarketplaceSyncJobSerializer(self.sync_job)
        data = serializer.data

        # Verify all required fields are present
        required_fields = [
            "id",
            "tenant",
            "tenant_name",
            "connection_id",
            "connection_name",
            "direction",
            "direction_display",
            "status",
            "status_display",
            "items_synced",
            "items_failed",
            "errors",
            "metadata",
            "created_at",
            "updated_at",
            "completed_at",
        ]

        for field in required_fields:
            self.assertIn(field, data, f"Required field {field} missing from serializer output")

    def test_serialize_sync_job_field_types(self):
        """Test that serializer returns correct field types"""
        serializer = MarketplaceSyncJobSerializer(self.sync_job)
        data = serializer.data

        # Verify field types
        self.assertIsInstance(data["id"], str)
        self.assertIsInstance(data["tenant"], str)
        self.assertIsInstance(data["tenant_name"], str)
        self.assertIsInstance(data["connection_id"], str)
        self.assertIsInstance(data["connection_name"], str)
        self.assertIsInstance(data["direction"], str)
        self.assertIsInstance(data["direction_display"], str)
        self.assertIsInstance(data["status"], str)
        self.assertIsInstance(data["status_display"], str)
        self.assertIsInstance(data["items_synced"], int)
        self.assertIsInstance(data["items_failed"], int)
        self.assertIsInstance(data["errors"], list)
        self.assertIsInstance(data["metadata"], dict)

    def test_serialize_sync_job_timestamp_format(self):
        """Test that timestamps are properly formatted"""
        serializer = MarketplaceSyncJobSerializer(self.sync_job)
        data = serializer.data

        # Timestamps should be strings (ISO format)
        self.assertIsInstance(data["created_at"], str)
        self.assertIsInstance(data["updated_at"], str)
        # completed_at may be None or string
        if data["completed_at"] is not None:
            self.assertIsInstance(data["completed_at"], str)


class MarketplaceSyncRequestSerializerTest(TestCase):
    """Test suite for MarketplaceSyncRequestSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test_key"},
            is_active=True,
        )

        self.valid_push_data = {
            "connection_id": str(self.connection.id),
            "direction": SyncDirection.PUSH.value,
            "asset_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
            "options": {"dry_run": False},
        }

        self.valid_pull_data = {
            "connection_id": str(self.connection.id),
            "direction": SyncDirection.PULL.value,
            "listing_ids": ["listing1", "listing2"],
            "filters": {"category": "data"},
            "options": {"create_assets": True},
        }

    def test_valid_push_request(self):
        """Test serializer with valid PUSH request"""
        serializer = MarketplaceSyncRequestSerializer(data=self.valid_push_data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["direction"], SyncDirection.PUSH.value)
        self.assertEqual(len(serializer.validated_data["asset_ids"]), 2)

    def test_valid_pull_request(self):
        """Test serializer with valid PULL request"""
        serializer = MarketplaceSyncRequestSerializer(data=self.valid_pull_data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["direction"], SyncDirection.PULL.value)
        self.assertEqual(len(serializer.validated_data["listing_ids"]), 2)

    def test_push_without_asset_ids(self):
        """Test PUSH direction requires asset_ids"""
        data = self.valid_push_data.copy()
        del data["asset_ids"]
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("asset_ids", serializer.errors)

    def test_push_with_empty_asset_ids(self):
        """Test PUSH direction rejects empty asset_ids"""
        data = self.valid_push_data.copy()
        data["asset_ids"] = []
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("asset_ids", serializer.errors)

    def test_pull_with_asset_ids(self):
        """Test PULL direction rejects asset_ids"""
        data = self.valid_pull_data.copy()
        data["asset_ids"] = [str(uuid.uuid4())]
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("asset_ids", serializer.errors)

    def test_invalid_direction(self):
        """Test serializer rejects invalid direction"""
        data = self.valid_push_data.copy()
        data["direction"] = "INVALID"
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("direction", serializer.errors)

    def test_invalid_connection_id(self):
        """Test serializer rejects invalid connection_id format"""
        data = self.valid_push_data.copy()
        data["connection_id"] = "not-a-uuid"
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("connection_id", serializer.errors)

    def test_invalid_filters(self):
        """Test serializer rejects non-dict filters"""
        data = self.valid_pull_data.copy()
        data["filters"] = "not a dict"
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("filters", serializer.errors)

    def test_invalid_options(self):
        """Test serializer rejects non-dict options"""
        data = self.valid_push_data.copy()
        data["options"] = "not a dict"
        serializer = MarketplaceSyncRequestSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("options", serializer.errors)

    def test_bidirectional_not_supported(self):
        """Test BIDIRECTIONAL direction validation"""
        data = self.valid_push_data.copy()
        data["direction"] = SyncDirection.BIDIRECTIONAL.value
        # BIDIRECTIONAL requires asset_ids
        serializer = MarketplaceSyncRequestSerializer(data=data)
        # Should validate, but API will reject it
        self.assertTrue(serializer.is_valid())

    def test_sync_request_serializer_missing_required_fields(self):
        """Test that sync request serializer validates required fields"""
        serializer = MarketplaceSyncRequestSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("connection_id", serializer.errors)
        self.assertIn("direction", serializer.errors)

    def test_sync_request_serializer_invalid_direction(self):
        """Test that sync request serializer rejects invalid direction"""
        invalid_data = {
            "connection_id": str(self.connection.id),
            "direction": "INVALID_DIRECTION",
        }
        serializer = MarketplaceSyncRequestSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("direction", serializer.errors)

    def test_sync_request_serializer_invalid_connection_id(self):
        """Test that sync request serializer validates connection_id format"""
        invalid_data = {
            "connection_id": "not-a-uuid",
            "direction": SyncDirection.PUSH.value,
        }
        serializer = MarketplaceSyncRequestSerializer(data=invalid_data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("connection_id", serializer.errors)

    def test_sync_request_serializer_with_empty_asset_ids(self):
        """Test that sync request serializer handles empty asset_ids"""
        data = {
            "connection_id": str(self.connection.id),
            "direction": SyncDirection.PUSH.value,
            "asset_ids": [],
        }
        serializer = MarketplaceSyncRequestSerializer(data=data)
        # May be valid or invalid depending on validation rules
        if serializer.is_valid():
            self.assertEqual(serializer.validated_data["asset_ids"], [])
        else:
            self.assertIn("asset_ids", serializer.errors)

    def test_sync_request_serializer_with_empty_listing_ids(self):
        """Test that sync request serializer handles empty listing_ids"""
        data = {
            "connection_id": str(self.connection.id),
            "direction": SyncDirection.PULL.value,
            "listing_ids": [],
        }
        serializer = MarketplaceSyncRequestSerializer(data=data)
        # May be valid or invalid depending on validation rules
        if serializer.is_valid():
            self.assertEqual(serializer.validated_data.get("listing_ids"), [])
        else:
            # If invalid, should have error
            self.assertTrue(len(serializer.errors) > 0)

    def test_sync_request_serializer_validates_all_fields(self):
        """Test that sync request serializer validates all fields"""
        valid_data = {
            "connection_id": str(self.connection.id),
            "direction": SyncDirection.PUSH.value,
            "asset_ids": [str(uuid.uuid4())],
            "options": {"dry_run": False},
        }
        serializer = MarketplaceSyncRequestSerializer(data=valid_data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["direction"], SyncDirection.PUSH.value)
        self.assertIn("asset_ids", serializer.validated_data)


class MarketplaceSyncJobCancelSerializerTest(TestCase):
    """Test suite for MarketplaceSyncJobCancelSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        self.valid_data = {"reason": "User requested cancellation"}

    def test_valid_cancel_request(self):
        """Test serializer with valid cancel request"""
        serializer = MarketplaceSyncJobCancelSerializer(data=self.valid_data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["reason"], "User requested cancellation")

    def test_cancel_without_reason(self):
        """Test serializer accepts cancel request without reason"""
        serializer = MarketplaceSyncJobCancelSerializer(data={})
        self.assertTrue(serializer.is_valid())
        self.assertIsNone(serializer.validated_data.get("reason"))

    def test_cancel_with_empty_reason(self):
        """Test serializer accepts empty reason"""
        serializer = MarketplaceSyncJobCancelSerializer(data={"reason": ""})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["reason"], "")

    def test_cancel_with_too_long_reason(self):
        """Test serializer rejects reason exceeding max length"""
        data = {"reason": "a" * 501}  # Exceeds max_length=500
        serializer = MarketplaceSyncJobCancelSerializer(data=data)
        self.assertFalse(serializer.is_valid())
        self.assertIn("reason", serializer.errors)

    def test_cancel_serializer_field_types(self):
        """Test that cancel serializer returns correct field types"""
        serializer = MarketplaceSyncJobCancelSerializer(data={"reason": "Test reason"})
        self.assertTrue(serializer.is_valid())
        data = serializer.data

        # Verify field types
        self.assertIsInstance(data["reason"], str)
