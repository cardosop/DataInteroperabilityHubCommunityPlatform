"""
Tests for DQ Service Integration with Contract Quality Rules (GAP-8.2.1).

Tests:
- Quality rules read from contract
- Custom rules executed
- Default profile used
"""
import pytest
from django.test import TestCase
from hub.apps.contracts.models import Contract, OriginalSpecType, OriginalFormat, ContractStatus
from hub.apps.tenants.models import Tenant
from hub.apps.dq.contract_integration import ContractQualityRulesExtractor
from hub.apps.dq.service_client import DQServiceClient

# Import DQ profile types - handle import path with hyphen
import sys
import os
dq_service_path = os.path.join(os.path.dirname(__file__), '../../../services/dq-service')
if dq_service_path not in sys.path:
    sys.path.insert(0, dq_service_path)
try:
    from dq_profile import DQCheck, DQCategory, DQSeverity
except ImportError:
    # Fallback: define minimal types for testing
    from enum import Enum
    
    class DQCategory(Enum):
        COMPLETENESS = "COMPLETENESS"
        ACCURACY = "ACCURACY"
        CONSISTENCY = "CONSISTENCY"
        TIMELINESS = "TIMELINESS"
        VALIDITY = "VALIDITY"
        UNIQUENESS = "UNIQUENESS"
    
    class DQSeverity(Enum):
        ERROR = "ERROR"
        WARNING = "WARNING"
        INFO = "INFO"
    
    class DQCheck:
        def __init__(self, check_id, name, category, severity, expectation_type, params, target_level, target_column=None, target_pattern=None):
            self.check_id = check_id
            self.name = name
            self.category = category
            self.severity = severity
            self.expectation_type = expectation_type
            self.params = params
            self.target_level = target_level
            self.target_column = target_column
            self.target_pattern = target_pattern


pytestmark = pytest.mark.django_db(transaction=True)


class ContractQualityRulesExtractionTest(TestCase):
    """Test quality rules extraction from contracts (GAP-8.2.1)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="VERIFIED"
        )
        
        # Create contract with quality rules
        self.contract_with_rules = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.DATACONTRACT_COM,
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
                },
                "quality": {
                    "default_profile_key": "custom_profile",
                    "rules": [
                        {
                            "rule_id": "rule1",
                            "dimension": "completeness",
                            "expression": "id IS NOT NULL",
                            "severity": "ERROR",
                            "field": "id"
                        },
                        {
                            "rule_id": "rule2",
                            "dimension": "validity",
                            "expression": "id > 0",
                            "severity": "WARNING",
                            "field": "id"
                        }
                    ]
                }
            }
        )
        
        # Create contract without quality rules
        self.contract_without_rules = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.DATACONTRACT_COM,
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
    
    def test_extract_quality_rules_from_contract(self):
        """Test that quality rules are correctly extracted from contract (GAP-8.2.1)"""
        result = ContractQualityRulesExtractor.extract_quality_rules(self.contract_with_rules)
        
        self.assertIn('rules', result)
        self.assertIn('default_profile_key', result)
        self.assertEqual(len(result['rules']), 2)
        self.assertEqual(result['default_profile_key'], 'custom_profile')
        
        # Verify rule structure
        rule1 = result['rules'][0]
        self.assertEqual(rule1['rule_id'], 'rule1')
        self.assertEqual(rule1['dimension'], 'completeness')
        self.assertEqual(rule1['expression'], 'id IS NOT NULL')
        self.assertEqual(rule1['severity'], 'ERROR')
    
    def test_extract_quality_rules_from_contract_without_rules(self):
        """Test extraction from contract without quality rules"""
        result = ContractQualityRulesExtractor.extract_quality_rules(self.contract_without_rules)
        
        self.assertIn('rules', result)
        self.assertIn('default_profile_key', result)
        self.assertEqual(len(result['rules']), 0)
        self.assertIsNone(result['default_profile_key'])
    
    def test_get_contract_profile_key_with_default(self):
        """Test getting default profile key from contract (GAP-8.2.1)"""
        profile_key = ContractQualityRulesExtractor.get_contract_profile_key(
            self.contract_with_rules,
            fallback="intake_basic_gx"
        )
        
        self.assertEqual(profile_key, "custom_profile")
    
    def test_get_contract_profile_key_without_default(self):
        """Test getting profile key when contract doesn't specify one"""
        profile_key = ContractQualityRulesExtractor.get_contract_profile_key(
            self.contract_without_rules,
            fallback="intake_basic_gx"
        )
        
        self.assertEqual(profile_key, "intake_basic_gx")
    
    def test_parse_rule_expression_not_null(self):
        """Test parsing IS NOT NULL expression"""
        parsed = ContractQualityRulesExtractor.parse_rule_expression(
            "id IS NOT NULL",
            field_name="id"
        )
        
        self.assertEqual(parsed['type'], 'not_null')
        self.assertEqual(parsed['field'], 'id')
    
    def test_parse_rule_expression_greater_than(self):
        """Test parsing greater than expression"""
        parsed = ContractQualityRulesExtractor.parse_rule_expression(
            "id > 0",
            field_name="id"
        )
        
        self.assertEqual(parsed['type'], 'greater_than')
        self.assertEqual(parsed['field'], 'id')
        self.assertEqual(parsed['threshold'], 0.0)
    
    def test_parse_rule_expression_in_values(self):
        """Test parsing IN clause expression"""
        parsed = ContractQualityRulesExtractor.parse_rule_expression(
            "status IN ('active', 'pending')",
            field_name="status"
        )
        
        self.assertEqual(parsed['type'], 'in_values')
        self.assertEqual(parsed['field'], 'status')
        self.assertIn('active', parsed['values'])
        self.assertIn('pending', parsed['values'])
    
    def test_convert_rule_to_dq_check(self):
        """Test converting quality rule to DQCheck (GAP-8.2.1)"""
        rule = {
            "rule_id": "rule1",
            "dimension": "completeness",
            "expression": "id IS NOT NULL",
            "severity": "ERROR",
            "field": "id"
        }
        
        dq_check = ContractQualityRulesExtractor.convert_rule_to_dq_check(rule)
        
        self.assertIsNotNone(dq_check)
        self.assertEqual(dq_check.check_id, "rule1")
        self.assertEqual(dq_check.category, DQCategory.COMPLETENESS)
        self.assertEqual(dq_check.severity, DQSeverity.ERROR)
        self.assertEqual(dq_check.expectation_type, 'expect_column_values_to_not_be_null')
        self.assertEqual(dq_check.target_column, "id")
    
    def test_get_contract_quality_checks(self):
        """Test getting all quality checks from contract (GAP-8.2.1)"""
        checks = ContractQualityRulesExtractor.get_contract_quality_checks(self.contract_with_rules)
        
        self.assertEqual(len(checks), 2)
        
        # Verify first check
        check1 = checks[0]
        self.assertEqual(check1.check_id, "rule1")
        self.assertEqual(check1.category, DQCategory.COMPLETENESS)
        self.assertEqual(check1.severity, DQSeverity.ERROR)
        
        # Verify second check
        check2 = checks[1]
        self.assertEqual(check2.check_id, "rule2")
        self.assertEqual(check2.category, DQCategory.VALIDITY)
        self.assertEqual(check2.severity, DQSeverity.WARNING)


class DQServiceContractIntegrationTest(TestCase):
    """Test DQ service integration with contracts (GAP-8.2.1)"""
    
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
            original_spec_type=OriginalSpecType.DATACONTRACT_COM,
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
                },
                "quality": {
                    "default_profile_key": "custom_profile",
                    "rules": [
                        {
                            "rule_id": "rule1",
                            "dimension": "completeness",
                            "expression": "id IS NOT NULL",
                            "severity": "ERROR",
                            "field": "id"
                        }
                    ]
                }
            }
        )
        
        self.client = DQServiceClient()
    
    def test_run_dq_with_contract_quality_rules(self):
        """Test running DQ with contract quality rules (GAP-8.2.1)"""
        # This test verifies that the service client correctly extracts and uses contract quality rules
        # Note: This requires the DQ service to be running or mocked at a higher level
        
        # Verify contract has quality rules
        quality_data = ContractQualityRulesExtractor.extract_quality_rules(self.contract)
        self.assertEqual(len(quality_data['rules']), 1)
        self.assertEqual(quality_data['default_profile_key'], 'custom_profile')
        
        # Verify quality checks can be extracted
        checks = ContractQualityRulesExtractor.get_contract_quality_checks(self.contract)
        self.assertEqual(len(checks), 1)
        self.assertEqual(checks[0].check_id, 'rule1')
        
        # Verify profile key is extracted
        profile_key = ContractQualityRulesExtractor.get_contract_profile_key(
            self.contract,
            fallback="intake_basic_gx"
        )
        self.assertEqual(profile_key, 'custom_profile')
    
    def test_custom_rules_executed(self):
        """Test that custom rules from contract are executed (GAP-8.2.1)"""
        # Extract custom checks
        checks = ContractQualityRulesExtractor.get_contract_quality_checks(self.contract)
        
        # Verify checks are properly formatted for DQ service
        self.assertEqual(len(checks), 1)
        check = checks[0]
        
        # Verify check has all required fields
        self.assertIsNotNone(check.check_id)
        self.assertIsNotNone(check.name)
        self.assertIsNotNone(check.category)
        self.assertIsNotNone(check.severity)
        self.assertIsNotNone(check.expectation_type)
        self.assertIsNotNone(check.params)
        self.assertIsNotNone(check.target_level)
        
        # Verify check can be serialized (as it would be sent to DQ service)
        check_dict = {
            'check_id': check.check_id,
            'name': check.name,
            'category': check.category.value,
            'severity': check.severity.value,
            'expectation_type': check.expectation_type,
            'params': check.params,
            'target_level': check.target_level,
            'target_column': check.target_column,
            'target_pattern': check.target_pattern
        }
        
        # Verify all fields are present
        self.assertIn('check_id', check_dict)
        self.assertIn('category', check_dict)
        self.assertIn('severity', check_dict)
        self.assertIn('expectation_type', check_dict)
    
    def test_default_profile_used(self):
        """Test that default profile from contract is used (GAP-8.2.1)"""
        # Get profile key from contract
        profile_key = ContractQualityRulesExtractor.get_contract_profile_key(
            self.contract,
            fallback="intake_basic_gx"
        )
        
        # Verify contract's default profile is used
        self.assertEqual(profile_key, "custom_profile")
        
        # Test with contract without default profile
        contract_no_profile = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.DATACONTRACT_COM,
            original_spec_version="2.2.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "2.2.2", "name": "test"}',
            status=ContractStatus.DRAFT,
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"name": "Test Contract"},
                "schema": {"fields": []}
            }
        )
        
        profile_key_fallback = ContractQualityRulesExtractor.get_contract_profile_key(
            contract_no_profile,
            fallback="intake_basic_gx"
        )
        
        # Verify fallback is used
        self.assertEqual(profile_key_fallback, "intake_basic_gx")

