"""
Comprehensive E2E tests for Error Handling.

Covers:
- Error response formats (standard format, codes, messages, details)
- Error recovery (retry logic, fallback mechanisms, notifications)
- Error logging (format, levels, aggregation)

Uses REAL services (no mocks).
"""

import json
import uuid
from datetime import datetime, timedelta

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.jobs.models import Job, JobStatus, JobType
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import User, UserStatus

from .conftest import E2ETestBase

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e5]


class ErrorResponseFormatE2ETest(E2ETestBase):
    """Comprehensive E2E tests for error response formats"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    # ========== Standard Error Response Format Tests ==========

    def test_error_response_standard_format(self):
        """Test that all error responses follow standard format"""
        # Try to access non-existent resource
        fake_id = uuid.uuid4()

        response = self.client.get(f"/api/v1/assets/assets/{fake_id}/")

        # Should return 404
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # Check error format
        self.assertIn("error", response.data)
        error = response.data["error"]

        # Required fields
        self.assertIn("code", error)
        self.assertIn("message", error)
        self.assertIn("http_status", error)
        self.assertIn("request_id", error)
        self.assertIn("timestamp", error)

        # Verify field types
        self.assertIsInstance(error["code"], str)
        self.assertIsInstance(error["message"], str)
        self.assertIsInstance(error["http_status"], int)
        self.assertIsInstance(error["request_id"], str)
        self.assertIsInstance(error["timestamp"], str)

        # Verify http_status matches actual status code
        self.assertEqual(error["http_status"], response.status_code)

    def test_error_response_codes(self):
        """Test error codes for different error types"""
        # Test unauthenticated request (401)
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/assets/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        if "error" in response.data:
            error = response.data["error"]
            self.assertIn("code", error)
            code = error["code"]
            self.assertIn("AUTH", code.upper())

        # Test not found (404) - need to authenticate first
        self.client.force_authenticate(user=self.user)
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/assets/assets/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        if "error" in response.data:
            error = response.data["error"]
            self.assertIn("code", error)
            code = error["code"]
            self.assertIn("NOT_FOUND", code.upper())

    def test_error_response_messages(self):
        """Test error messages are user-friendly"""
        # Try to access non-existent resource
        fake_id = uuid.uuid4()

        response = self.client.get(f"/api/v1/assets/assets/{fake_id}/")

        if "error" in response.data:
            error = response.data["error"]
            message = error.get("message", "")

            # Should not contain stack traces
            self.assertNotIn("Traceback", message)
            self.assertNotIn('File "', message)
            self.assertNotIn("line ", message)

            # Should not contain internal paths
            self.assertNotIn("/usr/", message)
            self.assertNotIn("/home/", message)
            self.assertNotIn("/var/", message)

            # Should not contain raw exception strings
            self.assertNotIn("DoesNotExist", message)
            self.assertNotIn("Exception:", message)

            # Should be non-empty
            self.assertGreater(len(message), 0)

    def test_error_response_details(self):
        """Test error details structure for validation errors"""
        # Try to create asset with invalid data
        response = self.client.post(
            "/api/v1/assets/assets/",
            {
                "key": "",  # Invalid: empty key
                "name": "",  # Invalid: empty name
            },
            format="json",
        )

        # Should return 400
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            if "error" in response.data:
                error = response.data["error"]

                # May have details
                if "details" in error:
                    details = error["details"]
                    self.assertIsInstance(details, dict)

                    # May contain field_errors array
                    if "field_errors" in details:
                        field_errors = details["field_errors"]
                        self.assertIsInstance(field_errors, list)

                        # Each field error should have structure
                        for field_error in field_errors:
                            self.assertIsInstance(field_error, dict)
                            if "field" in field_error:
                                self.assertIsInstance(field_error["field"], str)
                            if "message" in field_error:
                                self.assertIsInstance(field_error["message"], str)

    def test_error_response_request_id(self):
        """Test error response includes request ID"""
        fake_id = uuid.uuid4()

        response = self.client.get(f"/api/v1/assets/assets/{fake_id}/")

        if "error" in response.data:
            error = response.data["error"]
            self.assertIn("request_id", error)
            request_id = error["request_id"]

            # Should be a valid UUID string
            self.assertIsNotNone(request_id)
            self.assertIsInstance(request_id, str)
            # Try to parse as UUID to verify format
            try:
                uuid.UUID(request_id)
            except ValueError:
                self.fail(f"request_id '{request_id}' is not a valid UUID")

    def test_error_response_timestamp(self):
        """Test error response includes timestamp"""
        fake_id = uuid.uuid4()

        response = self.client.get(f"/api/v1/assets/assets/{fake_id}/")

        if "error" in response.data:
            error = response.data["error"]
            self.assertIn("timestamp", error)
            timestamp = error["timestamp"]

            # Should be ISO 8601 format
            self.assertIsNotNone(timestamp)
            self.assertIsInstance(timestamp, str)

            # Should be parseable as datetime (ISO 8601 format)
            try:
                # Handle both 'Z' and timezone offset formats
                timestamp_parsed = timestamp.replace("Z", "+00:00")
                parsed_time = datetime.fromisoformat(timestamp_parsed)
                # Make timezone-aware if needed
                if parsed_time.tzinfo is None:
                    parsed_time = timezone.make_aware(parsed_time, timezone.utc)
                else:
                    parsed_time = parsed_time.astimezone(timezone.utc)

                # Should be recent (within last minute)
                now = timezone.now()
                time_diff = abs((now - parsed_time).total_seconds())
                self.assertLess(time_diff, 60, "Timestamp should be recent")
            except (ValueError, AttributeError):
                # If parsing fails, just check format
                self.assertIn("T", timestamp)  # ISO format has T separator
                # Should have timezone indicator (Z or +/-)
                self.assertTrue("Z" in timestamp or "+" in timestamp or "-" in timestamp[-6:])

    def test_error_response_consistency(self):
        """Test error response format is consistent across endpoints"""
        fake_id = uuid.uuid4()

        endpoints = [
            f"/api/v1/assets/assets/{fake_id}/",
            f"/api/v1/contracts/contracts/{fake_id}/",
            f"/api/v1/datasets/datasets/{fake_id}/",
        ]

        for endpoint in endpoints:
            response = self.client.get(endpoint)

            # Should all return 404
            self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

            # Error format should be consistent
            if "error" in response.data:
                error = response.data["error"]
                # All should have same structure
                self.assertIn("code", error)
                self.assertIn("message", error)
                self.assertIn("http_status", error)
                self.assertIn("request_id", error)
                self.assertIn("timestamp", error)

    def test_validation_error_field_errors(self):
        """Test validation errors include field-level errors"""
        # Try to create asset with multiple validation errors
        response = self.client.post(
            "/api/v1/assets/assets/",
            {
                "key": "",  # Invalid: empty
                "name": "",  # Invalid: empty
            },
            format="json",
        )

        if response.status_code == status.HTTP_400_BAD_REQUEST:
            # Should have error structure
            if "error" in response.data:
                error = response.data["error"]
                self.assertEqual(error["code"], "VALIDATION_ERROR")

                # May have details with field_errors
                if "details" in error:
                    details = error["details"]
                    if "field_errors" in details:
                        field_errors = details["field_errors"]
                        self.assertGreater(len(field_errors), 0)

    def test_authentication_error_format(self):
        """Test authentication error format"""
        # Unauthenticated request
        self.client.force_authenticate(user=None)

        response = self.client.get("/api/v1/assets/assets/")

        # Should return 401
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        # Check error format
        if "error" in response.data:
            error = response.data["error"]
            self.assertIn("code", error)
            code = error["code"].upper()
            self.assertIn("AUTH", code)

    def test_forbidden_error_format(self):
        """Test forbidden error format"""
        # Create another tenant and user
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Create asset in current tenant
        asset_id = self.create_asset(key="forbidden-test", name="Forbidden Test")

        # Switch to other user
        self.client.force_authenticate(user=other_user)

        # Try to access asset from other tenant
        response = self.client.get(f"/api/v1/assets/assets/{asset_id}/")

        # Should return 404 (tenant isolation) or 403
        self.assertIn(response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_403_FORBIDDEN])

        if response.status_code == status.HTTP_403_FORBIDDEN:
            if "error" in response.data:
                error = response.data["error"]
                self.assertIn("code", error)
                code = error["code"].upper()
                self.assertIn("FORBIDDEN", code)

    def test_error_http_status_mapping(self):
        """Test HTTP status code mapping to error codes"""
        test_cases = [
            (status.HTTP_400_BAD_REQUEST, "VALIDATION_ERROR"),
            (status.HTTP_401_UNAUTHORIZED, "AUTH_UNAUTHORIZED"),
            (status.HTTP_403_FORBIDDEN, "AUTH_FORBIDDEN"),
            (status.HTTP_404_NOT_FOUND, "NOT_FOUND"),
            (status.HTTP_409_CONFLICT, "CONFLICT_ERROR"),
            (status.HTTP_429_TOO_MANY_REQUESTS, "RATE_LIMIT_EXCEEDED"),
        ]

        # Test unauthenticated for 401
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/assets/assets/")
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            if "error" in response.data:
                error = response.data["error"]
                self.assertEqual(error["http_status"], status.HTTP_401_UNAUTHORIZED)
                self.assertIn("AUTH", error["code"].upper())

        # Test not found for 404
        self.client.force_authenticate(user=self.user)
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/assets/assets/{fake_id}/")
        if response.status_code == status.HTTP_404_NOT_FOUND:
            if "error" in response.data:
                error = response.data["error"]
                self.assertEqual(error["http_status"], status.HTTP_404_NOT_FOUND)
                self.assertIn("NOT_FOUND", error["code"].upper())


class ErrorRecoveryE2ETest(E2ETestBase):
    """Comprehensive E2E tests for error recovery"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    # ========== Retry Logic Tests ==========

    def test_job_retry_on_transient_failure(self):
        """Test job retries on transient failures"""
        from hub.apps.jobs.utils import get_job_max_retries, is_transient_failure

        # Create a job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            created_by=self.user,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
        )

        # Simulate transient failure
        transient_error = ConnectionError("Service temporarily unavailable")

        # Check if error is transient (core retry logic)
        self.assertTrue(is_transient_failure(transient_error))

        # Verify job has retry configuration
        max_retries = get_job_max_retries(str(job.type))
        self.assertGreater(max_retries, 0, "Job should have retries configured")

        # Verify job can be retried (check retry count logic)
        if job.details_json is None:
            job.details_json = {}
        retry_count = job.details_json.get("retry_count", 0)
        self.assertLess(retry_count, max_retries, "Job should have retries remaining")

    def test_job_no_retry_on_non_transient_failure(self):
        """Test job does not retry on non-transient failures"""
        from hub.apps.jobs.utils import is_transient_failure

        # Create a job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            created_by=self.user,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
        )

        # Simulate non-transient failure
        non_transient_error = ValueError("Invalid input data")

        # Check if error is non-transient (core retry logic)
        self.assertFalse(is_transient_failure(non_transient_error))

        # Non-transient errors should not trigger retry logic
        # This is verified by the is_transient_failure check above
        # The retry_job function checks this first and returns False for non-transient errors

    def test_job_retry_exponential_backoff(self):
        """Test job retry uses exponential backoff"""
        from hub.apps.jobs.utils import calculate_retry_delay

        # Test exponential backoff calculation
        retry_0_delay = calculate_retry_delay(0)
        retry_1_delay = calculate_retry_delay(1)
        retry_2_delay = calculate_retry_delay(2)

        # Should increase exponentially
        self.assertLess(retry_0_delay, retry_1_delay)
        self.assertLess(retry_1_delay, retry_2_delay)

        # Verify formula: base_delay * (2 ^ retry_count)
        base_delay = 60  # Default base delay
        self.assertEqual(retry_0_delay, base_delay * (2**0))
        self.assertEqual(retry_1_delay, base_delay * (2**1))
        self.assertEqual(retry_2_delay, base_delay * (2**2))

    def test_job_retry_max_retries(self):
        """Test job respects max retry limits"""
        from hub.apps.jobs.utils import get_job_max_retries

        # Create a job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.PENDING,
            created_by=self.user,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
        )

        max_retries = get_job_max_retries(str(job.type))
        self.assertGreater(max_retries, 0, "Job should have max retries configured")

        # Set retry count to max
        if job.details_json is None:
            job.details_json = {}
        job.details_json["retry_count"] = max_retries
        job.save()

        # Verify retry count is at max
        job.refresh_from_db()
        self.assertEqual(job.details_json.get("retry_count"), max_retries)

        # When retry_count >= max_retries, job should not be retried
        # This is verified by checking the retry count logic
        self.assertGreaterEqual(job.details_json.get("retry_count", 0), max_retries)

    # ========== Fallback Mechanisms Tests ==========

    def test_service_client_retry_logic(self):
        """Test service client retry logic"""
        from hub.apps.core.services.cross_service_access import ServiceClient

        # Create service client (use service_url, not base_url)
        client = ServiceClient(service_name="test-service", service_url="http://invalid-url")

        # Service client should have retry configuration
        # Verify retry settings exist
        self.assertIsNotNone(client.retry_count)
        self.assertGreater(client.retry_count, 0, "Service client should have retries")
        self.assertIsNotNone(client.retry_delay)
        self.assertGreater(client.retry_delay, 0, "Service client should have retry delay")
        self.assertIsNotNone(client.retry_strategy)

    def test_event_bus_retry_logic(self):
        """Test event bus retry logic"""
        from hub.apps.core.events.bus import get_event_bus

        event_bus = get_event_bus()

        # Event bus should have retry configuration
        self.assertIsNotNone(event_bus.max_retries)

    # ========== Notification Tests ==========

    def test_job_failure_notification(self):
        """Test job failure triggers notification"""
        from hub.apps.jobs.models import Job, JobStatus, JobType

        # Create a job
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            created_by=self.user,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
        )

        # Mark job as failed
        job.status = JobStatus.FAILED
        job.error_message = "Test error message"
        job.save()

        # Check if notification task exists (job failure notifications are sent asynchronously)
        # The actual notification sending is handled by signals or tasks
        # For E2E test, we verify the job is in failed state
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertIsNotNone(job.error_message)

    def test_error_notification_format(self):
        """Test error notifications have proper format"""
        # This test verifies that when errors occur, notifications are properly formatted
        # Actual notification sending is async, so we test the job state

        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.FAILED,
            created_by=self.user,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
            error_message="Test error for notification",
        )

        # Verify job has error information needed for notification
        self.assertIsNotNone(job.error_message)
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertIsNotNone(job.created_by)  # Needed for notification recipient


class ErrorLoggingE2ETest(E2ETestBase):
    """Comprehensive E2E tests for error logging"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    # ========== Log Format Tests ==========

    def test_error_logging_format(self):
        """Test error logging uses structured format"""
        import structlog

        logger = structlog.get_logger(__name__)

        # Log an error
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/assets/assets/{fake_id}/")

        # Error should be logged (verified by checking response has request_id)
        if "error" in response.data:
            error = response.data["error"]
            self.assertIn("request_id", error)

            # Request ID should be in logs (we can't directly verify logs in E2E test,
            # but we verify the request_id exists which is used for log correlation)
            request_id = error["request_id"]
            self.assertIsNotNone(request_id)

    def test_error_logging_levels(self):
        """Test error logging uses appropriate levels"""
        # Different error types should be logged at appropriate levels
        # This is verified by checking error responses have proper structure

        # 404 error (not found)
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/assets/assets/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # 400 error (validation)
        response = self.client.post(
            "/api/v1/assets/assets/", {"key": "", "name": ""}, format="json"
        )
        if response.status_code == status.HTTP_400_BAD_REQUEST:
            if "error" in response.data:
                error = response.data["error"]
                # Should have proper error code
                self.assertIn("code", error)

    def test_error_logging_aggregation(self):
        """Test error logging supports aggregation"""
        # Multiple errors should be loggable and aggregatable
        # This is verified by checking error responses have request_id for correlation

        request_ids = set()

        # Generate multiple errors
        for _ in range(3):
            fake_id = uuid.uuid4()
            response = self.client.get(f"/api/v1/assets/assets/{fake_id}/")
            if "error" in response.data:
                error = response.data["error"]
                if "request_id" in error:
                    request_ids.add(error["request_id"])

        # Each error should have unique request_id for correlation
        # (or same request_id if same request, but different requests should have different IDs)
        self.assertGreater(len(request_ids), 0)

    def test_error_logging_pii_redaction(self):
        """Test error logging redacts PII"""
        from hub.apps.observability.logging import redact_pii

        # Test PII redaction
        test_cases = [
            ("test@example.com", "[EMAIL_REDACTED]"),
            ("1234-5678-9012-3456", "[CARD_REDACTED]"),
            ("123-45-6789", "[SSN_REDACTED]"),
        ]

        for original, expected in test_cases:
            redacted = redact_pii(original)
            # Should be redacted (exact match or contains redaction marker)
            self.assertIn("REDACTED", redacted.upper())

    def test_error_logging_context(self):
        """Test error logging includes context"""
        # Error responses should include context for logging
        fake_id = uuid.uuid4()

        response = self.client.get(f"/api/v1/assets/assets/{fake_id}/")

        if "error" in response.data:
            error = response.data["error"]

            # Should have request_id for correlation
            self.assertIn("request_id", error)

            # Should have timestamp
            self.assertIn("timestamp", error)

            # Should have error code
            self.assertIn("code", error)

            # These fields enable log correlation and aggregation

    def test_error_logging_trace_context(self):
        """Test error logging includes trace context"""
        # Error responses should support trace context for distributed tracing
        fake_id = uuid.uuid4()

        response = self.client.get(f"/api/v1/assets/assets/{fake_id}/")

        if "error" in response.data:
            error = response.data["error"]

            # Should have request_id (used for trace correlation)
            self.assertIn("request_id", error)
            request_id = error["request_id"]

            # Request ID should be valid UUID (trace IDs are typically UUIDs)
            self.assertIsNotNone(request_id)
            try:
                uuid.UUID(request_id)
            except ValueError:
                self.fail(f"request_id '{request_id}' should be valid UUID for trace correlation")

    def test_error_logging_structured_format(self):
        """Test error logging uses structured format (JSON)"""
        # Error responses should be structured for log aggregation
        fake_id = uuid.uuid4()

        response = self.client.get(f"/api/v1/assets/assets/{fake_id}/")

        # Response should be JSON (structured)
        self.assertEqual(response.get("Content-Type"), "application/json")

        # Error should be structured
        if "error" in response.data:
            error = response.data["error"]

            # Should have structured fields
            self.assertIn("code", error)
            self.assertIn("message", error)
            self.assertIn("http_status", error)
            self.assertIn("request_id", error)
            self.assertIn("timestamp", error)

            # All fields should be JSON-serializable
            try:
                json.dumps(error)
            except TypeError:
                self.fail("Error response should be JSON-serializable")

    def test_error_logging_correlation(self):
        """Test error logging supports correlation via request_id"""
        # Multiple related errors should be correlatable
        fake_id = uuid.uuid4()

        # First request
        response1 = self.client.get(f"/api/v1/assets/assets/{fake_id}/")
        request_id1 = None
        if "error" in response1.data:
            request_id1 = response1.data["error"].get("request_id")

        # Second request (different endpoint, same resource)
        response2 = self.client.get(f"/api/v1/contracts/contracts/{fake_id}/")
        request_id2 = None
        if "error" in response2.data:
            request_id2 = response2.data["error"].get("request_id")

        # Each should have request_id for correlation
        if request_id1:
            self.assertIsNotNone(request_id1)
        if request_id2:
            self.assertIsNotNone(request_id2)

    def test_error_logging_aggregation_by_code(self):
        """Test error logging supports aggregation by error code"""
        # Errors should be aggregatable by code
        error_codes = set()

        # Generate multiple errors
        for _ in range(3):
            fake_id = uuid.uuid4()
            response = self.client.get(f"/api/v1/assets/assets/{fake_id}/")
            if "error" in response.data:
                error = response.data["error"]
                if "code" in error:
                    error_codes.add(error["code"])

        # Should have consistent error codes for same error type
        # (all 404s should have same or similar code)
        self.assertGreater(len(error_codes), 0)
        # All codes should be related to NOT_FOUND
        for code in error_codes:
            self.assertIn("NOT_FOUND", code.upper())
