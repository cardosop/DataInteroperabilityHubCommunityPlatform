"""
Unit tests for DataMeshService check_compliance() and get_topology() methods.

Tests verify comprehensive compliance checking and topology generation:
- Policy retrieval and validation
- Asset validation
- Violation flagging
- Report generation
- Domain retrieval
- Relationship calculation
- Health metrics
- Topology generation

All tests use real implementations (no mocks/stubs) to ensure integration.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset, AssetStatus, ComplianceStatus
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.governance.models import AccessPolicy
from hub.apps.mesh.models import (
    MeshComplianceStatus,
)
from hub.apps.mesh.services import DataMeshService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, User, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class DataMeshComplianceCheckTest(TestCase):
    """Test check_compliance() method"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.tenant_id = str(self.tenant.id)

        # Get or create roles
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN", defaults={"description": "Tenant admin role"}
        )

        # Create tenant admin user
        self.tenant_admin_user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.tenant_admin_user, role=self.tenant_admin_role)

        # Create service
        self.service = DataMeshService(
            tenant_id=self.tenant_id, user_id=str(self.tenant_admin_user.id)
        )

        # Create domain
        self.domain = self.service.create_domain(
            tenant_id=self.tenant_id,
            name="Test Domain",
            description="Test domain for compliance checking",
        )

    def test_check_compliance_for_active_domain_with_no_policies(self):
        """Test compliance check for active domain with no policies"""
        report = self.service.check_compliance(
            domain_id=str(self.domain.id), tenant_id=self.tenant_id
        )

        self.assertIsNotNone(report)
        self.assertEqual(report.domain, self.domain)
        self.assertIsNone(report.asset)
        self.assertEqual(report.compliance_status, MeshComplianceStatus.COMPLIANT)
        self.assertEqual(report.get_violation_count(), 0)

    def test_check_compliance_for_inactive_domain(self):
        """Test compliance check for inactive domain"""
        # Update domain to inactive
        self.service.update_domain(
            domain_id=str(self.domain.id), tenant_id=self.tenant_id, status="INACTIVE"
        )

        report = self.service.check_compliance(
            domain_id=str(self.domain.id), tenant_id=self.tenant_id
        )

        self.assertEqual(report.compliance_status, MeshComplianceStatus.NON_COMPLIANT)
        self.assertGreater(report.get_violation_count(), 0)
        violations = report.violations.get("items", [])
        violation_types = [v.get("type") for v in violations]
        self.assertIn("DOMAIN_INACTIVE", violation_types)

    def test_check_compliance_with_applied_policies(self):
        """Test compliance check with applied policies"""
        # Create a policy
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            description="Test policy for compliance",
            enabled=True,
            conditions={},
            effect="ALLOW",
        )

        # Apply policy to domain
        self.service.apply_policy(
            domain_id=str(self.domain.id), policy_id=str(policy.id), tenant_id=self.tenant_id
        )

        # Check compliance
        report = self.service.check_compliance(
            domain_id=str(self.domain.id), tenant_id=self.tenant_id
        )

        self.assertIsNotNone(report)
        self.assertEqual(report.compliance_status, MeshComplianceStatus.COMPLIANT)

    def test_check_compliance_with_disabled_policy(self):
        """Test compliance check with disabled policy"""
        # Create an enabled policy
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Disabled Policy",
            description="Policy that will be disabled",
            enabled=True,
            conditions={},
            effect="ALLOW",
        )

        # Apply policy to domain (must be enabled to apply)
        self.service.apply_policy(
            domain_id=str(self.domain.id), policy_id=str(policy.id), tenant_id=self.tenant_id
        )

        # Disable the policy after application
        policy.enabled = False
        policy.save()

        # Check compliance
        report = self.service.check_compliance(
            domain_id=str(self.domain.id), tenant_id=self.tenant_id
        )

        self.assertEqual(report.compliance_status, MeshComplianceStatus.PARTIAL)
        violations = report.violations.get("items", [])
        violation_types = [v.get("type") for v in violations]
        self.assertIn("POLICY_DISABLED", violation_types)

    def test_check_compliance_with_asset_specific(self):
        """Test compliance check for specific asset"""
        # Create an asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            domain=self.domain.name,
            status=AssetStatus.ACTIVE,
            compliance_status=ComplianceStatus.PASS,
        )

        # Check compliance for asset
        report = self.service.check_compliance(
            domain_id=str(self.domain.id), tenant_id=self.tenant_id, asset_id=str(asset.id)
        )

        self.assertIsNotNone(report)
        self.assertEqual(report.domain, self.domain)
        self.assertEqual(report.asset, asset)
        self.assertEqual(report.compliance_status, MeshComplianceStatus.COMPLIANT)

    def test_check_compliance_with_failed_asset(self):
        """Test compliance check with asset that has compliance failures"""
        # Create an asset with compliance failure
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="failed-asset",
            name="Failed Asset",
            domain=self.domain.name,
            status=AssetStatus.ACTIVE,
            compliance_status=ComplianceStatus.FAIL,
        )

        # Check compliance for asset
        report = self.service.check_compliance(
            domain_id=str(self.domain.id), tenant_id=self.tenant_id, asset_id=str(asset.id)
        )

        self.assertEqual(report.compliance_status, MeshComplianceStatus.NON_COMPLIANT)
        violations = report.violations.get("items", [])
        violation_types = [v.get("type") for v in violations]
        self.assertIn("ASSET_COMPLIANCE_FAIL", violation_types)

    def test_check_compliance_with_domain_assets(self):
        """Test compliance check validates all assets in domain"""
        # Create assets with different compliance statuses
        Asset.objects.create(
            tenant=self.tenant,
            key="asset-1",
            name="Asset 1",
            domain=self.domain.name,
            status=AssetStatus.ACTIVE,
            compliance_status=ComplianceStatus.PASS,
        )
        Asset.objects.create(
            tenant=self.tenant,
            key="asset-2",
            name="Asset 2",
            domain=self.domain.name,
            status=AssetStatus.ACTIVE,
            compliance_status=ComplianceStatus.FAIL,
        )

        # Check compliance (domain-level, no asset_id)
        report = self.service.check_compliance(
            domain_id=str(self.domain.id), tenant_id=self.tenant_id
        )

        self.assertEqual(report.compliance_status, MeshComplianceStatus.NON_COMPLIANT)
        violations = report.violations.get("items", [])
        violation_types = [v.get("type") for v in violations]
        self.assertIn("DOMAIN_ASSETS_COMPLIANCE_FAIL", violation_types)

    def test_check_compliance_creates_report(self):
        """Test that check_compliance creates or updates compliance report"""
        # First check
        report1 = self.service.check_compliance(
            domain_id=str(self.domain.id), tenant_id=self.tenant_id
        )

        # Second check (should update existing report)
        report2 = self.service.check_compliance(
            domain_id=str(self.domain.id), tenant_id=self.tenant_id
        )

        self.assertEqual(report1.id, report2.id)  # Same report
        self.assertGreaterEqual(report2.generated_at, report1.generated_at)

    def test_check_compliance_raises_not_found_for_invalid_domain(self):
        """Test that check_compliance raises NotFoundError for invalid domain"""
        import uuid

        invalid_domain_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.check_compliance(domain_id=invalid_domain_id, tenant_id=self.tenant_id)

    def test_check_compliance_raises_not_found_for_invalid_asset(self):
        """Test that check_compliance raises NotFoundError for invalid asset"""
        import uuid

        invalid_asset_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.check_compliance(
                domain_id=str(self.domain.id), tenant_id=self.tenant_id, asset_id=invalid_asset_id
            )


class DataMeshTopologyTest(TestCase):
    """Test get_topology() method"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.tenant_id = str(self.tenant.id)

        # Get or create roles
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN", defaults={"description": "Tenant admin role"}
        )

        # Create tenant admin user
        self.tenant_admin_user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.tenant_admin_user, role=self.tenant_admin_role)

        # Create service
        self.service = DataMeshService(
            tenant_id=self.tenant_id, user_id=str(self.tenant_admin_user.id)
        )

    def test_get_topology_with_no_domains(self):
        """Test topology generation with no domains"""
        topology = self.service.get_topology(tenant_id=self.tenant_id)

        self.assertIsNotNone(topology)
        self.assertEqual(len(topology["nodes"]), 0)
        self.assertEqual(len(topology["edges"]), 0)
        self.assertEqual(topology["summary"]["total_domains"], 0)
        self.assertEqual(topology["metadata"]["tenant_id"], self.tenant_id)

    def test_get_topology_with_single_domain(self):
        """Test topology generation with single domain"""
        domain = self.service.create_domain(tenant_id=self.tenant_id, name="Domain 1")

        topology = self.service.get_topology(tenant_id=self.tenant_id)

        self.assertEqual(len(topology["nodes"]), 1)
        self.assertEqual(len(topology["edges"]), 0)
        self.assertEqual(topology["nodes"][0]["id"], str(domain.id))
        self.assertEqual(topology["nodes"][0]["name"], "Domain 1")
        self.assertEqual(topology["summary"]["total_domains"], 1)
        self.assertEqual(topology["summary"]["active_domains"], 1)

    def test_get_topology_with_multiple_domains(self):
        """Test topology generation with multiple domains"""
        domain1 = self.service.create_domain(tenant_id=self.tenant_id, name="Domain 1")
        domain2 = self.service.create_domain(tenant_id=self.tenant_id, name="Domain 2")
        domain3 = self.service.create_domain(
            tenant_id=self.tenant_id, name="Domain 3", status="INACTIVE"
        )

        topology = self.service.get_topology(tenant_id=self.tenant_id)

        self.assertEqual(len(topology["nodes"]), 3)
        self.assertEqual(topology["summary"]["total_domains"], 3)
        self.assertEqual(topology["summary"]["active_domains"], 2)

        # Check all domains are in nodes
        node_ids = [n["id"] for n in topology["nodes"]]
        self.assertIn(str(domain1.id), node_ids)
        self.assertIn(str(domain2.id), node_ids)
        self.assertIn(str(domain3.id), node_ids)

    def test_get_topology_includes_health_metrics(self):
        """Test that topology includes health metrics when requested"""
        self.service.create_domain(tenant_id=self.tenant_id, name="Domain with Metrics")

        topology = self.service.get_topology(tenant_id=self.tenant_id, include_health_metrics=True)

        self.assertEqual(len(topology["nodes"]), 1)
        node = topology["nodes"][0]
        self.assertIn("health_metrics", node)
        self.assertIn("health_score", node["health_metrics"])
        self.assertIn("policy_count", node["health_metrics"])
        self.assertIn("compliance_status", node["health_metrics"])
        self.assertIn("violation_count", node["health_metrics"])
        self.assertIn("is_active", node["health_metrics"])

    def test_get_topology_excludes_health_metrics(self):
        """Test that topology excludes health metrics when not requested"""
        self.service.create_domain(tenant_id=self.tenant_id, name="Domain without Metrics")

        topology = self.service.get_topology(tenant_id=self.tenant_id, include_health_metrics=False)

        self.assertEqual(len(topology["nodes"]), 1)
        node = topology["nodes"][0]
        self.assertNotIn("health_metrics", node)

    def test_get_topology_calculates_relationships(self):
        """Test that topology calculates relationships between domains"""
        # Create domains
        domain1 = self.service.create_domain(tenant_id=self.tenant_id, name="Domain 1")
        domain2 = self.service.create_domain(tenant_id=self.tenant_id, name="Domain 2")

        # Create a shared policy
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Shared Policy",
            description="Policy shared by domains",
            enabled=True,
            conditions={},
            effect="ALLOW",
        )

        # Apply policy to both domains
        self.service.apply_policy(
            domain_id=str(domain1.id), policy_id=str(policy.id), tenant_id=self.tenant_id
        )
        self.service.apply_policy(
            domain_id=str(domain2.id), policy_id=str(policy.id), tenant_id=self.tenant_id
        )

        topology = self.service.get_topology(tenant_id=self.tenant_id)

        # Should have relationships (edges) between domains sharing a policy
        self.assertIsInstance(topology["edges"], list)
        self.assertGreater(len(topology["edges"]), 0)

    def test_get_topology_includes_summary_statistics(self):
        """Test that topology includes summary statistics"""
        self.service.create_domain(tenant_id=self.tenant_id, name="Active Domain")
        self.service.create_domain(
            tenant_id=self.tenant_id, name="Inactive Domain", status="INACTIVE"
        )

        topology = self.service.get_topology(tenant_id=self.tenant_id)

        self.assertIn("summary", topology)
        summary = topology["summary"]
        self.assertEqual(summary["total_domains"], 2)
        self.assertEqual(summary["active_domains"], 1)
        self.assertIn("total_relationships", summary)

    def test_get_topology_includes_metadata(self):
        """Test that topology includes metadata"""
        topology = self.service.get_topology(tenant_id=self.tenant_id)

        self.assertIn("metadata", topology)
        metadata = topology["metadata"]
        self.assertEqual(metadata["tenant_id"], self.tenant_id)
        self.assertIn("domain_count", metadata)
        self.assertIn("relationship_count", metadata)
        self.assertIn("generated_at", metadata)

    def test_get_topology_raises_validation_error_without_tenant_id(self):
        """Test that get_topology raises ValidationError without tenant_id"""
        service = DataMeshService()  # No tenant_id

        with self.assertRaises(ValidationError):
            service.get_topology()


class DataMeshComplianceTopologyIntegrationTest(TestCase):
    """Integration tests for compliance checking and topology generation"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.tenant_id = str(self.tenant.id)

        # Get or create roles
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="TENANT_ADMIN", defaults={"description": "Tenant admin role"}
        )

        # Create tenant admin user
        self.tenant_admin_user = User.objects.create_user(
            email=f"admin-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=self.tenant_admin_user, role=self.tenant_admin_role)

        # Create service
        self.service = DataMeshService(
            tenant_id=self.tenant_id, user_id=str(self.tenant_admin_user.id)
        )

    def test_compliance_check_updates_topology_health_metrics(self):
        """Test that compliance checks update topology health metrics"""
        # Create domain
        domain = self.service.create_domain(tenant_id=self.tenant_id, name="Test Domain")

        # Get initial topology
        topology1 = self.service.get_topology(tenant_id=self.tenant_id)
        initial_health_score = topology1["nodes"][0]["health_metrics"]["health_score"]

        # Create compliance issue (inactive domain)
        self.service.update_domain(
            domain_id=str(domain.id), tenant_id=self.tenant_id, status="INACTIVE"
        )

        # Check compliance
        self.service.check_compliance(domain_id=str(domain.id), tenant_id=self.tenant_id)

        # Get updated topology
        topology2 = self.service.get_topology(tenant_id=self.tenant_id)
        updated_health_score = topology2["nodes"][0]["health_metrics"]["health_score"]

        # Health score should decrease due to inactive status
        self.assertLess(updated_health_score, initial_health_score)

    def test_complete_workflow_compliance_and_topology(self):
        """Test complete workflow: create domains, check compliance, get topology"""
        # Create multiple domains
        domain1 = self.service.create_domain(tenant_id=self.tenant_id, name="Domain 1")
        domain2 = self.service.create_domain(tenant_id=self.tenant_id, name="Domain 2")

        # Check compliance for both domains
        report1 = self.service.check_compliance(domain_id=str(domain1.id), tenant_id=self.tenant_id)
        report2 = self.service.check_compliance(domain_id=str(domain2.id), tenant_id=self.tenant_id)

        # Get topology
        topology = self.service.get_topology(tenant_id=self.tenant_id)

        # Verify all domains are in topology
        self.assertEqual(len(topology["nodes"]), 2)
        node_ids = [n["id"] for n in topology["nodes"]]
        self.assertIn(str(domain1.id), node_ids)
        self.assertIn(str(domain2.id), node_ids)

        # Verify compliance reports exist
        self.assertIsNotNone(report1)
        self.assertIsNotNone(report2)
