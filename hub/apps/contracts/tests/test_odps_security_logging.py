"""
Unit tests for ODPS security logging and monitoring.

Tests verify that:
1. Security violation logs are formatted correctly
2. Audit trail logs are formatted correctly
3. Alert rules match events correctly
4. Log structures include required security tags
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

from django.test import TestCase

from hub.apps.contracts.models import SecurityAuditLog
from hub.apps.contracts.odps_security_logging import (
    DEFAULT_ALERT_RULES,
    RefResolutionAuditLog,
    SecurityAlertRule,
    SecurityEventType,
    SecurityLogger,
    SecuritySeverity,
    SecurityViolationLog,
    get_security_logger,
)


class ODPSecurityLoggingTest(TestCase):
    """Test ODPS security logging and monitoring"""

    def setUp(self):
        """Set up test fixtures"""
        self.security_logger = SecurityLogger()

    def test_security_violation_log_structure(self):
        """Test that security violation logs have correct structure"""
        violation_log = SecurityViolationLog(
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            severity=SecuritySeverity.HIGH.value,
            timestamp=datetime.now(UTC).isoformat(),
            violation_type="Path Traversal Attempt",
            description="Test path traversal",
            attempted_path="../../../etc/passwd",
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
        )

        log_dict = violation_log.to_log_dict()

        # Check required fields
        self.assertIn("security_event", log_dict)
        self.assertTrue(log_dict["security_event"])
        self.assertIn("security_type", log_dict)
        self.assertEqual(log_dict["security_type"], SecurityEventType.PATH_TRAVERSAL.value)
        self.assertIn("security_severity", log_dict)
        self.assertEqual(log_dict["security_severity"], SecuritySeverity.HIGH.value)
        self.assertIn("event_type", log_dict)
        self.assertEqual(log_dict["event_type"], SecurityEventType.PATH_TRAVERSAL.value)
        self.assertIn("severity", log_dict)
        self.assertIn("timestamp", log_dict)
        self.assertIn("violation_type", log_dict)
        self.assertIn("description", log_dict)

    def test_security_violation_log_to_dict_removes_none(self):
        """Test that to_dict() removes None values"""
        violation_log = SecurityViolationLog(
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            severity=SecuritySeverity.HIGH.value,
            timestamp=datetime.now(UTC).isoformat(),
            violation_type="Path Traversal Attempt",
            description="Test path traversal",
            attempted_path="../../../etc/passwd",
            tenant_id=None,  # None value
            user_id=None,  # None value
        )

        log_dict = violation_log.to_dict()

        # None values should be removed
        self.assertNotIn("tenant_id", log_dict)
        self.assertNotIn("user_id", log_dict)

        # Non-None values should be present
        self.assertIn("event_type", log_dict)
        self.assertEqual(log_dict["event_type"], SecurityEventType.PATH_TRAVERSAL.value)
        self.assertIn("attempted_path", log_dict)

    def test_log_security_violation_path_traversal(self):
        """Test logging a path traversal security violation"""
        with patch.object(self.security_logger.logger, "warning") as mock_warning:
            violation_log = self.security_logger.log_security_violation(
                event_type=SecurityEventType.PATH_TRAVERSAL,
                severity=SecuritySeverity.HIGH,
                violation_type="Path Traversal Attempt",
                description="Attempted to access file outside allowed directories",
                attempted_path="../../../etc/passwd",
                allowed_dirs=["./contracts/refs", "./odps-refs"],
            )

            # Verify log was called
            mock_warning.assert_called_once()
            call_args = mock_warning.call_args

            # Verify log event name
            self.assertEqual(call_args[0][0], "odps_security_violation")

            # Verify log structure
            log_dict = call_args[1]
            self.assertTrue(log_dict["security_event"])
            self.assertEqual(log_dict["security_type"], SecurityEventType.PATH_TRAVERSAL.value)
            self.assertEqual(log_dict["security_severity"], SecuritySeverity.HIGH.value)
            self.assertEqual(log_dict["attempted_path"], "../../../etc/passwd")

            # Verify returned log object
            self.assertIsInstance(violation_log, SecurityViolationLog)
            self.assertEqual(violation_log.event_type, SecurityEventType.PATH_TRAVERSAL.value)

            # Also verify DB persistence happened (not just the mock)
            self.assertTrue(
                SecurityAuditLog.objects.filter(
                    event_type=SecurityEventType.PATH_TRAVERSAL.value
                ).exists(),
                "Expected security event to be persisted to SecurityAuditLog",
            )

    def test_log_security_violation_url_denied(self):
        """Test logging a URL denied security violation"""
        with patch.object(self.security_logger.logger, "warning") as mock_warning:
            self.security_logger.log_security_violation(
                event_type=SecurityEventType.URL_DENIED,
                severity=SecuritySeverity.MEDIUM,
                violation_type="URL Denied by Denylist",
                description="Attempted to access URL that is in denylist",
                attempted_url="https://malicious.com/schema.yaml",
                url_pattern="https://*.malicious.com",
            )

            mock_warning.assert_called_once()
            log_dict = mock_warning.call_args[1]

            self.assertEqual(log_dict["security_type"], SecurityEventType.URL_DENIED.value)
            self.assertEqual(log_dict["attempted_url"], "https://malicious.com/schema.yaml")
            self.assertEqual(log_dict["url_pattern"], "https://*.malicious.com")

            # Also verify DB persistence happened (not just the mock)
            self.assertTrue(
                SecurityAuditLog.objects.filter(
                    event_type=SecurityEventType.URL_DENIED.value
                ).exists(),
                "Expected security event to be persisted to SecurityAuditLog",
            )

    def test_log_security_violation_critical_severity(self):
        """Test that critical severity logs at error level"""
        with patch.object(self.security_logger.logger, "error") as mock_error:
            self.security_logger.log_security_violation(
                event_type=SecurityEventType.PATH_TRAVERSAL,
                severity=SecuritySeverity.CRITICAL,
                violation_type="Critical Path Traversal",
                description="Critical security violation",
            )

            mock_error.assert_called_once()
            self.assertEqual(mock_error.call_args[0][0], "odps_security_violation")

            # Also verify DB persistence happened (not just the mock)
            self.assertTrue(
                SecurityAuditLog.objects.filter(
                    event_type=SecurityEventType.PATH_TRAVERSAL.value
                ).exists(),
                "Expected security event to be persisted to SecurityAuditLog",
            )

    def test_log_security_violation_low_severity(self):
        """Test that low severity logs at info level"""
        with patch.object(self.security_logger.logger, "info") as mock_info:
            self.security_logger.log_security_violation(
                event_type=SecurityEventType.INVALID_URL,
                severity=SecuritySeverity.LOW,
                violation_type="Invalid URL Format",
                description="URL format validation failed",
            )

            mock_info.assert_called_once()
            self.assertEqual(mock_info.call_args[0][0], "odps_security_violation")

            # Also verify DB persistence happened (not just the mock)
            self.assertTrue(
                SecurityAuditLog.objects.filter(
                    event_type=SecurityEventType.INVALID_URL.value
                ).exists(),
                "Expected security event to be persisted to SecurityAuditLog",
            )

    def test_ref_resolution_audit_log_structure(self):
        """Test that audit trail logs have correct structure"""
        audit_log = RefResolutionAuditLog(
            operation_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            duration_ms=125.5,
            ref_type="external",
            ref_path="https://example.com/schema.yaml",
            success=True,
        )

        log_dict = audit_log.to_log_dict()

        # Check required fields
        self.assertIn("audit_event", log_dict)
        self.assertTrue(log_dict["audit_event"])
        self.assertIn("audit_type", log_dict)
        self.assertEqual(log_dict["audit_type"], "ref_resolution")
        self.assertIn("operation_id", log_dict)
        self.assertIn("timestamp", log_dict)
        self.assertIn("duration_ms", log_dict)
        self.assertIn("ref_type", log_dict)
        self.assertIn("ref_path", log_dict)
        self.assertIn("success", log_dict)

    def test_log_ref_resolution_audit_success(self):
        """Test logging a successful ref resolution audit"""
        with patch.object(self.security_logger.logger, "info") as mock_info:
            operation_id = str(uuid.uuid4())
            audit_log = self.security_logger.log_ref_resolution_audit(
                operation_id=operation_id,
                ref_type="external",
                ref_path="https://example.com/schema.yaml",
                success=True,
                duration_ms=125.5,
                tenant_id=str(uuid.uuid4()),
                resolved_path="https://example.com/schema.yaml",
                size_bytes=1024,
                cache_hit=False,
            )

            mock_info.assert_called_once()
            call_args = mock_info.call_args

            # Verify log event name
            self.assertEqual(call_args[0][0], "odps_ref_resolution_audit")

            # Verify log structure
            log_dict = call_args[1]
            self.assertTrue(log_dict["audit_event"])
            self.assertEqual(log_dict["audit_type"], "ref_resolution")
            self.assertEqual(log_dict["operation_id"], operation_id)
            self.assertTrue(log_dict["success"])
            self.assertEqual(log_dict["ref_type"], "external")
            self.assertEqual(log_dict["size_bytes"], 1024)
            self.assertFalse(log_dict["cache_hit"])

            # Verify returned log object
            self.assertIsInstance(audit_log, RefResolutionAuditLog)

            # Also verify DB persistence happened (not just the mock)
            self.assertTrue(
                SecurityAuditLog.objects.filter(event_type="REF_RESOLUTION_AUDIT").exists(),
                "Expected security audit event to be persisted to SecurityAuditLog",
            )

    def test_log_ref_resolution_audit_failure(self):
        """Test logging a failed ref resolution audit"""
        with patch.object(self.security_logger.logger, "warning") as mock_warning:
            self.security_logger.log_ref_resolution_audit(
                operation_id=str(uuid.uuid4()),
                ref_type="local",
                ref_path="./schema.yaml",
                success=False,
                duration_ms=50.0,
                error_type="FileNotFoundError",
                error_message="File not found: ./schema.yaml",
            )

            mock_warning.assert_called_once()
            log_dict = mock_warning.call_args[1]

            self.assertFalse(log_dict["success"])
            self.assertEqual(log_dict["error_type"], "FileNotFoundError")
            self.assertEqual(log_dict["error_message"], "File not found: ./schema.yaml")

            # Also verify DB persistence happened (not just the mock)
            self.assertTrue(
                SecurityAuditLog.objects.filter(event_type="REF_RESOLUTION_AUDIT").exists(),
                "Expected security audit event to be persisted to SecurityAuditLog",
            )

    def test_log_ref_resolution_audit_with_security_violations(self):
        """Test logging audit trail with security violations"""
        with patch.object(self.security_logger.logger, "warning") as mock_warning:
            self.security_logger.log_ref_resolution_audit(
                operation_id=str(uuid.uuid4()),
                ref_type="local",
                ref_path="../../../etc/passwd",
                success=False,
                duration_ms=10.0,
                security_checks_passed=False,
                security_violations=["PATH_TRAVERSAL"],
            )

            mock_warning.assert_called_once()
            log_dict = mock_warning.call_args[1]

            self.assertFalse(log_dict["security_checks_passed"])
            self.assertIn("security_violations", log_dict)
            self.assertEqual(log_dict["security_violations"], ["PATH_TRAVERSAL"])

            # Also verify DB persistence happened (not just the mock)
            self.assertTrue(
                SecurityAuditLog.objects.filter(event_type="REF_RESOLUTION_AUDIT").exists(),
                "Expected security audit event to be persisted to SecurityAuditLog",
            )

    def test_security_alert_rule_matches_event_type(self):
        """Test that alert rule matches events by event type"""
        rule = SecurityAlertRule(
            name="test_rule",
            pattern="event_type:PATH_TRAVERSAL",
            threshold=5,
            window_seconds=300,
            severity=SecuritySeverity.HIGH,
            description="Test rule",
        )

        matching_event = SecurityViolationLog(
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            severity=SecuritySeverity.HIGH.value,
            timestamp=datetime.now(UTC).isoformat(),
            violation_type="Path Traversal",
            description="Test",
        )

        non_matching_event = SecurityViolationLog(
            event_type=SecurityEventType.URL_DENIED.value,
            severity=SecuritySeverity.HIGH.value,
            timestamp=datetime.now(UTC).isoformat(),
            violation_type="URL Denied",
            description="Test",
        )

        self.assertTrue(rule.matches(matching_event))
        self.assertFalse(rule.matches(non_matching_event))

    def test_security_alert_rule_matches_tenant_id(self):
        """Test that alert rule matches events by tenant_id"""
        tenant_id = str(uuid.uuid4())
        rule = SecurityAlertRule(
            name="test_rule",
            pattern="event_type:PATH_TRAVERSAL,tenant_id:" + tenant_id,
            threshold=5,
            window_seconds=300,
            severity=SecuritySeverity.HIGH,
            description="Test rule",
        )

        matching_event = SecurityViolationLog(
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            severity=SecuritySeverity.HIGH.value,
            timestamp=datetime.now(UTC).isoformat(),
            violation_type="Path Traversal",
            description="Test",
            tenant_id=tenant_id,
        )

        non_matching_event = SecurityViolationLog(
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            severity=SecuritySeverity.HIGH.value,
            timestamp=datetime.now(UTC).isoformat(),
            violation_type="Path Traversal",
            description="Test",
            tenant_id=str(uuid.uuid4()),  # Different tenant
        )

        self.assertTrue(rule.matches(matching_event))
        self.assertFalse(rule.matches(non_matching_event))

    def test_default_alert_rules_exist(self):
        """Test that default alert rules are defined"""
        self.assertGreater(len(DEFAULT_ALERT_RULES), 0)

        # Check that default rules have required attributes
        for rule in DEFAULT_ALERT_RULES:
            self.assertIsInstance(rule, SecurityAlertRule)
            self.assertIsNotNone(rule.name)
            self.assertIsNotNone(rule.pattern)
            self.assertGreater(rule.threshold, 0)
            self.assertGreater(rule.window_seconds, 0)
            self.assertIsInstance(rule.severity, SecuritySeverity)

    def test_get_security_logger_singleton(self):
        """Test that get_security_logger returns singleton instance"""
        logger1 = get_security_logger()
        logger2 = get_security_logger()

        self.assertIs(logger1, logger2)

    def test_security_violation_log_all_event_types(self):
        """Test that all security event types can be logged"""
        for event_type in SecurityEventType:
            with patch.object(self.security_logger.logger, "warning"):
                violation_log = self.security_logger.log_security_violation(
                    event_type=event_type,
                    severity=SecuritySeverity.MEDIUM,
                    violation_type=f"{event_type.value} Violation",
                    description=f"Test {event_type.value} violation",
                )

                self.assertEqual(violation_log.event_type, event_type.value)

        # Also verify DB persistence happened (not just the mock)
        for event_type in SecurityEventType:
            self.assertTrue(
                SecurityAuditLog.objects.filter(event_type=event_type.value).exists(),
                f"No SecurityAuditLog entry for event type {event_type.value}",
            )

    def test_security_violation_log_all_severities(self):
        """Test that all security severity levels can be logged"""
        severity_log_methods = {
            SecuritySeverity.CRITICAL: "error",
            SecuritySeverity.HIGH: "warning",
            SecuritySeverity.MEDIUM: "warning",
            SecuritySeverity.LOW: "info",
        }

        # Count before test to measure delta (avoid cross-test contamination).
        before = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.PATH_TRAVERSAL.value
        ).count()

        for severity, expected_method in severity_log_methods.items():
            with patch.object(self.security_logger.logger, expected_method) as mock_log:
                self.security_logger.log_security_violation(
                    event_type=SecurityEventType.PATH_TRAVERSAL,
                    severity=severity,
                    violation_type="Test Violation",
                    description="Test",
                )

                mock_log.assert_called_once()

        # Also verify DB persistence happened (not just the mock).
        severity_count = len(list(SecuritySeverity))
        after = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.PATH_TRAVERSAL.value
        ).count()
        self.assertGreaterEqual(
            after - before,
            severity_count,
            f"Expected at least {severity_count} new PATH_TRAVERSAL entries",
        )

    def test_ref_resolution_audit_all_ref_types(self):
        """Test that audit logs work for all ref types"""
        ref_types = ["internal", "local", "external"]

        # Count entries before test to measure delta (avoid cross-test contamination).
        before_count = SecurityAuditLog.objects.filter(event_type="REF_RESOLUTION_AUDIT").count()

        for ref_type in ref_types:
            with patch.object(self.security_logger.logger, "info"):
                audit_log = self.security_logger.log_ref_resolution_audit(
                    operation_id=str(uuid.uuid4()),
                    ref_type=ref_type,
                    ref_path=f"test-{ref_type}",
                    success=True,
                    duration_ms=100.0,
                )

                self.assertEqual(audit_log.ref_type, ref_type)

        # Verify at least the expected number of new entries were persisted
        after_count = SecurityAuditLog.objects.filter(event_type="REF_RESOLUTION_AUDIT").count()
        self.assertGreaterEqual(
            after_count - before_count,
            len(ref_types),
            f"Expected at least {len(ref_types)} new REF_RESOLUTION_AUDIT entries",
        )

    def test_audit_log_to_dict_removes_none(self):
        """Test that audit log to_dict() removes None values"""
        audit_log = RefResolutionAuditLog(
            operation_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            duration_ms=100.0,
            ref_type="external",
            ref_path="https://example.com/schema.yaml",
            success=True,
            tenant_id=None,  # None value
            user_id=None,  # None value
        )

        log_dict = audit_log.to_dict()

        # None values should be removed
        self.assertNotIn("tenant_id", log_dict)
        self.assertNotIn("user_id", log_dict)

        # Non-None values should be present
        self.assertIn("operation_id", log_dict)
        self.assertIn("ref_path", log_dict)

    def test_security_violation_log_with_metadata(self):
        """Test that security violation logs can include metadata"""
        metadata = {"custom_field": "custom_value", "additional_info": 123}

        violation_log = SecurityViolationLog(
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            severity=SecuritySeverity.HIGH.value,
            timestamp=datetime.now(UTC).isoformat(),
            violation_type="Path Traversal",
            description="Test",
            metadata=metadata,
        )

        log_dict = violation_log.to_dict()
        self.assertIn("metadata", log_dict)
        self.assertEqual(log_dict["metadata"], metadata)

    def test_audit_log_with_metadata(self):
        """Test that audit logs can include metadata"""
        metadata = {"source": "api", "version": "1.0"}

        audit_log = RefResolutionAuditLog(
            operation_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            duration_ms=100.0,
            ref_type="external",
            ref_path="https://example.com/schema.yaml",
            success=True,
            metadata=metadata,
        )

        log_dict = audit_log.to_dict()
        self.assertIn("metadata", log_dict)
        self.assertEqual(log_dict["metadata"], metadata)

    def test_security_logging_handles_unicode_characters(self):
        """Test that security logging handles unicode characters correctly."""
        violation_log = SecurityViolationLog(
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            severity=SecuritySeverity.HIGH.value,
            timestamp=datetime.now(UTC).isoformat(),
            violation_type="路径遍历尝试",
            description="测试路径遍历",
            attempted_path="../../../etc/passwd",
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
        )

        log_dict = violation_log.to_log_dict()
        # Should handle unicode characters
        self.assertIsNotNone(log_dict)
        self.assertIn("security_event", log_dict)

    def test_security_logging_handles_special_characters(self):
        """Test that security logging handles special characters correctly."""
        violation_log = SecurityViolationLog(
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            severity=SecuritySeverity.HIGH.value,
            timestamp=datetime.now(UTC).isoformat(),
            violation_type="Test & Co. (Special)",
            description="Test <description> & more",
            attempted_path="../../../etc/passwd",
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
        )

        log_dict = violation_log.to_log_dict()
        # Should handle special characters
        self.assertIsNotNone(log_dict)
        self.assertIn("security_event", log_dict)

    def test_security_logging_handles_very_large_messages(self):
        """Test that security logging handles very large messages correctly."""
        large_description = "A" * 100000  # 100KB string
        violation_log = SecurityViolationLog(
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            severity=SecuritySeverity.HIGH.value,
            timestamp=datetime.now(UTC).isoformat(),
            violation_type="Path Traversal Attempt",
            description=large_description,
            attempted_path="../../../etc/passwd",
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
        )

        log_dict = violation_log.to_log_dict()
        # Should handle very large messages
        self.assertIsNotNone(log_dict)
        self.assertIn("security_event", log_dict)

    def test_security_logging_handles_none_values(self):
        """Test that security logging handles None values correctly."""
        violation_log = SecurityViolationLog(
            event_type=SecurityEventType.PATH_TRAVERSAL.value,
            severity=SecuritySeverity.HIGH.value,
            timestamp=datetime.now(UTC).isoformat(),
            violation_type="Path Traversal Attempt",
            description=None,  # None value
            attempted_path="../../../etc/passwd",
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
        )

        log_dict = violation_log.to_log_dict()
        # Should handle None values gracefully
        self.assertIsNotNone(log_dict)
        self.assertIn("security_event", log_dict)

    def test_security_logging_handles_nested_structures(self):
        """Test that security logging handles nested structures correctly."""
        nested_metadata = {"level1": {"level2": {"level3": {"value": "deep"}}}}
        audit_log = RefResolutionAuditLog(
            operation_id=str(uuid.uuid4()),
            timestamp=datetime.now(UTC).isoformat(),
            duration_ms=100.0,
            ref_type="external",
            ref_path="https://example.com/schema.yaml",
            success=True,
            metadata=nested_metadata,
        )

        log_dict = audit_log.to_dict()
        # Should handle nested structures
        self.assertIsNotNone(log_dict)
        self.assertIn("metadata", log_dict)
