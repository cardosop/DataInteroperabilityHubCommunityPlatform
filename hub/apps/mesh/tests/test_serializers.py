"""
Unit tests for Data Mesh Serializers.

Comprehensive tests without mocks/stubs, following engineering best practices and TDD principles.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase

from hub.apps.assets.models import Asset
from hub.apps.governance.models import AccessPolicy
from hub.apps.mesh.models import (
    ComplianceReport,
    DataMeshDomain,
    DomainStatus,
    MeshComplianceStatus,
    PolicyApplication,
    PolicyApplicationStatus,
)
from hub.apps.mesh.serializers import (
    ApplyPolicySerializer,
    CheckComplianceSerializer,
    ComplianceReportSerializer,
    DomainAnalyticsSerializer,
    DomainCreateSerializer,
    DomainRelationshipSerializer,
    DomainSerializer,
    DomainTopologySerializer,
    DomainUpdateSerializer,
    HealthMetricsSerializer,
    MeshHealthSerializer,
    PolicyApplicationSerializer,
    TopologyEdgeSerializer,
    TopologyMetadataSerializer,
    TopologyNodeSerializer,
    TopologySerializer,
    TopologySummarySerializer,
    TransferOwnershipSerializer,
)
from hub.apps.tenants.models import KYCStatus, Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class DomainSerializerTest(TestCase):
    """Test DomainSerializer"""

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
            tenant=self.tenant,
            name="Test Domain",
            description="Test description",
            owner=self.user,
            status=DomainStatus.ACTIVE,
            boundaries={"data_products": ["product1"]},
            capabilities={"apis": ["api1"]},
            resource_quota={"storage_gb": 100},
            resource_usage={"storage_gb_used": 50},
        )

    def test_serialize_domain_success(self):
        """Test successful domain serialization"""
        serializer = DomainSerializer(self.domain)
        data = serializer.data

        self.assertEqual(data["id"], str(self.domain.id))
        self.assertEqual(data["name"], self.domain.name)
        self.assertEqual(data["description"], self.domain.description)
        self.assertEqual(data["owner"], str(self.user.id))
        self.assertEqual(data["owner_email"], self.user.email)
        self.assertEqual(data["tenant_name"], self.tenant.name)
        self.assertEqual(data["status"], DomainStatus.ACTIVE)
        self.assertEqual(data["boundaries"], {"data_products": ["product1"]})
        self.assertEqual(data["capabilities"], {"apis": ["api1"]})
        self.assertEqual(data["resource_quota"], {"storage_gb": 100})
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_serialize_domain_without_owner(self):
        """Test serialization of domain without owner"""
        domain_no_owner = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Domain No Owner", status=DomainStatus.ACTIVE
        )
        serializer = DomainSerializer(domain_no_owner)
        data = serializer.data

        self.assertIsNone(data["owner"])
        self.assertIsNone(data["owner_email"])

    def test_validate_name_not_empty(self):
        """Test name validation - empty name"""
        serializer = DomainSerializer(
            self.domain, data={"name": ""}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_validate_name_whitespace_only(self):
        """Test name validation - whitespace only"""
        serializer = DomainSerializer(
            self.domain, data={"name": "   "}, partial=True
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_validate_name_strips_whitespace(self):
        """Test name validation - strips whitespace"""
        serializer = DomainSerializer(
            self.domain, data={"name": "  Test Domain  "}, partial=True
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Test Domain")

    def test_validate_boundaries_dict(self):
        """Test boundaries validation - must be dict"""
        serializer = DomainSerializer(
            self.domain,
            data={"name": "Test Domain", "boundaries": "not-a-dict"},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("boundaries", serializer.errors)

    def test_validate_boundaries_none_becomes_empty_dict(self):
        """Test boundaries validation - None becomes empty dict"""
        serializer = DomainSerializer(
            self.domain, data={"name": "Test Domain", "boundaries": None}, partial=True
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["boundaries"], {})

    def test_validate_capabilities_dict(self):
        """Test capabilities validation - must be dict"""
        serializer = DomainSerializer(
            self.domain,
            data={"name": "Test Domain", "capabilities": ["not-a-dict"]},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("capabilities", serializer.errors)

    def test_validate_capabilities_none_becomes_empty_dict(self):
        """Test capabilities validation - None becomes empty dict"""
        serializer = DomainSerializer(
            self.domain, data={"name": "Test Domain", "capabilities": None}, partial=True
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["capabilities"], {})

    def test_validate_resource_quota_dict(self):
        """Test resource_quota validation - must be dict"""
        serializer = DomainSerializer(
            self.domain,
            data={"name": "Test Domain", "resource_quota": "not-a-dict"},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("resource_quota", serializer.errors)

    def test_validate_resource_quota_negative_value(self):
        """Test resource_quota validation - negative values"""
        serializer = DomainSerializer(
            self.domain,
            data={"name": "Test Domain", "resource_quota": {"storage_gb": -10}},
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("resource_quota", serializer.errors)

    def test_validate_resource_quota_non_number(self):
        """Test resource_quota validation - non-number values"""
        serializer = DomainSerializer(
            self.domain,
            data={
                "name": "Test Domain",
                "resource_quota": {"storage_gb": "not-a-number"},
            },
            partial=True,
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("resource_quota", serializer.errors)

    def test_validate_resource_quota_valid(self):
        """Test resource_quota validation - valid values"""
        serializer = DomainSerializer(
            self.domain,
            data={
                "name": "Test Domain",
                "resource_quota": {"storage_gb": 100, "compute_hours": 50.5},
            },
            partial=True,
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["resource_quota"]["storage_gb"], 100)
        self.assertEqual(serializer.validated_data["resource_quota"]["compute_hours"], 50.5)

    def test_validate_resource_quota_none_becomes_empty_dict(self):
        """Test resource_quota validation - None becomes empty dict"""
        serializer = DomainSerializer(
            self.domain,
            data={"name": "Test Domain", "resource_quota": None},
            partial=True,
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["resource_quota"], {})

    def test_read_only_fields(self):
        """Test that read-only fields cannot be set"""
        serializer = DomainSerializer(
            self.domain,
            data={
                "id": str(uuid.uuid4()),
                "created_at": "2020-01-01T00:00:00Z",
                "updated_at": "2020-01-01T00:00:00Z",
                "tenant_name": "Changed Tenant",
                "owner_email": "changed@example.com",
                "name": "Updated Name",
            },
            partial=True,
        )
        # Read-only fields should be ignored, not cause errors
        self.assertTrue(serializer.is_valid())


class DomainCreateSerializerTest(TestCase):
    """Test DomainCreateSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

    def test_serialize_valid_data(self):
        """Test serialization with valid data"""
        data = {
            "name": "New Domain",
            "description": "New domain description",
            "owner_id": str(self.user.id),
            "boundaries": {"data_products": ["product1"]},
            "capabilities": {"apis": ["api1"]},
            "resource_quota": {"storage_gb": 100},
            "status": DomainStatus.ACTIVE,
        }
        serializer = DomainCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "New Domain")
        self.assertEqual(serializer.validated_data["description"], "New domain description")
        self.assertEqual(
            str(serializer.validated_data["owner_id"]), str(self.user.id)
        )

    def test_serialize_minimal_data(self):
        """Test serialization with minimal required data"""
        data = {"name": "Minimal Domain"}
        serializer = DomainCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Minimal Domain")
        self.assertEqual(serializer.validated_data.get("description"), None)
        self.assertEqual(serializer.validated_data.get("status"), DomainStatus.ACTIVE)

    def test_validate_name_empty(self):
        """Test name validation - empty"""
        serializer = DomainCreateSerializer(data={"name": ""})
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_validate_name_whitespace_only(self):
        """Test name validation - whitespace only"""
        serializer = DomainCreateSerializer(data={"name": "   "})
        self.assertFalse(serializer.is_valid())
        self.assertIn("name", serializer.errors)

    def test_validate_name_strips_whitespace(self):
        """Test name validation - strips whitespace"""
        serializer = DomainCreateSerializer(data={"name": "  Test Domain  "})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Test Domain")

    def test_validate_resource_quota_negative(self):
        """Test resource_quota validation - negative values"""
        serializer = DomainCreateSerializer(
            data={"name": "Test Domain", "resource_quota": {"storage_gb": -10}}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("resource_quota", serializer.errors)

    def test_validate_resource_quota_non_number(self):
        """Test resource_quota validation - non-number values"""
        serializer = DomainCreateSerializer(
            data={"name": "Test Domain", "resource_quota": {"storage_gb": "not-a-number"}}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("resource_quota", serializer.errors)

    def test_validate_resource_quota_valid(self):
        """Test resource_quota validation - valid values"""
        serializer = DomainCreateSerializer(
            data={
                "name": "Test Domain",
                "resource_quota": {"storage_gb": 100, "compute_hours": 50.5},
            }
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["resource_quota"]["storage_gb"], 100)

    def test_validate_resource_quota_empty_dict(self):
        """Test resource_quota validation - empty dict"""
        serializer = DomainCreateSerializer(data={"name": "Test Domain", "resource_quota": {}})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["resource_quota"], {})

    def test_default_status(self):
        """Test default status is ACTIVE"""
        serializer = DomainCreateSerializer(data={"name": "Test Domain"})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["status"], DomainStatus.ACTIVE)

    def test_optional_fields(self):
        """Test optional fields can be omitted"""
        serializer = DomainCreateSerializer(data={"name": "Test Domain"})
        self.assertTrue(serializer.is_valid())
        self.assertIsNone(serializer.validated_data.get("description"))
        self.assertIsNone(serializer.validated_data.get("owner_id"))
        self.assertEqual(serializer.validated_data.get("boundaries"), None)
        self.assertEqual(serializer.validated_data.get("capabilities"), None)


class DomainUpdateSerializerTest(TestCase):
    """Test DomainUpdateSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_serialize_valid_data(self):
        """Test serialization with valid data"""
        data = {
            "name": "Updated Domain",
            "description": "Updated description",
            "status": DomainStatus.INACTIVE,
        }
        serializer = DomainUpdateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Updated Domain")

    def test_serialize_partial_data(self):
        """Test serialization with partial data"""
        data = {"name": "Updated Name"}
        serializer = DomainUpdateSerializer(data=data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Updated Name")

    def test_validate_name_strips_whitespace(self):
        """Test name validation - strips whitespace"""
        serializer = DomainUpdateSerializer(data={"name": "  Test Domain  "})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["name"], "Test Domain")

    def test_validate_name_empty_string_passes_through(self):
        """Test name validation - empty string passes through (rejected by service layer)"""
        serializer = DomainUpdateSerializer(data={"name": ""})
        self.assertTrue(serializer.is_valid())
        # Empty string passes through - service layer will reject it
        self.assertEqual(serializer.validated_data["name"], "")

    def test_validate_resource_quota_negative(self):
        """Test resource_quota validation - negative values"""
        serializer = DomainUpdateSerializer(data={"resource_quota": {"storage_gb": -10}})
        self.assertFalse(serializer.is_valid())
        self.assertIn("resource_quota", serializer.errors)

    def test_validate_resource_quota_non_number(self):
        """Test resource_quota validation - non-number values"""
        serializer = DomainUpdateSerializer(data={"resource_quota": {"storage_gb": "not-a-number"}})
        self.assertFalse(serializer.is_valid())
        self.assertIn("resource_quota", serializer.errors)

    def test_validate_resource_quota_valid(self):
        """Test resource_quota validation - valid values"""
        serializer = DomainUpdateSerializer(data={"resource_quota": {"storage_gb": 100}})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["resource_quota"]["storage_gb"], 100)

    def test_all_fields_optional(self):
        """Test all fields are optional"""
        serializer = DomainUpdateSerializer(data={})
        self.assertTrue(serializer.is_valid())


class TransferOwnershipSerializerTest(TestCase):
    """Test TransferOwnershipSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

    def test_serialize_valid_owner_id(self):
        """Test serialization with valid owner ID"""
        serializer = TransferOwnershipSerializer(data={"new_owner_id": str(self.user.id)})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(
            str(serializer.validated_data["new_owner_id"]), str(self.user.id)
        )

    def test_serialize_none_owner_id(self):
        """Test serialization with None owner ID (remove owner)"""
        serializer = TransferOwnershipSerializer(data={"new_owner_id": None})
        self.assertTrue(serializer.is_valid())
        self.assertIsNone(serializer.validated_data["new_owner_id"])

    def test_serialize_empty_data(self):
        """Test serialization with empty data"""
        serializer = TransferOwnershipSerializer(data={})
        self.assertTrue(serializer.is_valid())
        self.assertIsNone(serializer.validated_data.get("new_owner_id"))

    def test_validate_invalid_uuid(self):
        """Test validation with invalid UUID"""
        serializer = TransferOwnershipSerializer(data={"new_owner_id": "not-a-uuid"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("new_owner_id", serializer.errors)


class PolicyApplicationSerializerTest(TestCase):
    """Test PolicyApplicationSerializer"""

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
            tenant=self.tenant, name="Test Domain", status=DomainStatus.ACTIVE
        )
        self.policy = AccessPolicy.objects.create(
            tenant=self.tenant,
            name="Test Policy",
            conditions={"user.role": "ADMIN"},
            effect="ALLOW",
            enabled=True,
            created_by=self.user,
        )
        self.policy_app = PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=self.user,
            status=PolicyApplicationStatus.APPLIED,
            overrides={"priority": 50},
        )

    def test_serialize_policy_application_success(self):
        """Test successful policy application serialization"""
        serializer = PolicyApplicationSerializer(self.policy_app)
        data = serializer.data

        self.assertEqual(data["id"], str(self.policy_app.id))
        self.assertEqual(data["domain_id"], str(self.domain.id))
        self.assertEqual(data["domain_name"], self.domain.name)
        self.assertEqual(data["policy_id"], str(self.policy.id))
        self.assertEqual(data["policy_name"], self.policy.name)
        self.assertEqual(data["applied_by_id"], str(self.user.id))
        self.assertEqual(data["applied_by_email"], self.user.email)
        self.assertEqual(data["status"], PolicyApplicationStatus.APPLIED)
        self.assertEqual(data["overrides"], {"priority": 50})
        self.assertIn("applied_at", data)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_serialize_policy_application_without_applied_by(self):
        """Test serialization of policy application without applied_by"""
        policy_app_no_user = PolicyApplication.objects.create(
            domain=self.domain,
            policy=self.policy,
            applied_by=None,
            status=PolicyApplicationStatus.PENDING,
        )
        serializer = PolicyApplicationSerializer(policy_app_no_user)
        data = serializer.data

        self.assertIsNone(data["applied_by_id"])
        self.assertIsNone(data["applied_by_email"])

    def test_read_only_fields(self):
        """Test that read-only fields cannot be set"""
        serializer = PolicyApplicationSerializer(
            self.policy_app,
            data={
                "id": str(uuid.uuid4()),
                "domain_id": str(uuid.uuid4()),
                "policy_id": str(uuid.uuid4()),
                "status": PolicyApplicationStatus.REVOKED,
            },
            partial=True,
        )
        # Read-only fields should be ignored, not cause errors
        self.assertTrue(serializer.is_valid())


class ApplyPolicySerializerTest(TestCase):
    """Test ApplyPolicySerializer"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_serialize_valid_data(self):
        """Test serialization with valid data"""
        policy_id = str(uuid.uuid4())
        serializer = ApplyPolicySerializer(
            data={"policy_id": policy_id, "overrides": {"priority": 50}}
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(
            str(serializer.validated_data["policy_id"]), policy_id
        )
        self.assertEqual(serializer.validated_data["overrides"], {"priority": 50})

    def test_serialize_without_overrides(self):
        """Test serialization without overrides"""
        policy_id = str(uuid.uuid4())
        serializer = ApplyPolicySerializer(data={"policy_id": policy_id})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(
            str(serializer.validated_data["policy_id"]), policy_id
        )
        self.assertEqual(serializer.validated_data.get("overrides"), {})

    def test_validate_overrides_dict(self):
        """Test overrides validation - must be dict"""
        serializer = ApplyPolicySerializer(
            data={"policy_id": str(uuid.uuid4()), "overrides": "not-a-dict"}
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("overrides", serializer.errors)

    def test_validate_overrides_none_becomes_empty_dict(self):
        """Test overrides validation - None becomes empty dict"""
        serializer = ApplyPolicySerializer(data={"policy_id": str(uuid.uuid4()), "overrides": None})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["overrides"], {})

    def test_validate_policy_id_required(self):
        """Test policy_id is required"""
        serializer = ApplyPolicySerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("policy_id", serializer.errors)

    def test_validate_invalid_uuid(self):
        """Test validation with invalid UUID"""
        serializer = ApplyPolicySerializer(data={"policy_id": "not-a-uuid"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("policy_id", serializer.errors)


class ComplianceReportSerializerTest(TestCase):
    """Test ComplianceReportSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", status=DomainStatus.ACTIVE
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant, name="Test Asset", description="Test asset"
        )
        self.compliance_report = ComplianceReport.objects.create(
            domain=self.domain,
            asset=self.asset,
            compliance_status=MeshComplianceStatus.COMPLIANT,
            violations={"items": []},
        )

    def test_serialize_compliance_report_success(self):
        """Test successful compliance report serialization"""
        serializer = ComplianceReportSerializer(self.compliance_report)
        data = serializer.data

        self.assertEqual(data["id"], str(self.compliance_report.id))
        self.assertEqual(data["domain_id"], str(self.domain.id))
        self.assertEqual(data["domain_name"], self.domain.name)
        self.assertEqual(data["asset_id"], str(self.asset.id))
        self.assertEqual(data["asset_name"], self.asset.name)
        self.assertEqual(data["compliance_status"], MeshComplianceStatus.COMPLIANT)
        self.assertEqual(data["violations"], {"items": []})
        self.assertEqual(data["violation_count"], 0)
        self.assertIn("generated_at", data)
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_serialize_compliance_report_without_asset(self):
        """Test serialization of compliance report without asset"""
        report_no_asset = ComplianceReport.objects.create(
            domain=self.domain,
            asset=None,
            compliance_status=MeshComplianceStatus.NON_COMPLIANT,
            violations={"items": [{"type": "TEST_VIOLATION"}]},
        )
        serializer = ComplianceReportSerializer(report_no_asset)
        data = serializer.data

        self.assertIsNone(data["asset_id"])
        self.assertIsNone(data["asset_name"])
        self.assertEqual(data["violation_count"], 1)

    def test_violation_count_with_items_list(self):
        """Test violation_count calculation with items list"""
        report = ComplianceReport.objects.create(
            domain=self.domain,
            compliance_status=MeshComplianceStatus.NON_COMPLIANT,
            violations={
                "items": [{"type": "VIOLATION1"}, {"type": "VIOLATION2"}, {"type": "VIOLATION3"}]
            },
        )
        serializer = ComplianceReportSerializer(report)
        self.assertEqual(serializer.data["violation_count"], 3)

    def test_violation_count_with_dict(self):
        """Test violation_count calculation with dict"""
        report = ComplianceReport.objects.create(
            domain=self.domain,
            compliance_status=MeshComplianceStatus.NON_COMPLIANT,
            violations={"violation1": True, "violation2": True, "violation3": False},
        )
        serializer = ComplianceReportSerializer(report)
        self.assertEqual(serializer.data["violation_count"], 2)

    def test_violation_count_empty(self):
        """Test violation_count with empty violations"""
        report = ComplianceReport.objects.create(
            domain=self.domain, compliance_status=MeshComplianceStatus.COMPLIANT, violations={}
        )
        serializer = ComplianceReportSerializer(report)
        self.assertEqual(serializer.data["violation_count"], 0)

    def test_violation_count_none(self):
        """Test violation_count with empty violations (model uses default_empty_dict, not null)"""
        report = ComplianceReport.objects.create(
            domain=self.domain,
            compliance_status=MeshComplianceStatus.COMPLIANT,
            violations={},
        )
        serializer = ComplianceReportSerializer(report)
        self.assertEqual(serializer.data["violation_count"], 0)

    def test_read_only_fields(self):
        """Test that read-only fields cannot be set"""
        serializer = ComplianceReportSerializer(
            self.compliance_report,
            data={
                "id": str(uuid.uuid4()),
                "domain_id": str(uuid.uuid4()),
                "compliance_status": MeshComplianceStatus.NON_COMPLIANT,
            },
            partial=True,
        )
        # Read-only fields should be ignored, not cause errors
        self.assertTrue(serializer.is_valid())


class CheckComplianceSerializerTest(TestCase):
    """Test CheckComplianceSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_serialize_with_asset_id(self):
        """Test serialization with asset ID"""
        asset_id = str(uuid.uuid4())
        serializer = CheckComplianceSerializer(data={"asset_id": asset_id})
        self.assertTrue(serializer.is_valid())
        self.assertEqual(
            str(serializer.validated_data["asset_id"]), asset_id
        )

    def test_serialize_without_asset_id(self):
        """Test serialization without asset ID"""
        serializer = CheckComplianceSerializer(data={})
        self.assertTrue(serializer.is_valid())
        self.assertIsNone(serializer.validated_data.get("asset_id"))

    def test_serialize_with_none_asset_id(self):
        """Test serialization with None asset ID"""
        serializer = CheckComplianceSerializer(data={"asset_id": None})
        self.assertTrue(serializer.is_valid())
        self.assertIsNone(serializer.validated_data["asset_id"])

    def test_validate_invalid_uuid(self):
        """Test validation with invalid UUID"""
        serializer = CheckComplianceSerializer(data={"asset_id": "not-a-uuid"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("asset_id", serializer.errors)


class HealthMetricsSerializerTest(TestCase):
    """Test HealthMetricsSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )

    def test_serialize_valid_data(self):
        """Test serialization with valid data"""
        serializer = HealthMetricsSerializer(
            data={
                "health_score": 85,
                "policy_count": 5,
                "compliance_status": MeshComplianceStatus.COMPLIANT,
                "violation_count": 0,
                "is_active": True,
            }
        )
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data["health_score"], 85)
        self.assertEqual(serializer.validated_data["policy_count"], 5)
        self.assertEqual(
            serializer.validated_data["compliance_status"], MeshComplianceStatus.COMPLIANT
        )
        self.assertEqual(serializer.validated_data["violation_count"], 0)
        self.assertTrue(serializer.validated_data["is_active"])

    def test_validate_health_score_range(self):
        """Test health_score validation - should accept 0-100"""
        serializer = HealthMetricsSerializer(
            data={
                "health_score": 0,
                "policy_count": 0,
                "compliance_status": MeshComplianceStatus.COMPLIANT,
                "violation_count": 0,
                "is_active": False,
            }
        )
        self.assertTrue(serializer.is_valid())

        serializer = HealthMetricsSerializer(
            data={
                "health_score": 100,
                "policy_count": 0,
                "compliance_status": MeshComplianceStatus.COMPLIANT,
                "violation_count": 0,
                "is_active": True,
            }
        )
        self.assertTrue(serializer.is_valid())

    def test_validate_all_fields_required(self):
        """Test all fields are required"""
        serializer = HealthMetricsSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn("health_score", serializer.errors)
        self.assertIn("policy_count", serializer.errors)
        self.assertIn("compliance_status", serializer.errors)
        self.assertIn("violation_count", serializer.errors)
        self.assertIn("is_active", serializer.errors)


class TopologySerializersTest(TestCase):
    """Test Topology-related serializers"""

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
            tenant=self.tenant, name="Test Domain", owner=self.user, status=DomainStatus.ACTIVE
        )

    def test_topology_node_serializer(self):
        """Test TopologyNodeSerializer"""
        from datetime import datetime

        from django.utils import timezone

        serializer = TopologyNodeSerializer(
            data={
                "id": str(self.domain.id),
                "name": self.domain.name,
                "description": "Test description",
                "status": DomainStatus.ACTIVE,
                "owner_id": str(self.user.id),
                "created_at": timezone.now().isoformat(),
            }
        )
        self.assertTrue(serializer.is_valid())

    def test_topology_edge_serializer(self):
        """Test TopologyEdgeSerializer"""
        domain2 = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Domain 2", status=DomainStatus.ACTIVE
        )
        serializer = TopologyEdgeSerializer(
            data={
                "source": str(self.domain.id),
                "target": str(domain2.id),
                "type": "SHARED_POLICY",
                "weight": 10,
            }
        )
        self.assertTrue(serializer.is_valid())

    def test_topology_metadata_serializer(self):
        """Test TopologyMetadataSerializer"""
        from datetime import datetime

        from django.utils import timezone

        serializer = TopologyMetadataSerializer(
            data={
                "tenant_id": str(self.tenant.id),
                "domain_count": 1,
                "relationship_count": 0,
                "generated_at": timezone.now().isoformat(),
            }
        )
        self.assertTrue(serializer.is_valid())

    def test_topology_summary_serializer(self):
        """Test TopologySummarySerializer"""
        serializer = TopologySummarySerializer(
            data={
                "total_domains": 1,
                "active_domains": 1,
                "total_relationships": 0,
                "average_health_score": 85.5,
            }
        )
        self.assertTrue(serializer.is_valid())

    def test_topology_serializer(self):
        """Test TopologySerializer"""
        from datetime import datetime

        from django.utils import timezone

        serializer = TopologySerializer(
            data={
                "nodes": [
                    {
                        "id": str(self.domain.id),
                        "name": self.domain.name,
                        "status": DomainStatus.ACTIVE,
                        "owner_id": str(self.user.id),
                    }
                ],
                "edges": [],
                "metadata": {
                    "tenant_id": str(self.tenant.id),
                    "domain_count": 1,
                    "relationship_count": 0,
                    "generated_at": timezone.now().isoformat(),
                },
                "summary": {
                    "total_domains": 1,
                    "active_domains": 1,
                    "total_relationships": 0,
                    "average_health_score": 85.5,
                },
            }
        )
        self.assertTrue(serializer.is_valid())

    def test_domain_topology_serializer(self):
        """Test DomainTopologySerializer"""
        serializer = DomainTopologySerializer(
            data={
                "domain": {
                    "id": str(self.domain.id),
                    "name": self.domain.name,
                    "status": DomainStatus.ACTIVE,
                },
                "relationships": [],
                "health_metrics": {
                    "health_score": 85,
                    "policy_count": 0,
                    "compliance_status": MeshComplianceStatus.COMPLIANT,
                    "violation_count": 0,
                    "is_active": True,
                },
            }
        )
        self.assertTrue(serializer.is_valid())

    def test_mesh_health_serializer(self):
        """Test MeshHealthSerializer"""
        serializer = MeshHealthSerializer(
            data={
                "overall_health_score": 85.5,
                "total_domains": 1,
                "active_domains": 1,
                "compliant_domains": 1,
                "non_compliant_domains": 0,
                "domains_with_violations": 0,
                "domain_health": [],
            }
        )
        self.assertTrue(serializer.is_valid())

    def test_domain_relationship_serializer(self):
        """Test DomainRelationshipSerializer"""
        serializer = DomainRelationshipSerializer(
            data={"relationships": [], "total_count": 0, "relationship_types": {}}
        )
        self.assertTrue(serializer.is_valid())


class DomainAnalyticsSerializerTest(TestCase):
    """Test DomainAnalyticsSerializer"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        self.domain = DataMeshDomain.objects.create(
            tenant=self.tenant, name="Test Domain", status=DomainStatus.ACTIVE
        )

    def test_serialize_domain_analytics(self):
        """Test serialization of domain analytics"""
        from datetime import datetime

        from django.utils import timezone

        serializer = DomainAnalyticsSerializer(
            data={
                "domain_id": str(self.domain.id),
                "domain_name": self.domain.name,
                "status": DomainStatus.ACTIVE,
                "created_at": timezone.now().isoformat(),
                "updated_at": timezone.now().isoformat(),
                "resource_usage": {"storage_gb_used": 50},
                "resource_quota": {"storage_gb": 100},
                "resource_usage_percentages": {"storage_gb": 50.0},
                "total_policies": 5,
                "applied_policies": 3,
                "pending_policies": 2,
                "compliance_status": MeshComplianceStatus.COMPLIANT,
                "violation_count": 0,
                "last_compliance_check": timezone.now().isoformat(),
                "boundaries_count": 2,
                "capabilities_count": 3,
                "health_score": 85.5,
                "health_status": "HEALTHY",
            }
        )
        self.assertTrue(serializer.is_valid())

    def test_serialize_with_null_values(self):
        """Test serialization with null values"""
        from datetime import datetime

        from django.utils import timezone

        serializer = DomainAnalyticsSerializer(
            data={
                "domain_id": str(self.domain.id),
                "domain_name": self.domain.name,
                "status": DomainStatus.ACTIVE,
                "created_at": timezone.now().isoformat(),
                "updated_at": timezone.now().isoformat(),
                "resource_usage": {},
                "resource_quota": {},
                "resource_usage_percentages": {},
                "total_policies": 0,
                "applied_policies": 0,
                "pending_policies": 0,
                "compliance_status": None,
                "violation_count": 0,
                "last_compliance_check": None,
                "boundaries_count": 0,
                "capabilities_count": 0,
                "health_score": None,
                "health_status": None,
            }
        )
        self.assertTrue(serializer.is_valid())
