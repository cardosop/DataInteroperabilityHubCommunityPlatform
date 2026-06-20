"""
Unit tests for Virtualization Topology API views.

Tests topology endpoints using real services and models (no mocks/stubs).
"""

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.governance.models import AccessPolicy
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


class VirtualizationTopologyViewSetTest(TestCase):
    """Test VirtualizationTopologyViewSet operations"""

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
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )

        # Create platform admin user
        self.platform_admin = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            is_platform_admin=True,
        )

        # Create regular user
        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create user in other tenant
        self.other_user = User.objects.create_user(
            email=f"other-user-{uuid.uuid4()}@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Get or create DATA_PROVIDER role
        self.data_provider_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="DATA_PROVIDER", defaults={"description": "Data Provider Role"}
        )

        # Get or create TENANT_ADMIN role
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN", defaults={"description": "Tenant Admin Role"}
        )

        # Assign roles to user
        UserRole.objects.get_or_create(user=self.user, role=self.data_provider_role)

        # Create virtual datasets
        self.dataset1 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Dataset 1",
            description="First test dataset",
            query="SELECT * FROM table1",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[
                {"id": "source1", "type": "postgresql", "host": "localhost", "database": "db1"},
                {"id": "source2", "type": "mysql", "host": "localhost", "database": "db2"},
            ],
        )

        self.dataset2 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Dataset 2",
            description="Second test dataset",
            query="SELECT * FROM table2",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[
                {"id": "source1", "type": "postgresql", "host": "localhost", "database": "db1"},
                {"id": "source3", "type": "sparql", "endpoint": "http://localhost:8890/sparql"},
            ],
        )

        self.dataset3 = VirtualDataset.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            name="Dataset 3",
            description="Third test dataset",
            query="SELECT * FROM table3",
            query_type=QueryType.SPARQL,
            status=VirtualDatasetStatus.DRAFT,
            sources=[{"id": "source4", "type": "rest", "url": "https://api.example.com/data"}],
        )

        # Create dataset in other tenant
        self.other_dataset = VirtualDataset.objects.create(
            tenant=self.other_tenant,
            created_by=self.other_user,
            name="Other Dataset",
            description="Dataset in other tenant",
            query="SELECT * FROM other_table",
            query_type=QueryType.SQL,
            status=VirtualDatasetStatus.ACTIVE,
            sources=[
                {"id": "source5", "type": "postgresql", "host": "localhost", "database": "otherdb"}
            ],
        )

        # Create query executions for health metrics
        self.execution1 = QueryExecution.objects.create(
            virtual_dataset=self.dataset1,
            query="SELECT * FROM table1",
            execution_mode=QueryExecutionMode.MANUAL,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now() - timedelta(hours=2),
            completed_at=timezone.now() - timedelta(hours=1, minutes=55),
            metrics={"duration_ms": 5000, "rows_returned": 100},
        )

        self.execution2 = QueryExecution.objects.create(
            virtual_dataset=self.dataset1,
            query="SELECT * FROM table1",
            execution_mode=QueryExecutionMode.MANUAL,
            status=QueryExecutionStatus.COMPLETED,
            started_at=timezone.now() - timedelta(hours=1),
            completed_at=timezone.now() - timedelta(minutes=55),
            metrics={"duration_ms": 3000, "rows_returned": 50},
        )

        self.execution3 = QueryExecution.objects.create(
            virtual_dataset=self.dataset1,
            query="SELECT * FROM table1",
            execution_mode=QueryExecutionMode.MANUAL,
            status=QueryExecutionStatus.FAILED,
            started_at=timezone.now() - timedelta(minutes=30),
            completed_at=timezone.now() - timedelta(minutes=25),
            metrics={"error": "Connection timeout"},
        )

    def test_list_topology_authenticated(self):
        """Test listing topology requires authentication"""
        response = self.client.get("/api/v1/virtualization/topology/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_topology_success(self):
        """Test successful topology listing"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/virtualization/topology/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check response structure
        self.assertIn("nodes", response.data)
        self.assertIn("edges", response.data)
        self.assertIn("metadata", response.data)
        self.assertIn("summary", response.data)

        # Check nodes
        nodes = response.data["nodes"]
        self.assertEqual(len(nodes), 3)  # Should have 3 datasets in tenant

        # Check that all datasets are present
        dataset_ids = [node["id"] for node in nodes]
        self.assertIn(str(self.dataset1.id), dataset_ids)
        self.assertIn(str(self.dataset2.id), dataset_ids)
        self.assertIn(str(self.dataset3.id), dataset_ids)

        # Check that other tenant's dataset is not included
        self.assertNotIn(str(self.other_dataset.id), dataset_ids)

        # Check edges (relationships based on shared sources)
        edges = response.data["edges"]
        # dataset1 and dataset2 share source1, so there should be an edge
        shared_source_edges = [
            edge
            for edge in edges
            if (edge["source"] == str(self.dataset1.id) and edge["target"] == str(self.dataset2.id))
            or (edge["source"] == str(self.dataset2.id) and edge["target"] == str(self.dataset1.id))
        ]
        self.assertGreater(len(shared_source_edges), 0)

        # Check metadata
        metadata = response.data["metadata"]
        self.assertEqual(metadata["dataset_count"], 3)
        self.assertIn("generated_at", metadata)

        # Check summary
        summary = response.data["summary"]
        self.assertEqual(summary["total_datasets"], 3)
        self.assertEqual(summary["active_datasets"], 2)  # dataset1 and dataset2 are ACTIVE

    def test_list_topology_with_health_metrics(self):
        """Test topology listing with health metrics"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/virtualization/topology/?include_health_metrics=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        nodes = response.data["nodes"]
        dataset1_node = next(node for node in nodes if node["id"] == str(self.dataset1.id))

        # Check health metrics
        self.assertIn("health_metrics", dataset1_node)
        health_metrics = dataset1_node["health_metrics"]
        self.assertIn("health_score", health_metrics)
        self.assertIn("total_executions", health_metrics)
        self.assertIn("completed_executions", health_metrics)
        self.assertIn("failed_executions", health_metrics)
        self.assertIn("success_rate", health_metrics)
        self.assertIn("is_active", health_metrics)

        # dataset1 has 2 completed and 1 failed execution
        self.assertEqual(health_metrics["total_executions"], 3)
        self.assertEqual(health_metrics["completed_executions"], 2)
        self.assertEqual(health_metrics["failed_executions"], 1)
        self.assertIsNotNone(health_metrics["success_rate"])

    def test_list_topology_without_health_metrics(self):
        """Test topology listing without health metrics"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/virtualization/topology/?include_health_metrics=false")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        nodes = response.data["nodes"]
        dataset1_node = next(node for node in nodes if node["id"] == str(self.dataset1.id))

        # Health metrics should not be present
        self.assertNotIn("health_metrics", dataset1_node)

    def test_retrieve_dataset_topology_success(self):
        """Test retrieving topology for a specific dataset"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/virtualization/topology/{self.dataset1.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check response structure
        self.assertIn("dataset", response.data)
        self.assertIn("relationships", response.data)
        self.assertIn("health_metrics", response.data)

        # Check dataset node
        dataset = response.data["dataset"]
        self.assertEqual(dataset["id"], str(self.dataset1.id))
        self.assertEqual(dataset["name"], self.dataset1.name)

        # Check relationships
        relationships = response.data["relationships"]
        # Should have relationship with dataset2 (shared source)
        dataset2_relationships = [
            rel
            for rel in relationships
            if rel["target"] == str(self.dataset2.id) or rel["source"] == str(self.dataset2.id)
        ]
        self.assertGreater(len(dataset2_relationships), 0)

    def test_retrieve_dataset_topology_not_found(self):
        """Test retrieving topology for non-existent dataset"""
        self.client.force_authenticate(user=self.user)

        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/virtualization/topology/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_dataset_topology_other_tenant(self):
        """Test that users cannot access topology for datasets in other tenants"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/virtualization/topology/{self.other_dataset.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_platform_admin_can_access_all_tenants(self):
        """Test that platform admin can access topology across tenants"""
        self.client.force_authenticate(user=self.platform_admin)

        response = self.client.get(f"/api/v1/virtualization/topology/{self.other_dataset.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_rate_limit_headers_present(self):
        """Test that rate limit headers are present in responses"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/virtualization/topology/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Check for rate limit headers
        headers = dict(response.headers)
        rate_limit_headers = [
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
            "RateLimit-Limit",
            "RateLimit-Remaining",
            "RateLimit-Reset",
        ]
        # At least some rate limit headers should be present
        present_headers = [h for h in rate_limit_headers if h in headers]
        self.assertGreater(len(present_headers), 0)

    def test_abac_policy_denial_prevents_access(self):
        """Test that ABAC DENY policy prevents dataset topology access"""
        self.client.force_authenticate(user=self.user)

        # Create DENY policy
        deny_policy = AccessPolicy.objects.create(
            name="Deny Dataset Topology Access",
            description="Deny access to dataset topology",
            tenant=self.tenant,
            effect="DENY",
            conditions={
                "user_id": str(self.user.id),
                "resource_type": "VIRTUAL_DATASET",
                "resource_id": str(self.dataset1.id),
            },
            priority=10,
        )

        response = self.client.get(f"/api/v1/virtualization/topology/{self.dataset1.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

        deny_policy.delete()

    def test_abac_policy_allow_permits_access(self):
        """Test that ABAC ALLOW policy permits dataset topology access"""
        self.client.force_authenticate(user=self.user)

        # Create ALLOW policy
        allow_policy = AccessPolicy.objects.create(
            name="Allow Dataset Topology Access",
            description="Allow access to dataset topology",
            tenant=self.tenant,
            effect="ALLOW",
            conditions={
                "user_id": str(self.user.id),
                "resource_type": "VIRTUAL_DATASET",
                "resource_id": str(self.dataset1.id),
            },
            priority=10,
        )

        response = self.client.get(f"/api/v1/virtualization/topology/{self.dataset1.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        allow_policy.delete()

    def test_platform_admin_can_bypass_abac(self):
        """Test that platform admin can bypass ABAC policies"""
        self.client.force_authenticate(user=self.platform_admin)

        # Create DENY policy
        deny_policy = AccessPolicy.objects.create(
            name="Deny Dataset Topology Access",
            description="Deny access to dataset topology",
            tenant=self.tenant,
            effect="DENY",
            conditions={
                "user_id": str(self.platform_admin.id),
                "resource_type": "VIRTUAL_DATASET",
                "resource_id": str(self.dataset1.id),
            },
            priority=10,
        )

        # Platform admin should still be able to access
        response = self.client.get(f"/api/v1/virtualization/topology/{self.dataset1.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        deny_policy.delete()

    def test_topology_relationships_based_on_shared_sources(self):
        """Test that topology relationships are correctly identified based on shared sources"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/virtualization/topology/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        edges = response.data["edges"]

        # dataset1 and dataset2 share source1, so there should be an edge
        dataset1_dataset2_edge = None
        for edge in edges:
            if (
                edge["source"] == str(self.dataset1.id) and edge["target"] == str(self.dataset2.id)
            ) or (
                edge["source"] == str(self.dataset2.id) and edge["target"] == str(self.dataset1.id)
            ):
                dataset1_dataset2_edge = edge
                break

        self.assertIsNotNone(dataset1_dataset2_edge)
        self.assertEqual(dataset1_dataset2_edge["type"], "SHARED_SOURCE")
        self.assertGreater(dataset1_dataset2_edge["weight"], 0)

    def test_topology_health_metrics_calculation(self):
        """Test that health metrics are correctly calculated"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/virtualization/topology/?include_health_metrics=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        nodes = response.data["nodes"]
        dataset1_node = next(node for node in nodes if node["id"] == str(self.dataset1.id))
        health_metrics = dataset1_node["health_metrics"]

        # Health score should be between 0 and 100
        self.assertGreaterEqual(health_metrics["health_score"], 0)
        self.assertLessEqual(health_metrics["health_score"], 100)

        # dataset1 is ACTIVE, so is_active should be True
        self.assertTrue(health_metrics["is_active"])

        # dataset3 is DRAFT, so is_active should be False
        dataset3_node = next(node for node in nodes if node["id"] == str(self.dataset3.id))
        dataset3_health = dataset3_node["health_metrics"]
        self.assertFalse(dataset3_health["is_active"])

    def test_topology_summary_statistics(self):
        """Test that topology summary statistics are correct"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/virtualization/topology/?include_health_metrics=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        summary = response.data["summary"]
        self.assertEqual(summary["total_datasets"], 3)
        self.assertEqual(summary["active_datasets"], 2)  # dataset1 and dataset2
        self.assertIsNotNone(summary["average_health_score"])
        self.assertGreaterEqual(summary["average_health_score"], 0)
        self.assertLessEqual(summary["average_health_score"], 100)
