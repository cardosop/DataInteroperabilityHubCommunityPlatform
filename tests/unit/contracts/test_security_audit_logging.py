"""
Unit tests for security audit logging enhancements.

Tests the enhanced security logging methods:
- log_external_ref_fetch
- log_rate_limit_violation
- log_cache_operation
- Database persistence
"""

import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.contracts.models import SecurityAuditLog
from hub.apps.contracts.odps_security_logging import (
    SecurityEventType,
    SecurityLogger,
    SecuritySeverity,
)
from tests.factories import TenantFactory, UserFactory

User = get_user_model()


class SecurityAuditLoggingUnitTest(TestCase):
    """Unit tests for security audit logging enhancements."""

    def setUp(self):
        """Set up test fixtures."""
        self.security_logger = SecurityLogger()
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)

    def test_log_external_ref_fetch_success(self):
        """Test logging external ref fetch (success)."""
        ref_path = "https://example.com/schema.json"

        # Log external ref fetch
        self.security_logger.log_external_ref_fetch(
            ref_path=ref_path,
            success=True,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            duration_ms=100.5,
            size_bytes=1024,
            cache_hit=False,
        )

        # Verify log was created in database
        log = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path=ref_path,
            tenant=self.tenant,
            user=self.user,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.ref_type, "external")
        self.assertEqual(log.metadata_json.get("success"), True)
        self.assertEqual(log.metadata_json.get("duration_ms"), 100.5)
        self.assertEqual(log.metadata_json.get("size_bytes"), 1024)
        self.assertEqual(log.metadata_json.get("cache_hit"), False)

    def test_log_external_ref_fetch_cache_hit(self):
        """Test logging external ref fetch (cache hit)."""
        ref_path = "https://example.com/schema.json"

        # Log external ref fetch from cache
        self.security_logger.log_external_ref_fetch(
            ref_path=ref_path,
            success=True,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            duration_ms=5.0,
            size_bytes=1024,
            cache_hit=True,
        )

        # Verify log was created
        log = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path=ref_path,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.metadata_json.get("cache_hit"), True)

    def test_log_external_ref_fetch_failure(self):
        """Test logging external ref fetch (failure)."""
        ref_path = "https://example.com/schema.json"
        error_message = "Connection timeout"

        # Log external ref fetch failure
        self.security_logger.log_external_ref_fetch(
            ref_path=ref_path,
            success=False,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            error_message=error_message,
        )

        # Verify log was created
        log = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path=ref_path,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.metadata_json.get("success"), False)
        self.assertEqual(log.metadata_json.get("error_message"), error_message)

    def test_log_rate_limit_violation(self):
        """Test logging rate limit violation."""
        ref_path = "https://example.com/schema.json"
        level = "global"
        retry_after = 3600.0

        # Log rate limit violation
        self.security_logger.log_rate_limit_violation(
            level=level,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            ref_path=ref_path,
            retry_after=retry_after,
        )

        # Verify log was created
        log = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value,
            rate_limit_level=level,
            tenant=self.tenant,
            user=self.user,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.severity, SecuritySeverity.MEDIUM.value)
        self.assertEqual(log.ref_path, ref_path)
        self.assertEqual(log.metadata_json.get("retry_after"), retry_after)

    def test_log_cache_hit(self):
        """Test logging cache hit."""
        ref_path = "https://example.com/schema.json"
        cache_key = "odps_ref:abc123"

        # Log cache hit
        self.security_logger.log_cache_operation(
            operation="hit",
            ref_path=ref_path,
            cache_key=cache_key,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify log was created
        log = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.CACHE_HIT.value,
            cache_operation="hit",
            ref_path=ref_path,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.cache_key, cache_key)

    def test_log_cache_miss(self):
        """Test logging cache miss."""
        ref_path = "https://example.com/schema.json"

        # Log cache miss
        self.security_logger.log_cache_operation(
            operation="miss",
            ref_path=ref_path,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify log was created
        log = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.CACHE_MISS.value,
            cache_operation="miss",
        ).first()

        self.assertIsNotNone(log)

    def test_log_cache_eviction(self):
        """Test logging cache eviction."""
        cache_key = "odps_ref:abc123"
        eviction_reason = "size_limit"

        # Log cache eviction
        self.security_logger.log_cache_operation(
            operation="eviction",
            cache_key=cache_key,
            eviction_reason=eviction_reason,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify log was created
        log = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.CACHE_EVICTION.value,
            cache_operation="eviction",
            eviction_reason=eviction_reason,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.cache_key, cache_key)

    def test_log_security_violation_persistence(self):
        """Test that security violations are persisted to database."""
        # Log security violation
        self.security_logger.log_security_violation(
            event_type=SecurityEventType.PATH_TRAVERSAL,
            severity=SecuritySeverity.HIGH,
            violation_type="Path Traversal Attempt",
            description="Attempted to access file outside allowed directories",
            attempted_path="../../../etc/passwd",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify log was created in database
        # Security violations are persisted with their actual event_type (PATH_TRAVERSAL), not SECURITY_VIOLATION
        log = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            violation_type="Path Traversal Attempt",
            tenant=self.tenant,
            user=self.user,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.severity, SecuritySeverity.HIGH.value)
        self.assertEqual(log.attempted_path, "../../../etc/passwd")

    def test_log_ref_resolution_audit_persistence(self):
        """Test that ref resolution audits are persisted to database."""
        operation_id = str(uuid.uuid4())

        # Log ref resolution audit
        self.security_logger.log_ref_resolution_audit(
            operation_id=operation_id,
            ref_type="external",
            ref_path="https://example.com/schema.json",
            success=True,
            duration_ms=150.0,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            cache_hit=False,
            size_bytes=2048,
        )

        # Verify log was created in database
        log = SecurityAuditLog.objects.filter(
            event_type="REF_RESOLUTION_AUDIT",
            tenant=self.tenant,
            user=self.user,
        ).first()

        self.assertIsNotNone(log)
        self.assertEqual(log.ref_type, "external")
        self.assertEqual(log.metadata_json.get("operation_id"), operation_id)
        self.assertEqual(log.metadata_json.get("success"), True)
        self.assertEqual(log.metadata_json.get("cache_hit"), False)

    def test_logging_without_tenant_or_user(self):
        """Test logging works without tenant or user."""
        ref_path = "https://example.com/schema.json"

        # Log without tenant/user
        self.security_logger.log_external_ref_fetch(
            ref_path=ref_path,
            success=True,
        )

        # Verify log was created (tenant/user should be None)
        log = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path=ref_path,
        ).first()

        self.assertIsNotNone(log)
        self.assertIsNone(log.tenant)
        self.assertIsNone(log.user)

    def test_logging_with_invalid_tenant_id(self):
        """Test logging handles invalid tenant_id gracefully."""
        invalid_tenant_id = str(uuid.uuid4())
        ref_path = "https://example.com/schema.json"

        # Log with invalid tenant_id (should not raise error)
        self.security_logger.log_external_ref_fetch(
            ref_path=ref_path,
            success=True,
            tenant_id=invalid_tenant_id,
        )

        # Verify log was created (tenant should be None)
        log = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path=ref_path,
        ).first()

        self.assertIsNotNone(log)
        self.assertIsNone(log.tenant)

    def test_logging_with_invalid_user_id(self):
        """Test logging handles invalid user_id gracefully."""
        invalid_user_id = str(uuid.uuid4())
        ref_path = "https://example.com/schema.json"

        # Log with invalid user_id (should not raise error)
        self.security_logger.log_external_ref_fetch(
            ref_path=ref_path,
            success=True,
            user_id=invalid_user_id,
        )

        # Verify log was created (user should be None)
        log = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path=ref_path,
        ).first()

        self.assertIsNotNone(log)
        self.assertIsNone(log.user)

    def test_logging_persistence_failure_does_not_raise(self):
        """Test that database persistence failures don't raise exceptions."""
        ref_path = "https://example.com/schema.json"

        # Mock database error
        with patch("hub.apps.contracts.models.SecurityAuditLog.objects.create") as mock_create:
            mock_create.side_effect = Exception("Database error")

            # Logging should not raise exception
            self.security_logger.log_external_ref_fetch(
                ref_path=ref_path,
                success=True,
            )

            # Should have attempted to create log
            mock_create.assert_called_once()
