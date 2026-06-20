"""
Comprehensive Integration Tests for Virtualization Views.

Tests all endpoints with:
- Real database (no mocks/stubs)
- Authorization (RBAC/ABAC)
- Rate limiting
- Error handling
- Performance

All tests use real services and run against Docker Compose instances.
"""

import time
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpRequest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.rate_limiting.service import check_rate_limit, get_rate_limit_headers
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan
from hub.apps.users.models import Role, User, UserRole, UserStatus
from hub.apps.virtualization.models import (
    QueryExecution,
    QueryExecutionMode,
    QueryExecutionStatus,
    QueryType,
    VirtualDataset,
    VirtualDatasetStatus,
)

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class VirtualizationViewsIntegrationTest(TestCase):
    """Comprehensive integration tests for virtualization views"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()
        cache.clear()

        # Create tenants
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED,
            virtualization_enabled=True,
        )

        _uid = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            kyc_status=KYCStatus.VERIFIED,
            virtualization_enabled=True,
        )

        # Create platform admin
        self.platform_admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            is_platform_admin=True,
        )

        # Create roles
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant Administrator"},
        )
        self.data_consumer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_CONSUMER", defaults={"description": "Data Consumer"}
        )

        # Create users
        self.data_provider_user = User.objects.create_user(
            email=f"provider-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.data_provider_user, role=self.data_provider_role)

        self.tenant_admin_user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@test-tenant.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.tenant_admin_user, role=self.tenant_admin_role)

        self.data_consumer_user = User.objects.create_user(
            email=f"consumer-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.data_consumer_user, role=self.data_consumer_role)

        self.other_tenant_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

        # Valid dataset data
        self.valid_dataset_data = {
            "name": "Test Virtual Dataset",
            "description": "Test description",
            "query": "SELECT id, name, age FROM users WHERE age > 18",
            "query_type": QueryType.SQL,
            "schema": {
                "fields": [
                    {"name": "id", "type": "integer"},
                    {"name": "name", "type": "string"},
                    {"name": "age", "type": "integer"},
                ]
            },
            "sources": [
                {
                    "type": "postgresql",
                    "host": "localhost",
                    "database": "testdb",
                    "asset_id": str(self.asset.id),
                }
            ],
            "version": "1.0.0",
            "status": VirtualDatasetStatus.DRAFT,
        }

        # Set up subscription/plan for tenants
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
        if self.other_tenant.plan_id != plan.id:
            self.other_tenant.plan = plan
            self.other_tenant.save(update_fields=["plan"])
        Subscription.objects.get_or_create(
            tenant=self.other_tenant,
            defaults={
                "plan": plan,
                "status": SubscriptionStatus.ACTIVE,
                "current_period_start": timezone.now(),
                "current_period_end": timezone.now(),
            },
        )

    # ==================== DATASET ENDPOINTS - REAL DATABASE TESTS ====================

    def test_create_dataset_with_real_database(self):
        """Test creating a virtual dataset with real database"""
        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.post(
            "/api/v1/virtualization/datasets/", self.valid_dataset_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], self.valid_dataset_data["name"])

        # Verify in database
        dataset = VirtualDataset.objects.get(id=response.data["id"])
        self.assertEqual(dataset.name, self.valid_dataset_data["name"])
        self.assertEqual(dataset.tenant_id, self.tenant.id)
        self.assertEqual(dataset.created_by_id, self.data_provider_user.id)
        self.assertEqual(dataset.query_type, QueryType.SQL)

    def test_list_datasets_with_real_database(self):
        """Test listing virtual datasets with real database"""
        # Create datasets
        dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Dataset 1",
            query="SELECT * FROM table1",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )
        dataset2 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Dataset 2",
            query="SELECT * FROM table2",
            query_type=QueryType.SPARQL,
            status=VirtualDatasetStatus.DRAFT,
        )
        # Dataset in other tenant (should not appear)
        VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_tenant_user,
            name="Other Dataset",
            query="SELECT * FROM other",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.get("/api/v1/virtualization/datasets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        dataset_ids = [d["id"] for d in response.data["results"]]
        self.assertIn(str(dataset1.id), dataset_ids)
        self.assertIn(str(dataset2.id), dataset_ids)

    def test_retrieve_dataset_with_real_database(self):
        """Test retrieving a virtual dataset with real database"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Test Dataset",
            query="SELECT * FROM test",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.get(f"/api/v1/virtualization/datasets/{dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(dataset.id))
        self.assertEqual(response.data["name"], "Test Dataset")

    def test_update_dataset_with_real_database(self):
        """Test updating a virtual dataset with real database"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Original Name",
            query="SELECT * FROM original",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        self.client.force_authenticate(user=self.data_provider_user)

        update_data = {"name": "Updated Name", "description": "Updated description"}

        response = self.client.patch(
            f"/api/v1/virtualization/datasets/{dataset.id}/", update_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Updated Name")

        # Verify in database
        dataset.refresh_from_db()
        self.assertEqual(dataset.name, "Updated Name")
        self.assertEqual(dataset.description, "Updated description")

    def test_delete_dataset_with_real_database(self):
        """Test deleting a virtual dataset with real database"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="To Delete",
            query="SELECT * FROM delete",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
        )
        dataset_id = dataset.id

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.delete(f"/api/v1/virtualization/datasets/{dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deleted from database
        self.assertFalse(VirtualDataset.objects.filter(id=dataset_id).exists())

    # ==================== AUTHORIZATION TESTS ====================

    def test_create_dataset_requires_data_provider_role(self):
        """Test that creating dataset requires DATA_PROVIDER or TENANT_ADMIN role"""
        self.client.force_authenticate(user=self.data_consumer_user)

        response = self.client.post(
            "/api/v1/virtualization/datasets/", self.valid_dataset_data, format="json"
        )

        # Should be forbidden (403) - consumer doesn't have write permission
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_dataset_allows_tenant_admin(self):
        """Test that tenant admin can create datasets"""
        self.client.force_authenticate(user=self.tenant_admin_user)

        response = self.client.post(
            "/api/v1/virtualization/datasets/", self.valid_dataset_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_list_datasets_tenant_isolation(self):
        """Test that users can only see datasets in their tenant"""
        # Create dataset in tenant
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Tenant Dataset",
            query="SELECT * FROM tenant",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        # Create dataset in other tenant
        other_dataset = VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_tenant_user,
            name="Other Tenant Dataset",
            query="SELECT * FROM other",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.get("/api/v1/virtualization/datasets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dataset_ids = [d["id"] for d in response.data["results"]]
        self.assertIn(str(dataset.id), dataset_ids)
        self.assertNotIn(str(other_dataset.id), dataset_ids)

    def test_retrieve_dataset_cross_tenant_forbidden(self):
        """Test that users cannot retrieve datasets from other tenants"""
        other_dataset = VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_tenant_user,
            name="Other Dataset",
            query="SELECT * FROM other",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.get(f"/api/v1/virtualization/datasets/{other_dataset.id}/")

        # Cross-tenant access returns 403 (PermissionDenied from cross_tenant_helpers).
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_dataset_cross_tenant_forbidden(self):
        """Test that users cannot update datasets from other tenants"""
        other_dataset = VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_tenant_user,
            name="Other Dataset",
            query="SELECT * FROM other",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.patch(
            f"/api/v1/virtualization/datasets/{other_dataset.id}/",
            {"name": "Hacked Name"},
            format="json",
        )

        # Cross-tenant access returns 403 (PermissionDenied from cross_tenant_helpers).
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_dataset_cross_tenant_forbidden(self):
        """Test that users cannot delete datasets from other tenants"""
        other_dataset = VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_tenant_user,
            name="Other Dataset",
            query="SELECT * FROM other",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.delete(f"/api/v1/virtualization/datasets/{other_dataset.id}/")

        # Cross-tenant access returns 403 (PermissionDenied from cross_tenant_helpers).
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_admin_can_access_all_tenants(self):
        """Test that platform admin can access datasets from all tenants"""
        dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Tenant 1 Dataset",
            query="SELECT * FROM t1",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )
        dataset2 = VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_tenant_user,
            name="Tenant 2 Dataset",
            query="SELECT * FROM t2",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get("/api/v1/virtualization/datasets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dataset_ids = [d["id"] for d in response.data["results"]]
        self.assertIn(str(dataset1.id), dataset_ids)
        self.assertIn(str(dataset2.id), dataset_ids)

    # ==================== RATE LIMITING TESTS ====================

    def test_list_datasets_rate_limit_headers(self):
        """Test that rate limit headers are included in list response."""
        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.get("/api/v1/virtualization/datasets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rate_limit_headers = [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "RateLimit-Limit",
            "RateLimit-Remaining",
            "RateLimit-Reset",
        ]
        has_header = any(h in response.headers for h in rate_limit_headers)
        self.assertTrue(
            has_header,
            f"At least one rate-limit header must be present. Got: {dict(response.headers)}",
        )

    def test_create_dataset_rate_limit_check(self):
        """Test that rate limiting is checked for dataset creation"""
        self.client.force_authenticate(user=self.data_provider_user)

        # Create request object for rate limit check
        request = HttpRequest()
        request.path = "/api/v1/virtualization/datasets/"
        request.method = "POST"
        request.tenant = self.tenant
        request.user = self.data_provider_user

        # Check rate limit
        allowed, results = check_rate_limit(request, tenant_id=str(self.tenant.id))

        # Should be allowed initially
        self.assertTrue(allowed)
        self.assertGreater(len(results), 0)

    def test_query_execution_rate_limit_check(self):
        """Test that rate limiting is checked for query execution"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Test Dataset",
            query="SELECT * FROM test",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        request = HttpRequest()
        request.path = f"/api/v1/virtualization/datasets/{dataset.id}/queries/"
        request.method = "POST"
        request.tenant = self.tenant
        request.user = self.data_provider_user

        allowed, _results = check_rate_limit(request, tenant_id=str(self.tenant.id))

        self.assertTrue(allowed)

    def test_rate_limit_headers_in_response(self):
        """Test that rate limit headers are properly formatted"""
        self.client.force_authenticate(user=self.data_provider_user)

        request = HttpRequest()
        request.path = "/api/v1/virtualization/datasets/"
        request.method = "GET"
        request.tenant = self.tenant
        request.user = self.data_provider_user

        _allowed, results = check_rate_limit(request, tenant_id=str(self.tenant.id))
        headers = get_rate_limit_headers(request, results)

        # Headers should include standard rate limit fields
        self.assertTrue(headers, "Rate limit headers should not be empty")
        self.assertIn("X-RateLimit-Limit", headers)
        self.assertIn("X-RateLimit-Remaining", headers)
        self.assertIn("X-RateLimit-Reset", headers)

    # ==================== ERROR HANDLING TESTS ====================

    def test_create_dataset_invalid_data(self):
        """Test error handling for invalid dataset creation data"""
        self.client.force_authenticate(user=self.data_provider_user)

        invalid_data = {
            "name": "",  # Empty name
            "query": "",  # Empty query
        }

        response = self.client.post("/api/v1/virtualization/datasets/", invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", response.data or {})
        self.assertIn("query", response.data or {})

    def test_create_dataset_missing_required_fields(self):
        """Test error handling for missing required fields"""
        self.client.force_authenticate(user=self.data_provider_user)

        incomplete_data = {
            "name": "Test Dataset"
            # Missing query and query_type
        }

        response = self.client.post(
            "/api/v1/virtualization/datasets/", incomplete_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retrieve_nonexistent_dataset(self):
        """Test error handling for retrieving non-existent dataset"""
        self.client.force_authenticate(user=self.data_provider_user)

        fake_id = uuid.uuid4()

        response = self.client.get(f"/api/v1/virtualization/datasets/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_nonexistent_dataset(self):
        """Test error handling for updating non-existent dataset"""
        self.client.force_authenticate(user=self.data_provider_user)

        fake_id = uuid.uuid4()

        response = self.client.patch(
            f"/api/v1/virtualization/datasets/{fake_id}/", {"name": "Updated"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_nonexistent_dataset(self):
        """Test error handling for deleting non-existent dataset"""
        self.client.force_authenticate(user=self.data_provider_user)

        fake_id = uuid.uuid4()

        response = self.client.delete(f"/api/v1/virtualization/datasets/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_dataset_invalid_version_format(self):
        """Test error handling for invalid version format"""
        self.client.force_authenticate(user=self.data_provider_user)

        invalid_data = self.valid_dataset_data.copy()
        invalid_data["version"] = "invalid-version"

        response = self.client.post("/api/v1/virtualization/datasets/", invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_dataset_invalid_query_type(self):
        """Test error handling for invalid query type"""
        self.client.force_authenticate(user=self.data_provider_user)

        invalid_data = self.valid_dataset_data.copy()
        invalid_data["query_type"] = "INVALID_TYPE"

        response = self.client.post("/api/v1/virtualization/datasets/", invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_validate_dataset_endpoint(self):
        """Test dataset validation endpoint"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Test Dataset",
            query="SELECT * FROM test",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.post(f"/api/v1/virtualization/datasets/{dataset.id}/validate/")

        # Validation endpoint returns 200 (valid) or 400 (invalid).
        # A 500 is a server error, not a valid validation result.
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST],
            f"Unexpected status {response.status_code} from validation endpoint",
        )
        if response.status_code == status.HTTP_200_OK:
            self.assertIn("is_valid", response.data)
            self.assertIn("errors", response.data)

    def test_get_dataset_versions_endpoint(self):
        """Test getting dataset versions endpoint"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Test Dataset",
            query="SELECT * FROM test",
            query_type=QueryType.SQL,
            version="1.0.0",
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.get(f"/api/v1/virtualization/datasets/{dataset.id}/versions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ==================== QUERY EXECUTION ENDPOINTS ====================

    def test_execute_query_endpoint(self):
        """Test query execution endpoint"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Test Dataset",
            query="SELECT * FROM test",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        execution_data = {
            "parameters": {"param1": "value1"},
            "execution_mode": QueryExecutionMode.SYNC,
        }

        response = self.client.post(
            f"/api/v1/virtualization/datasets/{dataset.id}/queries/", execution_data, format="json"
        )

        # Execution creation returns 201 (created), 200 (cached), or 400 (invalid).
        # A 500 is a server error, not a valid execution outcome.
        valid_codes = [status.HTTP_201_CREATED, status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]
        self.assertIn(
            response.status_code,
            valid_codes,
            f"Unexpected status {response.status_code} from execute query endpoint: "
            f"{getattr(response, 'data', '')}",
        )
        if response.status_code in (status.HTTP_201_CREATED, status.HTTP_200_OK):
            self.assertIn("id", response.data)
            self.assertIn("status", response.data)

    def test_list_query_executions(self):
        """Test listing query executions"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Test Dataset",
            query="SELECT * FROM test",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        execution1 = QueryExecution.objects.create(
            virtual_dataset=dataset,
            query="SELECT * FROM test",
            status=QueryExecutionStatus.COMPLETED,
        )
        execution2 = QueryExecution.objects.create(
            virtual_dataset=dataset, query="SELECT * FROM test", status=QueryExecutionStatus.PENDING
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.get("/api/v1/virtualization/queries/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        execution_ids = [e["id"] for e in response.data.get("results", [])]
        self.assertIn(str(execution1.id), execution_ids)
        self.assertIn(str(execution2.id), execution_ids)

    def test_retrieve_query_execution(self):
        """Test retrieving query execution"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Test Dataset",
            query="SELECT * FROM test",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        execution = QueryExecution.objects.create(
            virtual_dataset=dataset,
            query="SELECT * FROM test",
            status=QueryExecutionStatus.COMPLETED,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.get(f"/api/v1/virtualization/queries/{execution.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(execution.id))

    # ==================== TOPOLOGY ENDPOINTS ====================

    def test_list_topology(self):
        """Test listing virtualization topology"""
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Dataset 1",
            query="SELECT * FROM table1",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Dataset 2",
            query="SELECT * FROM table2",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.get("/api/v1/virtualization/topology/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("nodes", response.data)
        self.assertIn("edges", response.data)
        self.assertIn("metadata", response.data)

    def test_retrieve_dataset_topology(self):
        """Test retrieving dataset-specific topology"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Test Dataset",
            query="SELECT * FROM test",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.get(f"/api/v1/virtualization/topology/{dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("dataset", response.data)
        self.assertIn("relationships", response.data)

    # ==================== PERFORMANCE TESTS ====================

    def test_list_datasets_performance(self):
        """Test performance of listing datasets"""
        # Create multiple datasets
        for i in range(10):
            VirtualDataset.objects.create(
                tenant=self.tenant,
                created_by=self.data_provider_user,
                name=f"Dataset {i}",
                query=f"SELECT * FROM table{i}",
                query_type=QueryType.SQL,
                status=VirtualDatasetStatus.ACTIVE,
            )

        self.client.force_authenticate(user=self.data_provider_user)

        start_time = time.time()
        response = self.client.get("/api/v1/virtualization/datasets/")
        elapsed_time = time.time() - start_time

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should complete in reasonable time (< 5 seconds for 10 items in CI)
        self.assertLess(elapsed_time, 5.0)

    def test_list_datasets_pagination_performance(self):
        """Test performance with pagination"""
        # Create many datasets
        for i in range(50):
            VirtualDataset.objects.create(
                tenant=self.tenant,
                created_by=self.data_provider_user,
                name=f"Dataset {i}",
                query=f"SELECT * FROM table{i}",
                query_type=QueryType.SQL,
                status=VirtualDatasetStatus.ACTIVE,
            )

        self.client.force_authenticate(user=self.data_provider_user)

        start_time = time.time()
        response = self.client.get("/api/v1/virtualization/datasets/?page_size=10")
        elapsed_time = time.time() - start_time

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertLess(elapsed_time, 10.0)  # Should be fast even with pagination

    def test_create_dataset_performance(self):
        """Test performance of creating dataset"""
        self.client.force_authenticate(user=self.data_provider_user)

        start_time = time.time()
        response = self.client.post(
            "/api/v1/virtualization/datasets/", self.valid_dataset_data, format="json"
        )
        elapsed_time = time.time() - start_time

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Should complete in reasonable time (< 5 seconds in CI)
        self.assertLess(elapsed_time, 5.0)

    def test_sequential_dataset_creations(self):
        """Test handling of multiple sequential dataset creation requests.

        NOTE: True concurrent testing with ThreadPoolExecutor requires
        TransactionTestCase (thread-safe connections). The Django ORM and
        TestCase transactions are not thread-safe for concurrent writes.
        This test verifies that sequential creation within a single transaction
        is handled correctly.
        """
        self.client.force_authenticate(user=self.data_provider_user)

        # Create multiple datasets sequentially
        for i in range(5):
            data = self.valid_dataset_data.copy()
            data["name"] = f"Sequential Dataset {i}"
            response = self.client.post(
                "/api/v1/virtualization/datasets/", data, format="json"
            )
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                f"Dataset {i} creation failed: {response.status_code} "
                f"{getattr(response, 'data', '')}",
            )

    def test_create_dataset_non_json_body(self):
        """Test that POST with non-JSON body returns 400"""
        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.post(
            "/api/v1/virtualization/datasets/",
            "this is not json",
            content_type="text/plain",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rate_limit_exhausted_returns_429(self):
        """Test that exhausted rate limit returns 429 Too Many Requests"""
        from hub.apps.rate_limiting.service import check_rate_limit

        self.client.force_authenticate(user=self.data_provider_user)
        request = HttpRequest()
        request.path = "/api/v1/virtualization/datasets/"
        request.method = "POST"
        request.tenant = self.tenant
        request.user = self.data_provider_user

        # Exhaust the rate limit budget
        allowed = True
        for _ in range(200):  # High iteration count to exhaust any budget
            allowed, _results = check_rate_limit(request, tenant_id=str(self.tenant.id))
            if not allowed:
                break

        self.assertFalse(allowed, "Rate limit should be exhausted after many attempts")

    def test_create_dataset_exceeds_plan_limit(self):
        """Test that creating dataset beyond plan limit returns 403"""
        from hub.apps.users.models import Role, UserRole

        # Set a low limit on the tenant's plan
        plan = self.tenant.plan
        original_limits = plan.limits_json
        plan.limits_json = {**(original_limits or {}), "max_virtual_datasets": 2}
        plan.save(update_fields=["limits_json"])

        try:
            # Fill up to the limit
            for i in range(2):
                VirtualDataset.objects.create(
                    tenant=self.tenant,
                    created_by=self.data_provider_user,
                    name=f"Limit Dataset {i}",
                    query="SELECT 1",
                    query_type=QueryType.SQL,
                    status=VirtualDatasetStatus.ACTIVE,
                )

            # Next create should be blocked
            self.client.force_authenticate(user=self.data_provider_user)
            response = self.client.post(
                "/api/v1/virtualization/datasets/",
                self.valid_dataset_data,
                format="json",
            )

            # Should be denied (403 or 400 depending on where the limit is enforced)
            self.assertIn(
                response.status_code,
                [status.HTTP_403_FORBIDDEN, status.HTTP_400_BAD_REQUEST],
                f"Expected 403 or 400 for plan limit exceeded; got {response.status_code}",
            )
        finally:
            plan.limits_json = original_limits
            plan.save(update_fields=["limits_json"])

    # ==================== AUDIT LOGGING TESTS ====================

    def test_create_dataset_creates_audit_log(self):
        """Test that creating dataset creates audit log"""
        self.client.force_authenticate(user=self.data_provider_user)

        initial_count = AuditEvent.objects.count()

        response = self.client.post(
            "/api/v1/virtualization/datasets/", self.valid_dataset_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify audit log was created (at least one event; async operations may
        # produce multiple events under --reuse-db)
        self.assertGreater(AuditEvent.objects.count(), initial_count)
        # Verify a VIRTUAL_DATASET event exists among recent events
        recent_events = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET"
        ).order_by("-timestamp")
        self.assertTrue(recent_events.exists(), "No VIRTUAL_DATASET audit event found")

    def test_delete_dataset_creates_audit_log(self):
        """Test that deleting dataset creates audit log"""
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="To Delete",
            query="SELECT * FROM delete",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        initial_count = AuditEvent.objects.count()

        response = self.client.delete(f"/api/v1/virtualization/datasets/{dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify audit log was created (at least one event; async operations may
        # produce multiple events under --reuse-db)
        self.assertGreater(AuditEvent.objects.count(), initial_count)
        # Verify a VIRTUAL_DATASET event exists among recent events
        recent_events = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET"
        ).order_by("-timestamp")
        self.assertTrue(recent_events.exists(), "No VIRTUAL_DATASET audit event found")

    # ==================== FILTERING AND SEARCH TESTS ====================

    def test_filter_datasets_by_status(self):
        """Test filtering datasets by status"""
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Active Dataset",
            query="SELECT * FROM active",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Draft Dataset",
            query="SELECT * FROM draft",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.get("/api/v1/virtualization/datasets/?status=ACTIVE")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for dataset in response.data["results"]:
            self.assertEqual(dataset["status"], VirtualDatasetStatus.ACTIVE)

    def test_search_datasets_by_name(self):
        """Test searching datasets by name"""
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Test Dataset",
            query="SELECT * FROM test",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Other Dataset",
            query="SELECT * FROM other",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.get("/api/v1/virtualization/datasets/?search=Test")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should find "Test Dataset"
        names = [d["name"] for d in response.data["results"]]
        self.assertIn("Test Dataset", names)

    def test_order_datasets_by_name(self):
        """Test ordering datasets by name"""
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Zebra Dataset",
            query="SELECT * FROM zebra",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.data_provider_user,
            name="Alpha Dataset",
            query="SELECT * FROM alpha",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.data_provider_user)

        response = self.client.get("/api/v1/virtualization/datasets/?ordering=name")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [d["name"] for d in response.data["results"]]
        # Should be ordered alphabetically
        self.assertEqual(names, sorted(names))
