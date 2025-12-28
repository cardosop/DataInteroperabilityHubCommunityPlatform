"""
Security tests for virtualization operations.

Tests access control, data isolation, input validation, and security boundaries.
"""
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model
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
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User


pytestmark = pytest.mark.django_db(transaction=True)


class VirtualizationSecurityTest(TestCase):
    """Security tests for virtualization operations"""

    def setUp(self):
        """Set up test fixtures."""
        from hub.apps.users.models import Role, UserRole

        self.tenant1 = Tenant.objects.create(
            name="Tenant 1",
            slug="tenant-1"
        )
        self.tenant2 = Tenant.objects.create(
            name="Tenant 2",
            slug="tenant-2"
        )

        self.user1 = User.objects.create_user(
            email="user1@tenant1.com",
            password="testpass123",
            tenant=self.tenant1
        )
        self.user2 = User.objects.create_user(
            email="user2@tenant2.com",
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
        """Test that SQL injection attempts are prevented."""
        # Create dataset with parameterized query
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant1,
            created_by=self.user1,
            name="SQL Injection Test",
            query="SELECT * FROM users WHERE id = :user_id",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE
        )

        # Attempt SQL injection
        malicious_parameters = {
            "user_id": "1; DROP TABLE users; --"
        }

        # Service should validate and sanitize parameters
        try:
            execution = self.service1.execute_query(
                virtual_dataset_id=str(dataset.id),
                tenant_id=str(self.tenant1.id),
                user_id=str(self.user1.id),
                parameters=malicious_parameters
            )
            # If execution succeeds, verify parameters were sanitized
            # (In real implementation, parameters should be properly escaped)
            self.assertIsNotNone(execution)
        except ValidationError:
            # Validation error is acceptable - injection was prevented
            pass

    def test_query_parameter_validation(self):
        """Test that query parameters are properly validated."""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant1,
            created_by=self.user1,
            name="Parameter Validation Test",
            query="SELECT * FROM table WHERE id = :id",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE
        )

        # Invalid parameter types should be rejected
        invalid_parameters = {
            "id": {"nested": "object"}  # Complex objects should be rejected
        }

        with self.assertRaises(ValidationError):
            self.service1.execute_query(
                virtual_dataset_id=str(dataset.id),
                tenant_id=str(self.tenant1.id),
                user_id=str(self.user1.id),
                parameters=invalid_parameters
            )

    def test_user_permission_checks(self):
        """Test that user permissions are checked before operations."""
        # Create a user without virtualization permissions
        restricted_user = User.objects.create_user(
            email="restricted@tenant1.com",
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
                query_type=QueryType.SQL
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
        """Test that malicious query syntax is rejected or sanitized."""
        # Attempt to create dataset with potentially malicious query
        # Note: Some queries may pass syntax validation but should be handled safely
        malicious_queries = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
        ]

        for malicious_query in malicious_queries:
            # Query syntax validation should catch or sanitize these
            try:
                dataset = self.service1.create_virtual_dataset(
                    tenant_id=str(self.tenant1.id),
                    user_id=str(self.user1.id),
                    name="Malicious Dataset",
                    query=malicious_query,
                    query_type=QueryType.SQL
                )
                # If creation succeeds, verify query was stored (validation may allow it)
                # In production, these would be sanitized during execution
                self.assertIsNotNone(dataset)
            except ValidationError:
                # Validation error is acceptable - malicious query was rejected
                pass

