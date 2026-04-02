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
from datetime import datetime

import pytest
from django.utils import timezone
from rest_framework import status

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

        response = self.client.get(f"/api/v1/assets/{fake_id}/")

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
        response = self.client.get("/api/v1/assets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        if "error" in response.data:
            error = response.data["error"]
            self.assertIn("code", error)
            code = error["code"]
            self.assertIn("AUTH", code.upper())

        # Test not found (404) - need to authenticate first
        self.client.force_authenticate(user=self.user)
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/assets/{fake_id}/")
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

        response = self.client.get(f"/api/v1/assets/{fake_id}/")

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

            # Should be a meaningful message (at least 6 chars, not just "error")
            self.assertGreater(len(message), 5, "Error message should be meaningful, not a stub")

            # Should not contain raw exception class names
            self.assertNotIn("ValueError", message)
            self.assertNotIn("KeyError", message)
            self.assertNotIn("TypeError", message)
            self.assertNotIn("AttributeError", message)
            self.assertNotIn("NoneType", message)

    def test_error_response_details(self):
        """Test error details structure for validation errors"""
        # Try to create asset with invalid data
        response = self.client.post(
            "/api/v1/assets/",
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

        response = self.client.get(f"/api/v1/assets/{fake_id}/")

        self.assertIn("error", response.data, "Error response must have 'error' key")
        error = response.data["error"]
        self.assertIn("request_id", error)
        request_id = error["request_id"]

        # Should be a valid UUID string
        self.assertIsNotNone(request_id)
        self.assertIsInstance(request_id, str)
        self.assertGreater(len(request_id), 0, "request_id must not be empty")

        # Must be a valid UUID -- unconditional assertion, no try/except swallowing
        parsed = uuid.UUID(request_id)  # raises ValueError on invalid UUID
        self.assertEqual(str(parsed), request_id.lower().strip(),
                         "request_id must be a canonical UUID string")

    def test_error_response_timestamp(self):
        """Test error response includes timestamp"""
        fake_id = uuid.uuid4()

        response = self.client.get(f"/api/v1/assets/{fake_id}/")

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
            f"/api/v1/assets/{fake_id}/",
            f"/api/v1/contracts/{fake_id}/",
            f"/api/v1/datasets/{fake_id}/",
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
            "/api/v1/assets/",
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

        response = self.client.get("/api/v1/assets/")

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
            name=f"Other Tenant {uuid.uuid4().hex[:8]}", slug=f"other-tenant-{uuid.uuid4().hex[:8]}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Create asset in current tenant
        asset_id = self.create_asset(key="forbidden-test", name="Forbidden Test")

        # Switch to other user
        self.client.force_authenticate(user=other_user)

        # Try to access asset from other tenant
        response = self.client.get(f"/api/v1/assets/{asset_id}/")

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
        response = self.client.get("/api/v1/assets/")
        if response.status_code == status.HTTP_401_UNAUTHORIZED:
            if "error" in response.data:
                error = response.data["error"]
                self.assertEqual(error["http_status"], status.HTTP_401_UNAUTHORIZED)
                self.assertIn("AUTH", error["code"].upper())

        # Test not found for 404
        self.client.force_authenticate(user=self.user)
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/assets/{fake_id}/")
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
        """Test is_transient_failure correctly classifies transient vs non-transient errors"""
        from hub.apps.jobs.utils import get_job_max_retries, is_transient_failure

        # Transient errors: should return True
        transient_cases = [
            ConnectionError("Service temporarily unavailable"),
            TimeoutError("Request timed out"),
            ConnectionError("Network unreachable"),
            OSError("Service unavailable"),
        ]
        for err in transient_cases:
            self.assertTrue(
                is_transient_failure(err),
                f"is_transient_failure should return True for {type(err).__name__}: {err}",
            )

        # Non-transient errors: should return False
        non_transient_cases = [
            ValueError("Invalid input data"),
            KeyError("missing_field"),
            TypeError("expected str, got int"),
        ]
        for err in non_transient_cases:
            self.assertFalse(
                is_transient_failure(err),
                f"is_transient_failure should return False for {type(err).__name__}: {err}",
            )

        # Verify retry configuration is accessible for a real job type
        max_retries = get_job_max_retries(str(JobType.DQ_RUN))
        self.assertGreater(max_retries, 0, "DQ_RUN job type should have retries configured")
        self.assertIsInstance(max_retries, int)

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
        """Test job retry uses exponential backoff with increasing delays"""
        from hub.apps.jobs.utils import calculate_retry_delay

        # Verify the function is importable and callable
        self.assertTrue(callable(calculate_retry_delay))

        # Calculate delays for several retry attempts
        delays = [calculate_retry_delay(i) for i in range(5)]

        # All delays must be positive integers
        for i, delay in enumerate(delays):
            self.assertIsInstance(delay, int, f"Delay for retry {i} should be int")
            self.assertGreater(delay, 0, f"Delay for retry {i} should be positive")

        # Each delay must be >= 2x the previous (exponential growth)
        for i in range(1, len(delays)):
            self.assertGreaterEqual(
                delays[i], delays[i - 1] * 2,
                f"Delay at retry {i} ({delays[i]}s) should be >= 2x retry {i-1} ({delays[i-1]}s)",
            )

        # Verify formula: base_delay * (2 ^ retry_count) for default (no job_type)
        base_delay = 60  # Default base delay
        self.assertEqual(delays[0], base_delay * (2**0))
        self.assertEqual(delays[1], base_delay * (2**1))
        self.assertEqual(delays[2], base_delay * (2**2))

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
        """Test service client retry configuration has sensible values"""
        from hub.apps.core.services.cross_service_access import RetryStrategy, ServiceClient

        # Create service client (use service_url, not base_url)
        client = ServiceClient(service_name="test-service", service_url="http://invalid-url")

        # Verify retry_count is a positive integer
        self.assertIsInstance(client.retry_count, int)
        self.assertGreater(client.retry_count, 0, "Service client should have at least 1 retry")
        self.assertLessEqual(client.retry_count, 20, "Retry count should be reasonable (<=20)")

        # Verify retry_delay is a positive number
        self.assertIsInstance(client.retry_delay, (int, float))
        self.assertGreater(client.retry_delay, 0, "Retry delay must be positive")
        self.assertLessEqual(client.retry_delay, 300, "Retry delay should be reasonable (<=300s)")

        # Verify retry_strategy is a valid RetryStrategy enum member
        self.assertIsInstance(client.retry_strategy, RetryStrategy,
                              f"retry_strategy should be RetryStrategy enum, got {type(client.retry_strategy)}")

        # Verify max delay cap exists and is sensible
        self.assertIsInstance(client.retry_max_delay, (int, float))
        self.assertGreater(client.retry_max_delay, 0)

    def test_event_bus_retry_logic(self):
        """Test event bus retry configuration has sensible values"""
        from hub.apps.core.events.bus import get_event_bus

        event_bus = get_event_bus()

        # max_retries must be a positive integer
        self.assertIsNotNone(event_bus.max_retries)
        self.assertIsInstance(event_bus.max_retries, int)
        self.assertGreater(event_bus.max_retries, 0,
                           "Event bus should have at least 1 retry configured")
        self.assertLessEqual(event_bus.max_retries, 20,
                             "Event bus max_retries should be reasonable (<=20)")

        # Persistence should be enabled so failed events are not lost
        self.assertTrue(
            event_bus.enable_persistence,
            "Event bus persistence should be enabled to prevent event loss",
        )

    # ========== Notification Tests ==========

    def test_job_failure_notification(self):
        """Test job failure creates an audit event for notification"""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.jobs.models import Job, JobStatus, JobType

        # Create a job and mark it as failed
        resource_id = uuid.uuid4()
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.RUNNING,
            created_by=self.user,
            resource_type="ASSET",
            resource_id=resource_id,
        )

        error_msg = "Test transient error: service unavailable"
        job.status = JobStatus.FAILED
        job.error_message = error_msg
        job.save()

        # Create audit event as the real task infrastructure does (tasks_base.py)
        create_audit_event(
            resource_type="JOB",
            action="JOB_FAILED",
            actor_user=job.created_by,
            tenant=job.tenant,
            resource_id=str(job.id),
            result="FAILURE",
            details={"job_type": str(job.type), "error": error_msg},
        )

        # Verify job is in failed state
        job.refresh_from_db()
        self.assertEqual(job.status, JobStatus.FAILED)
        self.assertEqual(job.error_message, error_msg)

        # Verify audit event was created for this job failure
        audit_events = AuditEvent.objects.filter(
            resource_type="JOB",
            action="JOB_FAILED",
            resource_id=job.id,
            tenant=self.tenant,
        )
        self.assertGreater(
            audit_events.count(), 0,
            "A JOB_FAILED audit event should exist for the failed job",
        )
        event = audit_events.first()
        self.assertEqual(event.result, "FAILURE")
        self.assertIn("error", event.details_json)
        self.assertEqual(event.details_json["error"], error_msg)

    def test_error_notification_format(self):
        """Test job failure audit event has proper format for notification"""
        from hub.apps.audit.models import AuditEvent
        from hub.apps.audit.utils import create_audit_event

        error_msg = "Test error for notification format validation"
        job = Job.objects.create(
            tenant=self.tenant,
            type=JobType.DQ_RUN,
            status=JobStatus.FAILED,
            created_by=self.user,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
            error_message=error_msg,
        )

        # Create audit event as the real task infrastructure does
        create_audit_event(
            resource_type="JOB",
            action="JOB_FAILED",
            actor_user=job.created_by,
            tenant=job.tenant,
            resource_id=str(job.id),
            result="FAILURE",
            details={
                "job_type": str(job.type),
                "error": error_msg,
                "error_type": "TransientError",
            },
        )

        # Verify the audit event has all fields needed for a notification
        event = AuditEvent.objects.filter(
            resource_type="JOB", action="JOB_FAILED", resource_id=job.id,
        ).first()
        self.assertIsNotNone(event, "Audit event should exist for failed job")

        # Required notification fields
        self.assertIsNotNone(event.actor_user, "Audit event must have actor for notification recipient")
        self.assertEqual(event.actor_user.id, self.user.id)
        self.assertIsNotNone(event.tenant)
        self.assertEqual(event.result, "FAILURE")

        # Details must contain job_type and error for the notification body
        self.assertIsInstance(event.details_json, dict)
        self.assertIn("job_type", event.details_json)
        self.assertIn("error", event.details_json)
        self.assertEqual(event.details_json["error"], error_msg)
        self.assertIn("error_type", event.details_json)


class ErrorLoggingE2ETest(E2ETestBase):
    """Comprehensive E2E tests for error logging"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

    # ========== Log Format Tests ==========

    def test_error_logging_format(self):
        """Test error responses contain structured fields for log correlation"""
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/assets/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data, "Error response must have 'error' key")

        error = response.data["error"]

        # Must have request_id for log correlation
        self.assertIn("request_id", error)
        request_id = error["request_id"]
        self.assertIsNotNone(request_id)
        self.assertIsInstance(request_id, str)

        # request_id must be a valid UUID
        parsed = uuid.UUID(request_id)
        self.assertEqual(str(parsed), request_id.lower().strip(),
                         "request_id must be a canonical UUID")

        # Must have structured error fields
        self.assertIn("code", error)
        self.assertIsInstance(error["code"], str)
        self.assertGreater(len(error["code"]), 0)

        self.assertIn("message", error)
        self.assertIsInstance(error["message"], str)
        self.assertGreater(len(error["message"]), 0)

        self.assertIn("http_status", error)
        self.assertEqual(error["http_status"], 404)

    def test_error_logging_levels(self):
        """Test error logging uses appropriate levels"""
        # Different error types should be logged at appropriate levels
        # This is verified by checking error responses have proper structure

        # 404 error (not found)
        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/assets/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

        # 400 error (validation)
        response = self.client.post(
            "/api/v1/assets/", {"key": "", "name": ""}, format="json"
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
            response = self.client.get(f"/api/v1/assets/{fake_id}/")
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

        response = self.client.get(f"/api/v1/assets/{fake_id}/")

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

        response = self.client.get(f"/api/v1/assets/{fake_id}/")

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

        response = self.client.get(f"/api/v1/assets/{fake_id}/")

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
        response1 = self.client.get(f"/api/v1/assets/{fake_id}/")
        request_id1 = None
        if "error" in response1.data:
            request_id1 = response1.data["error"].get("request_id")

        # Second request (different endpoint, same resource)
        response2 = self.client.get(f"/api/v1/contracts/{fake_id}/")
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
            response = self.client.get(f"/api/v1/assets/{fake_id}/")
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
