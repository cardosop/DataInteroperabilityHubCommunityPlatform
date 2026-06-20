"""
Unit tests for PolicyApplication and ComplianceReport models.

Comprehensive tests without mocks/stubs, following engineering best practices.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from hub.apps.mesh.models import (
    ComplianceReport,
    DataMeshDomain,
    MeshComplianceStatus,
    PolicyApplication,
    PolicyApplicationStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class PolicyApplicationModelTest(TestCase):
    """Test PolicyApplication model"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user
        )
        # Create an AccessPolicy for testing
        from hub.apps.governance.models import AccessPolicy

        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            description="Test policy description",
            conditions={"user_role": "admin"},
            effect="ALLOW",
            created_by=self.user,
        )

    def test_create_policy_application(self):
        """Test policy application creation with minimal required fields"""
        application = PolicyApplication.objects.create(
            domain=self.domain, policy=self.policy, applied_by=self.user
        )

        self.assertEqual(application.domain, self.domain)
        self.assertEqual(application.policy, self.policy)
        self.assertEqual(application.applied_by, self.user)
        self.assertEqual(application.status, PolicyApplicationStatus.PENDING)
        self.assertEqual(application.overrides, {})
        self.assertIsNone(application.applied_at)
        self.assertIsNotNone(application.id)
        self.assertIsNotNone(application.created_at)
        self.assertIsNotNone(application.updated_at)

    def test_create_policy_application_with_all_fields(self):
        """Test policy application creation with all fields"""
        overrides = {
            "conditions": {"user_role": "admin", "additional_condition": "value"},
            "effect": "DENY",
            "priority": 50,
        }

        application = PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=self.user,
            overrides=overrides,
            status=PolicyApplicationStatus.APPLIED,
        )

        self.assertEqual(application.domain, self.domain)
        self.assertEqual(application.policy, self.policy)
        self.assertEqual(application.applied_by, self.user)
        self.assertEqual(application.overrides, overrides)
        self.assertEqual(application.status, PolicyApplicationStatus.APPLIED)
        self.assertIsNotNone(application.applied_at)

    def test_policy_application_status_choices(self):
        """Test policy application status enum"""
        application = PolicyApplication.objects.create(domain=self.domain, policy=self.policy)

        # Test PENDING status
        application.status = PolicyApplicationStatus.PENDING
        application.save()
        self.assertEqual(application.status, PolicyApplicationStatus.PENDING)
        self.assertTrue(application.is_pending())
        self.assertFalse(application.is_applied())
        self.assertFalse(application.is_failed())
        self.assertFalse(application.is_revoked())

        # Test APPLIED status
        application.status = PolicyApplicationStatus.APPLIED
        application.save()
        self.assertEqual(application.status, PolicyApplicationStatus.APPLIED)
        self.assertFalse(application.is_pending())
        self.assertTrue(application.is_applied())
        self.assertFalse(application.is_failed())
        self.assertFalse(application.is_revoked())
        self.assertIsNotNone(application.applied_at)

        # Test FAILED status
        application.status = PolicyApplicationStatus.FAILED
        application.save()
        self.assertEqual(application.status, PolicyApplicationStatus.FAILED)
        self.assertFalse(application.is_pending())
        self.assertFalse(application.is_applied())
        self.assertTrue(application.is_failed())
        self.assertFalse(application.is_revoked())

        # Test REVOKED status
        application.status = PolicyApplicationStatus.REVOKED
        application.save()
        self.assertEqual(application.status, PolicyApplicationStatus.REVOKED)
        self.assertFalse(application.is_pending())
        self.assertFalse(application.is_applied())
        self.assertFalse(application.is_failed())
        self.assertTrue(application.is_revoked())

    def test_policy_application_clean_validation_overrides_not_dict(self):
        """Test policy application clean() validation for overrides not being a dict"""
        application = PolicyApplication(
            domain=self.domain, policy=self.policy, overrides=["not", "a", "dict"]
        )

        with self.assertRaises(ValidationError) as cm:
            application.clean()
        self.assertIn("overrides", str(cm.exception))

    def test_policy_application_clean_validation_policy_different_tenant(self):
        """Test policy application clean() validation for policy from different tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        from hub.apps.governance.models import AccessPolicy

        other_policy = AccessPolicy.objects.create(
            tenant=other_tenant, name="Other Policy", conditions={}, effect="ALLOW"
        )

        application = PolicyApplication(domain=self.domain, policy=other_policy)

        with self.assertRaises(ValidationError) as cm:
            application.clean()
        self.assertIn("policy", str(cm.exception))
        self.assertIn("same tenant", str(cm.exception))

    def test_policy_application_clean_validation_applied_by_different_tenant(self):
        """Test policy application clean() validation for applied_by from different tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        other_user = User.objects.create_user(
            email=f"other-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=other_tenant,
        )

        application = PolicyApplication(
            domain=self.domain, policy=self.policy, applied_by=other_user
        )

        with self.assertRaises(ValidationError) as cm:
            application.clean()
        self.assertIn("applied_by", str(cm.exception))
        self.assertIn("same tenant", str(cm.exception))

    def test_policy_application_save_sets_applied_at(self):
        """Test that save() sets applied_at when status changes to APPLIED"""
        application = PolicyApplication.objects.create(
            domain=self.domain, policy=self.policy, status=PolicyApplicationStatus.PENDING
        )

        self.assertIsNone(application.applied_at)

        # Change status to APPLIED
        application.status = PolicyApplicationStatus.APPLIED
        application.save()

        self.assertIsNotNone(application.applied_at)

    def test_policy_application_str_representation(self):
        """Test policy application string representation"""
        application = PolicyApplication.objects.create(
            domain=self.domain, policy=self.policy, status=PolicyApplicationStatus.APPLIED
        )

        expected_str = (
            f"{self.policy.name} on {self.domain.name} ({PolicyApplicationStatus.APPLIED})"
        )
        self.assertEqual(str(application), expected_str)

    def test_policy_application_domain_cascade_delete(self):
        """Test that policy application is deleted when domain is deleted"""
        application = PolicyApplication.objects.create(domain=self.domain, policy=self.policy)
        application_id = application.id

        # Delete user first (User has RESTRICT foreign key to Tenant)
        self.user.delete()

        # Delete domain
        self.domain.delete()

        # Policy application should be deleted
        self.assertFalse(PolicyApplication.objects.filter(id=application_id).exists())

    def test_policy_application_policy_set_null_on_delete(self):
        """Test that policy application policy is set to NULL when policy is deleted"""
        application = PolicyApplication.objects.create(domain=self.domain, policy=self.policy)

        # Delete policy
        self.policy.delete()

        # Policy application should still exist but policy should be None
        application.refresh_from_db()
        self.assertIsNone(application.policy)

    def test_policy_application_applied_by_set_null_on_delete(self):
        """Test that policy application applied_by is set to NULL when user is deleted"""
        application = PolicyApplication.objects.create(
            domain=self.domain, policy=self.policy, applied_by=self.user
        )

        # Delete user
        self.user.delete()

        # Policy application should still exist but applied_by should be None
        application.refresh_from_db()
        self.assertIsNone(application.applied_by)


class ComplianceReportModelTest(TestCase):
    """Test ComplianceReport model"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", owner=self.user
        )
        from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility

        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.INTERNAL,
            created_by=self.user,
        )

    def test_create_compliance_report(self):
        """Test compliance report creation with minimal required fields"""
        report = ComplianceReport.objects.create(domain=self.domain)

        self.assertEqual(report.domain, self.domain)
        self.assertIsNone(report.asset)
        self.assertEqual(report.compliance_status, MeshComplianceStatus.UNKNOWN)
        self.assertEqual(report.violations, {})
        self.assertIsNotNone(report.generated_at)
        self.assertIsNotNone(report.id)
        self.assertIsNotNone(report.created_at)
        self.assertIsNotNone(report.updated_at)

    def test_create_compliance_report_with_all_fields(self):
        """Test compliance report creation with all fields"""
        violations = {
            "violations": [
                {
                    "type": "DATA_QUALITY",
                    "severity": "HIGH",
                    "description": "Data quality check failed",
                    "field": "email",
                },
                {
                    "type": "SCHEMA_COMPLIANCE",
                    "severity": "MEDIUM",
                    "description": "Schema validation failed",
                },
            ],
            "count": 2,
        }

        report = ComplianceReport.objects.create(
            domain=self.domain,
            asset=self.asset,
            compliance_status=MeshComplianceStatus.NON_COMPLIANT,
            violations=violations,
        )

        self.assertEqual(report.domain, self.domain)
        self.assertEqual(report.asset, self.asset)
        self.assertEqual(report.compliance_status, MeshComplianceStatus.NON_COMPLIANT)
        self.assertEqual(report.violations, violations)
        self.assertIsNotNone(report.generated_at)

    def test_compliance_report_status_choices(self):
        """Test compliance report status enum"""
        report = ComplianceReport.objects.create(domain=self.domain)

        # Test COMPLIANT status
        report.compliance_status = MeshComplianceStatus.COMPLIANT
        report.save()
        self.assertEqual(report.compliance_status, MeshComplianceStatus.COMPLIANT)
        self.assertTrue(report.is_compliant())
        self.assertFalse(report.is_non_compliant())
        self.assertFalse(report.is_partial())

        # Test NON_COMPLIANT status
        report.compliance_status = MeshComplianceStatus.NON_COMPLIANT
        report.save()
        self.assertEqual(report.compliance_status, MeshComplianceStatus.NON_COMPLIANT)
        self.assertFalse(report.is_compliant())
        self.assertTrue(report.is_non_compliant())
        self.assertFalse(report.is_partial())

        # Test PARTIAL status
        report.compliance_status = MeshComplianceStatus.PARTIAL
        report.save()
        self.assertEqual(report.compliance_status, MeshComplianceStatus.PARTIAL)
        self.assertFalse(report.is_compliant())
        self.assertFalse(report.is_non_compliant())
        self.assertTrue(report.is_partial())

        # Test UNKNOWN status
        report.compliance_status = MeshComplianceStatus.UNKNOWN
        report.save()
        self.assertEqual(report.compliance_status, MeshComplianceStatus.UNKNOWN)
        self.assertFalse(report.is_compliant())
        self.assertFalse(report.is_non_compliant())
        self.assertFalse(report.is_partial())

    def test_compliance_report_clean_validation_violations_not_dict(self):
        """Test compliance report clean() validation for violations not being a dict"""
        report = ComplianceReport(domain=self.domain, violations=["not", "a", "dict"])

        with self.assertRaises(ValidationError) as cm:
            report.clean()
        self.assertIn("violations", str(cm.exception))

    def test_compliance_report_clean_validation_asset_different_tenant(self):
        """Test compliance report clean() validation for asset from different tenant"""
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}", kyc_status=KYCStatus.VERIFIED
        )
        from hub.apps.assets.models import Asset, AssetStatus, AssetVisibility

        other_asset = Asset.objects.create(
            tenant=other_tenant,
            key="other-asset",
            name="Other Asset",
            status=AssetStatus.ACTIVE,
            visibility=AssetVisibility.INTERNAL,
        )

        report = ComplianceReport(domain=self.domain, asset=other_asset)

        with self.assertRaises(ValidationError) as cm:
            report.clean()
        self.assertIn("asset", str(cm.exception))
        self.assertIn("same tenant", str(cm.exception))

    def test_compliance_report_get_violation_count(self):
        """Test get_violation_count method"""
        # Test with violations list in dict
        violations1 = {
            "violations": [
                {"type": "DATA_QUALITY", "severity": "HIGH"},
                {"type": "SCHEMA_COMPLIANCE", "severity": "MEDIUM"},
            ]
        }
        report1 = ComplianceReport.objects.create(domain=self.domain, violations=violations1)
        self.assertEqual(report1.get_violation_count(), 2)

        # Test with count in dict
        violations2 = {"count": 5, "summary": "Multiple violations detected"}
        report2 = ComplianceReport.objects.create(domain=self.domain, violations=violations2)
        self.assertEqual(report2.get_violation_count(), 5)

        # Test with empty violations
        report3 = ComplianceReport.objects.create(domain=self.domain, violations={})
        self.assertEqual(report3.get_violation_count(), 0)

        # Test with None violations
        report4 = ComplianceReport.objects.create(domain=self.domain)
        self.assertEqual(report4.get_violation_count(), 0)

    def test_compliance_report_str_representation(self):
        """Test compliance report string representation"""
        # Without asset
        report1 = ComplianceReport.objects.create(
            domain=self.domain, compliance_status=MeshComplianceStatus.COMPLIANT
        )
        expected_str1 = (
            f"Compliance Report for {self.domain.name} ({MeshComplianceStatus.COMPLIANT})"
        )
        self.assertEqual(str(report1), expected_str1)

        # With asset
        report2 = ComplianceReport.objects.create(
            domain=self.domain,
            asset=self.asset,
            compliance_status=MeshComplianceStatus.NON_COMPLIANT,
        )
        expected_str2 = f"Compliance Report for {self.domain.name} - {self.asset.name} ({MeshComplianceStatus.NON_COMPLIANT})"
        self.assertEqual(str(report2), expected_str2)

    def test_compliance_report_domain_cascade_delete(self):
        """Test that compliance report is deleted when domain is deleted"""
        report = ComplianceReport.objects.create(domain=self.domain)
        report_id = report.id

        # Delete user first (User has RESTRICT foreign key to Tenant)
        self.user.delete()

        # Delete domain
        self.domain.delete()

        # Compliance report should be deleted
        self.assertFalse(ComplianceReport.objects.filter(id=report_id).exists())

    def test_compliance_report_asset_set_null_on_delete(self):
        """Test that compliance report asset is set to NULL when asset is deleted"""
        report = ComplianceReport.objects.create(domain=self.domain, asset=self.asset)

        # Delete asset
        self.asset.delete()

        # Compliance report should still exist but asset should be None
        report.refresh_from_db()
        self.assertIsNone(report.asset)
