"""
Integration tests for security audit log storage.

Tests database persistence and querying of security audit logs.
"""

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from hub.apps.contracts.models import SecurityAuditLog
from hub.apps.contracts.odps_security_logging import (
    SecurityEventType,
    SecurityLogger,
)
from tests.factories import TenantFactory, UserFactory

User = get_user_model()


class SecurityAuditLogStorageIntegrationTest(TestCase):
    """Integration tests for security audit log storage."""

    def setUp(self):
        """Set up test fixtures."""
        self.security_logger = SecurityLogger()
        self.tenant1 = TenantFactory()
        self.tenant2 = TenantFactory()
        self.user1 = UserFactory(tenant=self.tenant1)
        self.user2 = UserFactory(tenant=self.tenant2)

    def test_security_audit_log_immutability(self):
        """Test that security audit logs are immutable (cannot be updated or deleted)."""
        # Create a log entry
        log = SecurityAuditLog.objects.create(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path="https://example.com/schema.json",
            tenant=self.tenant1,
            user=self.user1,
        )

        # Try to update (should raise ValueError)
        with self.assertRaises(ValueError) as cm:
            log.description = "Updated description"
            log.save()

        self.assertIn("immutable", str(cm.exception).lower())

        # Try to delete (should raise ValueError)
        with self.assertRaises(ValueError) as cm:
            log.delete()

        self.assertIn("immutable", str(cm.exception).lower())

    def test_security_audit_log_indexes(self):
        """Test that security audit log indexes work correctly."""
        # Create logs with different event types
        SecurityAuditLog.objects.create(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path="https://example.com/schema1.json",
            tenant=self.tenant1,
            user=self.user1,
        )
        SecurityAuditLog.objects.create(
            event_type=SecurityEventType.CACHE_HIT.value,
            ref_path="https://example.com/schema2.json",
            tenant=self.tenant1,
            user=self.user1,
        )
        SecurityAuditLog.objects.create(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED.value,
            ref_path="https://example.com/schema3.json",
            tenant=self.tenant2,
            user=self.user2,
        )

        # Query by event_type (should use index)
        external_refs = SecurityAuditLog.objects.filter(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value
        )
        self.assertEqual(external_refs.count(), 1)

        # Query by tenant (should use index)
        tenant1_logs = SecurityAuditLog.objects.filter(tenant=self.tenant1)
        self.assertEqual(tenant1_logs.count(), 2)

        # Query by tenant and event_type (should use composite index)
        tenant1_external = SecurityAuditLog.objects.filter(
            tenant=self.tenant1, event_type=SecurityEventType.EXTERNAL_REF_FETCH.value
        )
        self.assertEqual(tenant1_external.count(), 1)

    def test_security_audit_log_timestamp_ordering(self):
        """Test that security audit logs are ordered by timestamp."""
        now = timezone.now()

        # Create logs with different timestamps
        log1 = SecurityAuditLog.objects.create(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path="https://example.com/schema1.json",
            tenant=self.tenant1,
            timestamp=now - timedelta(hours=2),
        )
        log2 = SecurityAuditLog.objects.create(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path="https://example.com/schema2.json",
            tenant=self.tenant1,
            timestamp=now - timedelta(hours=1),
        )
        log3 = SecurityAuditLog.objects.create(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path="https://example.com/schema3.json",
            tenant=self.tenant1,
            timestamp=now,
        )

        # Query should return newest first (default ordering)
        logs = SecurityAuditLog.objects.all()
        self.assertEqual(logs[0].id, log3.id)
        self.assertEqual(logs[1].id, log2.id)
        self.assertEqual(logs[2].id, log1.id)

    def test_security_audit_log_filtering_by_time_range(self):
        """Test filtering security audit logs by time range."""
        now = timezone.now()

        # Clear any existing logs from setUp
        SecurityAuditLog.objects.all().delete()

        # Create logs at different times
        # Note: timestamp has auto_now_add=True and save() prevents updates, so we use update() directly
        log1 = SecurityAuditLog.objects.create(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path="https://example.com/schema1.json",
            tenant=self.tenant1,
        )
        SecurityAuditLog.objects.filter(id=log1.id).update(timestamp=now - timedelta(hours=3))
        log1.refresh_from_db()

        log2 = SecurityAuditLog.objects.create(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path="https://example.com/schema2.json",
            tenant=self.tenant1,
        )
        SecurityAuditLog.objects.filter(id=log2.id).update(timestamp=now - timedelta(hours=1))
        log2.refresh_from_db()

        log3 = SecurityAuditLog.objects.create(
            event_type=SecurityEventType.EXTERNAL_REF_FETCH.value,
            ref_path="https://example.com/schema3.json",
            tenant=self.tenant1,
        )
        SecurityAuditLog.objects.filter(id=log3.id).update(timestamp=now)
        log3.refresh_from_db()

        # Filter by start_date
        start_date = now - timedelta(hours=2)
        recent_logs = SecurityAuditLog.objects.filter(timestamp__gte=start_date)
        self.assertEqual(recent_logs.count(), 2)
        self.assertIn(log2, recent_logs)
        self.assertIn(log3, recent_logs)

        # Filter by end_date
        end_date = now - timedelta(hours=2)
        old_logs = SecurityAuditLog.objects.filter(timestamp__lte=end_date)
        self.assertEqual(old_logs.count(), 1)
        self.assertIn(log1, old_logs)

    def test_security_audit_log_filtering_by_ref_type(self):
        """Test filtering security audit logs by ref_type."""
        # Create logs with different ref types
        SecurityAuditLog.objects.create(
            event_type="REF_RESOLUTION_AUDIT",
            ref_type="external",
            ref_path="https://example.com/schema1.json",
            tenant=self.tenant1,
        )
        SecurityAuditLog.objects.create(
            event_type="REF_RESOLUTION_AUDIT",
            ref_type="internal",
            ref_path="#/definitions/Schema",
            tenant=self.tenant1,
        )
        SecurityAuditLog.objects.create(
            event_type="REF_RESOLUTION_AUDIT",
            ref_type="local",
            ref_path="./schema.json",
            tenant=self.tenant1,
        )

        # Filter by ref_type
        external_logs = SecurityAuditLog.objects.filter(ref_type="external")
        self.assertEqual(external_logs.count(), 1)

        internal_logs = SecurityAuditLog.objects.filter(ref_type="internal")
        self.assertEqual(internal_logs.count(), 1)

    def test_security_audit_log_filtering_by_cache_operation(self):
        """Test filtering security audit logs by cache operation."""
        # Create logs with different cache operations
        SecurityAuditLog.objects.create(
            event_type=SecurityEventType.CACHE_HIT.value,
            cache_operation="hit",
            ref_path="https://example.com/schema1.json",
            tenant=self.tenant1,
        )
        SecurityAuditLog.objects.create(
            event_type=SecurityEventType.CACHE_MISS.value,
            cache_operation="miss",
            ref_path="https://example.com/schema2.json",
            tenant=self.tenant1,
        )
        SecurityAuditLog.objects.create(
            event_type=SecurityEventType.CACHE_EVICTION.value,
            cache_operation="eviction",
            cache_key="odps_ref:abc123",
            eviction_reason="size_limit",
            tenant=self.tenant1,
        )

        # Filter by cache_operation
        hits = SecurityAuditLog.objects.filter(cache_operation="hit")
        self.assertEqual(hits.count(), 1)

        misses = SecurityAuditLog.objects.filter(cache_operation="miss")
        self.assertEqual(misses.count(), 1)

        evictions = SecurityAuditLog.objects.filter(cache_operation="eviction")
        self.assertEqual(evictions.count(), 1)
        self.assertEqual(evictions.first().eviction_reason, "size_limit")

    def test_security_audit_log_metadata_json(self):
        """Test that metadata_json stores additional data correctly."""
        metadata = {
            "operation_id": str(uuid.uuid4()),
            "duration_ms": 150.5,
            "size_bytes": 2048,
            "cache_hit": False,
            "custom_field": "custom_value",
        }

        log = SecurityAuditLog.objects.create(
            event_type="REF_RESOLUTION_AUDIT",
            ref_type="external",
            ref_path="https://example.com/schema.json",
            tenant=self.tenant1,
            metadata_json=metadata,
        )

        # Verify metadata is stored correctly
        self.assertEqual(log.metadata_json, metadata)
        self.assertEqual(log.metadata_json.get("operation_id"), metadata["operation_id"])
        self.assertEqual(log.metadata_json.get("duration_ms"), 150.5)

    def test_security_audit_log_complete_event_lifecycle(self):
        """Test complete event lifecycle: fetch, cache hit, cache miss, eviction."""
        ref_path = "https://example.com/schema.json"

        # 1. Cache miss
        self.security_logger.log_cache_operation(
            operation="miss",
            ref_path=ref_path,
            tenant_id=str(self.tenant1.id),
            user_id=str(self.user1.id),
        )

        # 2. External ref fetch
        self.security_logger.log_external_ref_fetch(
            ref_path=ref_path,
            success=True,
            tenant_id=str(self.tenant1.id),
            user_id=str(self.user1.id),
            cache_hit=False,
            size_bytes=1024,
        )

        # 3. Cache hit (subsequent request)
        self.security_logger.log_cache_operation(
            operation="hit",
            ref_path=ref_path,
            tenant_id=str(self.tenant1.id),
            user_id=str(self.user1.id),
        )

        # 4. Cache eviction (when cache is full)
        self.security_logger.log_cache_operation(
            operation="eviction",
            cache_key="odps_ref:abc123",
            eviction_reason="size_limit",
            tenant_id=str(self.tenant1.id),
            user_id=str(self.user1.id),
        )

        # Verify all events were logged
        logs = SecurityAuditLog.objects.filter(
            tenant=self.tenant1,
            user=self.user1,
        ).order_by("timestamp")

        self.assertEqual(logs.count(), 4)
        self.assertEqual(logs[0].event_type, SecurityEventType.CACHE_MISS.value)
        self.assertEqual(logs[1].event_type, SecurityEventType.EXTERNAL_REF_FETCH.value)
        self.assertEqual(logs[2].event_type, SecurityEventType.CACHE_HIT.value)
        self.assertEqual(logs[3].event_type, SecurityEventType.CACHE_EVICTION.value)
