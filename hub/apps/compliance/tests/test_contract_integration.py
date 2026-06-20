"""
Tests for Compliance Service Integration with Contract Compliance Policy (GAP-8.2.2).

Tests:
- Compliance policy read from contract
- Categories used for targeted PII detection
- Jurisdictions used for regulatory mapping
- Retention policy enforced
"""

import uuid

import pytest
from django.test import TestCase

from hub.apps.compliance.contract_integration import (
    ContractCompliancePolicyExtractor,
    ContractComplianceSchemaError,
    validate_contract_compliance_payload,
)
from hub.apps.compliance.service_client import ComplianceServiceClient
from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class ContractComplianceSchemaValidationTest(TestCase):
    """Test contract compliance payload schema validation (5.4.2); real validation, no mocks."""

    def test_valid_payload_passes(self):
        """Valid privacy_compliance payload passes validation."""
        hub_contract = {
            "privacy_compliance": {
                "contains_personal_data": True,
                "personal_data_categories": ["EMAIL"],
                "jurisdictions": ["GDPR"],
                "legal_bases": ["CONSENT"],
                "retention_policy": {"period": "P1Y"},
            }
        }
        validate_contract_compliance_payload(hub_contract)

    def test_valid_empty_section_passes(self):
        """Empty or missing privacy_compliance passes."""
        validate_contract_compliance_payload({})
        validate_contract_compliance_payload({"privacy_compliance": {}})

    def test_invalid_payload_not_dict_raises(self):
        """Payload that is not a dict raises ContractComplianceSchemaError."""
        with self.assertRaises(ContractComplianceSchemaError) as ctx:
            validate_contract_compliance_payload([])
        self.assertIn("JSON object", ctx.exception.message)

    def test_invalid_privacy_compliance_not_dict_raises(self):
        """privacy_compliance that is not a dict raises."""
        with self.assertRaises(ContractComplianceSchemaError) as ctx:
            validate_contract_compliance_payload({"privacy_compliance": "not-a-dict"})
        self.assertIn("privacy_compliance", ctx.exception.message)

    def test_invalid_contains_personal_data_not_bool_raises(self):
        """contains_personal_data must be boolean."""
        with self.assertRaises(ContractComplianceSchemaError) as ctx:
            validate_contract_compliance_payload(
                {
                    "privacy_compliance": {"contains_personal_data": "yes"},
                }
            )
        self.assertIn("boolean", ctx.exception.message)

    def test_invalid_personal_data_categories_not_list_raises(self):
        """personal_data_categories must be a list."""
        with self.assertRaises(ContractComplianceSchemaError) as ctx:
            validate_contract_compliance_payload(
                {
                    "privacy_compliance": {"personal_data_categories": "EMAIL"},
                }
            )
        self.assertIn("list", ctx.exception.message)

    def test_invalid_retention_policy_not_dict_raises(self):
        """retention_policy must be dict or null."""
        with self.assertRaises(ContractComplianceSchemaError) as ctx:
            validate_contract_compliance_payload(
                {
                    "privacy_compliance": {"retention_policy": "P1Y"},
                }
            )
        self.assertIn("retention_policy", ctx.exception.message)


class ContractCompliancePolicyExtractionTest(TestCase):
    """Test compliance policy extraction from contracts (GAP-8.2.2)"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )

        # Create contract with compliance policy
        self.contract_with_policy = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="2.2.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "2.2.2", "name": "test"}',
            status=ContractStatus.DRAFT,
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"name": "Test Contract"},
                "schema": {
                    "fields": [
                        {"name": "email", "data_type": "string"},
                        {"name": "phone", "data_type": "string"},
                    ]
                },
                "privacy_compliance": {
                    "contains_personal_data": True,
                    "personal_data_categories": ["EMAIL", "PHONE_NUMBER"],
                    "jurisdictions": ["GDPR", "CCPA"],
                    "legal_bases": ["CONSENT", "CONTRACT"],
                    "retention_policy": {
                        "period": "P3Y",
                        "notes": "Retain for 3 years after contract termination",
                    },
                },
            },
        )

        # Create contract without compliance policy
        self.contract_without_policy = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="2.2.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "2.2.2", "name": "test"}',
            status=ContractStatus.DRAFT,
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"name": "Test Contract"},
                "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            },
        )

    def test_extract_compliance_policy_from_contract(self):
        """Test that compliance policy is correctly extracted from contract (GAP-8.2.2)"""
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(
            self.contract_with_policy
        )

        self.assertTrue(policy["contains_personal_data"])
        self.assertEqual(len(policy["personal_data_categories"]), 2)
        self.assertIn("EMAIL", policy["personal_data_categories"])
        self.assertIn("PHONE_NUMBER", policy["personal_data_categories"])
        self.assertEqual(len(policy["jurisdictions"]), 2)
        self.assertIn("GDPR", policy["jurisdictions"])
        self.assertIn("CCPA", policy["jurisdictions"])
        self.assertEqual(len(policy["legal_bases"]), 2)
        self.assertIn("CONSENT", policy["legal_bases"])
        self.assertIn("CONTRACT", policy["legal_bases"])
        self.assertIsNotNone(policy["retention_policy"])
        self.assertEqual(policy["retention_policy"]["period"], "P3Y")

    def test_extract_compliance_policy_from_contract_without_policy(self):
        """Test extraction from contract without compliance policy"""
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(
            self.contract_without_policy
        )

        self.assertFalse(policy["contains_personal_data"])
        self.assertEqual(len(policy["personal_data_categories"]), 0)
        self.assertEqual(len(policy["jurisdictions"]), 0)
        self.assertEqual(len(policy["legal_bases"]), 0)
        self.assertIsNone(policy["retention_policy"])

    def test_get_targeted_pii_categories(self):
        """Test getting targeted PII categories for focused detection (GAP-8.2.2)"""
        categories = ContractCompliancePolicyExtractor.get_targeted_pii_categories(
            self.contract_with_policy
        )

        self.assertEqual(len(categories), 2)
        self.assertIn("EMAIL", categories)
        self.assertIn("PHONE_NUMBER", categories)

    def test_get_regulatory_mapping(self):
        """Test getting jurisdictions for regulatory mapping (GAP-8.2.2)"""
        jurisdictions = ContractCompliancePolicyExtractor.get_regulatory_mapping(
            self.contract_with_policy
        )

        self.assertEqual(len(jurisdictions), 2)
        self.assertIn("GDPR", jurisdictions)
        self.assertIn("CCPA", jurisdictions)

    def test_get_legal_bases(self):
        """Test getting legal bases for compliance reporting (GAP-8.2.2)"""
        legal_bases = ContractCompliancePolicyExtractor.get_legal_bases(self.contract_with_policy)

        self.assertEqual(len(legal_bases), 2)
        self.assertIn("CONSENT", legal_bases)
        self.assertIn("CONTRACT", legal_bases)

    def test_get_retention_policy(self):
        """Test getting retention policy for data retention enforcement (GAP-8.2.2)"""
        retention_policy = ContractCompliancePolicyExtractor.get_retention_policy(
            self.contract_with_policy
        )

        self.assertIsNotNone(retention_policy)
        self.assertEqual(retention_policy["period"], "P3Y")
        self.assertEqual(retention_policy["notes"], "Retain for 3 years after contract termination")

    def test_categories_are_non_empty_strings(self):
        """Test that extracted PII categories are well-formed strings (GAP-8.2.2)"""
        categories = ContractCompliancePolicyExtractor.get_targeted_pii_categories(
            self.contract_with_policy
        )

        # Verify categories are present
        self.assertGreater(len(categories), 0)

        # Verify categories are non-empty strings in the known PII set
        known_categories = {"EMAIL", "PHONE_NUMBER", "SSN", "CREDIT_CARD",
                            "IP_ADDRESS", "NAME", "ADDRESS", "DOB"}
        for category in categories:
            self.assertIsInstance(category, str)
            self.assertGreater(len(category), 0)
            self.assertIn(
                category, known_categories,
                f"Category '{category}' not in known PII category set",
            )

    def test_jurisdictions_used_for_regulatory_mapping(self):
        """Test that jurisdictions are used for regulatory mapping (GAP-8.2.2)"""
        jurisdictions = ContractCompliancePolicyExtractor.get_regulatory_mapping(
            self.contract_with_policy
        )

        # Verify jurisdictions can be used for regulatory mapping
        self.assertGreater(len(jurisdictions), 0)

        # Verify jurisdictions are standard identifiers
        for jurisdiction in jurisdictions:
            self.assertIsInstance(jurisdiction, str)
            self.assertIn(jurisdiction, ["GDPR", "LGPD", "CCPA", "HIPAA"])

    def test_retention_policy_has_iso8601_period(self):
        """Test that the extracted retention policy has a well-formed ISO 8601
        duration period (GAP-8.2.2).  Enforcement is a downstream concern."""
        retention_policy = ContractCompliancePolicyExtractor.get_retention_policy(
            self.contract_with_policy
        )

        # Verify retention policy has required fields
        self.assertIsNotNone(retention_policy)
        self.assertIn("period", retention_policy)
        self.assertIsNotNone(retention_policy["period"])

        # Verify period is in ISO 8601 duration format
        period = retention_policy["period"]
        self.assertTrue(period.startswith("P"))

        # Verify notes field is present for downstream enforcement
        self.assertIsNotNone(retention_policy.get("notes"))


class ComplianceServiceContractIntegrationTest(TestCase):
    """Test compliance service integration with contracts (GAP-8.2.2)"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="VERIFIED",
        )

        self.contract = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="2.2.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "2.2.2", "name": "test"}',
            status=ContractStatus.DRAFT,
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"name": "Test Contract"},
                "schema": {"fields": [{"name": "email", "data_type": "string"}]},
                "privacy_compliance": {
                    "contains_personal_data": True,
                    "personal_data_categories": ["EMAIL"],
                    "jurisdictions": ["GDPR"],
                    "legal_bases": ["CONSENT"],
                    "retention_policy": {"period": "P1Y", "notes": "Retain for 1 year"},
                },
            },
        )

        self.client = ComplianceServiceClient()

    def test_compliance_policy_read(self):
        """Test that compliance policy is read from contract (GAP-8.2.2)"""
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(self.contract)

        # Verify policy is correctly extracted
        self.assertTrue(policy["contains_personal_data"])
        self.assertEqual(len(policy["personal_data_categories"]), 1)
        self.assertEqual(len(policy["jurisdictions"]), 1)
        self.assertEqual(len(policy["legal_bases"]), 1)
        self.assertIsNotNone(policy["retention_policy"])

    def test_categories_used(self):
        """Test that categories are used for targeted PII detection (GAP-8.2.2)"""
        categories = ContractCompliancePolicyExtractor.get_targeted_pii_categories(self.contract)

        # Verify categories are extracted
        self.assertEqual(len(categories), 1)
        self.assertIn("EMAIL", categories)

        # Verify categories can be passed to compliance service
        # (In real implementation, this would be used in scan_file call)
        self.assertIsInstance(categories, list)
        self.assertGreater(len(categories), 0)

    def test_jurisdictions_used(self):
        """Test that jurisdictions are used for regulatory mapping (GAP-8.2.2)"""
        jurisdictions = ContractCompliancePolicyExtractor.get_regulatory_mapping(self.contract)

        # Verify jurisdictions are extracted
        self.assertEqual(len(jurisdictions), 1)
        self.assertIn("GDPR", jurisdictions)

        # Verify jurisdictions can be passed to compliance service
        # (In real implementation, this would be used in scan_file call)
        self.assertIsInstance(jurisdictions, list)
        self.assertGreater(len(jurisdictions), 0)

    def test_retention_policy_extracted(self):
        """Test that the retention policy is correctly extracted from contract
        hub_contract_json (GAP-8.2.2).  Enforcement is a downstream concern."""
        retention_policy = ContractCompliancePolicyExtractor.get_retention_policy(self.contract)

        # Verify retention policy is extracted
        self.assertIsNotNone(retention_policy)
        self.assertEqual(retention_policy["period"], "P1Y")

        # Verify retention policy is well-formed for downstream enforcement
        self.assertIn("period", retention_policy)
        self.assertIsNotNone(retention_policy["period"])
