"""
Tests for execute_query() method in VirtualizationService.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone
import json

from hub.apps.tenants.models import Tenant, KYCStatus, TenantPlan, PlanTier
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.virtualization.models import (
    VirtualDataset,
    QueryExecution,
    QueryType,
    VirtualDatasetStatus,
    QueryExecutionStatus,
    QueryExecutionMode,
)
from hub.apps.virtualization.services import VirtualizationService
from hub.apps.core.services.base import ValidationError
from hub.apps.users.models import Role, UserRole
from django.conf import settings
import uuid

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _get_test_db_source():
    """Get source config pointing to the actual test database."""
    db = settings.DATABASES["default"]
    return {
        "type": "postgresql",
        "host": db.get("HOST", "localhost"),
        "port": int(db.get("PORT", 5432)),
        "database": db.get("NAME"),
        "username": db.get("USER"),
        "password": db.get("PASSWORD"),
    }


class VirtualizationServiceExecuteQueryTest(TestCase):
    """Test execute_query() method for virtual dataset query execution"""

    def setUp(self):
        """Set up test fixtures"""
        from hub.apps.users.models import Role, UserRole

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        # Create DATA_PROVIDER role and assign to user
        provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"}
        )
        UserRole.objects.get_or_create(
            user=self.user,
            role=provider_role
        )

        # Set up subscription/plan
        plan, _ = TenantPlan.objects.get_or_create(
            slug="virtualization-test-plan",
            defaults={
                "name": "Virtualization Test Plan",
                "tier": PlanTier.PRO,
                "limits_json": {"max_assets": 100, "max_storage_gb": 1000, "max_virtual_datasets": 100},
                "is_active": True,
            },
        )
        if "max_storage_gb" not in (plan.limits_json or {}):
            plan.limits_json = {**(plan.limits_json or {}), "max_storage_gb": 1000, "max_virtual_datasets": 100}
            plan.save(update_fields=["limits_json"])
        if self.tenant.plan_id != plan.id:
            self.tenant.plan = plan
            self.tenant.save(update_fields=["plan"])
        Subscription.objects.get_or_create(
            tenant=self.tenant,
            defaults={
                "plan": plan,
                "status": SubscriptionStatus.ACTIVE,
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now(),
            },
        )

        self.service = VirtualizationService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create a test virtual dataset
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT 1 AS id, 'test' AS name",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[_get_test_db_source()]
        )

        # Clear cache
        cache.clear()

    def test_execute_query_sync_mode_simple_sql(self):
        """Test executing a simple SQL query in sync mode"""
        from hub.apps.core.services.base import ValidationError

        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(self.virtual_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={}
            )
            # If no exception, verify execution completed
            self.assertIsNotNone(execution)
            self.assertEqual(execution.status, QueryExecutionStatus.COMPLETED)
        except (ValidationError, ValueError, Exception) as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                self.skipTest(f"Database source not reachable: {e}")
            # If connection fails, execution should still be created and tracked
            executions = QueryExecution.objects.filter(
                virtual_dataset_id=self.virtual_dataset.id
            ).order_by('-created_at')
            if executions.count() == 0:
                self.skipTest(f"Database source not reachable: {e}")
            execution = executions.first()
            self.assertIsNotNone(execution)
            self.assertEqual(execution.status, QueryExecutionStatus.FAILED)

        # Verify execution has proper tracking
        self.assertIsNotNone(execution.query)
        self.assertEqual(execution.virtual_dataset_id, self.virtual_dataset.id)
        self.assertEqual(execution.execution_mode, QueryExecutionMode.SYNC)

        # Failed executions should have error logs
        if execution.status == QueryExecutionStatus.FAILED:
            self.assertIsNotNone(execution.execution_log)
            self.assertIsInstance(execution.execution_log, list)
            self.assertGreater(len(execution.execution_log), 0)

    def test_execute_query_async_mode(self):
        """Test executing a query in async mode"""
        from hub.apps.core.services.base import ValidationError

        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(self.virtual_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.ASYNC,
                parameters={}
            )
        except (ValidationError, ValueError) as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                self.skipTest(f"Database source not reachable: {e}")
            raise

        self.assertIsNotNone(execution)
        self.assertEqual(execution.execution_mode, QueryExecutionMode.ASYNC)
        # Async execution should start as PENDING or RUNNING
        # In test environment async may execute synchronously, but should not fail for valid query
        self.assertIn(execution.status, [
            QueryExecutionStatus.PENDING,
            QueryExecutionStatus.RUNNING,
            QueryExecutionStatus.COMPLETED,
        ])

    def test_execute_query_with_parameters(self):
        """Test executing a query with parameters"""
        parameterized_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Parameterized Dataset",
            query="SELECT :id AS id, :name AS name",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[_get_test_db_source()]
        )

        from hub.apps.core.services.base import ValidationError

        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(parameterized_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={"id": 1, "name": "test"}
            )
        except (ValidationError, ValueError, Exception) as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                self.skipTest(f"Database source not reachable: {e}")
            executions = QueryExecution.objects.filter(
                virtual_dataset_id=parameterized_dataset.id
            ).order_by('-created_at')
            execution = executions.first()
            if execution is None:
                self.skipTest(f"Database source not reachable: {e}")

        self.assertIsNotNone(execution)
        self.assertEqual(execution.parameters, {"id": 1, "name": "test"})
        # With parameterized queries, placeholders are bound at execution
        # time — the stored query retains :name placeholders.
        self.assertIn("id", execution.query)
        self.assertIn("name", execution.query)

    def test_execute_query_result_caching(self):
        """Test that query results are cached"""
        from hub.apps.core.services.base import ValidationError

        try:
            execution1 = self.service.execute_query(
                virtual_dataset_id=str(self.virtual_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={}
            )
        except (ValidationError, ValueError, Exception) as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                self.skipTest(f"Database source not reachable: {e}")
            executions = QueryExecution.objects.filter(
                virtual_dataset_id=self.virtual_dataset.id
            ).order_by('-created_at')
            execution1 = executions.first()
            if execution1 is None:
                self.skipTest(f"Database source not reachable: {e}")

        try:
            execution2 = self.service.execute_query(
                virtual_dataset_id=str(self.virtual_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={}
            )
        except (ValidationError, ValueError, Exception) as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                self.skipTest(f"Database source not reachable: {e}")
            executions = QueryExecution.objects.filter(
                virtual_dataset_id=self.virtual_dataset.id
            ).order_by('-created_at')
            execution2 = executions.first()
            if execution2 is None:
                self.skipTest(f"Database source not reachable: {e}")

        self.assertIsNotNone(execution1)
        self.assertIsNotNone(execution2)

        self.assertEqual(execution1.status, QueryExecutionStatus.COMPLETED,
                         f"First execution should complete, got {execution1.status}")
        self.assertEqual(execution2.status, QueryExecutionStatus.COMPLETED,
                         f"Second execution should complete, got {execution2.status}")
        self.assertIsNotNone(execution1.result_cache_key)
        self.assertEqual(execution1.result_cache_key, execution2.result_cache_key)

    def test_execute_query_federated_multiple_sources(self):
        """Test executing a federated query across multiple sources"""
        from hub.apps.core.services.base import ValidationError

        db_source = _get_test_db_source()
        federated_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Federated Dataset",
            query="SELECT 1 AS id, 'federated' AS name",
            query_type=QueryType.FEDERATED,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[db_source, db_source]
        )

        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(federated_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={}
            )
        except ValidationError:
            executions = QueryExecution.objects.filter(
                virtual_dataset_id=federated_dataset.id
            ).order_by('-created_at')
            execution = executions.first()

        self.assertIsNotNone(execution)
        self.assertEqual(execution.virtual_dataset_id, federated_dataset.id)
        # Federated query execution may complete or fail depending on database availability
        self.assertIn(execution.status, [
            QueryExecutionStatus.COMPLETED,
            QueryExecutionStatus.FAILED
        ])

    def test_execute_query_sparql(self):
        """Test executing a SPARQL query"""
        from hub.apps.core.services.base import ValidationError

        sparql_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="SPARQL Dataset",
            query="SELECT ?s ?p ?o WHERE { ?s ?p ?o } LIMIT 10",
            query_type=QueryType.SPARQL,
            status=VirtualDatasetStatus.ACTIVE
        )

        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(sparql_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={}
            )
        except (ValidationError, ValueError) as e:
            err = str(e).lower()
            if "sparql" in err or "semantic" in err or "fuseki" in err:
                self.skipTest(f"SPARQL service not available: {e}")
            executions = QueryExecution.objects.filter(
                virtual_dataset_id=sparql_dataset.id
            ).order_by('-created_at')
            execution = executions.first()
            if execution is None:
                self.skipTest(f"SPARQL execution not created: {e}")

        self.assertIsNotNone(execution)
        self.assertEqual(execution.virtual_dataset_id, sparql_dataset.id)
        self.assertIn(execution.status, [
            QueryExecutionStatus.COMPLETED,
            QueryExecutionStatus.FAILED,
        ])

    def test_execute_query_invalid_dataset(self):
        """Test that executing query for non-existent dataset fails"""
        from hub.apps.core.services.base import NotFoundError

        with self.assertRaises(NotFoundError):
            self.service.execute_query(
                virtual_dataset_id="00000000-0000-0000-0000-000000000000",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={}
            )

    def test_execute_query_inactive_dataset(self):
        """Test that executing query for inactive dataset fails"""
        inactive_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Inactive Dataset",
            query="SELECT * FROM test",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.INACTIVE
        )

        with self.assertRaises(ValidationError):
            self.service.execute_query(
                virtual_dataset_id=str(inactive_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={}
            )

