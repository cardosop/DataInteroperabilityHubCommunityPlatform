"""
Unit tests for PolicyBusinessRules and TopologyBusinessRules.

Tests verify comprehensive business rules for:
- Policy application validation
- Compliance checking
- Violation detection
- Relationship calculation
- Health metrics calculation

All tests use real implementations (no mocks/stubs) to ensure integration.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.mesh.business_rules import (
    PolicyBusinessRules,
    TopologyBusinessRules,
)
from hub.apps.mesh.models import (
    DataMeshDomain,
    DomainStatus,
    PolicyApplication,
    PolicyApplicationStatus,
    ComplianceReport,
    MeshComplianceStatus,
)
from hub.apps.governance.models import AccessPolicy
from hub.apps.assets.models import Asset, AssetStatus, ComplianceStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus, Role, UserRole
from hub.apps.core.services.base import ValidationError

UserModel = get_user_model()


class PolicyBusinessRulesTest(TestCase):
    """Test PolicyBusinessRules class"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.tenant_id = str(self.tenant.id)

        # Get or create roles
        self.tenant_admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant admin role"}
        )

        # Create tenant admin user
        self.tenant_admin_user = User.objects.create_user(
            email="admin@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE
        )
        UserRole.objects.create(
            user=self.tenant_admin_user,
            role=self.tenant_admin_role
        )

        # Create domain
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Test Domain",
            description="Test domain",
            status=DomainStatus.ACTIVE
        )

        # Create policy
        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            description="Test policy",
            enabled=True,
            conditions={},
            effect="ALLOW"
        )

        # Create business rules
        self.business_rules = PolicyBusinessRules(
            tenant_id=self.tenant_id,
            user_id=str(self.tenant_admin_user.id)
        )

    def test_validate_policy_application_success(self):
        """Test successful policy application validation"""
        result = self.business_rules.validate_policy_application(
            domain=self.domain,
            policy=self.policy
        )

        self.assertTrue(result.is_valid)
        self.assertEqual(len(result.errors), 0)

    def test_validate_policy_application_domain_inactive(self):
        """Test policy application validation fails for inactive domain"""
        self.domain.status = DomainStatus.INACTIVE
        self.domain.save()

        result = self.business_rules.validate_policy_application(
            domain=self.domain,
            policy=self.policy
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("ACTIVE", result.errors[0])

    def test_validate_policy_application_policy_disabled(self):
        """Test policy application validation fails for disabled policy"""
        self.policy.enabled = False
        self.policy.save()

        result = self.business_rules.validate_policy_application(
            domain=self.domain,
            policy=self.policy
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("disabled", result.errors[0].lower())

    def test_validate_policy_application_tenant_mismatch(self):
        """Test policy application validation fails for tenant mismatch"""
        other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-tenant"
        )
        other_policy = AccessPolicy.objects.create(
            tenant=other_tenant,
            name="Other Policy",
            enabled=True,
            conditions={},
            effect="ALLOW"
        )

        result = self.business_rules.validate_policy_application(
            domain=self.domain,
            policy=other_policy
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("tenant", result.errors[0].lower())

    def test_validate_policy_application_invalid_overrides(self):
        """Test policy application validation with invalid overrides"""
        result = self.business_rules.validate_policy_application(
            domain=self.domain,
            policy=self.policy,
            overrides="not a dict"  # Invalid type
        )

        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_policy_application_existing_application_warning(self):
        """Test policy application validation warns about existing application"""
        # Apply policy first
        PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=self.tenant_admin_user,
            status=PolicyApplicationStatus.APPLIED
        )

        result = self.business_rules.validate_policy_application(
            domain=self.domain,
            policy=self.policy
        )

        self.assertTrue(result.is_valid)  # Still valid, just a warning
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("already applied", result.warnings[0].lower())

    def test_check_compliance_compliant_domain(self):
        """Test compliance check for compliant domain"""
        result = self.business_rules.check_compliance(domain=self.domain)

        self.assertEqual(result["compliance_status"], MeshComplianceStatus.COMPLIANT)
        self.assertEqual(len(result["violations"]), 0)

    def test_check_compliance_inactive_domain(self):
        """Test compliance check for inactive domain"""
        self.domain.status = DomainStatus.INACTIVE
        self.domain.save()

        result = self.business_rules.check_compliance(domain=self.domain)

        self.assertEqual(result["compliance_status"], MeshComplianceStatus.NON_COMPLIANT)
        self.assertGreater(len(result["violations"]), 0)
        violation_types = [v["type"] for v in result["violations"]]
        self.assertIn("DOMAIN_INACTIVE", violation_types)

    def test_check_compliance_with_disabled_policy(self):
        """Test compliance check with disabled policy"""
        # Apply policy
        PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=self.tenant_admin_user,
            status=PolicyApplicationStatus.APPLIED
        )

        # Disable policy
        self.policy.enabled = False
        self.policy.save()

        result = self.business_rules.check_compliance(domain=self.domain)

        self.assertEqual(result["compliance_status"], MeshComplianceStatus.PARTIAL)
        violation_types = [v["type"] for v in result["violations"]]
        self.assertIn("POLICY_DISABLED", violation_types)

    def test_check_compliance_with_asset(self):
        """Test compliance check with specific asset"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            domain=self.domain.name,
            status=AssetStatus.ACTIVE,
            compliance_status=ComplianceStatus.PASS
        )

        result = self.business_rules.check_compliance(domain=self.domain, asset=asset)

        self.assertEqual(result["compliance_status"], MeshComplianceStatus.COMPLIANT)

    def test_check_compliance_with_failed_asset(self):
        """Test compliance check with failed asset"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="failed-asset",
            name="Failed Asset",
            domain=self.domain.name,
            status=AssetStatus.ACTIVE,
            compliance_status=ComplianceStatus.FAIL
        )

        result = self.business_rules.check_compliance(domain=self.domain, asset=asset)

        self.assertEqual(result["compliance_status"], MeshComplianceStatus.NON_COMPLIANT)
        violation_types = [v["type"] for v in result["violations"]]
        self.assertIn("ASSET_COMPLIANCE_FAIL", violation_types)

    def test_detect_violations_no_violations(self):
        """Test violation detection with no violations"""
        violations = self.business_rules.detect_violations(domain=self.domain)

        self.assertEqual(len(violations), 0)

    def test_detect_violations_domain_inactive(self):
        """Test violation detection for inactive domain"""
        self.domain.status = DomainStatus.INACTIVE
        self.domain.save()

        violations = self.business_rules.detect_violations(domain=self.domain)

        self.assertGreater(len(violations), 0)
        violation_types = [v["type"] for v in violations]
        self.assertIn("DOMAIN_INACTIVE", violation_types)

    def test_detect_violations_policy_disabled(self):
        """Test violation detection for disabled policy"""
        # Apply policy
        PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=self.tenant_admin_user,
            status=PolicyApplicationStatus.APPLIED
        )

        # Disable policy
        self.policy.enabled = False
        self.policy.save()

        violations = self.business_rules.detect_violations(domain=self.domain)

        self.assertGreater(len(violations), 0)
        violation_types = [v["type"] for v in violations]
        self.assertIn("POLICY_DISABLED", violation_types)

    def test_detect_violations_with_asset(self):
        """Test violation detection with asset"""
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            domain=self.domain.name,
            status=AssetStatus.ACTIVE,
            compliance_status=ComplianceStatus.FAIL
        )

        violations = self.business_rules.detect_violations(domain=self.domain, asset=asset)

        self.assertGreater(len(violations), 0)
        violation_types = [v["type"] for v in violations]
        self.assertIn("ASSET_COMPLIANCE_FAIL", violation_types)


class TopologyBusinessRulesTest(TestCase):
    """Test TopologyBusinessRules class"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.tenant_id = str(self.tenant.id)

        # Create domains
        self.domain1 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 1",
            status=DomainStatus.ACTIVE
        )
        self.domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 2",
            status=DomainStatus.ACTIVE
        )
        self.domain3 = DataMeshDomain.objects.create(
            tenant=self.tenant,
            name="Domain 3",
            status=DomainStatus.INACTIVE
        )

        # Create business rules
        self.business_rules = TopologyBusinessRules(tenant_id=self.tenant_id)

    def test_calculate_relationships_no_relationships(self):
        """Test relationship calculation with no shared policies"""
        domains = [self.domain1, self.domain2]
        relationships = self.business_rules.calculate_relationships(domains)

        self.assertEqual(len(relationships), 0)

    def test_calculate_relationships_with_shared_policy(self):
        """Test relationship calculation with shared policy"""
        # Create a shared policy
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Shared Policy",
            enabled=True,
            conditions={},
            effect="ALLOW"
        )

        # Apply policy to both domains
        PolicyApplication.objects.create(
            domain=self.domain1,
            policy=policy,
            status=PolicyApplicationStatus.APPLIED
        )
        PolicyApplication.objects.create(
            domain=self.domain2,
            policy=policy,
            status=PolicyApplicationStatus.APPLIED
        )

        domains = [self.domain1, self.domain2]
        relationships = self.business_rules.calculate_relationships(domains)

        self.assertGreater(len(relationships), 0)
        relationship = relationships[0]
        self.assertEqual(relationship["type"], "SHARED_POLICY")
        self.assertIn(relationship["source"], [str(self.domain1.id), str(self.domain2.id)])
        self.assertIn(relationship["target"], [str(self.domain1.id), str(self.domain2.id)])
        self.assertEqual(relationship["weight"], 1)

    def test_calculate_relationships_multiple_shared_policies(self):
        """Test relationship calculation with multiple shared policies"""
        # Create multiple policies
        policy1 = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Policy 1",
            enabled=True,
            conditions={},
            effect="ALLOW"
        )
        policy2 = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Policy 2",
            enabled=True,
            conditions={},
            effect="ALLOW"
        )

        # Apply both policies to both domains
        PolicyApplication.objects.create(
            domain=self.domain1,
            policy=policy1,
            status=PolicyApplicationStatus.APPLIED
        )
        PolicyApplication.objects.create(
            domain=self.domain1,
            policy=policy2,
            status=PolicyApplicationStatus.APPLIED
        )
        PolicyApplication.objects.create(
            domain=self.domain2,
            policy=policy1,
            status=PolicyApplicationStatus.APPLIED
        )
        PolicyApplication.objects.create(
            domain=self.domain2,
            policy=policy2,
            status=PolicyApplicationStatus.APPLIED
        )

        domains = [self.domain1, self.domain2]
        relationships = self.business_rules.calculate_relationships(domains)

        self.assertGreater(len(relationships), 0)
        relationship = relationships[0]
        self.assertEqual(relationship["weight"], 2)  # Two shared policies

    def test_calculate_health_metrics_active_domain(self):
        """Test health metrics calculation for active domain"""
        metrics = self.business_rules.calculate_health_metrics(self.domain1)

        self.assertIn("health_score", metrics)
        self.assertIn("policy_count", metrics)
        self.assertIn("compliance_status", metrics)
        self.assertIn("violation_count", metrics)
        self.assertIn("is_active", metrics)
        self.assertTrue(metrics["is_active"])
        self.assertEqual(metrics["health_score"], 100)  # Perfect health for active domain with no issues

    def test_calculate_health_metrics_inactive_domain(self):
        """Test health metrics calculation for inactive domain"""
        metrics = self.business_rules.calculate_health_metrics(self.domain3)

        self.assertFalse(metrics["is_active"])
        self.assertLess(metrics["health_score"], 100)  # Should be less due to inactive status

    def test_calculate_health_metrics_with_compliance_issues(self):
        """Test health metrics calculation with compliance issues"""
        # Create compliance report with violations
        ComplianceReport.objects.create(
            domain=self.domain1,
            compliance_status=MeshComplianceStatus.NON_COMPLIANT,
            violations={"items": [
                {"type": "TEST_VIOLATION", "severity": "HIGH", "description": "Test"}
            ]}
        )

        metrics = self.business_rules.calculate_health_metrics(self.domain1)

        self.assertLess(metrics["health_score"], 100)
        self.assertEqual(metrics["compliance_status"], MeshComplianceStatus.NON_COMPLIANT)
        self.assertEqual(metrics["violation_count"], 1)

    def test_calculate_health_metrics_with_policies(self):
        """Test health metrics calculation with applied policies"""
        policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            enabled=True,
            conditions={},
            effect="ALLOW"
        )

        PolicyApplication.objects.create(
            domain=self.domain1,
            policy=policy,
            status=PolicyApplicationStatus.APPLIED
        )

        metrics = self.business_rules.calculate_health_metrics(self.domain1)

        self.assertEqual(metrics["policy_count"], 1)

    def test_calculate_health_metrics_partial_compliance(self):
        """Test health metrics calculation with partial compliance"""
        ComplianceReport.objects.create(
            domain=self.domain1,
            compliance_status=MeshComplianceStatus.PARTIAL,
            violations={"items": []}
        )

        metrics = self.business_rules.calculate_health_metrics(self.domain1)

        self.assertLess(metrics["health_score"], 100)
        self.assertGreater(metrics["health_score"], 0)
        self.assertEqual(metrics["compliance_status"], MeshComplianceStatus.PARTIAL)

    def test_calculate_health_metrics_no_compliance_report(self):
        """Test health metrics calculation without compliance report"""
        metrics = self.business_rules.calculate_health_metrics(self.domain1)

        self.assertEqual(metrics["compliance_status"], MeshComplianceStatus.UNKNOWN)
        self.assertEqual(metrics["violation_count"], 0)

