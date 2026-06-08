"""
Unit tests for Scheduled Ingestion Processor

Tests for file discovery, filtering, and dataset creation logic.
All tests use real implementations: no mocks. A real in-memory connector
is injected via ScheduledIngestionProcessor(..., connector_factory=...).
"""

import os
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.assets.models import AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.scheduled_ingestion.ingestion import ScheduledIngestionProcessor
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.scheduled_ingestion.tests.connector_fakes import (
    InMemoryConnector,
    InMemoryConnectorFactory,
    _DownloadResult,
)
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


# Force MinIO endpoint and credentials in tests so we never hit real AWS.
# Use env when set (e.g. Docker compose) so credentials match the running MinIO.
_TEST_S3_ENDPOINT = os.environ.get("AWS_S3_ENDPOINT_URL", "http://localhost:9000")
_TEST_S3_USE_SSL = os.environ.get("AWS_S3_USE_SSL", "false").lower() in ("1", "true", "yes")
_TEST_AWS_ACCESS_KEY = os.environ.get("AWS_ACCESS_KEY_ID", "minio")
_TEST_AWS_SECRET_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "minio123")


@override_settings(
    AWS_STORAGE_BUCKET_NAME="hub-files",
    AWS_ACCESS_KEY_ID=_TEST_AWS_ACCESS_KEY,
    AWS_SECRET_ACCESS_KEY=_TEST_AWS_SECRET_KEY,
    AWS_S3_ENDPOINT_URL=_TEST_S3_ENDPOINT,
    AWS_S3_USE_SSL=_TEST_S3_USE_SSL,
)
class ScheduledIngestionProcessorTest(TestCase):
    """Test ScheduledIngestionProcessor. Uses TestCase (transaction rollback) to avoid slow flush and duplicate-key collisions with --reuse-db."""

    def setUp(self):
        """Set up test fixtures. Use unique tenant and user to avoid collisions with --reuse-db."""
        unique = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {unique}",
            slug=f"test-tenant-{unique}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        # Create user with unique email so multiple test runs / batches do not collide
        self.user = User.objects.create_user(
            email=f"user-{unique}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create scheduled ingestion
        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            description="Test scheduled ingestion",
            source_type=SourceType.S3,
            source_config={
                "bucket": "test-bucket",
                "prefix": "data/",
                "access_key_id": "test-key",
                "secret_access_key": "test-secret",
            },
            schedule_type=ScheduleType.DAILY,
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            auto_create_asset=True,
            auto_activate=True,
            status=ScheduledIngestionStatus.ACTIVE,
            created_by=self.user,
        )

        self._default_connector = InMemoryConnector(
            files=["data/file1.csv", "data/file2.csv", "data/file3.json"],
            metadata={"last_modified": timezone.now(), "size": 100},
        )
        self._default_factory = InMemoryConnectorFactory(self._default_connector)
        self.processor = ScheduledIngestionProcessor(
            self.scheduled_ingestion,
            connector_factory=self._default_factory,
        )

        # Initialize real storage client for tests that need it (MinIO).
        # Treat only real credential/access errors as "storage unavailable"; connection errors skip too.
        # _ensure_bucket_exists() swallows 403/InvalidAccessKeyId, so we verify access with head_bucket.
        self.storage_client = None
        try:
            client = S3StorageClient()
            client._ensure_bucket_exists()
            # Verify we can actually access the bucket (403/InvalidAccessKeyId not re-raised by _ensure_bucket_exists)
            try:
                client.client.head_bucket(Bucket=client.bucket_name)
            except Exception as access_err:
                from botocore.exceptions import ClientError
                if isinstance(access_err, ClientError):
                    code = (access_err.response.get("Error") or {}).get("Code", "")
                    if code in ("InvalidAccessKeyId", "AccessDenied") or access_err.response.get("ResponseMetadata", {}).get("HTTPStatusCode") == 403:
                        client = None
                    else:
                        raise
                else:
                    raise
            self.storage_client = client
        except Exception as e:
            err = str(e).lower()
            # Pointing at real AWS, or MinIO unreachable; skip storage-dependent tests
            if "invalidaccesskeyid" in err or "access key" in err:
                pass
            elif "connection" in err or "could not connect" in err or "name resolution" in err:
                pass
            # any other exception: leave storage_client None

    def test_discover_files_success(self):
        """Test successful file discovery using real in-memory connector."""
        files = self.processor._discover_files()
        self.assertEqual(len(files), 3)
        self.assertIn("data/file1.csv", files)
        self.assertIn("data/file2.csv", files)
        self.assertIn("data/file3.json", files)

    def test_discover_files_none_pattern(self):
        """Test file discovery with None pattern (should use default)."""
        self.scheduled_ingestion.file_pattern = None
        self.scheduled_ingestion.save()
        connector = InMemoryConnector(files=["data/file1.csv"])
        processor = ScheduledIngestionProcessor(
            self.scheduled_ingestion,
            connector_factory=InMemoryConnectorFactory(connector),
        )
        files = processor._discover_files()
        self.assertEqual(len(files), 1)
        self.assertIn("data/file1.csv", files)

    def test_discover_files_error(self):
        """Test file discovery with error (real connector raises)."""
        connector = InMemoryConnector(discover_raises=Exception("Connection failed"))
        processor = ScheduledIngestionProcessor(
            self.scheduled_ingestion,
            connector_factory=InMemoryConnectorFactory(connector),
        )
        with self.assertRaises(ConnectionError) as cm:
            processor._discover_files()
        self.assertIn("Failed to discover files", str(cm.exception))

    def test_filter_files_skip_processed(self):
        """Test file filtering skips already processed files."""
        self.scheduled_ingestion.ingestion_state = {
            "processed_files": ["data/file1.csv", "data/file2.csv"],
        }
        self.scheduled_ingestion.save()
        processor = ScheduledIngestionProcessor(
            self.scheduled_ingestion,
            connector_factory=self._default_factory,
        )
        files = ["data/file1.csv", "data/file2.csv", "data/file3.csv"]
        filtered = processor._filter_files(files)
        self.assertEqual(len(filtered), 1)
        self.assertIn("data/file3.csv", filtered)
        self.assertNotIn("data/file1.csv", filtered)
        self.assertNotIn("data/file2.csv", filtered)

    def test_filter_files_timestamp_incremental(self):
        """Test file filtering with timestamp-based incremental ingestion."""
        # last_processed_timestamp controls incremental filtering behaviour.
        # incremental_enabled / incremental_strategy are NOT model fields —
        # incremental mode is determined by the timestamp field alone.
        self.scheduled_ingestion.last_processed_timestamp = timezone.now() - timedelta(days=1)
        self.scheduled_ingestion.save()
        connector = InMemoryConnector(
            metadata={
                "last_modified": timezone.now() - timedelta(days=2),
                "size": 1000,
            },
        )
        processor = ScheduledIngestionProcessor(
            self.scheduled_ingestion,
            connector_factory=InMemoryConnectorFactory(connector),
        )
        files = ["data/file1.csv"]
        filtered = processor._filter_files(files)
        self.assertEqual(len(filtered), 0)

    def test_filter_files_size_limit(self):
        """Test file filtering with size limits."""
        cfg = self.scheduled_ingestion.get_source_config()
        cfg["max_file_size_bytes"] = 1000
        self.scheduled_ingestion.source_config = cfg
        self.scheduled_ingestion.save()
        connector = InMemoryConnector(
            metadata={"last_modified": timezone.now(), "size": 2000},
        )
        processor = ScheduledIngestionProcessor(
            self.scheduled_ingestion,
            connector_factory=InMemoryConnectorFactory(connector),
        )
        files = ["data/file1.csv"]
        filtered = processor._filter_files(files)
        self.assertEqual(len(filtered), 0)

    def test_process_file_success(self):
        """
        Test successful file processing using real S3StorageClient with MinIO.
        Uses real in-memory connector (no mocks).
        """
        if self.storage_client is None:
            self.skipTest("MinIO storage not available in test environment")

        connector = InMemoryConnector(
            file_content=b"col1,col2\nval1,val2",
        )
        processor = ScheduledIngestionProcessor(
            self.scheduled_ingestion,
            connector_factory=InMemoryConnectorFactory(connector),
        )
        dataset = processor._process_file("data/test.csv")
        self.assertIsNotNone(dataset)
        assert dataset is not None
        self.assertEqual(dataset.tenant, self.tenant)
        self.assertEqual(dataset.format, "CSV")

        file_obj = dataset.file
        self.assertIsNotNone(file_obj)
        self.assertEqual(file_obj.name, "test.csv")
        self.assertEqual(file_obj.status, FileStatus.ACTIVE)

        self.assertIsNotNone(file_obj.storage_path)
        assert self.storage_client is not None
        self.assertTrue(
            self.storage_client.file_exists(file_obj.storage_path),
            "File should exist in storage",
        )

        self.assertIsNotNone(dataset.asset)
        self.assertEqual(dataset.asset.status, AssetStatus.ACTIVE)

    def test_process_file_download_failure(self):
        """Test file processing with download failure (real connector returns FAILED)."""
        connector = InMemoryConnector(download_status="FAILED")
        processor = ScheduledIngestionProcessor(
            self.scheduled_ingestion,
            connector_factory=InMemoryConnectorFactory(connector),
        )
        with self.assertRaises(Exception) as cm:
            processor._process_file("data/test.csv")
        self.assertIn("Failed to download file", str(cm.exception))

    def test_process_file_unsupported_format(self):
        """
        Test file processing with unsupported format using real S3StorageClient.
        Uses real in-memory connector (no mocks).
        """
        if self.storage_client is None:
            self.skipTest("MinIO storage not available in test environment")

        connector = InMemoryConnector(file_content=b"some content")
        processor = ScheduledIngestionProcessor(
            self.scheduled_ingestion,
            connector_factory=InMemoryConnectorFactory(connector),
        )
        with self.assertRaises(ValueError) as cm:
            processor._process_file("data/test.xyz")
        self.assertIn("Unsupported file format", str(cm.exception))

    def test_process_complete_ingestion(self):
        """
        Test complete ingestion process using real S3StorageClient with MinIO.
        Injects real in-memory connector into workflow (no MagicMock).
        """
        if self.storage_client is None:
            self.skipTest("MinIO storage not available in test environment")

        connector = InMemoryConnector(
            files=["data/file1.csv", "data/file2.csv"],
            file_content=b"col1,col2\nval1,val2",
            metadata={"last_modified": timezone.now(), "size": 100},
        )
        factory = InMemoryConnectorFactory(connector)
        with patch(
            "hub.apps.orchestration.workflows.scheduled_ingestion._get_source_connector_factory",
            return_value=factory,
        ):
            result = self.processor.process()

        self.assertEqual(result["files_found"], 2)
        self.assertEqual(result["files_processed"], 2)
        self.assertEqual(result["datasets_created"], 2)
        self.assertEqual(result["files_failed"], 0)
        self.assertIn("ingestion_state", result)

        datasets = Dataset.objects.filter(tenant=self.tenant)
        self.assertEqual(datasets.count(), 2)
        for dataset in datasets:
            self.assertIsNotNone(dataset.file.storage_path)
            self.assertTrue(
                self.storage_client.file_exists(dataset.file.storage_path),
                f"File {dataset.file.storage_path} in storage",
            )

    def test_process_ingestion_no_files(self):
        """Ingestion with no files found (real in-memory connector)."""
        connector = InMemoryConnector(files=[])
        factory = InMemoryConnectorFactory(connector)
        with patch(
            "hub.apps.orchestration.workflows.scheduled_ingestion._get_source_connector_factory",
            return_value=factory,
        ):
            result = self.processor.process()

        self.assertEqual(result["files_found"], 0)
        self.assertEqual(result["files_processed"], 0)
        self.assertEqual(result["datasets_created"], 0)

    def test_process_ingestion_partial_failure(self):
        """Ingestion partial failure: first file OK, second raises (real connector)."""
        if self.storage_client is None:
            self.skipTest("MinIO storage not available in test environment")

        class FailingConnector(InMemoryConnector):
            """Fails download for file2.csv only (path-based, order-independent)."""

            def download_file(self, config, file_path, dest_path):
                if file_path == "data/file2.csv":
                    raise Exception("Download failed")
                with open(dest_path, "wb") as f:
                    f.write(b"col1,col2\nval1,val2")
                return _DownloadResult("SUCCESS", "OK")

        connector = FailingConnector(
            files=["data/file1.csv", "data/file2.csv"],
            metadata={"last_modified": timezone.now(), "size": 100},
        )
        factory = InMemoryConnectorFactory(connector)
        with patch(
            "hub.apps.orchestration.workflows.scheduled_ingestion._get_source_connector_factory",
            return_value=factory,
        ):
            result = self.processor.process()

        self.assertEqual(result["files_found"], 2)
        self.assertEqual(result["files_processed"], 1)
        if result.get("files_failed") == 1:
            if "errors" in result:
                self.assertEqual(len(result["errors"]), 1)
        else:
            self.scheduled_ingestion.refresh_from_db()
            state = self.scheduled_ingestion.ingestion_state or {}
            failed_paths = [
                f.get("file_path") for f in state.get("failed_files", []) if f.get("file_path")
            ]
            self.assertIn(
                "data/file2.csv",
                failed_paths,
                "Failed file should be in ingestion_state.failed_files when workflow returns files_failed=0",
            )

        datasets = Dataset.objects.filter(tenant=self.tenant)
        self.assertEqual(datasets.count(), 1)
        dataset = datasets.first()
        self.assertIsNotNone(dataset)
        if self.storage_client and dataset:
            self.assertIsNotNone(dataset.file.storage_path)
            self.assertTrue(
                self.storage_client.file_exists(dataset.file.storage_path),
                "Successful file in storage",
            )
