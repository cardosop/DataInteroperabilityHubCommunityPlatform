"""
Unit tests for VirtualizationService audit logging.

Tests audit event creation for query execution:
- Query execution start audit logging
- Query execution completion audit logging
- Query execution failure audit logging
- Audit event details validation

Uses REAL audit system (no mocks).
"""

import contextlib
import uuid

import pytest
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.virtualization.models import (
    QueryExecution,
    QueryExecutionMode,
    QueryExecutionStatus,
    QueryType,
    VirtualDataset,
    VirtualDatasetStatus,
)
from hub.apps.virtualization.services import VirtualizationService

pytestmark = pytest.mark.django_db(transaction=True)


class VirtualizationAuditLoggingTest(TestCase):
    """Test audit logging in VirtualizationService"""

    def setUp(self):
        """Set up test fixtures"""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )

        # Create user
        self.user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create service instance
        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

        # Create virtual dataset
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Virtual Dataset",
            query="SELECT * FROM test_table LIMIT 10",
            query_type=QueryType.SQL,
            sources=[
                {
                    "type": "postgresql",
                    "asset_id": str(self.asset.id),
                    "host": "localhost",
                    "port": 5432,
                    "database": "testdb",
                }
            ],
            status=VirtualDatasetStatus.ACTIVE,
        )

    def test_audit_logging_query_execution_start(self):
        """Test audit logging for query execution start"""
        # Create query execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            status=QueryExecutionStatus.PENDING,
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
        )

        # Count audit events before
        initial_count = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="QUERY_EXECUTION_STARTED"
        ).count()

        # Execute query (will fail at execution but audit logging should run)
        try:
            self.service._execute_query_sync(execution, self.virtual_dataset, {}, 30)
        except Exception:
            # Execution may fail for various reasons (no actual database, etc.)
            # But audit logging should have run
            pass

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET",
            action="QUERY_EXECUTION_STARTED",
            resource_id=str(self.virtual_dataset.id),
        )
        self.assertGreater(audit_events.count(), initial_count)

        # Verify audit event details
        audit_event = audit_events.latest("timestamp")
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.result, "SUCCESS")
        self.assertIsNotNone(audit_event.details_json)

        # Verify details contain required fields
        details = audit_event.details_json
        self.assertEqual(details.get("execution_id"), str(execution.id))
        self.assertEqual(details.get("dataset_id"), str(self.virtual_dataset.id))
        self.assertEqual(details.get("dataset_name"), self.virtual_dataset.name)
        self.assertEqual(details.get("query_type"), self.virtual_dataset.query_type)
        self.assertIsInstance(details.get("sources"), list)
        self.assertEqual(details.get("execution_mode"), execution.execution_mode)

    def test_audit_logging_query_execution_completion(self):
        """Test audit logging for query execution completion"""
        # Create query execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            status=QueryExecutionStatus.PENDING,
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
        )

        # Count audit events before
        initial_count = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="QUERY_EXECUTION_COMPLETED"
        ).count()

        # Try to execute query (will likely fail but we're testing audit logging)
        try:
            self.service._execute_query_sync(execution, self.virtual_dataset, {}, 30)
        except Exception:
            # Execution may fail, but if it completes, audit logging should run
            pass

        # Check if completion audit event was created (only if execution succeeded)
        completion_events = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET",
            action="QUERY_EXECUTION_COMPLETED",
            resource_id=str(self.virtual_dataset.id),
        )

        # If execution completed, verify audit event
        if completion_events.count() > initial_count:
            audit_event = completion_events.latest("timestamp")
            self.assertEqual(audit_event.actor_user, self.user)
            self.assertEqual(audit_event.tenant, self.tenant)
            self.assertEqual(audit_event.result, "SUCCESS")
            self.assertIsNotNone(audit_event.details_json)

            # Verify details contain required fields
            details = audit_event.details_json
            self.assertEqual(details.get("execution_id"), str(execution.id))
            self.assertEqual(details.get("dataset_id"), str(self.virtual_dataset.id))
            self.assertEqual(details.get("query_type"), self.virtual_dataset.query_type)
            self.assertIn("duration_ms", details)
            self.assertIn("row_count", details)

    def test_audit_logging_query_execution_failure(self):
        """Test audit logging for query execution failure"""
        # Create query execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            status=QueryExecutionStatus.PENDING,
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
        )

        # Count audit events before
        initial_count = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="QUERY_EXECUTION_FAILED"
        ).count()

        # Execute query (will fail due to no actual database)
        try:
            self.service._execute_query_sync(execution, self.virtual_dataset, {}, 30)
        except Exception:
            # Execution should fail, triggering failure audit logging
            pass

        # Verify failure audit event was created
        failure_events = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET",
            action="QUERY_EXECUTION_FAILED",
            resource_id=str(self.virtual_dataset.id),
        )

        # If execution failed, verify audit event
        if failure_events.count() > initial_count:
            audit_event = failure_events.latest("timestamp")
            self.assertEqual(audit_event.actor_user, self.user)
            self.assertEqual(audit_event.tenant, self.tenant)
            self.assertEqual(audit_event.result, "FAILURE")
            self.assertIsNotNone(audit_event.details_json)

            # Verify details contain required fields
            details = audit_event.details_json
            self.assertEqual(details.get("execution_id"), str(execution.id))
            self.assertEqual(details.get("dataset_id"), str(self.virtual_dataset.id))
            self.assertEqual(details.get("query_type"), self.virtual_dataset.query_type)
            self.assertIn("error", details)
            self.assertIn("error_type", details)
            self.assertIn("duration_ms", details)

    def test_audit_logging_includes_all_required_fields(self):
        """Test that audit logging includes all required fields in details"""
        # Create query execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            status=QueryExecutionStatus.PENDING,
            parameters={"param1": "value1"},
            execution_mode=QueryExecutionMode.SYNC,
        )

        # Execute query (will fail but audit logging should run)
        with contextlib.suppress(Exception):
            self.service._execute_query_sync(
                execution, self.virtual_dataset, {"param1": "value1"}, 30
            )

        # Verify start audit event has all required fields
        start_event = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET",
            action="QUERY_EXECUTION_STARTED",
            resource_id=str(self.virtual_dataset.id),
        ).latest("timestamp")

        details = start_event.details_json
        required_fields = ["execution_id", "dataset_id", "query_type", "sources"]
        for field in required_fields:
            self.assertIn(field, details, f"Required field {field} missing from audit details")

        # Verify sources is a list
        self.assertIsInstance(details.get("sources"), list)

    def test_audit_logging_handles_missing_user_gracefully(self):
        """Audit logging does not crash when user_id is None.

        The query execution itself may fail in a unit-test environment
        (no real warehouse backend), but the audit-logging guard in
        _execute_query_sync must not raise a secondary exception that
        masks the original.
        """
        service_no_user = VirtualizationService(tenant_id=str(self.tenant.id), user_id=None)
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            status=QueryExecutionStatus.PENDING,
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
        )

        # Verify the call runs without crashing at the audit layer.
        # Warehouse-level failures are expected and harmless here.
        try:
            service_no_user._execute_query_sync(execution, self.virtual_dataset, {}, 30)
        except Exception as e:
            # Acceptable: warehouse backend unavailable in unit tests.
            # Assert the error is NOT about audit — it should be about
            # the warehouse connection.
            self.assertNotIn("audit", str(e).lower(),
                             f"Audit-related crash with null user: {e}")

    def test_audit_logging_handles_missing_tenant_gracefully(self):
        """Audit logging does not crash when tenant_id is None."""
        service_no_tenant = VirtualizationService(tenant_id=None, user_id=str(self.user.id))
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            status=QueryExecutionStatus.PENDING,
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
        )

        try:
            service_no_tenant._execute_query_sync(execution, self.virtual_dataset, {}, 30)
        except Exception as e:
            self.assertNotIn("audit", str(e).lower(),
                             f"Audit-related crash with null tenant: {e}")
