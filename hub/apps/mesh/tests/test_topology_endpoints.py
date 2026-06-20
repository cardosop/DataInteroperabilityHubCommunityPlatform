"""
Unit tests for Data Mesh Topology Endpoints.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.governance.models import AccessPolicy
from hub.apps.mesh.models import (
    ComplianceReport,
    DataMeshDomain,
    DomainStatus,
    MeshComplianceStatus,
    PolicyApplication,
    PolicyApplicationStatus,
)
from hub.apps.mesh.tests.setup_helpers import (
    create_mesh_test_api_keys,
    create_mesh_test_tenant,
    create_mesh_test_users,
    setup_mesh_test_environment,
)
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class TopologyViewSetTestCase(TestCase):
    """Base test case for TopologyViewSet tests"""

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Shared helpers: tenant with billing + ABAC, users with API keys
        self.tenant = create_mesh_test_tenant(data_mesh_enabled=True)
        self.admin_user, self.regular_user = create_mesh_test_users(self.tenant)
        self.admin_api_key, self.user_api_key = create_mesh_test_api_keys(
            self.tenant, self.admin_user, self.regular_user
        )
        setup_mesh_test_environment(self.tenant)

        # Create test domains
        self.domain1 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 1",
            description="First test domain",
            owner=self.admin_user,
            status=DomainStatus.ACTIVE,
            boundaries={"data_products": ["product1"]},
            capabilities={"apis": ["api1"]},
            resource_quota={"storage_gb": 100},
            resource_usage={"storage_gb_used": 50},
        )

        self.domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 2",
            description="Second test domain",
            owner=self.admin_user,
            status=DomainStatus.ACTIVE,
            boundaries={"data_products": ["product2"]},
            capabilities={"apis": ["api2"]},
            resource_quota={"storage_gb": 200},
            resource_usage={"storage_gb_used": 100},
        )

        # Create a policy for shared policy relationships
        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            description="Test policy for relationships",
            conditions={},
            effect="ALLOW",
        )

        # Apply policy to both domains to create a relationship
        PolicyApplication.objects.create(
            domain=self.domain1,
            policy=self.policy,
            applied_by=self.admin_user,
            status=PolicyApplicationStatus.APPLIED,
        )

        PolicyApplication.objects.create(
            domain=self.domain2,
            policy=self.policy,
            applied_by=self.admin_user,
            status=PolicyApplicationStatus.APPLIED,
        )

        # Create compliance report for domain1
        ComplianceReport.objects.create(
            domain=self.domain1,
            compliance_status=MeshComplianceStatus.COMPLIANT,
            violations={},
        )


class TopologyListEndpointTest(TopologyViewSetTestCase):
    """Test GET /api/v1/mesh/topology/ endpoint"""

    def test_get_topology_success(self):
        """Test successful topology retrieval"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("topology-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("nodes", response.data)
        self.assertIn("edges", response.data)
        self.assertIn("metadata", response.data)
        self.assertIn("summary", response.data)

        # Verify nodes
        nodes = response.data["nodes"]
        self.assertEqual(len(nodes), 2)
        node_ids = [node["id"] for node in nodes]
        self.assertIn(str(self.domain1.id), node_ids)
        self.assertIn(str(self.domain2.id), node_ids)

        # Verify edges (relationships via shared policies + ABAC policy)
        edges = response.data["edges"]
        self.assertEqual(len(edges), 2)

        # Verify metadata
        metadata = response.data["metadata"]
        self.assertEqual(metadata["tenant_id"], str(self.tenant.id))
        self.assertEqual(metadata["domain_count"], 2)
        self.assertEqual(metadata["relationship_count"], 2)

        # Verify summary
        summary = response.data["summary"]
        self.assertEqual(summary["total_domains"], 2)
        self.assertEqual(summary["active_domains"], 2)

    def test_get_topology_with_health_metrics(self):
        """Test topology retrieval with health metrics"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("topology-list")
        response = self.client.get(url, {"include_health_metrics": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nodes = response.data["nodes"]
        self.assertEqual(len(nodes), 2)

        # Check that health metrics are included
        first_node = nodes[0]
        self.assertIn("health_metrics", first_node)
        health_metrics = first_node["health_metrics"]
        self.assertIn("health_score", health_metrics)
        self.assertIn("policy_count", health_metrics)
        self.assertIn("compliance_status", health_metrics)
        self.assertIn("violation_count", health_metrics)
        self.assertIn("is_active", health_metrics)

    def test_get_topology_without_health_metrics(self):
        """Test topology retrieval without health metrics"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("topology-list")
        response = self.client.get(url, {"include_health_metrics": "false"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nodes = response.data["nodes"]
        self.assertEqual(len(nodes), 2)
        first_node = nodes[0]
        self.assertIsNone(first_node.get("health_metrics"))

    def test_get_topology_tenant_isolation(self):
        """Test that users can only see topology for their tenant"""
        # Create another tenant and domain
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_domain = DataMeshDomain.objects.create(
            tenant=other_tenant,
            name="Other Tenant Domain",
            status=DomainStatus.ACTIVE,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("topology-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        nodes = response.data["nodes"]
        node_ids = [node["id"] for node in nodes]
        # Should not include domain from other tenant
        self.assertNotIn(str(other_domain.id), node_ids)

    def test_get_topology_requires_authentication(self):
        """Test that topology endpoint requires authentication"""
        url = reverse("topology-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TopologyRetrieveEndpointTest(TopologyViewSetTestCase):
    """Test GET /api/v1/mesh/topology/{id}/ endpoint"""

    def test_get_domain_topology_success(self):
        """Test successful domain topology retrieval"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("topology-detail", kwargs={"pk": str(self.domain1.id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("domain", response.data)
        self.assertIn("relationships", response.data)
        self.assertIn("health_metrics", response.data)

        # Verify domain data
        domain = response.data["domain"]
        self.assertEqual(domain["id"], str(self.domain1.id))
        self.assertEqual(domain["name"], self.domain1.name)

        # Verify relationships
        relationships = response.data["relationships"]
        self.assertIsInstance(relationships, list)

        # Verify health metrics
        health_metrics = response.data["health_metrics"]
        self.assertIsNotNone(health_metrics)
        self.assertIn("health_score", health_metrics)
        self.assertIn("policy_count", health_metrics)
        self.assertIn("compliance_status", health_metrics)

    def test_get_domain_topology_not_found(self):
        """Test retrieving topology for non-existent domain"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        import uuid

        url = reverse("topology-detail", kwargs={"pk": str(uuid.uuid4())})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_domain_topology_tenant_isolation(self):
        """Test that users can only retrieve topology for domains in their tenant"""
        # Create another tenant and domain
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_domain = DataMeshDomain.objects.create(
            tenant=other_tenant,
            name="Other Tenant Domain",
            status=DomainStatus.ACTIVE,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("topology-detail", kwargs={"pk": str(other_domain.id)})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class TopologyHealthEndpointTest(TopologyViewSetTestCase):
    """Test GET /api/v1/mesh/topology/health/ endpoint"""

    def test_get_mesh_health_success(self):
        """Test successful mesh health retrieval"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("topology-health")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("overall_health_score", response.data)
        self.assertIn("total_domains", response.data)
        self.assertIn("active_domains", response.data)
        self.assertIn("compliant_domains", response.data)
        self.assertIn("non_compliant_domains", response.data)
        self.assertIn("domains_with_violations", response.data)
        self.assertIn("domain_health", response.data)

        # Verify values
        self.assertEqual(response.data["total_domains"], 2)
        self.assertEqual(response.data["active_domains"], 2)
        self.assertIsInstance(response.data["domain_health"], list)
        self.assertEqual(len(response.data["domain_health"]), 2)
        for domain_health_entry in response.data["domain_health"]:
            self.assertIn("domain_id", domain_health_entry)
            self.assertIn("health_score", domain_health_entry)

    def test_get_mesh_health_requires_authentication(self):
        """Test that health endpoint requires authentication"""
        url = reverse("topology-health")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class TopologyRelationshipsEndpointTest(TopologyViewSetTestCase):
    """Test GET /api/v1/mesh/topology/relationships/ endpoint"""

    def test_get_relationships_success(self):
        """Test successful relationships retrieval"""
        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("topology-relationships")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("relationships", response.data)
        self.assertIn("total_count", response.data)
        self.assertIn("relationship_types", response.data)

        # Verify relationships
        relationships = response.data["relationships"]
        self.assertIsInstance(relationships, list)
        self.assertEqual(response.data["total_count"], len(relationships))

        # Should have 2 relationships (shared test policy + ABAC policy)
        self.assertEqual(len(relationships), 2)

        # Verify relationship structure
        if len(relationships) > 0:
            rel = relationships[0]
            self.assertIn("source", rel)
            self.assertIn("target", rel)
            self.assertIn("type", rel)
            self.assertIn("weight", rel)

        # Verify relationship types
        relationship_types = response.data["relationship_types"]
        self.assertIsInstance(relationship_types, dict)

    def test_get_relationships_requires_authentication(self):
        """Test that relationships endpoint requires authentication"""
        url = reverse("topology-relationships")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_relationships_tenant_isolation(self):
        """Test that relationships only include domains from user's tenant"""
        # Create another tenant and domain
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_domain = DataMeshDomain.objects.create(
            tenant=other_tenant,
            name="Other Tenant Domain",
            status=DomainStatus.ACTIVE,
        )

        self.client.credentials(HTTP_AUTHORIZATION=f"ApiKey {self.user_api_key._plaintext_key}")

        url = reverse("topology-relationships")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        relationships = response.data["relationships"]

        # Verify no relationships include the other tenant's domain
        for rel in relationships:
            self.assertNotEqual(rel["source"], str(other_domain.id))
            self.assertNotEqual(rel["target"], str(other_domain.id))
