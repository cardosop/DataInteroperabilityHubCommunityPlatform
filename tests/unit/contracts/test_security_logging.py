"""
Unit tests for ODPS security logging.

Tests security logging functionality including:
- External ref fetch logging
- Rate limit violation logging
- Cache operation logging
- Security violation logging
"""

from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.contracts.odps_security_logging import (
    SecurityEventType,
    SecurityLogger,
    SecuritySeverity,
    SecurityViolationLog,
)
from tests.factories import TenantFactory, UserFactory

User = get_user_model()


class SecurityLoggerTest(TestCase):
    """Test SecurityLogger class."""

    def setUp(self):
        """Set up test fixtures."""
        self.security_logger = SecurityLogger()
        self.tenant = TenantFactory()
        self.user = UserFactory(tenant=self.tenant)

    def test_log_security_violation_creates_log(self):
        """Test that log_security_violation creates a SecurityViolationLog."""
        violation_log = self.security_logger.log_security_violation(
            event_type=SecurityEventType.PATH_TRAVERSAL,
            severity=SecuritySeverity.HIGH,
            violation_type="Path Traversal Attempt",
            description="Attempted to access file outside allowed directories",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            attempted_path="../../../etc/passwd",
        )

        self.assertIsInstance(violation_log, SecurityViolationLog)
        self.assertEqual(violation_log.event_type, SecurityEventType.PATH_TRAVERSAL.value)
        self.assertEqual(violation_log.severity, SecuritySeverity.HIGH.value)
        self.assertEqual(violation_log.violation_type, "Path Traversal Attempt")
        self.assertEqual(violation_log.attempted_path, "../../../etc/passwd")

    def test_log_security_violation_persists_to_db(self):
        """Test that log_security_violation persists to database."""
        from hub.apps.contracts.models import SecurityAuditLog

        initial_count = SecurityAuditLog.objects.count()

        self.security_logger.log_security_violation(
            event_type=SecurityEventType.PATH_TRAVERSAL,
            severity=SecuritySeverity.HIGH,
            violation_type="Path Traversal Attempt",
            description="Test violation",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Should have created one audit log entry
        self.assertEqual(SecurityAuditLog.objects.count(), initial_count + 1)
        log_entry = SecurityAuditLog.objects.latest("timestamp")
        # Implementation stores the specific event type (PATH_TRAVERSAL) for audit trail
        self.assertEqual(log_entry.event_type, SecurityEventType.PATH_TRAVERSAL.value)
        self.assertEqual(log_entry.severity, SecuritySeverity.HIGH.value)
        self.assertEqual(log_entry.tenant_id, self.tenant.id)
        self.assertEqual(log_entry.user_id, self.user.id)

    def test_log_external_ref_fetch_creates_log(self):
        """Test that log_external_ref_fetch creates a log entry."""
        from hub.apps.contracts.models import SecurityAuditLog

        initial_count = SecurityAuditLog.objects.count()

        self.security_logger.log_external_ref_fetch(
            ref_path="https://example.com/schema.json",
            success=True,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            duration_ms=100.5,
            size_bytes=1024,
            cache_hit=False,
        )

        # Should have created one audit log entry
        self.assertEqual(SecurityAuditLog.objects.count(), initial_count + 1)
        log_entry = SecurityAuditLog.objects.latest("timestamp")
        self.assertEqual(log_entry.event_type, SecurityEventType.EXTERNAL_REF_FETCH.value)
        self.assertEqual(log_entry.ref_path, "https://example.com/schema.json")
        self.assertEqual(log_entry.ref_type, "external")
        self.assertEqual(log_entry.tenant_id, self.tenant.id)
        self.assertEqual(log_entry.user_id, self.user.id)
        self.assertFalse(log_entry.metadata_json.get("cache_hit"))

    def test_log_external_ref_fetch_with_cache_hit(self):
        """Test that log_external_ref_fetch logs cache hits correctly."""
        from hub.apps.contracts.models import SecurityAuditLog

        self.security_logger.log_external_ref_fetch(
            ref_path="https://example.com/schema.json",
            success=True,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            cache_hit=True,
        )

        log_entry = SecurityAuditLog.objects.latest("timestamp")
        self.assertTrue(log_entry.metadata_json.get("cache_hit"))

    def test_log_rate_limit_violation_creates_log(self):
        """Test that log_rate_limit_violation creates a log entry."""
        from hub.apps.contracts.models import SecurityAuditLog

        initial_count = SecurityAuditLog.objects.count()

        self.security_logger.log_rate_limit_violation(
            level="global",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            ref_path="https://example.com/schema.json",
            retry_after=3600.0,
        )

        # Should have created one audit log entry
        self.assertEqual(SecurityAuditLog.objects.count(), initial_count + 1)
        log_entry = SecurityAuditLog.objects.latest("timestamp")
        self.assertEqual(log_entry.event_type, SecurityEventType.RATE_LIMIT_EXCEEDED.value)
        self.assertEqual(log_entry.rate_limit_level, "global")
        self.assertEqual(log_entry.severity, SecuritySeverity.MEDIUM.value)
        self.assertEqual(log_entry.tenant_id, self.tenant.id)
        self.assertEqual(log_entry.user_id, self.user.id)

    def test_log_cache_operation_hit(self):
        """Test that log_cache_operation logs cache hits."""
        from hub.apps.contracts.models import SecurityAuditLog

        initial_count = SecurityAuditLog.objects.count()

        self.security_logger.log_cache_operation(
            operation="hit",
            ref_path="https://example.com/schema.json",
            cache_key="odps_ref:abc123",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Should have created one audit log entry
        self.assertEqual(SecurityAuditLog.objects.count(), initial_count + 1)
        log_entry = SecurityAuditLog.objects.latest("timestamp")
        self.assertEqual(log_entry.event_type, SecurityEventType.CACHE_HIT.value)
        self.assertEqual(log_entry.cache_operation, "hit")
        self.assertEqual(log_entry.cache_key, "odps_ref:abc123")

    def test_log_cache_operation_miss(self):
        """Test that log_cache_operation logs cache misses."""
        from hub.apps.contracts.models import SecurityAuditLog

        self.security_logger.log_cache_operation(
            operation="miss",
            ref_path="https://example.com/schema.json",
            tenant_id=str(self.tenant.id),
        )

        log_entry = SecurityAuditLog.objects.latest("timestamp")
        self.assertEqual(log_entry.event_type, SecurityEventType.CACHE_MISS.value)
        self.assertEqual(log_entry.cache_operation, "miss")

    def test_log_cache_operation_eviction(self):
        """Test that log_cache_operation logs cache evictions."""
        from hub.apps.contracts.models import SecurityAuditLog

        self.security_logger.log_cache_operation(
            operation="eviction",
            cache_key="odps_ref:abc123",
            eviction_reason="size_limit",
            tenant_id=str(self.tenant.id),
        )

        log_entry = SecurityAuditLog.objects.latest("timestamp")
        self.assertEqual(log_entry.event_type, SecurityEventType.CACHE_EVICTION.value)
        self.assertEqual(log_entry.cache_operation, "eviction")
        self.assertEqual(log_entry.eviction_reason, "size_limit")

    def test_log_ref_resolution_audit_creates_log(self):
        """Test that log_ref_resolution_audit creates a log entry."""
        from hub.apps.contracts.models import SecurityAuditLog

        initial_count = SecurityAuditLog.objects.count()

        self.security_logger.log_ref_resolution_audit(
            operation_id="test-op-123",
            ref_type="external",
            ref_path="https://example.com/schema.json",
            success=True,
            duration_ms=150.0,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            cache_hit=False,
            size_bytes=2048,
        )

        # Should have created one audit log entry
        self.assertEqual(SecurityAuditLog.objects.count(), initial_count + 1)
        log_entry = SecurityAuditLog.objects.latest("timestamp")
        self.assertEqual(log_entry.event_type, "REF_RESOLUTION_AUDIT")
        self.assertEqual(log_entry.ref_type, "external")
        self.assertEqual(log_entry.ref_path, "https://example.com/schema.json")
        self.assertTrue(log_entry.metadata_json.get("success"))
        self.assertEqual(log_entry.metadata_json.get("operation_id"), "test-op-123")

    def test_log_security_violation_without_tenant_user(self):
        """Test that log_security_violation works without tenant/user."""
        from hub.apps.contracts.models import SecurityAuditLog

        initial_count = SecurityAuditLog.objects.count()

        self.security_logger.log_security_violation(
            event_type=SecurityEventType.INVALID_URL,
            severity=SecuritySeverity.LOW,
            violation_type="Invalid URL",
            description="Invalid URL format",
        )

        # Should still create log entry
        self.assertEqual(SecurityAuditLog.objects.count(), initial_count + 1)
        log_entry = SecurityAuditLog.objects.latest("timestamp")
        self.assertIsNone(log_entry.tenant)
        self.assertIsNone(log_entry.user)

    def test_log_external_ref_fetch_with_error(self):
        """Test that log_external_ref_fetch logs errors correctly."""
        from hub.apps.contracts.models import SecurityAuditLog

        self.security_logger.log_external_ref_fetch(
            ref_path="https://example.com/schema.json",
            success=False,
            tenant_id=str(self.tenant.id),
            error_message="Connection timeout",
        )

        log_entry = SecurityAuditLog.objects.latest("timestamp")
        self.assertFalse(log_entry.metadata_json.get("success"))
        self.assertEqual(log_entry.metadata_json.get("error_message"), "Connection timeout")

    def test_log_cache_operation_invalid_operation(self):
        """Test that log_cache_operation ignores invalid operations."""
        from hub.apps.contracts.models import SecurityAuditLog

        initial_count = SecurityAuditLog.objects.count()

        # Invalid operation should not create log entry
        self.security_logger.log_cache_operation(
            operation="invalid",
            ref_path="https://example.com/schema.json",
        )

        # Should not have created any log entry
        self.assertEqual(SecurityAuditLog.objects.count(), initial_count)
