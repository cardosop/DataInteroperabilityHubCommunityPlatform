"""
Tests for Bug Prevention Services
"""

from datetime import timedelta
from uuid import uuid4

from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from hub.apps.core.bug_prevention.models import IdempotencyKey, RequestDeduplication
from hub.apps.core.bug_prevention.services import (
    IdempotencyConflictError,
    IdempotencyService,
    RequestDeduplicationService,
)
from hub.apps.tenants.models import Tenant


class IdempotencyServiceTest(TestCase):
    """Test IdempotencyService."""

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        self.tenant_id = str(self.tenant.id)
        self.idempotency_key = "test-key-12345"
        self.method = "POST"
        self.path = "/api/v1/dq/runs/"
        self.body = {"dataset_id": str(uuid4())}

    def test_validate_key_format_success(self):
        """Test successful key format validation."""
        key = "test-key-12345"

        is_valid, error = IdempotencyService.validate_key_format(key)

        self.assertTrue(is_valid)
        self.assertIsNone(error)

    def test_validate_key_format_too_short(self):
        """Test key format validation with too short key."""
        key = "short"

        is_valid, error = IdempotencyService.validate_key_format(key)

        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
        self.assertTrue(
            "length" in error.lower() or "short" in error.lower(),
            f"Error message should mention length/short, got: {error}",
        )

    def test_validate_key_format_invalid_characters(self):
        """Test key format validation with invalid characters."""
        key = "test key with spaces!"

        is_valid, error = IdempotencyService.validate_key_format(key)

        self.assertFalse(is_valid)
        self.assertIsNotNone(error)
        self.assertIn(
            "characters", error.lower(), f"Error message should mention characters, got: {error}"
        )

    def test_check_idempotency_not_found(self):
        """Test checking idempotency when key doesn't exist."""
        record, cached_response = IdempotencyService.check_idempotency(
            self.tenant_id, self.idempotency_key, self.method, self.path, self.body
        )

        self.assertIsNone(record)
        self.assertIsNone(cached_response)

    def test_check_idempotency_found_matching(self):
        """Test checking idempotency when key exists with matching fingerprint."""
        # Store idempotency key
        response_body = {"job_id": str(uuid4()), "status": "PENDING"}
        IdempotencyService.store_idempotency(
            self.tenant_id,
            self.idempotency_key,
            self.method,
            self.path,
            self.body,
            status.HTTP_201_CREATED,
            response_body,
        )

        # Check idempotency with same request
        record, cached_response = IdempotencyService.check_idempotency(
            self.tenant_id, self.idempotency_key, self.method, self.path, self.body
        )

        self.assertIsNotNone(record)
        self.assertIsNotNone(cached_response)
        self.assertEqual(cached_response["status_code"], status.HTTP_201_CREATED)
        self.assertEqual(cached_response["data"], response_body)

    def test_check_idempotency_found_different_fingerprint(self):
        """Test checking idempotency when key exists with different fingerprint."""
        # Store idempotency key with original body
        original_body = {"dataset_id": str(uuid4())}
        response_body = {"job_id": str(uuid4()), "status": "PENDING"}
        IdempotencyService.store_idempotency(
            self.tenant_id,
            self.idempotency_key,
            self.method,
            self.path,
            original_body,
            status.HTTP_201_CREATED,
            response_body,
        )

        # Check idempotency with different body
        different_body = {"dataset_id": str(uuid4())}

        with self.assertRaises(IdempotencyConflictError):
            IdempotencyService.check_idempotency(
                self.tenant_id, self.idempotency_key, self.method, self.path, different_body
            )

    def test_check_idempotency_expired(self):
        """Test checking idempotency when key is expired."""
        # Create expired record
        record = IdempotencyKey.objects.create(
            tenant_id=self.tenant.id,
            idempotency_key=self.idempotency_key,
            method=self.method,
            path=self.path,
            request_fingerprint=IdempotencyKey.compute_fingerprint(
                self.method, self.path, self.body
            ),
            response_status=status.HTTP_201_CREATED,
            response_body={"job_id": str(uuid4())},
            expires_at=timezone.now() - timedelta(hours=1),  # Expired
        )

        # Check idempotency
        result_record, cached_response = IdempotencyService.check_idempotency(
            self.tenant_id, self.idempotency_key, self.method, self.path, self.body
        )

        # Should return None and delete expired record
        self.assertIsNone(result_record)
        self.assertIsNone(cached_response)
        self.assertFalse(IdempotencyKey.objects.filter(id=record.id).exists())

    def test_store_idempotency(self):
        """Test storing idempotency key."""
        response_body = {"job_id": str(uuid4()), "status": "PENDING"}

        record = IdempotencyService.store_idempotency(
            self.tenant_id,
            self.idempotency_key,
            self.method,
            self.path,
            self.body,
            status.HTTP_201_CREATED,
            response_body,
        )

        self.assertIsNotNone(record)
        # tenant_id is stored as UUID, compare UUIDs
        # Convert both to strings for comparison since Django may return UUID or string
        self.assertEqual(str(record.tenant_id), self.tenant_id)
        self.assertEqual(record.idempotency_key, self.idempotency_key)
        self.assertEqual(record.response_status, status.HTTP_201_CREATED)
        self.assertEqual(record.response_body, response_body)
        self.assertIsNotNone(record.expires_at)

    def test_store_idempotency_update_existing(self):
        """Test storing idempotency key updates existing record."""
        # Store initial record
        initial_body = {"dataset_id": str(uuid4())}
        initial_response = {"job_id": str(uuid4())}
        IdempotencyService.store_idempotency(
            self.tenant_id,
            self.idempotency_key,
            self.method,
            self.path,
            initial_body,
            status.HTTP_201_CREATED,
            initial_response,
        )

        # Store with same key but different body (should update)
        new_body = {"dataset_id": str(uuid4())}
        new_response = {"job_id": str(uuid4()), "status": "COMPLETED"}
        record = IdempotencyService.store_idempotency(
            self.tenant_id,
            self.idempotency_key,
            self.method,
            self.path,
            new_body,
            status.HTTP_200_OK,
            new_response,
        )

        # Re-fetch from DB to confirm persistence
        record.refresh_from_db()
        # Should have updated the record
        self.assertEqual(record.response_status, status.HTTP_200_OK)
        self.assertEqual(record.response_body, new_response)
        # Should only have one record
        self.assertEqual(
            IdempotencyKey.objects.filter(
                tenant_id=self.tenant.id, idempotency_key=self.idempotency_key
            ).count(),
            1,
        )

    def test_cleanup_expired(self):
        """Test cleaning up expired idempotency keys."""
        # Create expired record
        IdempotencyKey.objects.create(
            tenant_id=self.tenant.id,
            idempotency_key="expired-key",
            method="POST",
            path="/api/v1/test/",
            request_fingerprint="fingerprint",
            response_status=200,
            response_body={},
            expires_at=timezone.now() - timedelta(hours=25),
        )

        # Create non-expired record
        IdempotencyKey.objects.create(
            tenant_id=self.tenant.id,
            idempotency_key="active-key",
            method="POST",
            path="/api/v1/test/",
            request_fingerprint="fingerprint2",
            response_status=200,
            response_body={},
            expires_at=timezone.now() + timedelta(hours=1),
        )

        # Cleanup
        deleted_count = IdempotencyService.cleanup_expired(older_than_hours=24)

        self.assertEqual(deleted_count, 1)
        self.assertFalse(IdempotencyKey.objects.filter(idempotency_key="expired-key").exists())
        self.assertTrue(IdempotencyKey.objects.filter(idempotency_key="active-key").exists())

    def test_cleanup_expired_boundary_not_deleted(self):
        """Test that a record expiring exactly at the cutoff boundary is NOT deleted.

        The filter uses expires_at__lt (strict less than), so a record whose
        expires_at equals the cutoff should be retained.
        """
        # Create a record whose expires_at is just AFTER the cutoff.
        # cleanup_expired(older_than_hours=24) computes cutoff = now - 24h,
        # then deletes where expires_at < cutoff.
        # A record expiring 1 second AFTER the cutoff should survive.
        boundary_time = timezone.now() - timedelta(hours=24) + timedelta(seconds=1)
        IdempotencyKey.objects.create(
            tenant_id=self.tenant.id,
            idempotency_key="boundary-key",
            method="POST",
            path="/api/v1/test/",
            request_fingerprint="fingerprint-boundary",
            response_status=200,
            response_body={},
            expires_at=boundary_time,
        )

        deleted_count = IdempotencyService.cleanup_expired(older_than_hours=24)

        self.assertEqual(deleted_count, 0)
        self.assertTrue(IdempotencyKey.objects.filter(idempotency_key="boundary-key").exists())


class RequestDeduplicationServiceTest(TestCase):
    """Test RequestDeduplicationService."""

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )
        self.tenant_id = str(self.tenant.id)
        self.method = "POST"
        self.path = "/api/v1/contracts/"
        self.body = {"name": "Test Contract"}
        self.headers = {"Content-Type": "application/json"}

    def test_check_duplicate_not_found(self):
        """Test checking duplicate when request doesn't exist."""
        is_duplicate, record = RequestDeduplicationService.check_duplicate(
            self.tenant_id, self.method, self.path, self.body, self.headers
        )

        self.assertFalse(is_duplicate)
        self.assertIsNone(record)

    def test_check_duplicate_found(self):
        """Test checking duplicate when request exists."""
        # Store request
        RequestDeduplicationService.store_request(
            self.tenant_id, self.method, self.path, self.body, self.headers
        )

        # Check duplicate
        is_duplicate, record = RequestDeduplicationService.check_duplicate(
            self.tenant_id, self.method, self.path, self.body, self.headers
        )

        self.assertTrue(is_duplicate)
        self.assertIsNotNone(record)

    def test_check_duplicate_expired(self):
        """Test checking duplicate when record is expired."""
        # Create expired record
        record = RequestDeduplication.objects.create(
            tenant_id=self.tenant.id,
            request_fingerprint=RequestDeduplication.compute_fingerprint(
                self.tenant_id, self.method, self.path, self.body, self.headers
            ),
            method=self.method,
            path=self.path,
            request_body_hash="hash",
            expires_at=timezone.now() - timedelta(minutes=1),  # Expired
        )

        # Check duplicate
        is_duplicate, result_record = RequestDeduplicationService.check_duplicate(
            self.tenant_id, self.method, self.path, self.body, self.headers
        )

        # Should return False and delete expired record
        self.assertFalse(is_duplicate)
        self.assertIsNone(result_record)
        self.assertFalse(RequestDeduplication.objects.filter(id=record.id).exists())

    def test_store_request(self):
        """Test storing request for deduplication."""
        record = RequestDeduplicationService.store_request(
            self.tenant_id, self.method, self.path, self.body, self.headers
        )

        self.assertIsNotNone(record)
        # tenant_id is stored as UUID, compare as strings
        self.assertEqual(str(record.tenant_id), self.tenant_id)
        self.assertEqual(record.method, self.method.upper())
        self.assertEqual(record.path, self.path)
        self.assertIsNotNone(record.expires_at)

    def test_cleanup_expired(self):
        """Test cleaning up expired deduplication records."""
        # Create expired record
        RequestDeduplication.objects.create(
            tenant_id=self.tenant.id,
            request_fingerprint="expired-fingerprint",
            method="POST",
            path="/api/v1/test/",
            request_body_hash="hash",
            expires_at=timezone.now() - timedelta(minutes=10),
        )

        # Create non-expired record
        RequestDeduplication.objects.create(
            tenant_id=self.tenant.id,
            request_fingerprint="active-fingerprint",
            method="POST",
            path="/api/v1/test/",
            request_body_hash="hash2",
            expires_at=timezone.now() + timedelta(minutes=1),
        )

        # Cleanup
        deleted_count = RequestDeduplicationService.cleanup_expired(older_than_minutes=5)

        self.assertEqual(deleted_count, 1)
        self.assertFalse(
            RequestDeduplication.objects.filter(request_fingerprint="expired-fingerprint").exists()
        )
        self.assertTrue(
            RequestDeduplication.objects.filter(request_fingerprint="active-fingerprint").exists()
        )

    def test_cleanup_expired_boundary_not_deleted(self):
        """Test that a record expiring exactly at the cutoff boundary is NOT deleted.

        The filter uses expires_at__lt (strict less than), so a record whose
        expires_at equals the cutoff should be retained.
        """
        boundary_time = timezone.now() - timedelta(minutes=5) + timedelta(seconds=1)
        RequestDeduplication.objects.create(
            tenant_id=self.tenant.id,
            request_fingerprint="boundary-fingerprint",
            method="POST",
            path="/api/v1/test/",
            request_body_hash="hash-boundary",
            expires_at=boundary_time,
        )

        deleted_count = RequestDeduplicationService.cleanup_expired(older_than_minutes=5)

        self.assertEqual(deleted_count, 0)
        self.assertTrue(
            RequestDeduplication.objects.filter(request_fingerprint="boundary-fingerprint").exists()
        )
