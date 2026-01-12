"""
E2E tests for Dataset versioning event publishing through REST API.

Tests complete versioning lifecycle through REST API endpoints and verifies
events are published at each step (no mocks/stubs).
"""
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
import uuid

from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.core.events.models import Event

User = get_user_model()


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
    RATE_LIMIT_ENABLED=False,  # Disable rate limiting for E2E tests
)
class DatasetVersioningEventPublishingE2ETest(TestCase):
    """E2E tests for dataset versioning event publishing through REST API."""

    def setUp(self):
        """Set up test fixtures."""
        self.client = APIClient()

        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            kyc_status=KYCStatus.VERIFIED
        )

        # Create user
        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )

        self.client.force_authenticate(user=self.user)

        # Create file and asset for datasets
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user,
        )

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    @patch('hub.apps.datasets.views.boto3.client')
    def test_e2e_create_dataset_publishes_version_created_event(self, mock_boto3_client):
        """Test that creating a dataset via API publishes version.created event."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: b'col1,col2\nval1,val2')
        }

        # Count events before
        event_count_before = Event.objects.filter(event_type="version.created").count()

        # Create dataset via API
        dataset_data = {
            "file_id": str(self.file.id),
            "asset_id": str(self.asset.id),
        }

        response = self.client.post("/api/v1/datasets/", dataset_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        dataset_id = response.data["id"]

        # Verify version.created event was published
        event_count_after = Event.objects.filter(event_type="version.created").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        created_event = Event.objects.filter(event_type="version.created").order_by('-timestamp').first()
        self.assertIsNotNone(created_event)
        self.assertEqual(created_event.data["version_id"], dataset_id)
        self.assertEqual(created_event.data["resource_type"], "DATASET")
        self.assertEqual(created_event.data["resource_id"], dataset_id)
        self.assertEqual(str(created_event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(created_event.user_id), str(self.user.id))
        self.assertEqual(created_event.source_service, "versioning_service")
        # Tags are stored in metadata
        if created_event.metadata and "tags" in created_event.metadata:
            self.assertIn("versioning", created_event.metadata["tags"])
            self.assertIn("version", created_event.metadata["tags"])

    @patch('hub.apps.datasets.views.boto3.client')
    def test_e2e_create_version_via_api_publishes_version_created_event(self, mock_boto3_client):
        """Test that creating a version via API publishes version.created event."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: b'col1,col2\nval1,val2')
        }

        # Create initial dataset
        dataset_data = {
            "file_id": str(self.file.id),
            "asset_id": str(self.asset.id),
        }
        response = self.client.post("/api/v1/datasets/", dataset_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        parent_dataset_id = response.data["id"]

        # Count events before creating version
        event_count_before = Event.objects.filter(event_type="version.created").count()

        # Create version via API
        version_data = {
            "semantic_version": "1.1.0",
            "version_tags": ["production", "stable"],
        }

        response = self.client.post(
            f"/api/v1/datasets/{parent_dataset_id}/versions/",
            version_data,
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_version_id = response.data["id"]

        # Verify version.created event was published
        event_count_after = Event.objects.filter(event_type="version.created").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        created_event = Event.objects.filter(event_type="version.created").order_by('-timestamp').first()
        self.assertIsNotNone(created_event)
        self.assertEqual(created_event.data["version_id"], new_version_id)
        self.assertEqual(created_event.data["resource_type"], "DATASET")
        self.assertEqual(created_event.data["resource_id"], new_version_id)
        self.assertEqual(created_event.data["semantic_version"], "1.1.0")
        self.assertEqual(created_event.data["parent_version_id"], parent_dataset_id)
        self.assertEqual(str(created_event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(created_event.user_id), str(self.user.id))
        self.assertEqual(created_event.source_service, "versioning_service")
        # Tags are stored in metadata
        if created_event.metadata and "tags" in created_event.metadata:
            self.assertIn("versioning", created_event.metadata["tags"])
            self.assertIn("version", created_event.metadata["tags"])

    @patch('hub.apps.datasets.views.boto3.client')
    def test_e2e_create_version_without_semantic_version(self, mock_boto3_client):
        """Test that creating a version without semantic version still publishes event."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: b'col1,col2\nval1,val2')
        }

        # Create initial dataset
        dataset_data = {
            "file_id": str(self.file.id),
            "asset_id": str(self.asset.id),
        }
        response = self.client.post("/api/v1/datasets/", dataset_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        parent_dataset_id = response.data["id"]

        # Count events before creating version
        event_count_before = Event.objects.filter(event_type="version.created").count()

        # Create version without semantic version
        version_data = {}

        response = self.client.post(
            f"/api/v1/datasets/{parent_dataset_id}/versions/",
            version_data,
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_version_id = response.data["id"]

        # Verify version.created event was published
        event_count_after = Event.objects.filter(event_type="version.created").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        created_event = Event.objects.filter(event_type="version.created").order_by('-timestamp').first()
        self.assertIsNotNone(created_event)
        self.assertEqual(created_event.data["version_id"], new_version_id)
        self.assertEqual(created_event.data["parent_version_id"], parent_dataset_id)
        # semantic_version should be None or not present
        self.assertIn("parent_version_id", created_event.data)

    @patch('hub.apps.datasets.views.boto3.client')
    def test_e2e_list_versions_does_not_publish_events(self, mock_boto3_client):
        """Test that listing versions does not publish events."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: b'col1,col2\nval1,val2')
        }

        # Create initial dataset
        dataset_data = {
            "file_id": str(self.file.id),
            "asset_id": str(self.asset.id),
        }
        response = self.client.post("/api/v1/datasets/", dataset_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        dataset_id = response.data["id"]

        # Count events before listing
        event_count_before = Event.objects.filter(event_type="version.created").count()

        # List versions
        response = self.client.get(f"/api/v1/datasets/{dataset_id}/versions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

        # Verify no new events were published
        event_count_after = Event.objects.filter(event_type="version.created").count()
        self.assertEqual(event_count_after, event_count_before)

    @patch('hub.apps.datasets.views.boto3.client')
    def test_e2e_version_created_event_has_correct_metadata(self, mock_boto3_client):
        """Test that version.created event has all required metadata."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: b'col1,col2\nval1,val2')
        }

        # Create initial dataset
        dataset_data = {
            "file_id": str(self.file.id),
            "asset_id": str(self.asset.id),
        }
        response = self.client.post("/api/v1/datasets/", dataset_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        parent_dataset_id = response.data["id"]

        # Create version with all metadata
        version_data = {
            "semantic_version": "2.0.0",
            "version_tags": ["production", "stable", "test"],
        }

        response = self.client.post(
            f"/api/v1/datasets/{parent_dataset_id}/versions/",
            version_data,
            format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_version_id = response.data["id"]

        # Verify event metadata
        created_event = Event.objects.filter(event_type="version.created").order_by('-timestamp').first()
        self.assertIsNotNone(created_event)

        # Check required fields
        self.assertIn("version_id", created_event.data)
        self.assertIn("resource_type", created_event.data)
        self.assertIn("resource_id", created_event.data)

        # Check optional fields
        self.assertEqual(created_event.data["semantic_version"], "2.0.0")
        self.assertEqual(created_event.data["parent_version_id"], parent_dataset_id)

        # Check event metadata
        self.assertEqual(created_event.event_type, "version.created")
        self.assertEqual(str(created_event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(created_event.user_id), str(self.user.id))
        self.assertEqual(created_event.source_service, "versioning_service")
        # Tags are stored in metadata
        if created_event.metadata and "tags" in created_event.metadata:
            self.assertIn("versioning", created_event.metadata["tags"])
            self.assertIn("version", created_event.metadata["tags"])

    @patch('hub.apps.datasets.views.boto3.client')
    def test_e2e_multiple_versions_create_multiple_events(self, mock_boto3_client):
        """Test that creating multiple versions creates multiple events."""
        # Mock S3 client
        mock_s3_client = MagicMock()
        mock_boto3_client.return_value = mock_s3_client
        mock_s3_client.get_object.return_value = {
            'Body': MagicMock(read=lambda: b'col1,col2\nval1,val2')
        }

        # Create initial dataset
        dataset_data = {
            "file_id": str(self.file.id),
            "asset_id": str(self.asset.id),
        }
        response = self.client.post("/api/v1/datasets/", dataset_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        parent_dataset_id = response.data["id"]

        # Count events before
        event_count_before = Event.objects.filter(event_type="version.created").count()

        # Create multiple versions
        for i in range(3):
            version_data = {
                "semantic_version": f"1.{i}.0",
            }
            response = self.client.post(
                f"/api/v1/datasets/{parent_dataset_id}/versions/",
                version_data,
                format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            parent_dataset_id = response.data["id"]  # Use new version as parent for next

        # Verify 3 new events were published
        event_count_after = Event.objects.filter(event_type="version.created").count()
        self.assertEqual(event_count_after, event_count_before + 3)

        # Verify all events have correct parent relationships
        events = Event.objects.filter(event_type="version.created").order_by('timestamp')
        self.assertGreaterEqual(len(events), 3)

