"""
Unit tests for Virtualization API views.

Tests all CRUD endpoints and custom actions using real services and models (no mocks/stubs).
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan
from hub.apps.users.models import Role, User, UserRole, UserStatus
from hub.apps.virtualization.models import QueryType, VirtualDataset, VirtualDatasetStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class VirtualDatasetViewSetTest(TestCase):
    """Test VirtualDatasetViewSet CRUD operations"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            kyc_status=KYCStatus.VERIFIED,
            virtualization_enabled=True,
        )

        # Create another tenant for isolation tests
        _uid = uuid.uuid4().hex[:8]
        self.other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}",
            slug=f"other-tenant-{_uid}",
            kyc_status=KYCStatus.VERIFIED,
            virtualization_enabled=True,
        )

        # Create platform admin user
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
        self.other_data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.other_tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )

        # Create tenant user with DATA_PROVIDER role
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.user, role=self.data_provider_role)

        # Create other tenant user with DATA_PROVIDER role
        self.other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.other_user, role=self.other_data_provider_role)

        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

        # Valid virtual dataset data
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

    def test_create_virtual_dataset(self):
        """Test creating a virtual dataset"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/virtualization/datasets/", self.valid_dataset_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], self.valid_dataset_data["name"])
        self.assertEqual(response.data["query_type"], self.valid_dataset_data["query_type"])
        self.assertEqual(response.data["status"], self.valid_dataset_data["status"])

        # Verify dataset was created in database
        dataset = VirtualDataset.objects.get(id=response.data["id"])
        self.assertEqual(dataset.name, self.valid_dataset_data["name"])
        self.assertEqual(dataset.tenant_id, self.tenant.id)
        self.assertEqual(dataset.created_by_id, self.user.id)

    def test_create_virtual_dataset_minimal_data(self):
        """Test creating a virtual dataset with minimal required fields"""
        self.client.force_authenticate(user=self.user)

        minimal_data = {
            "name": "Minimal Dataset",
            "query": "SELECT * FROM users",
            "query_type": "SQL",
            "sources": [{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        }

        response = self.client.post("/api/v1/virtualization/datasets/", minimal_data, format="json")

        if response.status_code == status.HTTP_400_BAD_REQUEST:
            self.fail(f"Create failed with 400: {response.data}")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["name"], minimal_data["name"])

    def test_create_virtual_dataset_invalid_query(self):
        """Test creating a virtual dataset with invalid query"""
        self.client.force_authenticate(user=self.user)

        invalid_data = self.valid_dataset_data.copy()
        invalid_data["query"] = ""  # Empty query

        response = self.client.post("/api/v1/virtualization/datasets/", invalid_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_virtual_dataset_unauthorized(self):
        """Test creating a virtual dataset without authentication"""
        response = self.client.post(
            "/api/v1/virtualization/datasets/", self.valid_dataset_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_virtual_datasets(self):
        """Test listing virtual datasets"""
        self.client.force_authenticate(user=self.user)

        # Create test datasets
        dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Dataset 1",
            query="SELECT * FROM table1",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )
        dataset2 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Dataset 2",
            query="SELECT * FROM table2",
            query_type=QueryType.SPARQL,
            status=VirtualDatasetStatus.DRAFT,
        )

        response = self.client.get("/api/v1/virtualization/datasets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 2)

        # Verify tenant isolation
        dataset_ids = [d["id"] for d in response.data["results"]]
        self.assertIn(str(dataset1.id), dataset_ids)
        self.assertIn(str(dataset2.id), dataset_ids)

    def test_list_virtual_datasets_with_filters(self):
        """Test listing virtual datasets with filters"""
        self.client.force_authenticate(user=self.user)

        # Create test datasets
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="SQL Dataset",
            query="SELECT * FROM table1",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="SPARQL Dataset",
            query="SELECT ?s ?p ?o WHERE { ?s ?p ?o }",
            query_type=QueryType.SPARQL,
            status=VirtualDatasetStatus.DRAFT,
        )

        # Filter by query_type
        response = self.client.get("/api/v1/virtualization/datasets/?query_type=SQL")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for dataset in response.data["results"]:
            self.assertEqual(dataset["query_type"], QueryType.SQL)

        # Filter by status
        response = self.client.get("/api/v1/virtualization/datasets/?status=ACTIVE")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for dataset in response.data["results"]:
            self.assertEqual(dataset["status"], VirtualDatasetStatus.ACTIVE)

    def test_list_virtual_datasets_tenant_isolation(self):
        """Test tenant isolation in list endpoint"""
        self.client.force_authenticate(user=self.user)

        # Create dataset in user's tenant
        dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="My Dataset",
            query="SELECT * FROM table1",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        # Create dataset in other tenant
        dataset2 = VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_user,
            name="Other Dataset",
            query="SELECT * FROM table2",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        response = self.client.get("/api/v1/virtualization/datasets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dataset_ids = [d["id"] for d in response.data["results"]]
        self.assertIn(str(dataset1.id), dataset_ids)
        self.assertNotIn(str(dataset2.id), dataset_ids)

    def test_retrieve_virtual_dataset(self):
        """Test retrieving a virtual dataset"""
        self.client.force_authenticate(user=self.user)

        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        response = self.client.get(f"/api/v1/virtualization/datasets/{dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(dataset.id))
        self.assertEqual(response.data["name"], dataset.name)

    def test_retrieve_virtual_dataset_not_found(self):
        """Test retrieving a non-existent virtual dataset"""
        self.client.force_authenticate(user=self.user)

        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/virtualization/datasets/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        # API wraps errors in {"error": {...}} or {"detail": "..."}
        self.assertTrue(
            "detail" in response.data or "error" in response.data,
            f"Expected 'detail' or 'error' in response: {response.data}",
        )

    def test_list_virtual_datasets_unauthenticated_returns_401(self):
        """Test list endpoint returns 401 when unauthenticated (error_handling)."""
        response = self.client.get("/api/v1/virtualization/datasets/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_virtual_dataset_missing_required_returns_400(self):
        """Test create with missing required fields returns 400 (error_handling)."""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/virtualization/datasets/",
            {"query": "SELECT 1"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(
            "name" in (response.data or {}) or "query_type" in (response.data or {}),
            f"Expected field errors in response: {getattr(response, 'data', None)}",
        )

    def test_retrieve_virtual_dataset_response_structure_tdd(self):
        """TDD: retrieve response contains required keys."""
        self.client.force_authenticate(user=self.user)
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="TDD Dataset",
            query="SELECT * FROM t",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )
        response = self.client.get(f"/api/v1/virtualization/datasets/{dataset.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for key in ("id", "name", "query", "query_type", "status", "created_at", "updated_at"):
            self.assertIn(key, response.data, f"Missing key: {key}")

    def test_retrieve_virtual_dataset_tenant_isolation(self):
        """Test tenant isolation in retrieve endpoint"""
        self.client.force_authenticate(user=self.user)

        # Create dataset in other tenant
        dataset = VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_user,
            name="Other Dataset",
            query="SELECT * FROM table",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        response = self.client.get(f"/api/v1/virtualization/datasets/{dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_update_virtual_dataset(self):
        """Test updating a virtual dataset"""
        self.client.force_authenticate(user=self.user)

        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Original Name",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        update_data = {
            "name": "Updated Name",
            "description": "Updated description",
            "status": VirtualDatasetStatus.ACTIVE,
        }

        response = self.client.put(
            f"/api/v1/virtualization/datasets/{dataset.id}/", update_data, format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Update failed: {getattr(response, 'data', '')}",
        )
        self.assertEqual(response.data["name"], update_data["name"])
        self.assertEqual(response.data["status"], update_data["status"])

        # Verify update in database
        dataset.refresh_from_db()
        self.assertEqual(dataset.name, update_data["name"])
        self.assertEqual(dataset.status, update_data["status"])

    def test_partial_update_virtual_dataset(self):
        """Test partially updating a virtual dataset"""
        self.client.force_authenticate(user=self.user)

        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Original Name",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        update_data = {"name": "Updated Name"}

        response = self.client.patch(
            f"/api/v1/virtualization/datasets/{dataset.id}/", update_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], update_data["name"])

        # Verify other fields unchanged
        dataset.refresh_from_db()
        self.assertEqual(dataset.query, "SELECT * FROM users")

    def test_update_virtual_dataset_tenant_isolation(self):
        """Test tenant isolation in update endpoint"""
        self.client.force_authenticate(user=self.user)

        # Create dataset in other tenant
        dataset = VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_user,
            name="Other Dataset",
            query="SELECT * FROM table",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        update_data = {"name": "Hacked Name"}

        response = self.client.put(
            f"/api/v1/virtualization/datasets/{dataset.id}/", update_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_delete_virtual_dataset(self):
        """Test deleting a virtual dataset"""
        self.client.force_authenticate(user=self.user)

        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="To Delete",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        dataset_id = dataset.id

        response = self.client.delete(f"/api/v1/virtualization/datasets/{dataset_id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify deletion
        self.assertFalse(VirtualDataset.objects.filter(id=dataset_id).exists())

    def test_delete_virtual_dataset_tenant_isolation(self):
        """Test tenant isolation in delete endpoint"""
        self.client.force_authenticate(user=self.user)

        # Create dataset in other tenant
        dataset = VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_user,
            name="Other Dataset",
            query="SELECT * FROM table",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        response = self.client.delete(f"/api/v1/virtualization/datasets/{dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        # Verify dataset still exists
        self.assertTrue(VirtualDataset.objects.filter(id=dataset.id).exists())

    def test_validate_virtual_dataset(self):
        """Test validating a virtual dataset"""
        self.client.force_authenticate(user=self.user)

        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT id, name, age FROM users WHERE age > 18",
            query_type=QueryType.SQL,
            schema={
                "fields": [
                    {"name": "id", "type": "integer"},
                    {"name": "name", "type": "string"},
                    {"name": "age", "type": "integer"},
                ]
            },
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        response = self.client.post(
            f"/api/v1/virtualization/datasets/{dataset.id}/validate/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("is_valid", response.data)
        self.assertIn("errors", response.data)
        self.assertIn("warnings", response.data)
        self.assertIn("details", response.data)

    def test_validate_virtual_dataset_not_found(self):
        """Test validating a non-existent virtual dataset"""
        self.client.force_authenticate(user=self.user)

        fake_id = uuid.uuid4()
        response = self.client.post(
            f"/api/v1/virtualization/datasets/{fake_id}/validate/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_validate_virtual_dataset_tenant_isolation(self):
        """Test tenant isolation in validate endpoint"""
        self.client.force_authenticate(user=self.user)

        # Create dataset in other tenant
        dataset = VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_user,
            name="Other Dataset",
            query="SELECT * FROM table",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        response = self.client.post(
            f"/api/v1/virtualization/datasets/{dataset.id}/validate/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_virtual_dataset_versions(self):
        """Test getting all versions of a virtual dataset"""
        self.client.force_authenticate(user=self.user)

        # Create multiple versions of the same dataset
        dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM v1",
            query_type=QueryType.SQL,
            version="1.0.0",
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM v2",
            query_type=QueryType.SQL,
            version="2.0.0",
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM v3",
            query_type=QueryType.SQL,
            version="3.0.0",
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        response = self.client.get(f"/api/v1/virtualization/datasets/{dataset1.id}/versions/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("versions", response.data)
        self.assertIn("count", response.data)
        self.assertEqual(response.data["count"], 3)

        # Verify all versions are returned
        version_numbers = [v["version"] for v in response.data["versions"]]
        self.assertIn("1.0.0", version_numbers)
        self.assertIn("2.0.0", version_numbers)
        self.assertIn("3.0.0", version_numbers)

    def test_get_virtual_dataset_versions_tenant_isolation(self):
        """Test tenant isolation in versions endpoint"""
        self.client.force_authenticate(user=self.user)

        # Create dataset in other tenant
        dataset = VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_user,
            name="Other Dataset",
            query="SELECT * FROM table",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        response = self.client.get(f"/api/v1/virtualization/datasets/{dataset.id}/versions/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_admin_can_access_all_datasets(self):
        """Test platform admin can access datasets from all tenants"""
        self.client.force_authenticate(user=self.platform_admin)

        # Create dataset in regular tenant
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Regular Dataset",
            query="SELECT * FROM table",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        response = self.client.get(f"/api/v1/virtualization/datasets/{dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(dataset.id))

    def test_search_virtual_datasets(self):
        """Test searching virtual datasets"""
        self.client.force_authenticate(user=self.user)

        # Create test datasets
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Customer Dataset",
            query="SELECT * FROM customers",
            query_type=QueryType.SQL,
            description="Customer data",
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Product Dataset",
            query="SELECT * FROM products",
            query_type=QueryType.SQL,
            description="Product data",
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        # Search by name
        response = self.client.get("/api/v1/virtualization/datasets/?search=Customer")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)
        self.assertIn("Customer", response.data["results"][0]["name"])

        # Search by description
        response = self.client.get("/api/v1/virtualization/datasets/?search=Product")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)

    def test_ordering_virtual_datasets(self):
        """Test ordering virtual datasets"""
        self.client.force_authenticate(user=self.user)

        # Create test datasets
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="A Dataset",
            query="SELECT * FROM table1",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )
        VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="B Dataset",
            query="SELECT * FROM table2",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        # Order by name ascending
        response = self.client.get("/api/v1/virtualization/datasets/?ordering=name")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = [d["name"] for d in response.data["results"]]
        self.assertIn("A Dataset", names)
        self.assertIn("B Dataset", names)
        # Verify actual ascending order (A before B)
        a_idx = names.index("A Dataset") if "A Dataset" in names else -1
        b_idx = names.index("B Dataset") if "B Dataset" in names else -1
        self.assertLess(a_idx, b_idx, f"Expected A before B in ascending order; got {names}")

        # Order by name descending
        response = self.client.get("/api/v1/virtualization/datasets/?ordering=-name")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names_desc = [d["name"] for d in response.data["results"]]
        self.assertIn("A Dataset", names_desc)
        self.assertIn("B Dataset", names_desc)
        # Verify actual descending order (B before A)
        a_idx_desc = names_desc.index("A Dataset") if "A Dataset" in names_desc else -1
        b_idx_desc = names_desc.index("B Dataset") if "B Dataset" in names_desc else -1
        self.assertLess(b_idx_desc, a_idx_desc,
                        f"Expected B before A in descending order; got {names_desc}")

    def test_filter_by_owner(self):
        """Test filtering virtual datasets by owner/created_by"""
        self.client.force_authenticate(user=self.user)

        # Create datasets by different users
        dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="My Dataset",
            query="SELECT * FROM table1",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )
        # Create another user in the same tenant
        import uuid

        unique_email = f"other-{uuid.uuid4().hex[:8]}@example.com"
        other_user = User.objects.create_user(
            email=unique_email, password="testpass123", tenant=self.tenant, status=UserStatus.ACTIVE
        )
        dataset2 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=other_user,
            name="Other User Dataset",
            query="SELECT * FROM table2",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        # Filter by owner (using created_by)
        response = self.client.get(f"/api/v1/virtualization/datasets/?created_by={self.user.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dataset_ids = [d["id"] for d in response.data["results"]]
        self.assertIn(str(dataset1.id), dataset_ids)
        self.assertNotIn(str(dataset2.id), dataset_ids)

        # Filter by owner (using owner alias)
        response = self.client.get(f"/api/v1/virtualization/datasets/?owner={other_user.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        dataset_ids = [d["id"] for d in response.data["results"]]
        self.assertIn(str(dataset2.id), dataset_ids)
        self.assertNotIn(str(dataset1.id), dataset_ids)

    def test_pagination(self):
        """Test pagination for virtual datasets list"""
        self.client.force_authenticate(user=self.user)

        # Create multiple datasets
        for i in range(15):
            VirtualDataset.objects.create(
                tenant=self.tenant,
                created_by=self.user,
                name=f"Dataset {i}",
                query=f"SELECT * FROM table{i}",
                query_type=QueryType.SQL,
                sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
            )

        # Test first page
        response = self.client.get("/api/v1/virtualization/datasets/?page=1&page_size=10")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("page", response.data)
        self.assertIn("page_size", response.data)
        self.assertIn("total_pages", response.data)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 10)

        # Test second page
        response = self.client.get("/api/v1/virtualization/datasets/?page=2&page_size=10")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 5)

    def test_rate_limit_headers_present(self):
        """Test that rate limit headers are present in responses"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/virtualization/datasets/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check for rate limit headers (may be optional depending on implementation)
        headers = response.headers
        rate_limit_headers = [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "RateLimit-Limit",
            "RateLimit-Remaining",
            "RateLimit-Reset",
        ]
        has_rate_limit_header = any(h in headers for h in rate_limit_headers)
        self.assertTrue(
            has_rate_limit_header,
            f"At least one rate-limit header must be present in the response. "
            f"Headers found: {dict(headers)}",
        )

    def test_rbac_write_operations_require_role(self):
        """Test that write operations require DATA_PROVIDER or TENANT_ADMIN role"""
        # Create user without DATA_PROVIDER or TENANT_ADMIN role
        consumer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_CONSUMER", defaults={"description": "Data Consumer"}
        )
        consumer_user = User.objects.create_user(
            email=f"consumer-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=consumer_user, role=consumer_role)

        self.client.force_authenticate(user=consumer_user)

        # Try to create virtual dataset - should fail due to missing role
        data = {"name": "Test Dataset", "query": "SELECT * FROM users", "query_type": QueryType.SQL}

        response = self.client.post("/api/v1/virtualization/datasets/", data, format="json")

        # Should be denied (403 Forbidden) due to missing role
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_rbac_read_operations_allow_authenticated_users(self):
        """Test that read operations allow any authenticated user"""
        # Create user without DATA_PROVIDER or TENANT_ADMIN role
        consumer_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_CONSUMER", defaults={"description": "Data Consumer"}
        )
        consumer_user = User.objects.create_user(
            email=f"consumer-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=consumer_user, role=consumer_role)

        # Create dataset
        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Dataset",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        self.client.force_authenticate(user=consumer_user)

        # Should be able to read
        response = self.client.get(f"/api/v1/virtualization/datasets/{dataset.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_abac_policy_check_integration(self):
        """Test that a DENY ABAC policy blocks virtual dataset access."""
        from hub.apps.governance.models import AccessPolicy

        self.client.force_authenticate(user=self.user)

        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="ABAC Test Dataset",
            query="SELECT 1",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
            status=VirtualDatasetStatus.ACTIVE,
        )

        # Create a DENY policy targeting virtual datasets in this tenant
        AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Deny virtualization read",
            effect="DENY",
            conditions={"resource": {"type": "VIRTUAL_DATASET"}},
        )

        response = self.client.get(f"/api/v1/virtualization/datasets/{dataset.id}/")

        # A DENY policy MUST block access with 403 FORBIDDEN.
        # The ABAC engine is expected to be active in the test environment.
        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
            f"ABAC DENY policy should block virtual dataset access. "
            f"Got status {response.status_code}: {getattr(response, 'data', '')}",
        )

    def test_audit_logging_on_create(self):
        """Test that audit events are created on virtual dataset creation"""
        from hub.apps.audit.models import AuditEvent

        self.client.force_authenticate(user=self.user)

        initial_count = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="VIRTUAL_DATASET_CREATED"
        ).count()

        response = self.client.post(
            "/api/v1/virtualization/datasets/", self.valid_dataset_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify audit event was created
        final_count = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="VIRTUAL_DATASET_CREATED"
        ).count()

        self.assertEqual(final_count, initial_count + 1)

        # Verify audit event details
        audit_event = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="VIRTUAL_DATASET_CREATED", actor_user=self.user
        ).latest("timestamp")

        self.assertEqual(str(audit_event.resource_id), response.data["id"])
        self.assertIn("name", audit_event.details_json)
        self.assertEqual(audit_event.details_json["name"], self.valid_dataset_data["name"])

    def test_audit_logging_on_update(self):
        """Test that audit events are created on virtual dataset update"""
        from hub.apps.audit.models import AuditEvent

        self.client.force_authenticate(user=self.user)

        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Original Name",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.DRAFT,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        initial_count = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="VIRTUAL_DATASET_UPDATED"
        ).count()

        update_data = {"name": "Updated Name", "status": VirtualDatasetStatus.ACTIVE}

        response = self.client.put(
            f"/api/v1/virtualization/datasets/{dataset.id}/", update_data, format="json"
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
            f"Update failed: {getattr(response, 'data', '')}",
        )

        # Verify audit event was created
        final_count = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="VIRTUAL_DATASET_UPDATED"
        ).count()

        self.assertEqual(final_count, initial_count + 1)

    def test_audit_logging_on_delete(self):
        """Test that audit events are created on virtual dataset deletion"""
        from hub.apps.audit.models import AuditEvent

        self.client.force_authenticate(user=self.user)

        dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="To Delete",
            query="SELECT * FROM users",
            query_type=QueryType.SQL,
            sources=[{"type": "postgresql", "host": "localhost", "database": "testdb"}],
        )

        initial_count = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="VIRTUAL_DATASET_DELETED"
        ).count()

        response = self.client.delete(f"/api/v1/virtualization/datasets/{dataset.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify audit event was created
        final_count = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="VIRTUAL_DATASET_DELETED"
        ).count()

        self.assertEqual(final_count, initial_count + 1)

        # Verify audit event details
        audit_event = AuditEvent.objects.filter(
            resource_type="VIRTUAL_DATASET", action="VIRTUAL_DATASET_DELETED", actor_user=self.user
        ).latest("timestamp")

        self.assertEqual(str(audit_event.resource_id), str(dataset.id))
        self.assertIn("name", audit_event.details_json)
        self.assertEqual(audit_event.details_json["name"], dataset.name)

    # ==================== EDGE CASE TESTS ====================

    def test_update_virtual_dataset_not_found(self):
        """Test that updating a non-existent virtual dataset returns 404"""
        self.client.force_authenticate(user=self.user)
        fake_id = uuid.uuid4()

        response = self.client.patch(
            f"/api/v1/virtualization/datasets/{fake_id}/",
            {"name": "New Name"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_virtual_dataset_not_found(self):
        """Test that deleting a non-existent virtual dataset returns 404"""
        self.client.force_authenticate(user=self.user)
        fake_id = uuid.uuid4()

        response = self.client.delete(f"/api/v1/virtualization/datasets/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
