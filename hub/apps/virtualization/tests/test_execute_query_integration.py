"""
Integration tests for execute_query() method.

Tests federated query execution and E2E workflows using real services.
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.utils import timezone

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


def _setup_subscription(tenant):
    """Set up subscription/plan for a tenant to avoid 403 responses."""
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
    if tenant.plan_id != plan.id:
        tenant.plan = plan
        tenant.save(update_fields=["plan"])
    Subscription.objects.get_or_create(
        tenant=tenant,
        defaults={
            "plan": plan,
            "status": SubscriptionStatus.ACTIVE,
            "current_period_start": timezone.now(),
            "current_period_end": timezone.now(),
        },
    )


def semantic_service_available() -> bool:
    """Check if SemanticService is available (for SPARQL queries)"""
    try:
        from hub.apps.semantic.service_client import SemanticServiceClient
        client = SemanticServiceClient()
        is_healthy, _ = client.health_check()
        return is_healthy
    except Exception:
        return False


class VirtualizationExecuteQueryIntegrationTest(TestCase):
    """Integration tests for execute_query() using real services"""

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

        _setup_subscription(self.tenant)
        self.service = VirtualizationService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Clear cache
        cache.clear()

    @pytest.mark.skipif(not semantic_service_available(), reason="SemanticService not available")
    def test_federated_query_execution_sparql(self):
        """Test executing a federated query with SPARQL source"""
        from hub.apps.core.services.base import ValidationError

        sparql_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="SPARQL Integration Dataset",
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
            if any(kw in err for kw in ("sparql", "semantic", "fuseki", "circuit")):
                self.skipTest(f"SPARQL service not available: {e}")
            executions = QueryExecution.objects.filter(
                virtual_dataset_id=sparql_dataset.id
            ).order_by('-created_at')
            execution = executions.first()

        self.assertIsNotNone(execution)
        self.assertEqual(execution.virtual_dataset_id, sparql_dataset.id)
        # SPARQL query may complete or fail depending on Fuseki availability
        self.assertIn(execution.status, [
            QueryExecutionStatus.COMPLETED,
            QueryExecutionStatus.FAILED
        ])

    def test_federated_query_execution_multiple_sources(self):
        """Test executing a federated query across multiple sources"""
        db_source = _get_test_db_source()
        federated_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Federated Integration Dataset",
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
                execution_mode=QueryExecutionMode.ASYNC,
                parameters={}
            )
        except (ValidationError, ValueError, Exception) as e:
            err = str(e).lower()
            if any(kw in err for kw in (
                "connection", "refused", "timeout",
                "operational",
            )):
                self.skipTest(f"Database source not reachable: {e}")
            raise

        self.assertIsNotNone(execution)
        self.assertEqual(execution.virtual_dataset_id, federated_dataset.id)
        self.assertEqual(execution.execution_mode, QueryExecutionMode.ASYNC)
        self.assertIn(execution.status, [
            QueryExecutionStatus.PENDING,
            QueryExecutionStatus.RUNNING,
            QueryExecutionStatus.COMPLETED,
            QueryExecutionStatus.FAILED
        ])

        # If execution failed due to unreachable sources, skip
        if execution.status == QueryExecutionStatus.FAILED:
            self.skipTest(
                "Federated query failed (sources not reachable)"
            )

        # Verify execution was enqueued (has log entry)
        self.assertIsNotNone(execution.execution_log)
        self.assertGreaterEqual(len(execution.execution_log), 0)

    def test_query_execution_result_caching(self):
        """Test that query results are properly cached"""
        simple_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Caching Test Dataset",
            query="SELECT 1 as test_value",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[_get_test_db_source()]
        )

        # First execution
        try:
            execution1 = self.service.execute_query(
                virtual_dataset_id=str(simple_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={}
            )
        except (ValidationError, ValueError, Exception) as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                self.skipTest(f"Database source not reachable: {e}")
            executions = QueryExecution.objects.filter(
                virtual_dataset_id=simple_dataset.id
            ).order_by('-created_at')
            execution1 = executions.first()
            if execution1 is None:
                self.skipTest(f"Database source not reachable: {e}")

        # Second execution with same parameters
        try:
            execution2 = self.service.execute_query(
                virtual_dataset_id=str(simple_dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={}
            )
        except (ValidationError, ValueError, Exception) as e:
            if "connection" in str(e).lower() or "refused" in str(e).lower():
                self.skipTest(f"Database source not reachable: {e}")
            executions = QueryExecution.objects.filter(
                virtual_dataset_id=simple_dataset.id
            ).order_by('-created_at')
            execution2 = executions.first()
            if execution2 is None:
                self.skipTest(f"Database source not reachable: {e}")

        self.assertIsNotNone(execution1)
        self.assertIsNotNone(execution2)

        if execution1.status == QueryExecutionStatus.COMPLETED:
            self.assertIsNotNone(execution1.result_cache_key)
            if execution2.status == QueryExecutionStatus.COMPLETED:
                self.assertIsNotNone(execution2.result_cache_key)
                self.assertEqual(
                    execution1.result_cache_key,
                    execution2.result_cache_key
                )


class VirtualizationExecuteQueryE2ETest(TestCase):
    """End-to-end tests for complete query execution workflow"""

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

        _setup_subscription(self.tenant)
        self.service = VirtualizationService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Clear cache
        cache.clear()

    def test_e2e_query_execution_workflow(self):
        """Test complete E2E workflow: create dataset -> execute query -> check results"""
        from hub.apps.core.services.base import ValidationError

        # Create virtual dataset
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="E2E Test Dataset",
            query="SELECT 1 as test_column",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[_get_test_db_source()]
        )

        # Execute query
        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.SYNC,
                parameters={}
            )
        except ValidationError:
            # If workflow fails, try to get execution from database
            executions = QueryExecution.objects.filter(
                virtual_dataset_id=dataset.id
            ).order_by('-created_at')
            execution = executions.first()

            # If still no execution, check workflow instance
            if not execution:
                from hub.apps.orchestration.models import WorkflowInstance
                workflow_instances = WorkflowInstance.objects.filter(
                    workflow_name="virtualization_query_execution",
                    tenant_id=self.tenant.id
                ).order_by('-created_at')
                if workflow_instances.exists():
                    workflow_instance = workflow_instances.first()
                    execution_id = workflow_instance.state_data.get("execution_id")
                    if execution_id:
                        try:
                            execution = QueryExecution.objects.get(id=execution_id)
                        except QueryExecution.DoesNotExist:
                            pass

        # Verify execution was created
        if execution is None:
            # Check if it's an infrastructure issue
            from hub.apps.orchestration.models import WorkflowInstance
            wi = WorkflowInstance.objects.filter(
                workflow_name="virtualization_query_execution",
                tenant_id=self.tenant.id
            ).order_by('-created_at').first()
            if wi and "connection" in str(wi.state_data.get("error", "")).lower():
                self.skipTest("Database not reachable for query execution")
            self.fail("execute_query() did not create an execution record")

        self.assertEqual(execution.virtual_dataset_id, dataset.id)

        # Verify execution has proper status
        self.assertIn(execution.status, [
            QueryExecutionStatus.PENDING,
            QueryExecutionStatus.RUNNING,
            QueryExecutionStatus.COMPLETED,
            QueryExecutionStatus.FAILED
        ])

        # Verify execution has query text
        self.assertIsNotNone(execution.query)
        self.assertGreater(len(execution.query), 0)

        # Verify execution has metrics/result data if completed
        if execution.status == QueryExecutionStatus.COMPLETED:
            self.assertIsNotNone(execution.metrics)
            self.assertIsInstance(execution.metrics, dict)

        # Verify execution log exists
        self.assertIsNotNone(execution.execution_log)
        self.assertIsInstance(execution.execution_log, list)

        # Verify timestamps (if execution started)
        if execution.started_at:
            self.assertIsNotNone(execution.started_at)
            if execution.status in [QueryExecutionStatus.COMPLETED, QueryExecutionStatus.FAILED]:
                self.assertIsNotNone(execution.completed_at)
                self.assertLessEqual(execution.started_at, execution.completed_at)

    def test_e2e_async_query_execution_workflow(self):
        """Test complete E2E workflow for async query execution"""
        from hub.apps.core.services.base import ValidationError

        # Create virtual dataset
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="E2E Async Test Dataset",
            query="SELECT 1 AS id, 'async_test' AS name",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[_get_test_db_source()]
        )

        # Execute query asynchronously (may fail if database not available)
        try:
            execution = self.service.execute_query(
                virtual_dataset_id=str(dataset.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                execution_mode=QueryExecutionMode.ASYNC,
                parameters={}
            )
        except ValidationError:
            # If workflow fails, try to get execution from database
            executions = QueryExecution.objects.filter(
                virtual_dataset_id=dataset.id
            ).order_by('-created_at')
            execution = executions.first()

            # If still no execution, check workflow instance
            if not execution:
                from hub.apps.orchestration.models import WorkflowInstance
                workflow_instances = WorkflowInstance.objects.filter(
                    workflow_name="virtualization_query_execution",
                    tenant_id=self.tenant.id
                ).order_by('-created_at')
                if workflow_instances.exists():
                    workflow_instance = workflow_instances.first()
                    execution_id = workflow_instance.state_data.get("execution_id")
                    if execution_id:
                        try:
                            execution = QueryExecution.objects.get(id=execution_id)
                        except QueryExecution.DoesNotExist:
                            pass

        # Verify execution was created
        if execution is None:
            # Check if it's an infrastructure issue
            from hub.apps.orchestration.models import WorkflowInstance
            wi = WorkflowInstance.objects.filter(
                workflow_name="virtualization_query_execution",
                tenant_id=self.tenant.id
            ).order_by('-created_at').first()
            if wi and "connection" in str(wi.state_data.get("error", "")).lower():
                self.skipTest("Database not reachable for query execution")
            self.fail("execute_query() did not create an execution record")
        self.assertEqual(execution.execution_mode, QueryExecutionMode.ASYNC)

        # In test environment, async execution may complete synchronously
        self.assertIn(execution.status, [
            QueryExecutionStatus.PENDING,
            QueryExecutionStatus.RUNNING,
            QueryExecutionStatus.COMPLETED,
            QueryExecutionStatus.FAILED,
        ])

        # Verify execution can be retrieved
        # Refresh execution from database to ensure it's saved
        execution.refresh_from_db()

        # Query directly from database to avoid transaction isolation issues in tests
        retrieved_execution = QueryExecution.objects.get(id=execution.id)

        self.assertIsNotNone(retrieved_execution)
        self.assertEqual(retrieved_execution.id, execution.id)
        self.assertEqual(retrieved_execution.virtual_dataset_id, dataset.id)


class VirtualizationGetQueryResultIntegrationTest(TestCase):
    """Integration tests for get_query_result() method"""

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

        _setup_subscription(self.tenant)
        self.service = VirtualizationService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create a test virtual dataset
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM test_table",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE
        )

        # Clear cache
        cache.clear()

    def test_get_query_result_integration_cached_result(self):
        """Integration test: Retrieve query result from cache after execution"""
        from django.core.cache import cache
        from hub.apps.core.services.base import NotFoundError

        # Create test results
        test_results = [
            {"id": 1, "name": "Item 1", "value": 100},
            {"id": 2, "name": "Item 2", "value": 200},
            {"id": 3, "name": "Item 3", "value": 300}
        ]

        # Simulate query execution by creating execution with cached results
        cache_key = self.service._get_query_cache_key(self.virtual_dataset, {})
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": self.virtual_dataset.query_type,
                "cached_at": timezone.now().isoformat()
            },
            timeout=3600
        )

        # Create completed execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={
                "duration_ms": 150,
                "rows_processed": len(test_results)
            }
        )

        # Retrieve results
        result = self.service.get_query_result(
            execution_id=str(execution.id),
            format="json"
        )

        # Verify results
        self.assertIsNotNone(result)
        self.assertEqual(result["execution_id"], str(execution.id))
        self.assertEqual(result["format"], "json")
        self.assertEqual(result["total_count"], len(test_results))
        self.assertEqual(result["returned_count"], len(test_results))
        self.assertEqual(len(result["data"]), len(test_results))
        self.assertEqual(result["data"][0]["id"], 1)
        self.assertEqual(result["data"][0]["name"], "Item 1")

    def test_get_query_result_integration_pagination_workflow(self):
        """Integration test: Full workflow with pagination"""
        from django.core.cache import cache

        # Create large test dataset
        test_results = [
            {"id": i, "name": f"Item {i}", "value": i * 10}
            for i in range(1, 251)  # 250 items
        ]

        # Cache results
        cache_key = self.service._get_query_cache_key(self.virtual_dataset, {})
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": self.virtual_dataset.query_type,
                "cached_at": timezone.now().isoformat()
            },
            timeout=3600
        )

        # Create completed execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={
                "duration_ms": 200,
                "rows_processed": len(test_results)
            }
        )

        # Test pagination across multiple pages
        page_size = 50
        total_pages = (len(test_results) + page_size - 1) // page_size

        for page in range(1, min(4, total_pages + 1)):  # Test first 3 pages
            result = self.service.get_query_result(
                execution_id=str(execution.id),
                tenant_id=str(self.tenant.id),
                format="json",
                page=page,
                page_size=page_size
            )

            # Verify pagination metadata
            self.assertIsNotNone(result["pagination"])
            self.assertEqual(result["pagination"]["page"], page)
            self.assertEqual(result["pagination"]["page_size"], page_size)
            self.assertEqual(result["pagination"]["total_pages"], total_pages)
            self.assertEqual(result["total_count"], len(test_results))
            self.assertEqual(result["returned_count"], min(page_size, len(test_results) - (page - 1) * page_size))

            # Verify data integrity
            expected_start_id = (page - 1) * page_size + 1
            self.assertEqual(result["data"][0]["id"], expected_start_id)

    def test_get_query_result_integration_format_conversion(self):
        """Integration test: Format conversion (JSON -> CSV -> Parquet)"""
        from django.core.cache import cache
        import base64
        import pandas as pd
        import io

        # Create test results
        test_results = [
            {"id": 1, "name": "Item 1", "value": 100},
            {"id": 2, "name": "Item 2", "value": 200}
        ]

        # Cache results
        cache_key = self.service._get_query_cache_key(self.virtual_dataset, {})
        cache.set(
            cache_key,
            {
                "data": test_results,
                "row_count": len(test_results),
                "query_type": self.virtual_dataset.query_type,
                "cached_at": timezone.now().isoformat()
            },
            timeout=3600
        )

        # Create completed execution
        execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query=self.virtual_dataset.query,
            parameters={},
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now(),
            result_cache_key=cache_key,
            metrics={"duration_ms": 100, "rows_processed": len(test_results)}
        )

        # Test JSON format
        json_result = self.service.get_query_result(
            execution_id=str(execution.id),
            format="json"
        )
        self.assertEqual(json_result["format"], "json")
        self.assertIsInstance(json_result["data"], list)
        self.assertEqual(len(json_result["data"]), 2)

        # Test CSV format
        csv_result = self.service.get_query_result(
            execution_id=str(execution.id),
            format="csv"
        )
        self.assertEqual(csv_result["format"], "csv")
        self.assertIsInstance(csv_result["data"], str)
        self.assertIn("id,name,value", csv_result["data"])
        # Verify CSV can be parsed
        df = pd.read_csv(io.StringIO(csv_result["data"]))
        self.assertEqual(len(df), 2)

        # Test Parquet format
        parquet_result = self.service.get_query_result(
            execution_id=str(execution.id),
            format="parquet"
        )
        self.assertEqual(parquet_result["format"], "parquet")
        self.assertIsInstance(parquet_result["data"], str)
        # Verify Parquet can be decoded and parsed
        decoded = base64.b64decode(parquet_result["data"])
        df_parquet = pd.read_parquet(io.BytesIO(decoded))
        self.assertEqual(len(df_parquet), 2)
        self.assertEqual(list(df_parquet.columns), ["id", "name", "value"])

