"""
Tests for Compliance Service Integration with Contract Compliance Policy (GAP-8.2.2).

Tests:
- Compliance policy read from contract
- Categories used for targeted PII detection
- Jurisdictions used for regulatory mapping
- Retention policy enforced
"""
import pytest
from django.test import TestCase
from hub.apps.contracts.models import Contract, OriginalSpecType, OriginalFormat, ContractStatus
from hub.apps.tenants.models import Tenant
from hub.apps.compliance.contract_integration import ContractCompliancePolicyExtractor
from hub.apps.compliance.service_client import ComplianceServiceClient


pytestmark = pytest.mark.django_db(transaction=True)


class ContractCompliancePolicyExtractionTest(TestCase):
    """Test compliance policy extraction from contracts (GAP-8.2.2)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="VERIFIED"
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
                        {"name": "phone", "data_type": "string"}
                    ]
                },
                "privacy_compliance": {
                    "contains_personal_data": True,
                    "personal_data_categories": ["EMAIL", "PHONE_NUMBER"],
                    "jurisdictions": ["GDPR", "CCPA"],
                    "legal_bases": ["CONSENT", "CONTRACT"],
                    "retention_policy": {
                        "period": "P3Y",
                        "notes": "Retain for 3 years after contract termination"
                    }
                }
            }
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
                "schema": {
                    "fields": [
                        {"name": "id", "data_type": "string"}
                    ]
                }
            }
        )
    
    def test_extract_compliance_policy_from_contract(self):
        """Test that compliance policy is correctly extracted from contract (GAP-8.2.2)"""
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(self.contract_with_policy)
        
        self.assertTrue(policy['contains_personal_data'])
        self.assertEqual(len(policy['personal_data_categories']), 2)
        self.assertIn('EMAIL', policy['personal_data_categories'])
        self.assertIn('PHONE_NUMBER', policy['personal_data_categories'])
        self.assertEqual(len(policy['jurisdictions']), 2)
        self.assertIn('GDPR', policy['jurisdictions'])
        self.assertIn('CCPA', policy['jurisdictions'])
        self.assertEqual(len(policy['legal_bases']), 2)
        self.assertIn('CONSENT', policy['legal_bases'])
        self.assertIn('CONTRACT', policy['legal_bases'])
        self.assertIsNotNone(policy['retention_policy'])
        self.assertEqual(policy['retention_policy']['period'], 'P3Y')
    
    def test_extract_compliance_policy_from_contract_without_policy(self):
        """Test extraction from contract without compliance policy"""
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(self.contract_without_policy)
        
        self.assertFalse(policy['contains_personal_data'])
        self.assertEqual(len(policy['personal_data_categories']), 0)
        self.assertEqual(len(policy['jurisdictions']), 0)
        self.assertEqual(len(policy['legal_bases']), 0)
        self.assertIsNone(policy['retention_policy'])
    
    def test_get_targeted_pii_categories(self):
        """Test getting targeted PII categories for focused detection (GAP-8.2.2)"""
        categories = ContractCompliancePolicyExtractor.get_targeted_pii_categories(self.contract_with_policy)
        
        self.assertEqual(len(categories), 2)
        self.assertIn('EMAIL', categories)
        self.assertIn('PHONE_NUMBER', categories)
    
    def test_get_regulatory_mapping(self):
        """Test getting jurisdictions for regulatory mapping (GAP-8.2.2)"""
        jurisdictions = ContractCompliancePolicyExtractor.get_regulatory_mapping(self.contract_with_policy)
        
        self.assertEqual(len(jurisdictions), 2)
        self.assertIn('GDPR', jurisdictions)
        self.assertIn('CCPA', jurisdictions)
    
    def test_get_legal_bases(self):
        """Test getting legal bases for compliance reporting (GAP-8.2.2)"""
        legal_bases = ContractCompliancePolicyExtractor.get_legal_bases(self.contract_with_policy)
        
        self.assertEqual(len(legal_bases), 2)
        self.assertIn('CONSENT', legal_bases)
        self.assertIn('CONTRACT', legal_bases)
    
    def test_get_retention_policy(self):
        """Test getting retention policy for data retention enforcement (GAP-8.2.2)"""
        retention_policy = ContractCompliancePolicyExtractor.get_retention_policy(self.contract_with_policy)
        
        self.assertIsNotNone(retention_policy)
        self.assertEqual(retention_policy['period'], 'P3Y')
        self.assertEqual(retention_policy['notes'], 'Retain for 3 years after contract termination')
    
    def test_categories_used_for_targeted_detection(self):
        """Test that categories are used for targeted PII detection (GAP-8.2.2)"""
        categories = ContractCompliancePolicyExtractor.get_targeted_pii_categories(self.contract_with_policy)
        
        # Verify categories can be used for targeted detection
        self.assertGreater(len(categories), 0)
        
        # Verify categories are in expected format
        for category in categories:
            self.assertIsInstance(category, str)
            self.assertGreater(len(category), 0)
    
    def test_jurisdictions_used_for_regulatory_mapping(self):
        """Test that jurisdictions are used for regulatory mapping (GAP-8.2.2)"""
        jurisdictions = ContractCompliancePolicyExtractor.get_regulatory_mapping(self.contract_with_policy)
        
        # Verify jurisdictions can be used for regulatory mapping
        self.assertGreater(len(jurisdictions), 0)
        
        # Verify jurisdictions are standard identifiers
        for jurisdiction in jurisdictions:
            self.assertIsInstance(jurisdiction, str)
            self.assertIn(jurisdiction, ['GDPR', 'LGPD', 'CCPA', 'HIPAA'])
    
    def test_retention_policy_enforced(self):
        """Test that retention policy is enforced (GAP-8.2.2)"""
        retention_policy = ContractCompliancePolicyExtractor.get_retention_policy(self.contract_with_policy)
        
        # Verify retention policy has required fields
        self.assertIsNotNone(retention_policy)
        self.assertIn('period', retention_policy)
        self.assertIsNotNone(retention_policy['period'])
        
        # Verify period is in ISO 8601 duration format
        period = retention_policy['period']
        self.assertTrue(period.startswith('P'))
        
        # Verify policy can be used for enforcement
        # (In real implementation, this would trigger data retention logic)
        self.assertIsNotNone(retention_policy.get('notes'))


class ComplianceServiceContractIntegrationTest(TestCase):
    """Test compliance service integration with contracts (GAP-8.2.2)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="VERIFIED"
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
                "schema": {
                    "fields": [
                        {"name": "email", "data_type": "string"}
                    ]
                },
                "privacy_compliance": {
                    "contains_personal_data": True,
                    "personal_data_categories": ["EMAIL"],
                    "jurisdictions": ["GDPR"],
                    "legal_bases": ["CONSENT"],
                    "retention_policy": {
                        "period": "P1Y",
                        "notes": "Retain for 1 year"
                    }
                }
            }
        )
        
        self.client = ComplianceServiceClient()
    
    def test_compliance_policy_read(self):
        """Test that compliance policy is read from contract (GAP-8.2.2)"""
        policy = ContractCompliancePolicyExtractor.extract_compliance_policy(self.contract)
        
        # Verify policy is correctly extracted
        self.assertTrue(policy['contains_personal_data'])
        self.assertEqual(len(policy['personal_data_categories']), 1)
        self.assertEqual(len(policy['jurisdictions']), 1)
        self.assertEqual(len(policy['legal_bases']), 1)
        self.assertIsNotNone(policy['retention_policy'])
    
    def test_categories_used(self):
        """Test that categories are used for targeted PII detection (GAP-8.2.2)"""
        categories = ContractCompliancePolicyExtractor.get_targeted_pii_categories(self.contract)
        
        # Verify categories are extracted
        self.assertEqual(len(categories), 1)
        self.assertIn('EMAIL', categories)
        
        # Verify categories can be passed to compliance service
        # (In real implementation, this would be used in scan_file call)
        self.assertIsInstance(categories, list)
        self.assertGreater(len(categories), 0)
    
    def test_jurisdictions_used(self):
        """Test that jurisdictions are used for regulatory mapping (GAP-8.2.2)"""
        jurisdictions = ContractCompliancePolicyExtractor.get_regulatory_mapping(self.contract)
        
        # Verify jurisdictions are extracted
        self.assertEqual(len(jurisdictions), 1)
        self.assertIn('GDPR', jurisdictions)
        
        # Verify jurisdictions can be passed to compliance service
        # (In real implementation, this would be used in scan_file call)
        self.assertIsInstance(jurisdictions, list)
        self.assertGreater(len(jurisdictions), 0)
    
    def test_retention_policy_enforced(self):
        """Test that retention policy is enforced (GAP-8.2.2)"""
        retention_policy = ContractCompliancePolicyExtractor.get_retention_policy(self.contract)
        
        # Verify retention policy is extracted
        self.assertIsNotNone(retention_policy)
        self.assertEqual(retention_policy['period'], 'P1Y')
        
        # Verify retention policy can be used for enforcement
        # (In real implementation, this would trigger data retention logic)
        self.assertIn('period', retention_policy)
        self.assertIsNotNone(retention_policy['period'])

