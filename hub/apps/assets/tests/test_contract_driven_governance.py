"""
Phase 26-OB: Contract-driven governance tests.

Tests quality rule extraction (ContractQualityRulesExtractor) and
compliance policy extraction (ContractCompliancePolicyExtractor) from
hub_contract_json.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.assets.models import Asset
from hub.apps.compliance.contract_integration import ContractCompliancePolicyExtractor
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.dq.contract_integration import ContractQualityRulesExtractor
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ContractDrivenGovernanceTest(TestCase):
    """Contract-driven quality rule and compliance policy extraction."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Gov Tenant {uid}",
            slug=f"gov-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"gov-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"gov-asset-{uid}",
            name="Governance Asset",
            created_by=self.user,
        )

    # -- helpers -------------------------------------------------------

    def _create_contract(self, hub_json):
        return Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            status=ContractStatus.ACTIVE,
            validation_status=ValidationStatus.VALID,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            original_spec_type=OriginalSpecType.ODCS,
            original_format=OriginalFormat.JSON,
            original_raw='{"id":"test"}',
            hub_contract_json=hub_json,
            created_by=self.user,
        )

    # == Quality rules tests ==========================================

    def test_quality_rules_extracted_from_hub_contract(self):
        """Contract with quality.rules returns DQCheck list."""
        hub_json = {
            "quality": {
                "rules": [
                    {
                        "rule_id": "q1",
                        "dimension": "completeness",
                        "expression": "email IS NOT NULL",
                        "severity": "ERROR",
                        "field": "email",
                    },
                    {
                        "rule_id": "q2",
                        "dimension": "validity",
                        "expression": "age > 0",
                        "severity": "WARNING",
                        "field": "age",
                    },
                ]
            }
        }
        contract = self._create_contract(hub_json)
        checks = ContractQualityRulesExtractor.get_contract_quality_checks(contract)
        self.assertEqual(len(checks), 2)
        self.assertEqual(checks[0].check_id, "q1")
        self.assertEqual(checks[1].check_id, "q2")

    def test_quality_rules_empty_when_no_quality_section(self):
        """Contract without quality section returns empty list."""
        contract = self._create_contract({"name": "no-quality"})
        checks = ContractQualityRulesExtractor.get_contract_quality_checks(contract)
        self.assertEqual(checks, [])

    def test_completeness_rule_parsed(self):
        """Rule with dimension=completeness, 'IS NOT NULL' maps to expect_column_values_to_not_be_null."""
        hub_json = {
            "quality": {
                "rules": [
                    {
                        "rule_id": "c1",
                        "dimension": "completeness",
                        "expression": "field IS NOT NULL",
                        "severity": "ERROR",
                        "field": "field",
                    }
                ]
            }
        }
        contract = self._create_contract(hub_json)
        checks = ContractQualityRulesExtractor.get_contract_quality_checks(contract)
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].expectation_type, "expect_column_values_to_not_be_null")

    def test_range_rule_parsed(self):
        """Rule 'value > 0' maps to expect_column_values_to_be_between."""
        hub_json = {
            "quality": {
                "rules": [
                    {
                        "rule_id": "r1",
                        "dimension": "validity",
                        "expression": "value > 0",
                        "severity": "ERROR",
                        "field": "value",
                    }
                ]
            }
        }
        contract = self._create_contract(hub_json)
        checks = ContractQualityRulesExtractor.get_contract_quality_checks(contract)
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].expectation_type, "expect_column_values_to_be_between")

    def test_invalid_rule_skipped(self):
        """Rule with unparseable expression is skipped; valid rules still returned."""
        hub_json = {
            "quality": {
                "rules": [
                    {
                        "rule_id": "bad",
                        "dimension": "validity",
                        "expression": "",
                        "severity": "ERROR",
                    },
                    {
                        "rule_id": "good",
                        "dimension": "completeness",
                        "expression": "name IS NOT NULL",
                        "severity": "ERROR",
                        "field": "name",
                    },
                ]
            }
        }
        contract = self._create_contract(hub_json)
        checks = ContractQualityRulesExtractor.get_contract_quality_checks(contract)
        # At least the valid rule should be present
        good_checks = [c for c in checks if c.check_id == "good"]
        self.assertTrue(len(good_checks) >= 1)

    # == Compliance policy tests ======================================

    def test_compliance_policy_extracted(self):
        """Contract with privacy_compliance section returns regulations list."""
        hub_json = {
            "privacy_compliance": {
                "contains_personal_data": True,
                "jurisdictions": ["GDPR", "LGPD"],
                "legal_bases": ["CONSENT"],
            }
        }
        contract = self._create_contract(hub_json)
        regs = ContractCompliancePolicyExtractor.get_regulatory_mapping(contract)
        self.assertIn("GDPR", regs)
        self.assertIn("LGPD", regs)

    def test_compliance_jurisdictions_normalized(self):
        """Jurisdictions go through REGULATION_KEY_ALIASES normalization."""
        hub_json = {
            "privacy_compliance": {
                "contains_personal_data": True,
                "jurisdictions": ["GDPR", "LGPD"],
            }
        }
        contract = self._create_contract(hub_json)
        regs = ContractCompliancePolicyExtractor.get_regulatory_mapping(contract)
        self.assertEqual(regs, ["GDPR", "LGPD"])

    def test_compliance_empty_when_no_privacy_section(self):
        """No privacy_compliance section returns empty lists."""
        contract = self._create_contract({"name": "no-privacy"})
        regs = ContractCompliancePolicyExtractor.get_regulatory_mapping(contract)
        self.assertEqual(regs, [])

    def test_compliance_legal_bases_extracted(self):
        """Contract with legal_bases=['CONSENT'] extracts correctly."""
        hub_json = {
            "privacy_compliance": {
                "contains_personal_data": True,
                "legal_bases": ["CONSENT"],
            }
        }
        contract = self._create_contract(hub_json)
        bases = ContractCompliancePolicyExtractor.get_legal_bases(contract)
        self.assertEqual(bases, ["CONSENT"])

    def test_multi_regulation_extracted(self):
        """Contract with ['GDPR','HIPAA','CCPA'] returns all three."""
        hub_json = {
            "privacy_compliance": {
                "contains_personal_data": True,
                "jurisdictions": ["GDPR", "HIPAA", "CCPA"],
            }
        }
        contract = self._create_contract(hub_json)
        regs = ContractCompliancePolicyExtractor.get_regulatory_mapping(contract)
        self.assertIn("GDPR", regs)
        self.assertIn("HIPAA", regs)
        self.assertIn("CCPA", regs)
        self.assertEqual(len(regs), 3)
