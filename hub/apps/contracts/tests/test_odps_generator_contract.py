"""
Unit tests for ODPS Generator - Contract Generation (Task 2.1.3)

Tests verify:
1. Generate ODCS from HubContract (if original ODCS available)
2. Embed as product.contract.spec (inline)
3. Reference as product.contract.contractURL
4. Error handling for invalid contract data
"""

from django.test import SimpleTestCase

from hub.apps.contracts.odps_errors import ODPSExportError
from hub.apps.contracts.odps_generator import generate_odps_from_hubcontract


class ODPSGeneratorContractEmbeddingTest(SimpleTestCase):
    """Test ODPS generator contract embedding (inline spec)"""

    def test_contract_embedding_with_original_odcs_contract(self):
        """
        Test embedding original ODCS contract as product.contract.spec (inline).

        Scenario: Generate ODPS with original ODCS contract embedded inline
        Expected: product.contract.spec contains the ODCS contract dictionary
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "description": "Test product description"},
            "schema": {"fields": []},
        }

        original_odcs_contract = {
            "apiVersion": "odcs/v3.0.2",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {"properties": {"id": {"type": "string"}, "name": {"type": "string"}}},
        }

        result = generate_odps_from_hubcontract(
            hub_contract, original_odcs_contract=original_odcs_contract
        )

        # Verify product.contract.spec exists
        self.assertIn("product", result)
        self.assertIn("contract", result["product"])
        self.assertIn("spec", result["product"]["contract"])

        # Verify spec contains the ODCS contract
        self.assertEqual(result["product"]["contract"]["spec"], original_odcs_contract)

        # Verify contractURL is not present (spec takes precedence)
        self.assertNotIn("contractURL", result["product"]["contract"])

    def test_contract_embedding_with_complete_odcs_contract(self):
        """
        Test embedding complete ODCS contract with all sections.

        Scenario: Generate ODPS with complete ODCS contract (schema, quality, compliance)
        Expected: product.contract.spec contains complete ODCS contract
        """
        hub_contract = {
            "id": "test-product-complete",
            "info": {"name": "Complete Test Product"},
            "schema": {"fields": []},
        }

        original_odcs_contract = {
            "apiVersion": "odcs/v3.0.2",
            "id": "complete-contract",
            "name": "Complete Contract",
            "version": "2.0.0",
            "schema": {
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "email": {"type": "string", "format": "email"},
                },
                "required": ["id", "name"],
            },
            "quality": {"rules": [{"type": "completeness", "field": "name", "threshold": 0.95}]},
            "compliance": {"jurisdictions": ["EU"], "legal_bases": ["consent"]},
        }

        result = generate_odps_from_hubcontract(
            hub_contract, original_odcs_contract=original_odcs_contract
        )

        # Verify product.contract.spec contains complete ODCS contract
        self.assertIn("product", result)
        self.assertIn("contract", result["product"])
        self.assertIn("spec", result["product"]["contract"])

        spec = result["product"]["contract"]["spec"]
        self.assertEqual(spec["id"], "complete-contract")
        self.assertEqual(spec["name"], "Complete Contract")
        self.assertIn("schema", spec)
        self.assertIn("quality", spec)
        self.assertIn("compliance", spec)

    def test_contract_embedding_with_invalid_odcs_contract_type(self):
        """
        Test error handling when original_odcs_contract is not a dictionary.

        Scenario: Generate ODPS with invalid original_odcs_contract type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(
                hub_contract,
                original_odcs_contract="not-a-dict",  # Invalid type
            )

        error = context.exception
        self.assertIn("original_odcs_contract", error.message.lower())
        self.assertIn("dictionary", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/product/contract/spec")
        self.assertEqual(error.context["expected"], "dict")
        self.assertIn("actual", error.context)


class ODPSGeneratorContractURLReferenceTest(SimpleTestCase):
    """Test ODPS generator contract URL reference"""

    def test_contract_reference_with_original_odcs_url(self):
        """
        Test referencing original ODCS contract as product.contract.contractURL.

        Scenario: Generate ODPS with original ODCS contract URL reference
        Expected: product.contract.contractURL contains the URL string
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "description": "Test product description"},
            "schema": {"fields": []},
        }

        original_odcs_url = "https://example.com/contracts/test-contract.json"

        result = generate_odps_from_hubcontract(hub_contract, original_odcs_url=original_odcs_url)

        # Verify product.contract.contractURL exists
        self.assertIn("product", result)
        self.assertIn("contract", result["product"])
        self.assertIn("contractURL", result["product"]["contract"])

        # Verify contractURL contains the URL
        self.assertEqual(result["product"]["contract"]["contractURL"], original_odcs_url)

        # Verify spec is not present (contractURL takes precedence when spec is not provided)
        self.assertNotIn("spec", result["product"]["contract"])

    def test_contract_reference_with_https_url(self):
        """
        Test referencing ODCS contract with HTTPS URL.

        Scenario: Generate ODPS with HTTPS URL for ODCS contract
        Expected: product.contract.contractURL contains HTTPS URL
        """
        hub_contract = {
            "id": "test-product-https",
            "info": {"name": "HTTPS Test Product"},
            "schema": {"fields": []},
        }

        original_odcs_url = "https://api.example.com/v1/contracts/test-contract-v3.0.2.json"

        result = generate_odps_from_hubcontract(hub_contract, original_odcs_url=original_odcs_url)

        self.assertEqual(result["product"]["contract"]["contractURL"], original_odcs_url)

    def test_contract_reference_with_http_url(self):
        """
        Test referencing ODCS contract with HTTP URL.

        Scenario: Generate ODPS with HTTP URL for ODCS contract
        Expected: product.contract.contractURL contains HTTP URL
        """
        hub_contract = {
            "id": "test-product-http",
            "info": {"name": "HTTP Test Product"},
            "schema": {"fields": []},
        }

        original_odcs_url = "http://internal.example.com/contracts/test-contract.json"

        result = generate_odps_from_hubcontract(hub_contract, original_odcs_url=original_odcs_url)

        self.assertEqual(result["product"]["contract"]["contractURL"], original_odcs_url)

    def test_contract_reference_with_invalid_url_type(self):
        """
        Test error handling when original_odcs_url is not a string.

        Scenario: Generate ODPS with invalid original_odcs_url type
        Expected: ODPSExportError with field_path and expected/actual types
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract, original_odcs_url=12345)  # Invalid type

        error = context.exception
        self.assertIn("original_odcs_url", error.message.lower())
        self.assertIn("string", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/product/contract/contractURL")
        self.assertEqual(error.context["expected"], "str")
        self.assertIn("actual", error.context)

    def test_contract_reference_with_empty_url(self):
        """
        Test error handling when original_odcs_url is empty string.

        Scenario: Generate ODPS with empty original_odcs_url
        Expected: ODPSExportError with field_path and expected/actual
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        with self.assertRaises(ODPSExportError) as context:
            generate_odps_from_hubcontract(hub_contract, original_odcs_url="")  # Empty string

        error = context.exception
        self.assertIn("original_odcs_url", error.message.lower())
        self.assertIn("non-empty", error.message.lower())
        self.assertIn("field_path", error.context)
        self.assertEqual(error.context["field_path"], "/product/contract/contractURL")
        self.assertEqual(error.context["expected"], "str (non-empty)")
        self.assertEqual(error.context["actual"], "empty string")


class ODPSGeneratorContractPrecedenceTest(SimpleTestCase):
    """Test ODPS generator contract precedence (spec vs contractURL)"""

    def test_contract_spec_takes_precedence_over_url(self):
        """
        Test that original_odcs_contract takes precedence over original_odcs_url.

        Scenario: Generate ODPS with both original_odcs_contract and original_odcs_url
        Expected: product.contract.spec is used, contractURL is ignored
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        original_odcs_contract = {
            "apiVersion": "odcs/v3.0.2",
            "id": "test-contract",
            "name": "Test Contract",
        }

        original_odcs_url = "https://example.com/contracts/test-contract.json"

        result = generate_odps_from_hubcontract(
            hub_contract,
            original_odcs_contract=original_odcs_contract,
            original_odcs_url=original_odcs_url,
        )

        # Verify spec is present (takes precedence)
        self.assertIn("product", result)
        self.assertIn("contract", result["product"])
        self.assertIn("spec", result["product"]["contract"])
        self.assertEqual(result["product"]["contract"]["spec"], original_odcs_contract)

        # Verify contractURL is not present (spec takes precedence)
        self.assertNotIn("contractURL", result["product"]["contract"])

    def test_contract_omitted_when_neither_provided(self):
        """
        Test that product.contract section is omitted when neither spec nor URL provided.

        Scenario: Generate ODPS without original_odcs_contract or original_odcs_url
        Expected: product.contract section is not present (optional in ODPS)
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        result = generate_odps_from_hubcontract(hub_contract)

        # Verify product exists
        self.assertIn("product", result)

        # Verify contract section is not present (optional)
        self.assertNotIn("contract", result["product"])

    def test_contract_with_only_spec(self):
        """
        Test contract generation with only spec (no URL).

        Scenario: Generate ODPS with only original_odcs_contract
        Expected: product.contract.spec is present, contractURL is not
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        original_odcs_contract = {
            "apiVersion": "odcs/v3.0.2",
            "id": "test-contract",
            "name": "Test Contract",
        }

        result = generate_odps_from_hubcontract(
            hub_contract, original_odcs_contract=original_odcs_contract
        )

        # Verify spec is present
        self.assertIn("product", result)
        self.assertIn("contract", result["product"])
        self.assertIn("spec", result["product"]["contract"])

        # Verify contractURL is not present
        self.assertNotIn("contractURL", result["product"]["contract"])

    def test_contract_with_only_url(self):
        """
        Test contract generation with only URL (no spec).

        Scenario: Generate ODPS with only original_odcs_url
        Expected: product.contract.contractURL is present, spec is not
        """
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        original_odcs_url = "https://example.com/contracts/test-contract.json"

        result = generate_odps_from_hubcontract(hub_contract, original_odcs_url=original_odcs_url)

        # Verify contractURL is present
        self.assertIn("product", result)
        self.assertIn("contract", result["product"])
        self.assertIn("contractURL", result["product"]["contract"])

        # Verify spec is not present
        self.assertNotIn("spec", result["product"]["contract"])


class ODPSGeneratorContractIntegrationTest(SimpleTestCase):
    """Integration tests for ODPS generator contract generation"""

    def test_contract_generation_with_complete_hubcontract(self):
        """
        Test contract generation with complete HubContract including all sections.

        Scenario: Generate ODPS with complete HubContract and original ODCS contract
        Expected: Complete ODPS document with product.contract.spec embedded
        """
        hub_contract = {
            "id": "complete-product",
            "info": {
                "name": "Complete Product",
                "description": "Complete product description",
                "version": "1.0.0",
                "tags": ["data", "analytics"],
                "owners": [{"name": "Data Team", "email": "data@example.com"}],
            },
            "schema": {
                "fields": [
                    {"name": "id", "data_type": "string"},
                    {"name": "name", "data_type": "string"},
                ]
            },
            "marketplace": {
                "license_summary": "MIT License",
                "intended_use": ["ANALYTICS"],
                "x_odps": {"pricing_plans": [{"name": "Basic", "price": 0}]},
            },
        }

        original_odcs_contract = {
            "apiVersion": "odcs/v3.0.2",
            "id": "complete-contract",
            "name": "Complete Contract",
            "version": "1.0.0",
            "schema": {"properties": {"id": {"type": "string"}, "name": {"type": "string"}}},
        }

        result = generate_odps_from_hubcontract(
            hub_contract, original_odcs_contract=original_odcs_contract
        )

        # Verify complete ODPS structure
        self.assertIn("schema", result)
        self.assertIn("version", result)
        self.assertIn("product", result)
        self.assertIn("details", result["product"])
        self.assertIn("contract", result["product"])
        self.assertIn("spec", result["product"]["contract"])
        self.assertIn("marketplace", result["product"])
        self.assertIn("license", result)

        # Verify contract spec is embedded
        self.assertEqual(result["product"]["contract"]["spec"], original_odcs_contract)

    def test_contract_generation_handles_unicode_characters(self):
        """Test that contract generation handles unicode characters correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "测试产品", "description": "测试描述"},
            "schema": {"fields": []},
        }

        original_odcs_contract = {
            "apiVersion": "odcs/v3.0.2",
            "id": "测试合同",
            "name": "测试合同名称",
            "version": "1.0.0",
            "schema": {"properties": {"id": {"type": "string"}}},
        }

        result = generate_odps_from_hubcontract(
            hub_contract, original_odcs_contract=original_odcs_contract
        )

        # Verify unicode characters are preserved
        self.assertIn("product", result)
        self.assertIn("contract", result["product"])
        self.assertIn("spec", result["product"]["contract"])
        spec = result["product"]["contract"]["spec"]
        self.assertEqual(spec["id"], "测试合同")
        self.assertEqual(spec["name"], "测试合同名称")

    def test_contract_generation_handles_special_characters(self):
        """Test that contract generation handles special characters correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test & Co. (Special)"},
            "schema": {"fields": []},
        }

        original_odcs_contract = {
            "apiVersion": "odcs/v3.0.2",
            "id": "test-contract",
            "name": "Test <Contract> & More",
            "version": "1.0.0",
            "schema": {"properties": {"id": {"type": "string"}}},
        }

        result = generate_odps_from_hubcontract(
            hub_contract, original_odcs_contract=original_odcs_contract
        )

        # Verify special characters are preserved
        self.assertIn("product", result)
        self.assertIn("contract", result["product"])
        self.assertIn("spec", result["product"]["contract"])
        spec = result["product"]["contract"]["spec"]
        self.assertEqual(spec["name"], "Test <Contract> & More")

    def test_contract_generation_handles_very_large_documents(self):
        """Test that contract generation handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product", "description": large_description},
            "schema": {"fields": []},
        }

        original_odcs_contract = {
            "apiVersion": "odcs/v3.0.2",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "description": large_description,
            "schema": {"properties": {"id": {"type": "string"}}},
        }

        # Valid data (large docs) must succeed
        result = generate_odps_from_hubcontract(
            hub_contract, original_odcs_contract=original_odcs_contract
        )
        self.assertIn("product", result)

    def test_contract_generation_handles_none_values(self):
        """Test that contract generation handles None values correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        original_odcs_contract = {
            "apiVersion": "odcs/v3.0.2",
            "id": "test-contract",
            "name": None,  # None value
            "version": "1.0.0",
            "schema": {"properties": {"id": {"type": "string"}}},
        }

        # Should handle None values gracefully
        result = generate_odps_from_hubcontract(
            hub_contract, original_odcs_contract=original_odcs_contract
        )
        self.assertIsNotNone(result)
        self.assertIn("product", result)

    def test_contract_generation_handles_nested_structures(self):
        """Test that contract generation handles nested structures correctly."""
        hub_contract = {
            "id": "test-product",
            "info": {"name": "Test Product"},
            "schema": {"fields": []},
        }

        original_odcs_contract = {
            "apiVersion": "odcs/v3.0.2",
            "id": "test-contract",
            "name": "Test Contract",
            "version": "1.0.0",
            "schema": {
                "properties": {
                    "id": {"type": "string"},
                    "nested": {
                        "type": "object",
                        "properties": {
                            "level1": {
                                "type": "object",
                                "properties": {
                                    "level2": {
                                        "type": "object",
                                        "properties": {"level3": {"type": "string"}},
                                    }
                                },
                            }
                        },
                    },
                }
            },
        }

        result = generate_odps_from_hubcontract(
            hub_contract, original_odcs_contract=original_odcs_contract
        )

        # Verify nested structure is preserved
        self.assertIn("product", result)
        self.assertIn("contract", result["product"])
        self.assertIn("spec", result["product"]["contract"])
        spec = result["product"]["contract"]["spec"]
        self.assertIn("schema", spec)
        self.assertIn("properties", spec["schema"])
        self.assertIn(
            "nested",
            spec["schema"]["properties"],
            "Nested schema structure must be preserved in contract spec",
        )
        nested = spec["schema"]["properties"]["nested"]
        self.assertIn("properties", nested)
        self.assertIn("level1", nested["properties"])
        self.assertIn(
            "level2",
            nested["properties"]["level1"]["properties"],
            "Nested structures should be preserved",
        )
