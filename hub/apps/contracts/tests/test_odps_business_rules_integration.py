"""
Integration tests for ODPS Business Rules with ContractService.

Tests verify that the migrated ODPS business rules work correctly
when integrated with ContractService operations.

All tests use real implementations (no mocks/stubs) and verify:
- ContractService integration with ODPSBusinessRules
- ContractService integration with ODPSLinkingRules
- ContractService integration with ODPSExportRules
- Framework-based validation execution
- Registry integration
"""
import json
from django.test import TestCase

from hub.apps.contracts.business_rules import (
    ODPSBusinessRules,
    ODPSLinkingRules,
    ODPSExportRules,
    ODPSNormalizationRules,
    ODPSRuleExecutionContext
)
from hub.apps.contracts.services import ContractService
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    OriginalSpecType,
    OriginalFormat,
)
from hub.apps.core.business_rules.base import ValidationResult
from hub.apps.core.business_rules.registry import get_registry
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import User, UserStatus


class ODPSBusinessRulesContractServiceIntegrationTest(TestCase):
    """Integration tests for ODPSBusinessRules with ContractService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )
        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        self.odps_rules = ODPSBusinessRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    def test_contract_service_with_odps_validation(self):
        """Test ContractService.get_contract with ODPS business rules validation"""
        # Create ODPS contract via service
        from hub.apps.contracts.services import ODPSService
        odps_service = ODPSService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-integration",
                        "name": "Test Product Integration"
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}]
                }
            }
        })

        contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Validate using business rules framework
        context = ODPSRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            contract=contract
        )
        result = self.odps_rules.validate(context, validation_type='contract')

        self.assertTrue(result.is_valid, f"Validation failed: {result.errors}")
        self.assertIn('contract', result.details['validated_items'])

        # Verify contract can be retrieved via ContractService
        retrieved_contract = self.contract_service.get_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id)
        )
        self.assertEqual(retrieved_contract.id, contract.id)

    def test_contract_service_with_odps_structure_validation(self):
        """Test ODPS structure validation via framework"""
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}]
                }
            }
        }

        context = ODPSRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            odps_doc=odps_doc
        )
        result = self.odps_rules.validate(context, validation_type='structure')

        self.assertTrue(result.is_valid, f"Structure validation failed: {result.errors}")
        self.assertIn('structure', result.details['validated_items'])

    def test_contract_service_with_odps_version_validation(self):
        """Test ODPS version validation via framework"""
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}]
                }
            }
        }

        context = ODPSRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            odps_doc=odps_doc
        )
        result = self.odps_rules.validate(
            context,
            validation_type='version',
            required_version='4.1'
        )

        self.assertTrue(result.is_valid, f"Version validation failed: {result.errors}")
        self.assertIn('version', result.details['validated_items'])


class ODPSLinkingRulesContractServiceIntegrationTest(TestCase):
    """Integration tests for ODPSLinkingRules with ContractService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )
        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        self.linking_rules = ODPSLinkingRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create ODCS contract
        odcs_raw = json.dumps({
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-odcs-integration",
            "name": "Test ODCS Integration",
            "version": "3.0.2",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            }
        })

        self.odcs_contract = self.contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS.value
        )

        # Create ODPS contract
        from hub.apps.contracts.services import ODPSService
        odps_service = ODPSService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Store ODCS raw for use in linking tests
        self.odcs_raw = odcs_raw

        # Create ODPS contract without contract section initially
        # (we'll link it properly in tests)
        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-odps-integration",
                        "name": "Test ODPS Integration"
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}]
                }
            }
        })

        self.odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    def test_contract_service_with_linking_validation(self):
        """Test ContractService.link_odps_to_odcs with linking rules validation"""
        # Create ODPS with embedded ODCS contract for linking
        odcs_contract_dict = json.loads(self.odcs_raw)
        odps_with_contract = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-odps-linking-validation",
                        "name": "Test ODPS for Linking Validation"
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}]
                },
                "contract": {
                    "spec": odcs_contract_dict
                }
            }
        })

        # Link contracts via service using odps_raw (creates and links in one step)
        linked_odps = self.contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_raw=odps_with_contract,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Refresh from database
        linked_odps.refresh_from_db()
        self.odcs_contract.refresh_from_db()

        # Validate using business rules framework
        context = ODPSRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            contract=linked_odps,
            odcs_contract=self.odcs_contract
        )

        # Test link validation (should pass - link exists)
        link_result = self.linking_rules.validate(context, validation_type='link')
        self.assertTrue(link_result.is_valid, f"Link validation failed: {link_result.errors}")
        self.assertIn('link', link_result.details['validated_items'])

        # Test referential integrity separately
        integrity_result = self.linking_rules.validate(context, validation_type='integrity')
        self.assertTrue(integrity_result.is_valid, f"Integrity validation failed: {integrity_result.errors}")
        self.assertIn('integrity', integrity_result.details['validated_items'])

    def test_contract_service_with_referential_integrity_validation(self):
        """Test referential integrity validation via framework"""
        # Create ODPS with embedded ODCS contract and link them
        odcs_contract_dict = json.loads(self.odcs_raw)
        odps_with_contract = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-odps-integrity-validation",
                        "name": "Test ODPS for Integrity Validation"
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}]
                },
                "contract": {
                    "spec": odcs_contract_dict
                }
            }
        })

        # Link contracts via service
        linked_odps = self.contract_service.link_odps_to_odcs(
            odcs_contract_id=str(self.odcs_contract.id),
            odps_raw=odps_with_contract,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        linked_odps.refresh_from_db()

        # Validate referential integrity
        context = ODPSRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            contract=linked_odps
        )
        result = self.linking_rules.validate(context, validation_type='integrity')

        self.assertTrue(result.is_valid, f"Referential integrity validation failed: {result.errors}")
        self.assertIn('integrity', result.details['validated_items'])


class ODPSExportRulesContractServiceIntegrationTest(TestCase):
    """Integration tests for ODPSExportRules with ContractService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )
        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        self.export_rules = ODPSExportRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create ODPS contract
        from hub.apps.contracts.services import ODPSService
        odps_service = ODPSService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-odps-export-integration",
                        "name": "Test ODPS Export Integration"
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}]
                }
            }
        })

        self.odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

    def test_contract_service_with_export_format_validation(self):
        """Test export format validation via framework"""
        context = ODPSRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            metadata={'output_format': 'json'}
        )
        result = self.export_rules.validate(context, validation_type='format', output_format='json')

        self.assertTrue(result.is_valid, f"Export format validation failed: {result.errors}")
        self.assertIn('format', result.details['validated_items'])

    def test_contract_service_with_data_completeness_validation(self):
        """Test data completeness validation via framework"""
        context = ODPSRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            contract=self.odps_contract
        )
        result = self.export_rules.validate(context, validation_type='completeness')

        self.assertTrue(result.is_valid, f"Data completeness validation failed: {result.errors}")
        self.assertIn('completeness', result.details['validated_items'])

    def test_contract_service_with_fidelity_validation(self):
        """Test export fidelity validation via framework"""
        # Generate exported ODPS
        from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract
        # Pass hub_contract_json instead of contract object
        if not self.odps_contract.hub_contract_json:
            self.skipTest("ODPS contract has no hub_contract_json")
        exported_odps = generate_odps_from_hubcontract(self.odps_contract.hub_contract_json)

        context = ODPSRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            contract=self.odps_contract,
            odps_doc=exported_odps
        )
        result = self.export_rules.validate(
            context,
            validation_type='fidelity',
            exported_odps=exported_odps,
            output_format='json'
        )

        self.assertTrue(result.is_valid, f"Fidelity validation failed: {result.errors}")
        self.assertIn('fidelity', result.details['validated_items'])


class ODPSBusinessRulesRegistryIntegrationTest(TestCase):
    """Integration tests for ODPS business rules registry"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )
        self.registry = get_registry()

    def test_odps_rules_registered(self):
        """Test that ODPS rules are registered in the registry"""
        odps_rule = self.registry.get_rule("odps_validation")
        self.assertIsNotNone(odps_rule)
        self.assertEqual(odps_rule.rule_class, ODPSBusinessRules)
        self.assertIn("odps", odps_rule.tags)
        self.assertIn("contracts", odps_rule.tags)

        linking_rule = self.registry.get_rule("odps_linking_validation")
        self.assertIsNotNone(linking_rule)
        self.assertEqual(linking_rule.rule_class, ODPSLinkingRules)
        self.assertIn("odps", linking_rule.tags)
        self.assertIn("linking", linking_rule.tags)

        export_rule = self.registry.get_rule("odps_export_validation")
        self.assertIsNotNone(export_rule)
        self.assertEqual(export_rule.rule_class, ODPSExportRules)
        self.assertIn("odps", export_rule.tags)
        self.assertIn("export", export_rule.tags)

    def test_odps_rules_execution_via_registry(self):
        """Test executing ODPS rules via registry"""
        odps_doc = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product"
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}]
                }
            }
        }

        from hub.apps.core.business_rules.base import RuleExecutionContext
        context = RuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            metadata={'odps_doc': odps_doc}
        )

        # Execute via registry
        results = self.registry.execute_rules(
            rule_names=["odps_validation"],
            context=context,
            odps_doc=odps_doc,
            validation_type='structure'
        )

        self.assertIn("odps_validation", results)
        result = results["odps_validation"]
        self.assertTrue(result.is_valid, f"Registry execution failed: {result.errors}")


class ODPSNormalizationRulesContractServiceIntegrationTest(TestCase):
    """Integration tests for ODPSNormalizationRules with ContractService"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Test User",
        )
        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        self.normalization_rules = ODPSNormalizationRules(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )
        self.registry = get_registry()

    def test_contract_service_with_normalization_eligibility(self):
        """Test normalization eligibility validation via framework"""
        # Create ODCS contract via service
        odcs_raw = json.dumps({
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract-normalization",
            "name": "Test Contract Normalization",
            "version": "3.0.2",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "value", "type": "integer"}
                ]
            }
        })

        contract = self.contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS.value
        )

        # Validate eligibility using business rules framework
        context = ODPSRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            contract=contract
        )

        result = self.normalization_rules.execute(
            context=context,
            validation_type="eligibility"
        )

        self.assertTrue(result.is_valid, f"Eligibility validation failed: {result.errors}")
        self.assertIn("eligibility", result.details)
        self.assertTrue(result.details["eligibility"]["is_eligible"])

    def test_contract_service_with_normalization_status(self):
        """Test normalization status validation via framework"""
        # Create and normalize ODCS contract via service
        odcs_raw = json.dumps({
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract-status",
            "name": "Test Contract Status",
            "version": "3.0.2",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"}
                ]
            }
        })

        contract = self.contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS.value
        )

        # Contract should be normalized after creation
        self.assertIsNotNone(contract.normalization_status)
        self.assertIsNotNone(contract.hub_contract_json)

        # Validate status using business rules framework
        context = ODPSRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            contract=contract
        )

        result = self.normalization_rules.execute(
            context=context,
            validation_type="status"
        )

        self.assertTrue(result.is_valid, f"Status validation failed: {result.errors}")
        self.assertIn("status", result.details)
        self.assertTrue(result.details["status"]["status_valid"])

    def test_contract_service_with_normalization_fidelity(self):
        """Test normalization fidelity validation via framework"""
        # Create and normalize ODCS contract via service
        odcs_raw = json.dumps({
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract-fidelity",
            "name": "Test Contract Fidelity",
            "version": "3.0.2",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "value", "type": "integer"}
                ]
            }
        })

        contract = self.contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS.value
        )

        # Contract should be normalized after creation
        self.assertIsNotNone(contract.normalization_status)
        self.assertIsNotNone(contract.hub_contract_json)

        # Validate fidelity using business rules framework
        context = ODPSRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            contract=contract
        )

        result = self.normalization_rules.execute(
            context=context,
            validation_type="fidelity"
        )

        self.assertTrue(result.is_valid, f"Fidelity validation failed: {result.errors}")
        self.assertIn("fidelity", result.details)
        self.assertEqual(result.details["fidelity"]["fidelity_check"], "performed")

    def test_normalization_rules_registered(self):
        """Test that normalization rules are registered in the registry"""
        normalization_rule = self.registry.get_rule("odps_normalization_validation")
        self.assertIsNotNone(normalization_rule)
        self.assertEqual(normalization_rule.rule_class, ODPSNormalizationRules)
        self.assertIn("odps", normalization_rule.tags)
        self.assertIn("normalization", normalization_rule.tags)

    def test_normalization_rules_execution_via_registry(self):
        """Test normalization rules execution via registry"""
        # Create contract
        odcs_raw = json.dumps({
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-contract-registry",
            "name": "Test Contract Registry",
            "version": "3.0.2",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"}
                ]
            }
        })

        contract = self.contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="JSON",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS.value
        )

        # Execute via registry
        context = ODPSRuleExecutionContext(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            contract=contract
        )

        results = self.registry.execute_rules(
            rule_names=["odps_normalization_validation"],
            context=context,
            validation_type="eligibility"
        )

        self.assertIn("odps_normalization_validation", results)
        result = results["odps_normalization_validation"]
        self.assertTrue(result.is_valid, f"Registry execution failed: {result.errors}")

