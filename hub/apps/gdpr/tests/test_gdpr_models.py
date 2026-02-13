"""
Comprehensive unit tests for GDPR models.

Tests cover:
- Model creation and validation
- Model relationships
- Model methods (__str__)
- Edge cases
- Error handling
- Database constraints
- Field defaults and choices

All tests use real implementations (no mocks/stubs).
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from hub.apps.gdpr.models import (
    DataExportJob,
    DataExportStatus,
    ErasureRequest,
    ErasureRequestStatus,
)
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DataExportJobModelTest(TestCase):
    """Comprehensive tests for DataExportJob model"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant", status="ACTIVE")

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

    # ========== MODEL CREATION TESTS ==========

    def test_create_data_export_job_success(self):
        """Test successful data export job creation"""
        job = DataExportJob.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=DataExportStatus.PENDING,
        )

        self.assertIsNotNone(job.id)
        self.assertEqual(job.user, self.user)
        self.assertEqual(job.tenant, self.tenant)
        self.assertEqual(job.status, DataExportStatus.PENDING)
        self.assertIsNone(job.storage_path)
        self.assertIsNone(job.download_url)
        self.assertIsNone(job.download_url_expires_at)
        self.assertIsNone(job.error_message)
        self.assertIsNone(job.completed_at)
        self.assertIsNotNone(job.created_at)
        self.assertIsNotNone(job.updated_at)

    def test_create_data_export_job_with_all_fields(self):
        """Test data export job creation with all fields"""
        storage_path = "data-exports/test-tenant/job-id/export.zip"
        download_url = "https://storage.example.com/download/export.zip"
        expires_at = timezone.now() + timezone.timedelta(hours=24)
        completed_at = timezone.now()

        job = DataExportJob.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=DataExportStatus.COMPLETED,
            storage_path=storage_path,
            download_url=download_url,
            download_url_expires_at=expires_at,
            completed_at=completed_at,
        )

        self.assertEqual(job.storage_path, storage_path)
        self.assertEqual(job.download_url, download_url)
        self.assertEqual(job.download_url_expires_at, expires_at)
        self.assertEqual(job.completed_at, completed_at)
        self.assertEqual(job.status, DataExportStatus.COMPLETED)

    def test_create_data_export_job_with_error(self):
        """Test data export job creation with error message"""
        error_message = "Failed to process export: Storage unavailable"

        job = DataExportJob.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=DataExportStatus.FAILED,
            error_message=error_message,
        )

        self.assertEqual(job.status, DataExportStatus.FAILED)
        self.assertEqual(job.error_message, error_message)

    def test_data_export_job_default_status(self):
        """Test that default status is PENDING"""
        job = DataExportJob.objects.create(user=self.user, tenant=self.tenant)

        self.assertEqual(job.status, DataExportStatus.PENDING)

    # ========== MODEL STATUS CHOICES TESTS ==========

    def test_data_export_status_choices(self):
        """Test DataExportStatus choices are valid"""
        self.assertEqual(DataExportStatus.PENDING, "PENDING")
        self.assertEqual(DataExportStatus.PROCESSING, "PROCESSING")
        self.assertEqual(DataExportStatus.COMPLETED, "COMPLETED")
        self.assertEqual(DataExportStatus.FAILED, "FAILED")

    def test_data_export_job_status_choices_validation(self):
        """Test that only valid status choices are accepted"""
        # Valid status
        job = DataExportJob.objects.create(
            user=self.user, tenant=self.tenant, status=DataExportStatus.PROCESSING
        )
        self.assertEqual(job.status, DataExportStatus.PROCESSING)

        # Invalid status should raise ValidationError
        with self.assertRaises(ValidationError):
            job.status = "INVALID_STATUS"
            job.full_clean()

    # ========== MODEL RELATIONSHIPS TESTS ==========

    def test_data_export_job_user_relationship(self):
        """Test DataExportJob user relationship"""
        job = DataExportJob.objects.create(user=self.user, tenant=self.tenant)

        self.assertEqual(job.user, self.user)
        self.assertIn(job, self.user.data_export_jobs.all())

    def test_data_export_job_tenant_relationship(self):
        """Test DataExportJob tenant relationship"""
        job = DataExportJob.objects.create(user=self.user, tenant=self.tenant)

        self.assertEqual(job.tenant, self.tenant)
        self.assertIn(job, self.tenant.data_export_jobs.all())

    def test_data_export_job_cascade_delete_user(self):
        """Test that deleting user cascades to export jobs"""
        job = DataExportJob.objects.create(user=self.user, tenant=self.tenant)
        job_id = job.id

        self.user.delete()

        self.assertFalse(DataExportJob.objects.filter(id=job_id).exists())

    def test_data_export_job_cascade_delete_tenant(self):
        """Test that deleting tenant cascades to export jobs"""
        job = DataExportJob.objects.create(user=self.user, tenant=self.tenant)
        job_id = job.id

        self.tenant.delete()

        self.assertFalse(DataExportJob.objects.filter(id=job_id).exists())

    # ========== MODEL METHODS TESTS ==========

    def test_data_export_job_str_representation(self):
        """Test DataExportJob __str__ method"""
        job = DataExportJob.objects.create(
            user=self.user, tenant=self.tenant, status=DataExportStatus.PENDING
        )

        str_repr = str(job)
        self.assertIn(str(job.id), str_repr)
        self.assertIn(self.user.email, str_repr)
        self.assertIn(DataExportStatus.PENDING, str_repr)

    # ========== MODEL ORDERING TESTS ==========

    def test_data_export_job_ordering(self):
        """Test DataExportJob default ordering (most recent first)"""
        job1 = DataExportJob.objects.create(user=self.user, tenant=self.tenant)
        job2 = DataExportJob.objects.create(user=self.user, tenant=self.tenant)
        job3 = DataExportJob.objects.create(user=self.user, tenant=self.tenant)

        jobs = list(DataExportJob.objects.all())
        self.assertEqual(jobs[0], job3)
        self.assertEqual(jobs[1], job2)
        self.assertEqual(jobs[2], job1)

    # ========== EDGE CASES TESTS ==========

    def test_data_export_job_long_storage_path(self):
        """Test data export job with long storage path"""
        long_path = "a" * 500  # Max length is 500
        job = DataExportJob.objects.create(
            user=self.user, tenant=self.tenant, storage_path=long_path
        )

        self.assertEqual(len(job.storage_path), 500)

    def test_data_export_job_long_download_url(self):
        """Test data export job with long download URL"""
        long_url = "https://example.com/" + "a" * 2027  # Max length is 2048
        job = DataExportJob.objects.create(
            user=self.user, tenant=self.tenant, download_url=long_url
        )

        self.assertEqual(len(job.download_url), 2048)

    def test_data_export_job_empty_error_message(self):
        """Test data export job with empty error message"""
        job = DataExportJob.objects.create(user=self.user, tenant=self.tenant, error_message="")

        self.assertEqual(job.error_message, "")

    def test_data_export_job_multiple_jobs_same_user(self):
        """Test multiple export jobs for same user"""
        job1 = DataExportJob.objects.create(user=self.user, tenant=self.tenant)
        job2 = DataExportJob.objects.create(user=self.user, tenant=self.tenant)
        job3 = DataExportJob.objects.create(user=self.user, tenant=self.tenant)

        self.assertEqual(DataExportJob.objects.filter(user=self.user).count(), 3)
        self.assertNotEqual(job1.id, job2.id)
        self.assertNotEqual(job2.id, job3.id)

    # ========== ERROR HANDLING TESTS ==========

    def test_data_export_job_requires_user(self):
        """Test that DataExportJob requires user"""
        with self.assertRaises(IntegrityError):
            DataExportJob.objects.create(tenant=self.tenant)

    def test_data_export_job_requires_tenant(self):
        """Test that DataExportJob requires tenant"""
        with self.assertRaises(IntegrityError):
            DataExportJob.objects.create(user=self.user)


class ErasureRequestModelTest(TestCase):
    """Comprehensive tests for ErasureRequest model"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant", status="ACTIVE")

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

    # ========== MODEL CREATION TESTS ==========

    def test_create_erasure_request_success(self):
        """Test successful erasure request creation"""
        request = ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=ErasureRequestStatus.PENDING,
        )

        self.assertIsNotNone(request.id)
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.tenant, self.tenant)
        self.assertEqual(request.status, ErasureRequestStatus.PENDING)
        self.assertIsNone(request.completed_at)
        self.assertIsNone(request.error_message)
        self.assertEqual(request.anonymized_fields, [])
        self.assertEqual(request.deleted_resources, [])
        self.assertEqual(request.retention_exceptions, [])
        self.assertIsNotNone(request.requested_at)
        self.assertIsNotNone(request.created_at)
        self.assertIsNotNone(request.updated_at)

    def test_create_erasure_request_with_all_fields(self):
        """Test erasure request creation with all fields"""
        completed_at = timezone.now()
        error_message = "Some error occurred"
        anonymized_fields = ["email", "display_name"]
        deleted_resources = ["sessions", "api_keys"]
        retention_exceptions = ["audit_events"]

        request = ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=ErasureRequestStatus.COMPLETED,
            completed_at=completed_at,
            error_message=error_message,
            anonymized_fields=anonymized_fields,
            deleted_resources=deleted_resources,
            retention_exceptions=retention_exceptions,
        )

        self.assertEqual(request.status, ErasureRequestStatus.COMPLETED)
        self.assertEqual(request.completed_at, completed_at)
        self.assertEqual(request.error_message, error_message)
        self.assertEqual(request.anonymized_fields, anonymized_fields)
        self.assertEqual(request.deleted_resources, deleted_resources)
        self.assertEqual(request.retention_exceptions, retention_exceptions)

    def test_create_erasure_request_with_error(self):
        """Test erasure request creation with error message"""
        error_message = "Failed to execute erasure: Database error"

        request = ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=ErasureRequestStatus.FAILED,
            error_message=error_message,
        )

        self.assertEqual(request.status, ErasureRequestStatus.FAILED)
        self.assertEqual(request.error_message, error_message)

    def test_erasure_request_default_status(self):
        """Test that default status is PENDING"""
        request = ErasureRequest.objects.create(user=self.user, tenant=self.tenant)

        self.assertEqual(request.status, ErasureRequestStatus.PENDING)

    def test_erasure_request_default_json_fields(self):
        """Test that default JSON fields are empty lists"""
        request = ErasureRequest.objects.create(user=self.user, tenant=self.tenant)

        self.assertEqual(request.anonymized_fields, [])
        self.assertEqual(request.deleted_resources, [])
        self.assertEqual(request.retention_exceptions, [])

    # ========== MODEL STATUS CHOICES TESTS ==========

    def test_erasure_request_status_choices(self):
        """Test ErasureRequestStatus choices are valid"""
        self.assertEqual(ErasureRequestStatus.PENDING, "PENDING")
        self.assertEqual(ErasureRequestStatus.PROCESSING, "PROCESSING")
        self.assertEqual(ErasureRequestStatus.COMPLETED, "COMPLETED")
        self.assertEqual(ErasureRequestStatus.FAILED, "FAILED")

    def test_erasure_request_status_choices_validation(self):
        """Test that only valid status choices are accepted"""
        # Valid status
        request = ErasureRequest.objects.create(
            user=self.user, tenant=self.tenant, status=ErasureRequestStatus.PROCESSING
        )
        self.assertEqual(request.status, ErasureRequestStatus.PROCESSING)

        # Invalid status should raise ValidationError
        with self.assertRaises(ValidationError):
            request.status = "INVALID_STATUS"
            request.full_clean()

    # ========== MODEL RELATIONSHIPS TESTS ==========

    def test_erasure_request_user_relationship(self):
        """Test ErasureRequest user relationship"""
        request = ErasureRequest.objects.create(user=self.user, tenant=self.tenant)

        self.assertEqual(request.user, self.user)
        self.assertIn(request, self.user.erasure_requests.all())

    def test_erasure_request_tenant_relationship(self):
        """Test ErasureRequest tenant relationship"""
        request = ErasureRequest.objects.create(user=self.user, tenant=self.tenant)

        self.assertEqual(request.tenant, self.tenant)
        self.assertIn(request, self.tenant.erasure_requests.all())

    def test_erasure_request_cascade_delete_user(self):
        """Test that deleting user cascades to erasure requests"""
        request = ErasureRequest.objects.create(user=self.user, tenant=self.tenant)
        request_id = request.id

        self.user.delete()

        self.assertFalse(ErasureRequest.objects.filter(id=request_id).exists())

    def test_erasure_request_cascade_delete_tenant(self):
        """Test that deleting tenant cascades to erasure requests"""
        request = ErasureRequest.objects.create(user=self.user, tenant=self.tenant)
        request_id = request.id

        self.tenant.delete()

        self.assertFalse(ErasureRequest.objects.filter(id=request_id).exists())

    # ========== MODEL METHODS TESTS ==========

    def test_erasure_request_str_representation(self):
        """Test ErasureRequest __str__ method"""
        request = ErasureRequest.objects.create(
            user=self.user, tenant=self.tenant, status=ErasureRequestStatus.PENDING
        )

        str_repr = str(request)
        self.assertIn(str(request.id), str_repr)
        self.assertIn(self.user.email, str_repr)
        self.assertIn(ErasureRequestStatus.PENDING, str_repr)

    # ========== MODEL ORDERING TESTS ==========

    def test_erasure_request_ordering(self):
        """Test ErasureRequest default ordering (most recent first)"""
        request1 = ErasureRequest.objects.create(user=self.user, tenant=self.tenant)
        request2 = ErasureRequest.objects.create(user=self.user, tenant=self.tenant)
        request3 = ErasureRequest.objects.create(user=self.user, tenant=self.tenant)

        requests = list(ErasureRequest.objects.all())
        self.assertEqual(requests[0], request3)
        self.assertEqual(requests[1], request2)
        self.assertEqual(requests[2], request1)

    # ========== JSON FIELD TESTS ==========

    def test_erasure_request_anonymized_fields_json(self):
        """Test anonymized_fields JSON field stores list correctly"""
        anonymized_fields = ["email", "display_name", "phone_number"]

        request = ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            anonymized_fields=anonymized_fields,
        )

        request.refresh_from_db()
        self.assertEqual(request.anonymized_fields, anonymized_fields)
        self.assertIsInstance(request.anonymized_fields, list)

    def test_erasure_request_deleted_resources_json(self):
        """Test deleted_resources JSON field stores list correctly"""
        deleted_resources = ["sessions", "api_keys", "tokens"]

        request = ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            deleted_resources=deleted_resources,
        )

        request.refresh_from_db()
        self.assertEqual(request.deleted_resources, deleted_resources)
        self.assertIsInstance(request.deleted_resources, list)

    def test_erasure_request_retention_exceptions_json(self):
        """Test retention_exceptions JSON field stores list correctly"""
        retention_exceptions = ["audit_events", "financial_records"]

        request = ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            retention_exceptions=retention_exceptions,
        )

        request.refresh_from_db()
        self.assertEqual(request.retention_exceptions, retention_exceptions)
        self.assertIsInstance(request.retention_exceptions, list)

    def test_erasure_request_empty_json_fields(self):
        """Test that empty JSON fields work correctly"""
        request = ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            anonymized_fields=[],
            deleted_resources=[],
            retention_exceptions=[],
        )

        request.refresh_from_db()
        self.assertEqual(request.anonymized_fields, [])
        self.assertEqual(request.deleted_resources, [])
        self.assertEqual(request.retention_exceptions, [])

    # ========== EDGE CASES TESTS ==========

    def test_erasure_request_long_error_message(self):
        """Test erasure request with long error message"""
        long_error = "Error: " + "x" * 10000
        request = ErasureRequest.objects.create(
            user=self.user, tenant=self.tenant, error_message=long_error
        )

        self.assertEqual(len(request.error_message), 10006)

    def test_erasure_request_multiple_requests_same_user(self):
        """Test multiple erasure requests for same user"""
        request1 = ErasureRequest.objects.create(user=self.user, tenant=self.tenant)
        request2 = ErasureRequest.objects.create(user=self.user, tenant=self.tenant)
        request3 = ErasureRequest.objects.create(user=self.user, tenant=self.tenant)

        self.assertEqual(ErasureRequest.objects.filter(user=self.user).count(), 3)
        self.assertNotEqual(request1.id, request2.id)
        self.assertNotEqual(request2.id, request3.id)

    def test_erasure_request_completed_at_before_requested_at(self):
        """Test edge case: completed_at before requested_at (shouldn't happen but test it)"""
        requested_at = timezone.now()
        completed_at = requested_at - timezone.timedelta(hours=1)

        request = ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            requested_at=requested_at,
            completed_at=completed_at,
        )

        # Model allows this (no validation constraint)
        self.assertLess(request.completed_at, request.requested_at)

    # ========== ERROR HANDLING TESTS ==========

    def test_erasure_request_requires_user(self):
        """Test that ErasureRequest requires user"""
        with self.assertRaises(IntegrityError):
            ErasureRequest.objects.create(tenant=self.tenant)

    def test_erasure_request_requires_tenant(self):
        """Test that ErasureRequest requires tenant"""
        with self.assertRaises(IntegrityError):
            ErasureRequest.objects.create(user=self.user)
