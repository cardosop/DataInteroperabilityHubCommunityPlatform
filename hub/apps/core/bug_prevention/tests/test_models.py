"""
Tests for Bug Prevention Models
"""

from datetime import timedelta
from uuid import uuid4

from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from hub.apps.core.bug_prevention.models import IdempotencyKey, RequestDeduplication
from hub.apps.tenants.models import Tenant


class IdempotencyKeyModelTest(TestCase):
    """Test IdempotencyKey model."""

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )

    def test_create_idempotency_key(self):
        """Test creating idempotency key."""
        key = IdempotencyKey.objects.create(
            tenant_id=self.tenant.id,
            idempotency_key="test-key-123",
            method="POST",
            path="/api/v1/dq/runs/",
            request_fingerprint="fingerprint123",
            response_status=201,
            response_body={"job_id": str(uuid4())},
        )

        self.assertIsNotNone(key.id)
        self.assertEqual(key.tenant_id, self.tenant.id)
        self.assertEqual(key.idempotency_key, "test-key-123")
        self.assertIsNotNone(key.expires_at)

    def test_compute_fingerprint(self):
        """Test computing request fingerprint."""
        method = "POST"
        path = "/api/v1/dq/runs/"
        body = {"dataset_id": str(uuid4())}

        fingerprint1 = IdempotencyKey.compute_fingerprint(method, path, body)
        fingerprint2 = IdempotencyKey.compute_fingerprint(method, path, body)

        # Same inputs should produce same fingerprint
        self.assertEqual(fingerprint1, fingerprint2)
        self.assertEqual(len(fingerprint1), 64)  # SHA-256 hex length

    def test_compute_fingerprint_different_body(self):
        """Test computing fingerprint with different body produces different hash."""
        method = "POST"
        path = "/api/v1/dq/runs/"
        body1 = {"dataset_id": str(uuid4())}
        body2 = {"dataset_id": str(uuid4())}

        fingerprint1 = IdempotencyKey.compute_fingerprint(method, path, body1)
        fingerprint2 = IdempotencyKey.compute_fingerprint(method, path, body2)

        # Different bodies should produce different fingerprints
        self.assertNotEqual(fingerprint1, fingerprint2)

    def test_compute_fingerprint_normalizes_path(self):
        """Test fingerprint computation normalizes path."""
        method = "POST"
        path1 = "/api/v1/dq/runs/"
        path2 = "/api/v1/dq/runs"
        body = {"dataset_id": str(uuid4())}

        fingerprint1 = IdempotencyKey.compute_fingerprint(method, path1, body)
        fingerprint2 = IdempotencyKey.compute_fingerprint(method, path2, body)

        # Normalized paths should produce same fingerprint
        self.assertEqual(fingerprint1, fingerprint2)

        # Verify normalization produces the canonical (no trailing slash) path fingerprint
        canonical_fingerprint = IdempotencyKey.compute_fingerprint(method, "/api/v1/dq/runs", body)
        self.assertEqual(fingerprint1, canonical_fingerprint)

    def test_is_expired(self):
        """Test checking if key is expired."""
        # Create expired key
        expired_key = IdempotencyKey.objects.create(
            tenant_id=self.tenant.id,
            idempotency_key="expired-key",
            method="POST",
            path="/api/v1/test/",
            request_fingerprint="fingerprint",
            response_status=200,
            response_body={},
            expires_at=timezone.now() - timedelta(hours=1),
        )

        # Create non-expired key
        active_key = IdempotencyKey.objects.create(
            tenant_id=self.tenant.id,
            idempotency_key="active-key",
            method="POST",
            path="/api/v1/test/",
            request_fingerprint="fingerprint2",
            response_status=200,
            response_body={},
            expires_at=timezone.now() + timedelta(hours=1),
        )

        self.assertTrue(expired_key.is_expired())
        self.assertFalse(active_key.is_expired())

    def test_save_sets_expires_at(self):
        """Test that save automatically sets expires_at."""
        key = IdempotencyKey(
            tenant_id=self.tenant.id,
            idempotency_key="test-key",
            method="POST",
            path="/api/v1/test/",
            request_fingerprint="fingerprint",
            response_status=200,
            response_body={},
        )

        self.assertIsNone(key.expires_at)
        key.save()
        self.assertIsNotNone(key.expires_at)
        # Should be approximately 24 hours from now
        expected_expires = timezone.now() + timedelta(hours=24)
        self.assertAlmostEqual(
            key.expires_at.timestamp(),
            expected_expires.timestamp(),
            delta=60,  # Within 1 minute
        )

    def test_unique_constraint(self):
        """Test unique constraint on tenant_id, idempotency_key, method, path."""
        IdempotencyKey.objects.create(
            tenant_id=self.tenant.id,
            idempotency_key="test-key",
            method="POST",
            path="/api/v1/test/",
            request_fingerprint="fingerprint",
            response_status=200,
            response_body={},
        )

        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            IdempotencyKey.objects.create(
                tenant_id=self.tenant.id,
                idempotency_key="test-key",
                method="POST",
                path="/api/v1/test/",
                request_fingerprint="different-fingerprint",
                response_status=200,
                response_body={},
            )


class RequestDeduplicationModelTest(TestCase):
    """Test RequestDeduplication model."""

    def setUp(self):
        """Set up test fixtures."""
        uid = uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )

    def test_create_request_deduplication(self):
        """Test creating request deduplication record."""
        record = RequestDeduplication.objects.create(
            tenant_id=self.tenant.id,
            request_fingerprint="fingerprint123",
            method="POST",
            path="/api/v1/contracts/",
            request_body_hash="bodyhash123",
        )

        self.assertIsNotNone(record.id)
        self.assertEqual(record.tenant_id, self.tenant.id)
        self.assertEqual(record.request_fingerprint, "fingerprint123")
        self.assertIsNotNone(record.expires_at)

    def test_compute_fingerprint(self):
        """Test computing request fingerprint."""
        tenant_id = str(self.tenant.id)
        method = "POST"
        path = "/api/v1/contracts/"
        body = {"name": "Test Contract"}
        headers = {"Content-Type": "application/json"}

        fingerprint1 = RequestDeduplication.compute_fingerprint(
            tenant_id, method, path, body, headers
        )
        fingerprint2 = RequestDeduplication.compute_fingerprint(
            tenant_id, method, path, body, headers
        )

        # Same inputs should produce same fingerprint
        self.assertEqual(fingerprint1, fingerprint2)
        self.assertEqual(len(fingerprint1), 64)  # SHA-256 hex length

    def test_compute_fingerprint_different_tenant(self):
        """Test computing fingerprint with different tenant produces different hash."""
        tenant_id1 = str(uuid4())
        tenant_id2 = str(uuid4())
        method = "POST"
        path = "/api/v1/contracts/"
        body = {"name": "Test Contract"}

        fingerprint1 = RequestDeduplication.compute_fingerprint(tenant_id1, method, path, body)
        fingerprint2 = RequestDeduplication.compute_fingerprint(tenant_id2, method, path, body)

        # Different tenants should produce different fingerprints
        self.assertNotEqual(fingerprint1, fingerprint2)

    def test_is_expired(self):
        """Test checking if record is expired."""
        # Create expired record
        expired_record = RequestDeduplication.objects.create(
            tenant_id=self.tenant.id,
            request_fingerprint="expired-fingerprint",
            method="POST",
            path="/api/v1/test/",
            request_body_hash="hash",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        # Create non-expired record
        active_record = RequestDeduplication.objects.create(
            tenant_id=self.tenant.id,
            request_fingerprint="active-fingerprint",
            method="POST",
            path="/api/v1/test/",
            request_body_hash="hash2",
            expires_at=timezone.now() + timedelta(minutes=1),
        )

        self.assertTrue(expired_record.is_expired())
        self.assertFalse(active_record.is_expired())

    def test_save_sets_expires_at(self):
        """Test that save automatically sets expires_at."""
        record = RequestDeduplication(
            tenant_id=self.tenant.id,
            request_fingerprint="fingerprint",
            method="POST",
            path="/api/v1/test/",
            request_body_hash="hash",
        )

        self.assertIsNone(record.expires_at)
        record.save()
        self.assertIsNotNone(record.expires_at)
        # Should be approximately 5 minutes from now
        expected_expires = timezone.now() + timedelta(minutes=5)
        self.assertAlmostEqual(
            record.expires_at.timestamp(),
            expected_expires.timestamp(),
            delta=10,  # Within 10 seconds
        )

    def test_unique_fingerprint(self):
        """Test unique constraint on request_fingerprint."""
        RequestDeduplication.objects.create(
            tenant_id=self.tenant.id,
            request_fingerprint="unique-fingerprint",
            method="POST",
            path="/api/v1/test/",
            request_body_hash="hash",
        )

        # Try to create duplicate
        with self.assertRaises(IntegrityError):
            RequestDeduplication.objects.create(
                tenant_id=self.tenant.id,
                request_fingerprint="unique-fingerprint",
                method="GET",
                path="/api/v1/different/",
                request_body_hash="different-hash",
            )
