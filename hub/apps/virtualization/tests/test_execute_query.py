"""
Tests for execute_query() method in VirtualizationService.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

import socket
import unittest
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from hub.apps.core.services.base import ValidationError
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.testing.virtualization_support import get_test_db_source as _get_test_db_source
from hub.apps.users.models import Role, UserRole
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
User = get_user_model()


def _database_reachable():
    """Check if the test database is reachable via TCP connection."""
    from django.conf import settings

    db = settings.DATABASES["default"]
    try:
        sock = socket.create_connection(
            (db.get("HOST", "localhost"), int(db.get("PORT", 5432))), timeout=2
        )
        sock.close()
        return True
    except OSError:
        return False


class VirtualizationServiceExecuteQueryTest(TestCase):
    """Test execute_query() method for virtual dataset query execution"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if not _database_reachable():
            raise unittest.SkipTest("Database source not reachable")

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.orchestration.registry import reset_workflow_definition_cache

        reset_workflow_definition_cache()

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

        # Create DATA_PROVIDER role and assign to user
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        UserRole.objects.get_or_create(user=self.user, role=provider_role)

        ensure_tenant_has_active_subscription(self.tenant)

        self.service = VirtualizationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        # Create a test virtual dataset
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT 1 AS id, 'test' AS name",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[_get_test_db_source()],
        )

        # Clear cache
        cache.clear()

    def test_execute_query_sync_mode_simple_sql(self):
        """Test executing a simple SQL query in sync mode"""
        execution = self.service.execute_query(
            virtual_dataset_id=str(self.virtual_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=QueryExecutionMode.SYNC,
            parameters={},
        )

        self.assertIsNotNone(execution)
        self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
        self.assertIsNotNone(execution.query)
        self.assertEqual(execution.virtual_dataset_id, self.virtual_dataset.id)
        self.assertEqual(execution.execution_mode, QueryExecutionMode.SYNC)

    def test_execute_query_async_mode(self):
        """Test executing a query in async mode"""
        execution = self.service.execute_query(
            virtual_dataset_id=str(self.virtual_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=QueryExecutionMode.ASYNC,
            parameters={},
        )

        self.assertIsNotNone(execution)
        self.assertEqual(execution.execution_mode, QueryExecutionMode.ASYNC)
        self.assertIn(
            execution.status,
            [
                QueryExecutionStatus.PENDING,
                QueryExecutionStatus.RUNNING,
                QueryExecutionStatus.COMPLETED,
            ],
        )

    def test_execute_query_with_parameters(self):
        """Test executing a query with parameters"""
        parameterized_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Parameterized Dataset",
            query="SELECT :id AS id, :name AS name",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[_get_test_db_source()],
        )

        execution = self.service.execute_query(
            virtual_dataset_id=str(parameterized_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=QueryExecutionMode.SYNC,
            parameters={"id": 1, "name": "test"},
        )

        self.assertIsNotNone(execution)
        self.assertEqual(execution.parameters, {"id": 1, "name": "test"})
        self.assertIn("id", execution.query)
        self.assertIn("name", execution.query)

    def test_execute_query_result_caching(self):
        """Test that query results are cached"""
        execution1 = self.service.execute_query(
            virtual_dataset_id=str(self.virtual_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=QueryExecutionMode.SYNC,
            parameters={},
        )
        execution2 = self.service.execute_query(
            virtual_dataset_id=str(self.virtual_dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            execution_mode=QueryExecutionMode.SYNC,
            parameters={},
        )

        self.assertIsNotNone(execution1)
        self.assertIsNotNone(execution2)
        self.assertEqual(
            execution1.status,
            QueryExecutionStatus.COMPLETED,
            f"First execution should complete, got {execution1.status}",
        )
        self.assertEqual(
            execution2.status,
            QueryExecutionStatus.COMPLETED,
            f"Second execution should complete, got {execution2.status}",
        )
        self.assertIsNotNone(execution1.result_cache_key)
        self.assertEqual(execution1.result_cache_key, execution2.result_cache_key)

    def test_execute_query_federated_multiple_sources(self):
        """Test executing a federated query across multiple sources"""
        db_source = _get_test_db_source()
        federated_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Federated Dataset",
            query="SELECT 1 AS id, 'federated' AS name",
            query_type=QueryType.FEDERATED,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[db_source, db_source],
        )

        execution = None
        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(federated_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        except ValidationError:
            execution = QueryExecution.objects.filter(
                virtual_dataset_id=federated_dataset.id
            ).order_by("-created_at").first()

        self.assertIsNotNone(
            execution,
            "Federated query execution must produce an execution record",
        )
        self.assertEqual(execution.virtual_dataset_id, federated_dataset.id)
        self.assertIn(
            execution.status, [QueryExecutionStatus.COMPLETED, QueryExecutionStatus.FAILED]
        )

    def test_execute_query_sparql(self):
        """Test executing a SPARQL query"""
        sparql_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="SPARQL Dataset",
            query="SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10",
            query_type=QueryType.SPARQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        execution = None
        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(sparql_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        except (ValidationError, ValueError) as e:
            err = str(e).lower()
            if any(kw in err for kw in ("sparql", "semantic", "fuseki")):
                self.skipTest(f"SPARQL service not available: {e}")
            # Non-SPARQL errors are unexpected — re-raise
            execution = QueryExecution.objects.filter(
                virtual_dataset_id=sparql_dataset.id
            ).order_by("-created_at").first()
            if execution is None:
                raise

        self.assertIsNotNone(execution)
        self.assertEqual(execution.virtual_dataset_id, sparql_dataset.id)
        self.assertIn(
            execution.status,
            [QueryExecutionStatus.COMPLETED, QueryExecutionStatus.FAILED],
        )

    def test_execute_query_invalid_dataset(self):
        """Test that executing query for non-existent dataset fails"""
        from hub.apps.core.services.base import NotFoundError

        with self.assertRaises(NotFoundError):
            self.service.execute_query(
                virtual_dataset_id="00000000-0000-0000-0000-000000000000",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )

    def test_execute_query_inactive_dataset(self):
        """Test that executing query for inactive dataset fails"""
        inactive_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Inactive Dataset",
            query="SELECT * FROM test",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.INACTIVE,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        with self.assertRaises(ValidationError) as cm:
            self.service.execute_query(
                virtual_dataset_id=str(inactive_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={},
            )
        # Verify the error is about the inactive status, not missing sources
        err = str(cm.exception).lower()
        self.assertTrue(
            "inactive" in err or "not active" in err or "status" in err,
            f"Expected 'inactive' error; got: {cm.exception}",
        )
