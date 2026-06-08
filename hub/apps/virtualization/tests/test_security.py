"""
Security tests for virtualization operations.

Tests access control, data isolation, input validation, and security boundaries.
"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
import uuid
import pytest

from hub.apps.virtualization.models import (
    VirtualDataset,
    QueryExecution,
    QueryType,
    VirtualDatasetStatus,
    QueryExecutionStatus,
    QueryExecutionMode,
)
from hub.apps.virtualization.services import VirtualizationService
from hub.apps.core.services.base import PermissionError, ValidationError, NotFoundError
from hub.apps.tenants.models import Tenant, TenantPlan, PlanTier
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.users.models import User


pytestmark = pytest.mark.django_db(transaction=True)


class VirtualizationSecurityTest(TestCase):
    """Security tests for virtualization operations"""

    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.orchestration.registry import reset_workflow_definition_cache
        reset_workflow_definition_cache()
        from hub.apps.users.models import Role, UserRole

        _uid1 = uuid.uuid4().hex[:8]
        self.tenant1 = Tenant.objects.create(
            name=f"Tenant 1 {_uid1}",
            slug=f"tenant-1-{_uid1}"
        )
        _uid2 = uuid.uuid4().hex[:8]
        self.tenant2 = Tenant.objects.create(
            name=f"Tenant 2 {_uid2}",
            slug=f"tenant-2-{_uid2}"
        )

        self.user1 = User.objects.create_user(
            email=f"user1-{_uid1}@tenant1.com",
            password="testpass123",
            tenant=self.tenant1
        )
        self.user2 = User.objects.create_user(
            email=f"user2-{_uid2}@tenant2.com",
            password="testpass123",
            tenant=self.tenant2
        )

        # Assign DATA_PROVIDER role to users
        role1, _ = Role.objects.get_or_create(
            tenant=self.tenant1,
            name="DATA_PROVIDER",
            defaults={"description": "Data provider role"}
        )
        UserRole.objects.get_or_create(user=self.user1, role=role1)

        role2, _ = Role.objects.get_or_create(
            tenant=self.tenant2,
            name="DATA_PROVIDER",
            defaults={"description": "Data provider role"}
        )
        UserRole.objects.get_or_create(user=self.user2, role=role2)

        # Set up subscription/plan for both tenants
        for t in [self.tenant1, self.tenant2]:
            plan, _ = TenantPlan.objects.get_or_create(
                slug="virtualization-test-plan",
                defaults={
                    "name": "Virtualization Test Plan",
                    "tier": PlanTier.PRO,
                    "limits_json": {
                        "max_assets": 100,
                        "max_storage_gb": 1000,
                        "max_virtual_datasets": 100,
                    },
                    "is_active": True,
                },
            )
            if "max_storage_gb" not in (plan.limits_json or {}):
                plan.limits_json = {
                    **(plan.limits_json or {}),
                    "max_storage_gb": 1000,
                    "max_virtual_datasets": 100,
                }
                plan.save(update_fields=["limits_json"])
            if t.plan_id != plan.id:
                t.plan = plan
                t.save(update_fields=["plan"])
            Subscription.objects.get_or_create(
                tenant=t,
                defaults={
                    "plan": plan,
                    "status": SubscriptionStatus.ACTIVE,
                    "current_period_start": timezone.now(),
                    "current_period_end": timezone.now(),
                },
            )

        self.service1 = VirtualizationService(
            tenant_id=str(self.tenant1.id),
            user_id=str(self.user1.id)
        )
        self.service2 = VirtualizationService(
            tenant_id=str(self.tenant2.id),
            user_id=str(self.user2.id)
        )

    def test_tenant_isolation_dataset_access(self):
        """Test that tenants cannot access each other's datasets."""
        # Create dataset in tenant1
        dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant1,
            created_by=self.user1,
            name="Tenant 1 Dataset",
            query="SELECT 1",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE
        )

        # Try to access from tenant2 service
        with self.assertRaises((NotFoundError, PermissionError)):
            self.service2.get_virtual_dataset(
                virtual_dataset_id=str(dataset1.id),
                tenant_id=str(self.tenant2.id)
            )

    def test_tenant_isolation_query_execution(self):
        """Test that tenants cannot execute queries on other tenants' datasets."""
        # Create dataset in tenant1
        dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant1,
            created_by=self.user1,
            name="Tenant 1 Dataset",
            query="SELECT 1",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE
        )

        # Try to execute query from tenant2
        with self.assertRaises((NotFoundError, PermissionError, ValidationError)):
            self.service2.execute_query(
                virtual_dataset_id=str(dataset1.id),
                tenant_id=str(self.tenant2.id),
                user_id=str(self.user2.id)
            )

    def test_sql_injection_prevention(self):
        """Test that SQL injection attempts are rejected."""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant1,
            created_by=self.user1,
            name="SQL Injection Test",
            query="SELECT * FROM users WHERE id = :user_id",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE
        )

        malicious_parameters = {
            "user_id": "1; DROP TABLE users; --"
        }

        # The service MUST reject malicious parameters — either by raising
        # ValidationError or by executing safely with sanitized parameters.
        # In neither case should the test silently accept the outcome.
        try:
            execution = self.service1.execute_query(
                virtual_dataset_id=str(dataset.id),
                tenant_id=str(self.tenant1.id),
                user_id=str(self.user1.id),
                parameters=malicious_parameters
            )
        except ValidationError:
            # Injection was blocked — this is the expected secure outcome.
            return

        # If execution succeeded, the parameters must have been sanitized.
        # Verify the execution was actually created (the service didn't
        # silently drop the request).
        self.assertIsNotNone(execution)
        # The executed query must NOT contain the raw malicious payload.
        if execution.executed_query:
            self.assertNotIn(
                "DROP TABLE",
                execution.executed_query.upper(),
                "Malicious SQL should not appear in the executed query"
            )

    def test_query_parameter_validation(self):
        """Test that query parameters are properly validated."""
        from django.conf import settings
        db = settings.DATABASES["default"]
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant1,
            created_by=self.user1,
            name="Parameter Validation Test",
            query="SELECT 1 WHERE 1 = :id",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[{
                "type": "postgresql",
                "host": db.get("HOST", "localhost"),
                "port": int(db.get("PORT", 5432)),
                "database": db.get("NAME"),
                "username": db.get("USER"),
                "password": db.get("PASSWORD"),
            }],
        )

        # Invalid parameter types should be rejected
        invalid_parameters = {
            "id": {"nested": "object"}  # Complex objects should be rejected
        }

        with self.assertRaises((ValidationError, ValueError)) as cm:
            self.service1.execute_query(
                virtual_dataset_id=str(dataset.id),
                tenant_id=str(self.tenant1.id),
                user_id=str(self.user1.id),
                parameters=invalid_parameters
            )
        # Complex dict parameters are rejected — either by our validation
        # ("parameter") or by the DB adapter ("can't adapt type 'dict'")
        err = str(cm.exception).lower()
        self.assertTrue(
            "parameter" in err or "adapt" in err or "dict" in err or "invalid" in err,
            f"Expected parameter validation error, got: {cm.exception}",
        )

    def test_user_permission_checks(self):
        """Test that user permissions are checked before operations."""
        # Create a user without virtualization permissions
        restricted_user = User.objects.create_user(
            email=f"restricted-{uuid.uuid4().hex[:8]}@tenant1.com",
            password="testpass123",
            tenant=self.tenant1
        )

        restricted_service = VirtualizationService(
            tenant_id=str(self.tenant1.id),
            user_id=str(restricted_user.id)
        )

        # Try to create dataset without permissions - should fail
        with self.assertRaises(PermissionError):
            restricted_service.create_virtual_dataset(
                tenant_id=str(self.tenant1.id),
                user_id=str(restricted_user.id),
                name="Restricted Dataset",
                query="SELECT 1",
                query_type=QueryType.SQL,
                sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
            )

    def test_query_result_data_isolation(self):
        """Test that query results are properly isolated by tenant."""
        # Create datasets in different tenants
        dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant1,
            created_by=self.user1,
            name="Tenant 1 Dataset",
            query="SELECT * FROM tenant1_data",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE
        )

        dataset2 = VirtualDataset.objects.create(
            tenant=self.tenant2,
            created_by=self.user2,
            name="Tenant 2 Dataset",
            query="SELECT * FROM tenant2_data",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE
        )

        # Create executions for each
        execution1 = QueryExecution.objects.create(
            virtual_dataset=dataset1,
            query="SELECT * FROM tenant1_data",
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now()
        )

        execution2 = QueryExecution.objects.create(
            virtual_dataset=dataset2,
            query="SELECT * FROM tenant2_data",
            execution_mode=QueryExecutionMode.SYNC,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now(),
            completed_at=timezone.now()
        )

        # Verify executions belong to correct tenants
        self.assertEqual(execution1.virtual_dataset.tenant_id, self.tenant1.id)
        self.assertEqual(execution2.virtual_dataset.tenant_id, self.tenant2.id)

        # Verify tenant2 cannot access tenant1's execution
        with self.assertRaises((NotFoundError, PermissionError)):
            self.service2.get_query_execution(
                query_execution_id=str(execution1.id),
                tenant_id=str(self.tenant2.id)
            )

    def test_query_syntax_validation(self):
        """Test that syntactically invalid / malicious queries are rejected."""
        malicious_queries = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
        ]

        for malicious_query in malicious_queries:
            # The service must reject these — they are neither valid SELECT
            # statements nor safe parameterized queries.
            with self.assertRaises(
                (ValidationError, ValueError),
                msg=f"Malicious query should be rejected: {malicious_query!r}"
            ):
                self.service1.create_virtual_dataset(
                    tenant_id=str(self.tenant1.id),
                    user_id=str(self.user1.id),
                    name="Malicious Dataset",
                    query=malicious_query,
                    query_type=QueryType.SQL
                )

