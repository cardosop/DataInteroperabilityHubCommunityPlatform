"""
E2E tests for FileViewSet event publishing.

Tests complete file lifecycle through REST API endpoints and verifies
events are published at each step (no mocks/stubs).
Uses real S3StorageClient with graceful handling when storage unavailable.
"""

import hashlib

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.django_db]
from django.core.files.base import ContentFile
from django.test import TestCase, override_settings
from rest_framework import status

from hub.apps.core.events.models import Event
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tests.test_base import FilesAPITestBase


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,
    RATE_LIMIT_ENABLED=False,
    # Event lifecycle here is not testing async malware scan; avoid PENDING_SCAN on download.
    CLAMAV_ENABLED=False,
)
class FileViewsEventPublishingE2ETest(FilesAPITestBase):
    """E2E tests for file event publishing through REST API."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.storage_available = False
        try:
            self.storage_client = S3StorageClient()
            self.storage_client._ensure_bucket_exists()
            self.storage_available = True
        except Exception:
            self.storage_available = False

    def test_e2e_file_lifecycle_events(self):
        """Test complete file lifecycle and verify all events are published."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # Step 1: Initialize file upload (should publish file.created)
        test_content = b"test content"
        init_data = {
            "name": "test_file.csv",
            "content_type": "text/csv",
            "size": len(test_content),
            "upload_method": "browser",
        }

        event_count_before = Event.objects.filter(event_type="file.created").count()
        response = self.client.post("/api/v1/files/init/", init_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        file_id = response.data["file_id"]

        # Verify file.created event was published
        event_count_after = Event.objects.filter(event_type="file.created").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        created_event = (
            Event.objects.filter(event_type="file.created").order_by("-timestamp").first()
        )
        self.assertIsNotNone(created_event)
        self.assertEqual(created_event.data["file_id"], file_id)
        self.assertEqual(created_event.data["name"], "test_file.csv")
        self.assertEqual(created_event.data["content_type"], "text/csv")
        self.assertEqual(created_event.data["size"], len(test_content))
        self.assertEqual(str(created_event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(created_event.user_id), str(self.user.id))

        # Step 2: Upload file content to storage
        file_obj = File.objects.get(id=file_id)
        self.storage_client.save_file(
            tenant_id=str(self.tenant.id),
            file_id=str(file_obj.id),
            file_content=ContentFile(test_content),
            file_name=file_obj.name,
        )

        # Step 3: Complete file upload (should publish file.uploaded and file.updated)
        sha256_hash = hashlib.sha256(test_content).hexdigest()

        complete_data = {"content_sha256": sha256_hash}

        uploaded_count_before = Event.objects.filter(event_type="file.uploaded").count()
        updated_count_before = Event.objects.filter(event_type="file.updated").count()

        response = self.client.post(
            f"/api/v1/files/{file_id}/complete/", complete_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify file.uploaded event was published
        uploaded_count_after = Event.objects.filter(event_type="file.uploaded").count()
        self.assertEqual(uploaded_count_after, uploaded_count_before + 1)

        uploaded_event = (
            Event.objects.filter(event_type="file.uploaded").order_by("-timestamp").first()
        )
        self.assertIsNotNone(uploaded_event)
        self.assertEqual(uploaded_event.data["file_id"], file_id)
        self.assertEqual(uploaded_event.data["file_size"], len(test_content))
        self.assertEqual(uploaded_event.data["content_type"], "text/csv")
        self.assertEqual(uploaded_event.data["content_sha256"], sha256_hash)

        # Verify file.updated event was published (status change)
        updated_count_after = Event.objects.filter(event_type="file.updated").count()
        self.assertEqual(updated_count_after, updated_count_before + 1)

        updated_event = (
            Event.objects.filter(event_type="file.updated").order_by("-timestamp").first()
        )
        self.assertIsNotNone(updated_event)
        self.assertEqual(updated_event.data["file_id"], file_id)
        self.assertIn("status", updated_event.data["changes"])
        self.assertEqual(updated_event.data["new_status"], FileStatus.COMPLETED.value)

        # Step 4: Get download URL (should publish file.downloaded)
        downloaded_count_before = Event.objects.filter(event_type="file.downloaded").count()
        response = self.client.get(f"/api/v1/files/{file_id}/download/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("download_url", response.data)

        # Verify file.downloaded event was published
        downloaded_count_after = Event.objects.filter(event_type="file.downloaded").count()
        self.assertEqual(downloaded_count_after, downloaded_count_before + 1)

        downloaded_event = (
            Event.objects.filter(event_type="file.downloaded").order_by("-timestamp").first()
        )
        self.assertIsNotNone(downloaded_event)
        self.assertEqual(downloaded_event.data["file_id"], file_id)
        self.assertEqual(downloaded_event.data["download_size"], len(test_content))
        self.assertIsNotNone(downloaded_event.data.get("download_duration_ms"))

        # Step 5: Delete file (should publish file.deleted)
        deleted_count_before = Event.objects.filter(event_type="file.deleted").count()
        response = self.client.delete(f"/api/v1/files/{file_id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify file.deleted event was published
        deleted_count_after = Event.objects.filter(event_type="file.deleted").count()
        self.assertEqual(deleted_count_after, deleted_count_before + 1)

        deleted_event = (
            Event.objects.filter(event_type="file.deleted").order_by("-timestamp").first()
        )
        self.assertIsNotNone(deleted_event)
        self.assertEqual(deleted_event.data["file_id"], file_id)
        self.assertEqual(deleted_event.data["reason"], "User requested deletion")
        self.assertIn("deleted_at", deleted_event.data)

    def test_e2e_file_upload_init_publishes_created_event(self):
        """Test that file upload initialization publishes file.created event."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        data = {
            "name": "new_file.json",
            "content_type": "application/json",
            "size": 2048,
            "upload_method": "sdk",
        }

        event_count_before = Event.objects.filter(event_type="file.created").count()
        response = self.client.post("/api/v1/files/init/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify event was published
        event_count_after = Event.objects.filter(event_type="file.created").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        event = Event.objects.filter(event_type="file.created").order_by("-timestamp").first()
        self.assertEqual(event.data["name"], "new_file.json")
        self.assertEqual(event.data["content_type"], "application/json")
        self.assertEqual(event.data["size"], 2048)
        self.assertEqual(event.data["status"], FileStatus.PENDING.value)

    def test_e2e_file_upload_complete_publishes_uploaded_event(self):
        """Test that file upload completion publishes file.uploaded event."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        test_content = b"test"
        # Declared size must match stored object bytes or complete returns 400.
        init_data = {
            "name": "complete_test.csv",
            "content_type": "text/csv",
            "size": len(test_content),
            "upload_method": "browser",
        }
        response = self.client.post("/api/v1/files/init/", init_data, format="json")
        file_id = response.data["file_id"]

        # Upload file content to storage
        file_obj = File.objects.get(id=file_id)
        self.storage_client.save_file(
            tenant_id=str(self.tenant.id),
            file_id=str(file_obj.id),
            file_content=ContentFile(test_content),
            file_name=file_obj.name,
        )

        # Complete upload
        sha256_hash = hashlib.sha256(test_content).hexdigest()
        complete_data = {"content_sha256": sha256_hash}

        event_count_before = Event.objects.filter(event_type="file.uploaded").count()
        response = self.client.post(
            f"/api/v1/files/{file_id}/complete/", complete_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Verify file.uploaded event was published
        event_count_after = Event.objects.filter(event_type="file.uploaded").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        event = Event.objects.filter(event_type="file.uploaded").order_by("-timestamp").first()
        self.assertEqual(event.data["file_id"], file_id)
        self.assertEqual(event.data["file_size"], len(test_content))
        self.assertEqual(event.data["content_sha256"], sha256_hash)

    def test_e2e_file_download_publishes_downloaded_event(self):
        """Test that file download publishes file.downloaded event."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # Create active file
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="download_test.csv",
            content_type="text/csv",
            size=2048,
            storage_path=f"{self.tenant.id}/download_test.csv",
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            created_by=self.user,
        )

        event_count_before = Event.objects.filter(event_type="file.downloaded").count()
        response = self.client.get(f"/api/v1/files/{file_obj.id}/download/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("download_url", response.data)

        # Verify file.downloaded event was published
        event_count_after = Event.objects.filter(event_type="file.downloaded").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        event = Event.objects.filter(event_type="file.downloaded").order_by("-timestamp").first()
        self.assertEqual(event.data["file_id"], str(file_obj.id))
        self.assertEqual(event.data["download_size"], 2048)
        self.assertIsNotNone(event.data.get("download_duration_ms"))

    def test_e2e_file_delete_publishes_deleted_event(self):
        """Test that file deletion publishes file.deleted event."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # Create active file
        file_obj = File.objects.create(
            tenant=self.tenant,
            name="delete_test.csv",
            content_type="text/csv",
            size=1024,
            storage_path=f"{self.tenant.id}/delete_test.csv",
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            created_by=self.user,
        )

        event_count_before = Event.objects.filter(event_type="file.deleted").count()
        response = self.client.delete(f"/api/v1/files/{file_obj.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify file.deleted event was published
        event_count_after = Event.objects.filter(event_type="file.deleted").count()
        self.assertEqual(event_count_after, event_count_before + 1)

        event = Event.objects.filter(event_type="file.deleted").order_by("-timestamp").first()
        self.assertEqual(event.data["file_id"], str(file_obj.id))
        self.assertEqual(event.data["reason"], "User requested deletion")
        self.assertIn("deleted_at", event.data)

        # Verify file was soft deleted
        file_obj.refresh_from_db()
        self.assertEqual(file_obj.status, FileStatus.DELETED)

    def test_e2e_multipart_upload_events(self):
        """Test that multipart upload publishes correct events.

        Performs a real multipart upload with a single 5 MiB part so
        that the complete endpoint succeeds and we can assert events
        unconditionally.
        """
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        # Use a size > 100 MB to trigger multipart path in init_upload view
        declared_size = 150 * 1024 * 1024  # 150 MB
        init_data = {
            "name": "large_file.csv",
            "content_type": "text/csv",
            "size": declared_size,
            "upload_method": "sdk",
        }

        created_count_before = Event.objects.filter(event_type="file.created").count()
        response = self.client.post("/api/v1/files/init/", init_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        file_id = response.data["file_id"]
        self.assertTrue(response.data["requires_multipart"])

        # Verify file.created event was published
        created_count_after = Event.objects.filter(event_type="file.created").count()
        self.assertEqual(created_count_after, created_count_before + 1)

        # Upload a real part (5 MiB minimum for S3 multipart)
        file_obj = File.objects.get(id=file_id)
        part_data = b"x" * (5 * 1024 * 1024)
        upload_id = file_obj.metadata_json["multipart_upload_id"]

        s3 = self.storage_client.client
        part_resp = s3.upload_part(
            Bucket=self.storage_client.bucket_name,
            Key=file_obj.storage_path,
            UploadId=upload_id,
            PartNumber=1,
            Body=part_data,
        )
        real_etag = part_resp["ETag"]

        # Fix declared size to match actual upload so complete succeeds
        file_obj.size = len(part_data)
        file_obj.save(update_fields=["size"])

        sha256_hash = hashlib.sha256(part_data).hexdigest()
        complete_data = {
            "content_sha256": sha256_hash,
            "parts": [{"ETag": real_etag, "PartNumber": 1}],
        }

        uploaded_count_before = Event.objects.filter(event_type="file.uploaded").count()
        response = self.client.post(
            f"/api/v1/files/{file_id}/complete/", complete_data, format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Expected 200 but got {response.status_code}: {getattr(response, 'data', '')}",
        )

        uploaded_count_after = Event.objects.filter(event_type="file.uploaded").count()
        self.assertEqual(uploaded_count_after, uploaded_count_before + 1)

    def test_e2e_events_include_correct_tenant_and_user(self):
        """Test that all events include correct tenant_id and user_id."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        test_content = b"test"
        init_data = {
            "name": "tenant_test.csv",
            "content_type": "text/csv",
            "size": len(test_content),
            "upload_method": "browser",
        }
        init_response = self.client.post("/api/v1/files/init/", init_data, format="json")
        self.assertEqual(init_response.status_code, status.HTTP_201_CREATED)
        file_id = init_response.data["file_id"]

        # Upload content
        file_obj = File.objects.get(id=file_id)
        self.storage_client.save_file(
            tenant_id=str(self.tenant.id),
            file_id=str(file_obj.id),
            file_content=ContentFile(test_content),
            file_name=file_obj.name,
        )

        # Complete upload
        sha256_hash = hashlib.sha256(test_content).hexdigest()
        complete_data = {"content_sha256": sha256_hash}
        complete_response = self.client.post(
            f"/api/v1/files/{file_id}/complete/", complete_data, format="json"
        )
        self.assertEqual(complete_response.status_code, status.HTTP_200_OK)

        # Download
        download_response = self.client.get(f"/api/v1/files/{file_id}/download/")
        self.assertEqual(download_response.status_code, status.HTTP_200_OK)

        # Delete
        delete_response = self.client.delete(f"/api/v1/files/{file_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

        # Assert intermediate response status codes
        # (init and complete are already checked above implicitly via file lifecycle)

        # Verify all events have correct tenant and user
        events = Event.objects.filter(data__file_id=file_id).order_by("timestamp")

        # Full lifecycle: file.created, file.uploaded, file.updated, file.downloaded, file.deleted
        # At minimum 4 events (downloaded may also produce an event via get_file)
        self.assertGreaterEqual(
            events.count(),
            4,
            f"Expected at least 4 events for full lifecycle, got {events.count()}: "
            f"{[e.event_type for e in events]}",
        )

        for event in events:
            self.assertEqual(str(event.tenant_id), str(self.tenant.id))
            self.assertEqual(str(event.user_id), str(self.user.id))
