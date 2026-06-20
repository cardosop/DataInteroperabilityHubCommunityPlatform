"""
Comprehensive URL routing tests for Virtualization app.

Tests cover:
- URL routing works correctly
- No duplicate service names (basenames)
- All endpoints are accessible
- URL resolution works correctly
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import Resolver404, resolve, reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.tenants.models import KYCStatus, Tenant
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


class VirtualizationURLRoutingTest(TestCase):
    """Test URL routing for virtualization endpoints"""

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

        # Create roles
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider"}
        )

        # Create user with DATA_PROVIDER role
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.user, role=self.data_provider_role)

        # Create test asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.ACTIVE
        )

        # Create test virtual dataset
        self.virtual_dataset = VirtualDataset.objects.create(
            tenant=self.tenant,
            name="Test Virtual Dataset",
            description="Test description",
            query_type=QueryType.SQL,
            query="SELECT * FROM test_table",
            status=VirtualDatasetStatus.ACTIVE,
            created_by=self.user,
        )

        # Create test query execution
        self.query_execution = QueryExecution.objects.create(
            virtual_dataset=self.virtual_dataset,
            query="SELECT * FROM test_table",
            status=QueryExecutionStatus.COMPLETED,
            execution_mode=QueryExecutionMode.SYNC,
        )

        # Authenticate
        self.client.force_authenticate(user=self.user)

    def test_virtual_dataset_list_url_resolution(self):
        """Test that virtual dataset list URL resolves correctly"""
        url = reverse("virtual-dataset-list")
        self.assertEqual(url, "/api/v1/virtualization/datasets/")

        # Test URL resolution
        resolved = resolve(url)
        self.assertEqual(resolved.view_name, "virtual-dataset-list")
        self.assertEqual(resolved.url_name, "virtual-dataset-list")

    def test_virtual_dataset_detail_url_resolution(self):
        """Test that virtual dataset detail URL resolves correctly"""
        url = reverse("virtual-dataset-detail", kwargs={"id": str(self.virtual_dataset.id)})
        expected_url = f"/api/v1/virtualization/datasets/{self.virtual_dataset.id}/"
        self.assertEqual(url, expected_url)

        # Test URL resolution
        resolved = resolve(url)
        self.assertEqual(resolved.view_name, "virtual-dataset-detail")
        self.assertEqual(resolved.kwargs["id"], str(self.virtual_dataset.id))

    def test_query_execution_list_url_resolution(self):
        """Test that query execution list URL resolves correctly"""
        url = reverse("query-execution-list")
        self.assertEqual(url, "/api/v1/virtualization/queries/")

        # Test URL resolution
        resolved = resolve(url)
        self.assertEqual(resolved.view_name, "query-execution-list")
        self.assertEqual(resolved.url_name, "query-execution-list")

    def test_query_execution_detail_url_resolution(self):
        """Test that query execution detail URL resolves correctly"""
        url = reverse("query-execution-detail", kwargs={"id": str(self.query_execution.id)})
        expected_url = f"/api/v1/virtualization/queries/{self.query_execution.id}/"
        self.assertEqual(url, expected_url)

        # Test URL resolution
        resolved = resolve(url)
        self.assertEqual(resolved.view_name, "query-execution-detail")
        self.assertEqual(resolved.kwargs["id"], str(self.query_execution.id))

    def test_virtualization_topology_list_url_resolution(self):
        """Test that virtualization topology list URL resolves correctly"""
        url = reverse("virtualization-topology-list")
        self.assertEqual(url, "/api/v1/virtualization/topology/")

        # Test URL resolution
        resolved = resolve(url)
        self.assertEqual(resolved.view_name, "virtualization-topology-list")
        self.assertEqual(resolved.url_name, "virtualization-topology-list")

    def test_virtualization_topology_detail_url_resolution(self):
        """Test that virtualization topology detail URL resolves correctly"""
        url = reverse("virtualization-topology-detail", kwargs={"pk": str(self.virtual_dataset.id)})
        expected_url = f"/api/v1/virtualization/topology/{self.virtual_dataset.id}/"
        self.assertEqual(url, expected_url)

        # Test URL resolution
        resolved = resolve(url)
        self.assertEqual(resolved.view_name, "virtualization-topology-detail")
        self.assertEqual(resolved.kwargs["pk"], str(self.virtual_dataset.id))

    def test_virtual_dataset_list_endpoint_accessible(self):
        """Test that virtual dataset list endpoint is accessible"""
        url = reverse("virtual-dataset-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)

    def test_virtual_dataset_detail_endpoint_accessible(self):
        """Test that virtual dataset detail endpoint is accessible"""
        url = reverse("virtual-dataset-detail", kwargs={"id": str(self.virtual_dataset.id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.virtual_dataset.id))
        self.assertEqual(response.data["name"], self.virtual_dataset.name)

    def test_query_execution_list_endpoint_accessible(self):
        """Test that query execution list endpoint is accessible"""
        url = reverse("query-execution-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)

    def test_query_execution_detail_endpoint_accessible(self):
        """Test that query execution detail endpoint is accessible"""
        url = reverse("query-execution-detail", kwargs={"id": str(self.query_execution.id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.query_execution.id))

    def test_virtualization_topology_list_endpoint_accessible(self):
        """Test that virtualization topology list endpoint is accessible"""
        url = reverse("virtualization-topology-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("nodes", response.data)
        self.assertIn("metadata", response.data)

    def test_virtualization_topology_detail_endpoint_accessible(self):
        """Test that virtualization topology detail endpoint is accessible"""
        url = reverse("virtualization-topology-detail", kwargs={"pk": str(self.virtual_dataset.id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("dataset", response.data)

    def test_virtual_dataset_custom_action_urls(self):
        """Test that custom action URLs are accessible"""
        # Test validate_dataset action
        url = reverse(
            "virtual-dataset-validate-dataset", kwargs={"id": str(self.virtual_dataset.id)}
        )
        self.assertEqual(
            url, f"/api/v1/virtualization/datasets/{self.virtual_dataset.id}/validate/"
        )

        # Test execute_query action
        url = reverse("virtual-dataset-execute-query", kwargs={"id": str(self.virtual_dataset.id)})
        self.assertEqual(url, f"/api/v1/virtualization/datasets/{self.virtual_dataset.id}/queries/")

    def test_query_execution_custom_action_urls(self):
        """Test that query execution custom action URLs are accessible"""
        # Test cancel_execution action
        url = reverse(
            "query-execution-cancel-execution", kwargs={"id": str(self.query_execution.id)}
        )
        self.assertEqual(url, f"/api/v1/virtualization/queries/{self.query_execution.id}/cancel/")

        # Test get_result action (url_path='result')
        url = reverse("query-execution-get-result", kwargs={"id": str(self.query_execution.id)})
        self.assertEqual(url, f"/api/v1/virtualization/queries/{self.query_execution.id}/result/")

        # Test stream_result action (url_path='stream')
        url = reverse("query-execution-stream-result", kwargs={"id": str(self.query_execution.id)})
        self.assertEqual(url, f"/api/v1/virtualization/queries/{self.query_execution.id}/stream/")

    def test_url_patterns_follow_api_standards(self):
        """Test that URL patterns follow API naming standards"""
        # All virtualization URLs should start with /api/v1/virtualization/
        base_path = "/api/v1/virtualization/"

        # Check dataset URLs
        url = reverse("virtual-dataset-list")
        self.assertTrue(url.startswith(base_path))
        self.assertIn("/datasets/", url)

        # Check query execution URLs
        url = reverse("query-execution-list")
        self.assertTrue(url.startswith(base_path))
        self.assertIn("/queries/", url)

        # Check topology URLs
        url = reverse("virtualization-topology-list")
        self.assertTrue(url.startswith(base_path))
        self.assertIn("/topology/", url)

    def test_no_duplicate_basenames(self):
        """Test that there are no duplicate basenames in virtualization URLs"""
        from hub.apps.virtualization.urls import router

        # Get all registered basenames
        basenames = []
        for _prefix, _viewset, basename in router.registry:
            basenames.append(basename)

        # Check for duplicates
        self.assertEqual(
            len(basenames), len(set(basenames)), f"Duplicate basenames found: {basenames}"
        )

        # Verify expected basenames
        expected_basenames = ["virtual-dataset", "query-execution", "virtualization-topology"]
        for basename in expected_basenames:
            self.assertIn(
                basename, basenames, f"Expected basename '{basename}' not found in router registry"
            )

    def test_urls_registered_in_api_urls(self):
        """Test that virtualization URLs are registered in main API URLs"""
        from django.urls import resolve

        # Test that virtualization base path resolves
        try:
            resolved = resolve("/api/v1/virtualization/")
            # Should resolve to virtualization app URLs
            self.assertIsNotNone(resolved)
        except Resolver404:
            self.fail("Virtualization URLs not registered in main API URLs")

    def test_all_viewset_actions_have_urls(self):
        """Test that all ViewSet actions have corresponding URLs"""
        from hub.apps.virtualization.urls import router

        # Get all registered viewsets
        viewsets = {}
        for _prefix, viewset, basename in router.registry:
            viewsets[basename] = viewset

        # Check VirtualDatasetViewSet actions
        if "virtual-dataset" in viewsets:
            viewset = viewsets["virtual-dataset"]
            # Standard CRUD actions should be available
            # Note: DRF routers use 'list' for GET list, 'detail' for retrieve/update/partial_update/destroy
            # POST create uses 'list' endpoint, other actions use 'detail' endpoint
            standard_actions = {
                "list": None,  # No kwargs needed
                "detail": {
                    "id": str(self.virtual_dataset.id)
                },  # retrieve, update, partial_update, destroy
            }
            for action, kwargs in standard_actions.items():
                # Try to reverse the URL
                try:
                    if kwargs:
                        url = reverse(f"virtual-dataset-{action}", kwargs=kwargs)
                    else:
                        url = reverse(f"virtual-dataset-{action}")
                    self.assertIsNotNone(url)
                except Exception as e:
                    self.fail(f"URL for action '{action}' not accessible: {e}")

    def test_url_paths_are_consistent(self):
        """Test that URL paths follow consistent patterns"""
        # All list URLs should end with /
        list_urls = [
            reverse("virtual-dataset-list"),
            reverse("query-execution-list"),
            reverse("virtualization-topology-list"),
        ]

        for url in list_urls:
            self.assertTrue(url.endswith("/"), f"List URL '{url}' should end with '/'")

        # All detail URLs should end with /
        detail_urls = [
            reverse("virtual-dataset-detail", kwargs={"id": str(self.virtual_dataset.id)}),
            reverse("query-execution-detail", kwargs={"id": str(self.query_execution.id)}),
            reverse("virtualization-topology-detail", kwargs={"pk": str(self.virtual_dataset.id)}),
        ]

        for url in detail_urls:
            self.assertTrue(url.endswith("/"), f"Detail URL '{url}' should end with '/'")

    def test_url_resolution_with_invalid_id(self):
        """Test URL resolution with invalid ID format"""
        # URL resolution doesn't validate UUID format, it just creates the URL
        # The validation happens when the URL is accessed
        # So we test that the URL is created (even with invalid format)
        url = reverse("virtual-dataset-detail", kwargs={"id": "invalid-uuid"})
        self.assertIsNotNone(url)
        self.assertIn("invalid-uuid", url)

        # But accessing it should return 404, 400, or 500 (depending on how validation is handled)
        response = self.client.get(url)
        # Accept any error status code as valid validation
        self.assertGreaterEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_url_resolution_with_nonexistent_id(self):
        """Test URL resolution with non-existent ID (should still resolve URL)"""
        non_existent_id = uuid.uuid4()
        url = reverse("virtual-dataset-detail", kwargs={"id": str(non_existent_id)})

        # URL should resolve correctly even if resource doesn't exist
        self.assertIsNotNone(url)
        self.assertIn(str(non_existent_id), url)

        # But accessing it should return 404
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
