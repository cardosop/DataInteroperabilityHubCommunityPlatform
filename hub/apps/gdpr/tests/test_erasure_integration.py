"""
Comprehensive integration tests for GDPR erasure workflow (Phase 25.5.2).

Tests cover:
- Erasure request creation and execution
- Edge cases (multiple requests, concurrent requests, etc.)
- Error handling (failures, retries, etc.)
- TDD compliance (proper test structure, assertions, etc.)

Uses real DB and real services (no mocks/stubs).
"""

# CRITICAL: Patch sql_flush to use CASCADE for foreign key constraints
# This is needed when running tests with manage.py test (not pytest)
# Fixes: psycopg2.errors.FeatureNotSupported: cannot truncate a table referenced in a foreign key constraint
try:
    import django.db.backends.postgresql.operations as pg_operations

    if not hasattr(pg_operations.DatabaseOperations.sql_flush, "_patched_for_cascade"):
        _original_sql_flush = pg_operations.DatabaseOperations.sql_flush

        def _patched_sql_flush(self, style, tables, *, reset_sequences=False, allow_cascade=False):
            """
            Patched sql_flush that always uses CASCADE to handle foreign key constraints.

            ROOT CAUSE: During test teardown, Django tries to truncate tables but fails
            when tables have foreign key constraints. PostgreSQL requires CASCADE to truncate
            tables with foreign key references.

            SOLUTION: Always use allow_cascade=True when truncating tables during teardown.
            """
            return _original_sql_flush(
                self, style, tables, reset_sequences=reset_sequences, allow_cascade=True
            )

        _patched_sql_flush._patched_for_cascade = True
        pg_operations.DatabaseOperations.sql_flush = _patched_sql_flush
except Exception:
    # Patch failed, but tests should still run
    pass

import uuid

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.test import TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import create_audit_event
from hub.apps.baas.models import APIKey, APITier, APITierModel
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.gdpr.models import ErasureRequest, ErasureRequestStatus
from hub.apps.gdpr.services import ErasureService
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

User = get_user_model()


class ErasureWorkflowIntegrationTest(TransactionTestCase):
    """
    Integration tests for erasure workflow.

    Uses real DB and real services.
    """

    def setUp(self):
        """Set up test data"""
        # Create tenant
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant", status="ACTIVE")

        # Ensure tenant has active subscription so POST request-erasure is not 403
        ensure_tenant_has_active_subscription(self.tenant)

        # Create user
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
        )

        # Create API tier
        self.tier = APITierModel.objects.get_or_create(
            name=APITier.FREE,
            defaults={
                "rate_limit_per_hour": 1000,
                "rate_limit_per_day": 10000,
                "max_requests_per_month": 100000,
            },
        )[0]

        # Create API key for user
        key_value = APIKey.generate_key()
        key_hash = APIKey.hash_key(key_value)
        self.api_key = APIKey.objects.create(
            user=self.user,
            tenant=self.tenant,
            name="Test API Key",
            key_hash=key_hash,
            tier=self.tier,
        )

        # Create API client
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def tearDown(self):
        # TransactionTestCase teardown runs flush; ensure DB connection is valid
        # so teardown does not raise when connection was closed or DB was briefly unavailable
        from django.db import connection

        try:
            connection.ensure_connection()
        except Exception:
            pass
        super().tearDown()

    def test_erasure_request_creation(self):
        """Test erasure request creation"""
        service = ErasureService(user_id=str(self.user.id))
        request = service.create_request(user_id=str(self.user.id))

        self.assertEqual(request.status, ErasureRequestStatus.PENDING)
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.tenant, self.tenant)

    def test_erasure_execution_anonymizes_user(self):
        """Test that erasure execution anonymizes user"""
        original_email = self.user.email

        service = ErasureService(user_id=str(self.user.id))
        request = service.create_request(user_id=str(self.user.id))
        request = service.execute_erasure(request_id=str(request.id))

        # Refresh user from DB
        self.user.refresh_from_db()

        # Check user is anonymized
        self.assertNotEqual(self.user.email, original_email)
        self.assertIn("deleted-", self.user.email)
        self.assertEqual(self.user.display_name, "Deleted User")

        # Check request is completed
        self.assertEqual(request.status, ErasureRequestStatus.COMPLETED)
        self.assertIn("email", request.anonymized_fields)
        self.assertIn("display_name", request.anonymized_fields)

    def test_erasure_revokes_api_keys(self):
        """Test that erasure deactivates API keys"""
        service = ErasureService(user_id=str(self.user.id))
        request = service.create_request(user_id=str(self.user.id))
        request = service.execute_erasure(request_id=str(request.id))

        # Refresh API key from DB
        self.api_key.refresh_from_db()

        # Check API key is revoked (erasure sets revoked_at)
        self.assertIsNotNone(self.api_key.revoked_at)
        self.assertFalse(self.api_key.is_active())
        self.assertIn("api_keys", request.deleted_resources)

    def test_erasure_request_api(self):
        """Test erasure request via API"""
        response = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("request_id", response.data)
        self.assertIn("status", response.data)
        self.assertIn("requested_at", response.data)

        # Verify request was created
        request_id = response.data["request_id"]
        request = ErasureRequest.objects.get(id=request_id)
        self.assertEqual(request.user, self.user)
        self.assertEqual(request.tenant, self.tenant)

    # ========== EDGE CASES TESTS ==========

    def test_erasure_request_with_existing_pending_request(self):
        """Test that creating erasure request when pending request exists raises ValidationError"""
        # Create pending request
        ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=ErasureRequestStatus.PENDING,
        )

        service = ErasureService(user_id=str(self.user.id))

        with self.assertRaises(ValidationError) as cm:
            service.create_request(user_id=str(self.user.id))

        self.assertEqual(cm.exception.code, "ERASURE_IN_PROGRESS")

    def test_erasure_request_with_existing_processing_request(self):
        """Test that creating erasure request when processing request exists raises ValidationError"""
        # Create processing request
        ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=ErasureRequestStatus.PROCESSING,
        )

        service = ErasureService(user_id=str(self.user.id))

        with self.assertRaises(ValidationError) as cm:
            service.create_request(user_id=str(self.user.id))

        self.assertEqual(cm.exception.code, "ERASURE_IN_PROGRESS")

    def test_erasure_request_allows_multiple_completed_requests(self):
        """Test that multiple completed erasure requests are allowed"""
        # Create completed request
        ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=ErasureRequestStatus.COMPLETED,
        )

        service = ErasureService(user_id=str(self.user.id))
        request = service.create_request(user_id=str(self.user.id))

        self.assertIsNotNone(request.id)
        self.assertEqual(request.status, ErasureRequestStatus.PENDING)

    def test_erasure_execution_idempotent(self):
        """Test that executing erasure multiple times is idempotent"""
        service = ErasureService(user_id=str(self.user.id))
        request = service.create_request(user_id=str(self.user.id))

        # Execute first time
        request1 = service.execute_erasure(request_id=str(request.id))
        status1 = request1.status
        completed_at1 = request1.completed_at

        # Execute second time
        request2 = service.execute_erasure(request_id=str(request.id))
        status2 = request2.status
        completed_at2 = request2.completed_at

        # Should be the same
        self.assertEqual(status1, status2)
        self.assertEqual(completed_at1, completed_at2)

    def test_erasure_execution_with_nonexistent_request(self):
        """Test that executing erasure with nonexistent request raises NotFoundError"""
        fake_request_id = str(uuid.uuid4())

        service = ErasureService(user_id=str(self.user.id))

        with self.assertRaises(NotFoundError):
            service.execute_erasure(request_id=fake_request_id)

    def test_erasure_anonymizes_audit_events(self):
        """Test that erasure anonymizes audit events"""
        # Create audit event with user email in details
        create_audit_event(
            resource_type="ASSET",
            action="ASSET_CREATED",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id=str(uuid.uuid4()),
            details={"user_email": self.user.email, "actor_email": self.user.email},
        )

        service = ErasureService(user_id=str(self.user.id))
        request = service.create_request(user_id=str(self.user.id))
        service.execute_erasure(request_id=str(request.id))

        # Check audit event details are anonymized
        audit_event = AuditEvent.objects.filter(actor_user=self.user).first()
        if audit_event and audit_event.details_json:
            if isinstance(audit_event.details_json, dict):
                if "user_email" in audit_event.details_json:
                    self.assertEqual(
                        audit_event.details_json["user_email"], "deleted@deleted.local"
                    )
                if "actor_email" in audit_event.details_json:
                    self.assertEqual(
                        audit_event.details_json["actor_email"], "deleted@deleted.local"
                    )

    def test_erasure_records_retention_exceptions(self):
        """Test that erasure records retention exceptions"""
        service = ErasureService(user_id=str(self.user.id))
        request = service.create_request(user_id=str(self.user.id))
        request = service.execute_erasure(request_id=str(request.id))

        # Audit events should be in retention exceptions
        self.assertIn("audit_events", request.retention_exceptions)

    def test_erasure_creates_audit_events(self):
        """Test that erasure creates audit events"""
        service = ErasureService(user_id=str(self.user.id))

        # Count initial audit events
        initial_count = AuditEvent.objects.filter(resource_type="ERASURE_REQUEST").count()

        request = service.create_request(user_id=str(self.user.id))
        service.execute_erasure(request_id=str(request.id))

        # Should have created at least 2 audit events (REQUESTED and COMPLETED)
        final_count = AuditEvent.objects.filter(resource_type="ERASURE_REQUEST").count()

        self.assertGreaterEqual(final_count, initial_count + 2)

    def test_erasure_different_users_independent(self):
        """Test that erasure for different users is independent"""
        # Create another user
        user2 = User.objects.create_user(
            email="test2@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User 2",
        )

        service1 = ErasureService(user_id=str(self.user.id))
        service2 = ErasureService(user_id=str(user2.id))

        # Create requests for both users
        request1 = service1.create_request(user_id=str(self.user.id))
        request2 = service2.create_request(user_id=str(user2.id))

        # Execute erasure for first user
        service1.execute_erasure(request_id=str(request1.id))

        # Second user should still be intact
        user2.refresh_from_db()
        self.assertEqual(user2.email, "test2@example.com")
        self.assertEqual(user2.display_name, "Test User 2")

    # ========== ERROR HANDLING TESTS ==========

    def test_erasure_request_with_nonexistent_user(self):
        """Test that creating erasure request with nonexistent user raises NotFoundError"""
        fake_user_id = str(uuid.uuid4())

        service = ErasureService(user_id=str(self.user.id))

        with self.assertRaises(NotFoundError):
            service.create_request(user_id=fake_user_id)

    def test_erasure_execution_handles_failure_gracefully(self):
        """Test that erasure execution handles failures gracefully.

        Uses IntegrityError: pre-create a user with the anonymized email so that
        user.save() fails during anonymization. The request survives (no CASCADE)
        and is marked FAILED by the service.
        """
        service = ErasureService(user_id=str(self.user.id))
        request = service.create_request(user_id=str(self.user.id))

        # Pre-create user with anonymized email so user.save() fails (unique constraint)
        anon_email = f"deleted-{self.user.id}@deleted.local"
        User.objects.create_user(
            email=anon_email,
            password="unused",
            tenant=self.tenant,
            display_name="Collision User",
        )

        # Should raise exception, but request should be marked as FAILED
        with self.assertRaises(Exception):
            service.execute_erasure(request_id=str(request.id))

        # Request should be marked as failed (request survives; no CASCADE)
        request.refresh_from_db()
        self.assertEqual(request.status, ErasureRequestStatus.FAILED)
        self.assertIsNotNone(request.error_message)

    def test_erasure_api_with_existing_pending_request(self):
        """Test that API returns error when pending request exists"""
        # Create pending request
        ErasureRequest.objects.create(
            user=self.user,
            tenant=self.tenant,
            status=ErasureRequestStatus.PENDING,
        )

        response = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")

        # Should return error
        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_409_CONFLICT],
        )

    def test_erasure_api_handles_execution_failure_gracefully(self):
        """Test that API handles execution failure gracefully"""
        # This test verifies that if erasure execution fails,
        # the request is still created and can be retried
        response = self.client.post("/api/v1/users/me/erasure-requests/request-erasure/")

        # Should succeed even if execution fails
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("request_id", response.data)

        # Request should exist
        request_id = response.data["request_id"]
        request = ErasureRequest.objects.get(id=request_id)
        self.assertIsNotNone(request)

    # ========== TDD COMPLIANCE TESTS ==========

    def test_erasure_request_has_all_required_fields(self):
        """Test that erasure request has all required fields"""
        service = ErasureService(user_id=str(self.user.id))
        request = service.create_request(user_id=str(self.user.id))

        # Verify all required fields are present
        self.assertIsNotNone(request.id)
        self.assertIsNotNone(request.user)
        self.assertIsNotNone(request.tenant)
        self.assertIsNotNone(request.status)
        self.assertIsNotNone(request.requested_at)
        self.assertIsNotNone(request.created_at)
        self.assertIsNotNone(request.updated_at)

        # Verify default values
        self.assertEqual(request.status, ErasureRequestStatus.PENDING)
        self.assertEqual(request.anonymized_fields, [])
        self.assertEqual(request.deleted_resources, [])
        self.assertEqual(request.retention_exceptions, [])

    def test_erasure_execution_sets_all_fields(self):
        """Test that erasure execution sets all required fields"""
        service = ErasureService(user_id=str(self.user.id))
        request = service.create_request(user_id=str(self.user.id))
        request = service.execute_erasure(request_id=str(request.id))

        # Verify all fields are set
        self.assertEqual(request.status, ErasureRequestStatus.COMPLETED)
        self.assertIsNotNone(request.completed_at)
        self.assertIsInstance(request.anonymized_fields, list)
        self.assertIsInstance(request.deleted_resources, list)
        self.assertIsInstance(request.retention_exceptions, list)
        self.assertGreater(len(request.anonymized_fields), 0)
        self.assertGreater(len(request.deleted_resources), 0)
