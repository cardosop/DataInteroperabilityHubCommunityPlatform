"""
Integration tests for ODPS generation endpoint (Task 3.5.3)

Comprehensive integration tests for POST /api/v1/contracts/{id}/generate-odps/ endpoint:
1. Success scenarios (generate ODPS from HubContract)
2. Error scenarios (missing hub_contract_json, invalid parameters)
3. Edge cases (different ODPS versions, output formats, ODCS embedding)
4. Multi-tenant isolation
5. Permission checks

Tests use real implementations (no mocks/stubs) and follow TDD principles.
"""

import json

from rest_framework import status

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
from hub.apps.contracts.tests.test_base import ContractsAPITestBase
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import UserStatus
from tests.fixtures.test_data_factories import TenantFactory, UserFactory


class ODPSGenerationEndpointIntegrationTest(ContractsAPITestBase):
    """Integration tests for ODPS generation endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create ODCS contract with HubContract (for ODPS generation)
        self.odcs_contract_raw = json.dumps(
            {
                "apiVersion": "odcs/v3",
                "kind": "DataContract",
                "id": "test-contract-odcs",
                "name": "Test ODCS Contract",
                "description": "Test contract for ODPS generation",
                "schema": {
                    "fields": [
                        {"name": "id", "type": "string", "description": "Unique identifier"},
                        {"name": "name", "type": "string", "description": "Name field"},
                    ]
                },
            }
        )

        self.hub_contract_json = {
            "hub_contract_version": "1.0.0",
            "id": "test-contract-odcs",
            "info": {
                "name": "Test ODCS Contract",
                "description": "Test contract for ODPS generation",
                "version": "1.0.0",
                "owners": [{"name": "John Doe", "email": "john@example.com"}],
                "tags": ["test", "integration"],
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "description": "Unique identifier"},
                    {"name": "name", "type": "string", "description": "Name field"},
                ]
            },
            "marketplace": {
                "license_summary": "MIT License",
                "intended_use": ["analytics", "reporting"],
                "restricted_use": ["resale"],
                "x_odps": {
                    "pricing_plans": [
                        {"planID": "basic", "name": "Basic Plan", "price": 9.99, "currency": "USD"},
                    ],
                    "access_methods": {
                        "api": {"type": "REST API", "endpoint": "https://api.example.com/v1"},
                    },
                },
            },
        }

        # Use factory to create contract (ensures proper setup)
        self.odcs_contract = ContractFactoryEnhanced.create_contract(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            hub_contract_json=self.hub_contract_json,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            name="Test ODCS Contract",
        )

        # Override original_raw with our test data
        self.odcs_contract.original_raw = self.odcs_contract_raw
        self.odcs_contract.save(update_fields=["original_raw"])

        # Refresh contract from DB to ensure all fields are loaded
        self.odcs_contract.refresh_from_db()

        # Create contract without hub_contract_json (for error testing)
        self.contract_no_hub = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw=self.odcs_contract_raw,
            normalization_status=NormalizationStatus.NOT_NORMALIZED,
            status=ContractStatus.DRAFT,
        )

    # ========== SUCCESS SCENARIOS ==========

    def test_generate_odps_success_default_params(self):
        """Test successful ODPS generation with default parameters"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{self.odcs_contract.id}/generate-odps/", {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("odps_document", response.data)
        self.assertIn("target_version", response.data)
        self.assertIn("output_format", response.data)

        # Verify ODPS document structure
        odps_doc = response.data["odps_document"]
        self.assertEqual(odps_doc["version"], "4.1")
        self.assertIn("product", odps_doc)
        self.assertIn("details", odps_doc["product"])
        self.assertIn("en", odps_doc["product"]["details"])

        # Verify product details
        product_details = odps_doc["product"]["details"]["en"]
        self.assertEqual(product_details["productID"], "test-contract-odcs")
        self.assertEqual(product_details["name"], "Test ODCS Contract")
        self.assertEqual(product_details["description"], "Test contract for ODPS generation")

        # Verify marketplace section
        self.assertIn("marketplace", odps_doc["product"])
        marketplace = odps_doc["product"]["marketplace"]
        self.assertIn("pricingPlans", marketplace)
        self.assertIn("accessMethods", marketplace)

        # Verify license section
        self.assertIn("license", odps_doc)
        license_en = odps_doc["license"]["en"]
        self.assertEqual(license_en["definition"], "MIT License")
        self.assertIn("rights", license_en)
        self.assertIn("restrictions", license_en)

    def test_generate_odps_success_custom_version(self):
        """Test successful ODPS generation with custom target version"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{self.odcs_contract.id}/generate-odps/",
            {"target_version": "4.0"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        odps_doc = response.data["odps_document"]
        self.assertEqual(odps_doc["version"], "4.0")
        self.assertEqual(response.data["target_version"], "4.0")

    def test_generate_odps_success_yaml_output(self):
        """Test successful ODPS generation with YAML output format"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{self.odcs_contract.id}/generate-odps/",
            {"output_format": "yaml"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("odps_document", response.data)
        self.assertIn("odps_content", response.data)  # YAML string
        self.assertEqual(response.data["output_format"], "yaml")
        self.assertIsInstance(response.data["odps_content"], str)

    def test_generate_odps_success_with_odcs_embedding(self):
        """Test successful ODPS generation with ODCS contract embedding"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{self.odcs_contract.id}/generate-odps/",
            {"embed_odcs": True},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        odps_doc = response.data["odps_document"]

        # Verify ODCS contract is embedded
        self.assertIn("product", odps_doc)
        self.assertIn("contract", odps_doc["product"])
        self.assertIn("spec", odps_doc["product"]["contract"])

        # Verify embedded ODCS contract structure
        embedded_odcs = odps_doc["product"]["contract"]["spec"]
        self.assertEqual(embedded_odcs["apiVersion"], "odcs/v3")
        self.assertEqual(embedded_odcs["kind"], "DataContract")
        self.assertEqual(embedded_odcs["id"], "test-contract-odcs")

    def test_generate_odps_success_without_odcs_embedding(self):
        """Test successful ODPS generation without ODCS contract embedding"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{self.odcs_contract.id}/generate-odps/",
            {"embed_odcs": False},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        odps_doc = response.data["odps_document"]

        # Verify ODCS contract is NOT embedded
        if "product" in odps_doc and "contract" in odps_doc["product"]:
            # If contract section exists, it should not have spec
            self.assertNotIn("spec", odps_doc["product"]["contract"])

    def test_generate_odps_success_minimal_hubcontract(self):
        """Test successful ODPS generation from minimal HubContract (only required fields)"""
        minimal_hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "minimal-contract",
            "info": {
                "name": "Minimal Contract",
            },
            "schema": {
                "fields": [],
            },
        }

        minimal_contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "minimal"}',
            hub_contract_version="1.0.0",
            hub_contract_json=minimal_hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{minimal_contract.id}/generate-odps/", {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        odps_doc = response.data["odps_document"]
        self.assertIn("product", odps_doc)
        self.assertIn("details", odps_doc["product"])
        self.assertIn("en", odps_doc["product"]["details"])

        # Verify minimal product details
        product_details = odps_doc["product"]["details"]["en"]
        self.assertEqual(product_details["productID"], "minimal-contract")
        self.assertEqual(product_details["name"], "Minimal Contract")

    # ========== ERROR SCENARIOS ==========

    def test_generate_odps_error_no_hub_contract_json(self):
        """Test error when contract has no hub_contract_json"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{self.contract_no_hub.id}/generate-odps/", {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("hub_contract_json", response.data["error"])

    def test_generate_odps_error_invalid_target_version(self):
        """Test error when target_version is invalid"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{self.odcs_contract.id}/generate-odps/",
            {"target_version": ""},  # Empty string
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("target_version", response.data["error"])

    def test_generate_odps_error_invalid_output_format(self):
        """Test error when output_format is invalid"""
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{self.odcs_contract.id}/generate-odps/",
            {"output_format": "xml"},  # Invalid format
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("output_format", response.data["error"])

    def test_generate_odps_error_contract_not_found(self):
        """Test error when contract does not exist"""
        import uuid

        non_existent_id = uuid.uuid4()

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{non_existent_id}/generate-odps/", {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_generate_odps_error_invalid_hub_contract_structure(self):
        """Test error when hub_contract_json has invalid structure"""
        invalid_hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "invalid-contract",
            # Missing required 'info' section
        }

        invalid_contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "invalid"}',
            hub_contract_version="1.0.0",
            hub_contract_json=invalid_hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{invalid_contract.id}/generate-odps/", {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("error_code", response.data)

    # ========== MULTI-TENANT ISOLATION ==========

    def test_generate_odps_tenant_isolation(self):
        """Test that users can only generate ODPS for contracts in their tenant"""
        # Create another tenant and user
        other_tenant = TenantFactory.create_tenant(
            name="Other Tenant",
            slug=f"other-tenant-{id(self)}",
            status=TenantStatus.ACTIVE.value,
            kyc_status=KYCStatus.VERIFIED.value,
        )
        ensure_tenant_has_active_subscription(other_tenant)
        other_user = UserFactory.create_user(
            email="other@example.com",
            tenant=other_tenant,
            status=UserStatus.ACTIVE.value,
        )

        # Try to generate ODPS for contract in different tenant
        self.client.force_authenticate(user=other_user)
        response = self.client.post(
            f"/api/v1/contracts/{self.odcs_contract.id}/generate-odps/", {}, format="json"
        )

        # Should return 404 (contract not found in user's tenant)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ========== PERMISSION CHECKS ==========

    def test_generate_odps_unauthenticated(self):
        """Test that unauthenticated users cannot generate ODPS"""
        # Explicitly clear authentication
        self.client.force_authenticate(user=None)
        response = self.client.post(
            f"/api/v1/contracts/{self.odcs_contract.id}/generate-odps/", {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== EDGE CASES ==========

    def test_generate_odps_with_all_marketplace_fields(self):
        """Test ODPS generation with all marketplace fields populated"""
        comprehensive_hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "comprehensive-contract",
            "info": {
                "name": "Comprehensive Contract",
                "description": "Contract with all marketplace fields",
                "version": "2.0.0",
                "owners": [
                    {"name": "Owner 1", "email": "owner1@example.com"},
                    {"name": "Owner 2", "email": "owner2@example.com"},
                ],
                "tags": ["tag1", "tag2", "tag3"],
            },
            "schema": {"fields": []},
            "marketplace": {
                "license_summary": "Apache 2.0 License",
                "intended_use": ["analytics", "reporting", "machine-learning"],
                "restricted_use": ["resale", "redistribution"],
                "x_odps": {
                    "pricing_plans": [
                        {"planID": "free", "name": "Free Plan", "price": 0, "currency": "USD"},
                        {"planID": "pro", "name": "Pro Plan", "price": 99.99, "currency": "USD"},
                    ],
                    "access_methods": {
                        "api": {"type": "REST API", "endpoint": "https://api.example.com/v1"},
                        "download": {"type": "File Download", "format": "CSV"},
                    },
                    "payment_gateways": {
                        "stripe": {"enabled": True, "publicKey": "pk_test_123"},
                    },
                },
            },
            "quality": {
                "default_profile_key": "intake_basic",
                "rules": [
                    {
                        "rule_id": "completeness_rule",
                        "dimension": "completeness",
                        "name": "Completeness Check",
                        "expression": ">= 0.95 percentage",
                    }
                ],
            },
            "lifecycle": {
                "slas": {"availability": 99.9, "latency_ms_p95": 100},
                "x_odps": {
                    "status": "active",
                    "sla_dimensions": [
                        {"name": "availability", "data": {"target": 99.9}},
                        {"name": "latency", "data": {"target": 100}},
                    ],
                },
            },
        }

        comprehensive_contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "comprehensive"}',
            hub_contract_version="1.0.0",
            hub_contract_json=comprehensive_hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{comprehensive_contract.id}/generate-odps/", {}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        odps_doc = response.data["odps_document"]

        # Verify all marketplace sections are present
        self.assertIn("product", odps_doc)
        self.assertIn("marketplace", odps_doc["product"])
        marketplace = odps_doc["product"]["marketplace"]

        # Verify pricing plans
        self.assertIn("pricingPlans", marketplace)
        self.assertEqual(len(marketplace["pricingPlans"]), 2)

        # Verify access methods
        self.assertIn("accessMethods", marketplace)
        self.assertIn("api", marketplace["accessMethods"])
        self.assertIn("download", marketplace["accessMethods"])

        # Verify payment gateways (ODPS 4.1+)
        self.assertIn("paymentGateways", marketplace)
        self.assertIn("stripe", marketplace["paymentGateways"])

        # Verify license
        self.assertIn("license", odps_doc)
        license_en = odps_doc["license"]["en"]
        self.assertEqual(license_en["definition"], "Apache 2.0 License")
        self.assertEqual(len(license_en["rights"]), 3)
        self.assertEqual(len(license_en["restrictions"]), 2)

        # Verify data quality
        self.assertIn("dataQuality", odps_doc["product"])
        data_quality = odps_doc["product"]["dataQuality"]
        self.assertIn("declarative", data_quality)
        self.assertEqual(data_quality["declarative"]["default"], "intake_basic")

        # Verify SLA
        self.assertIn("SLA", odps_doc["product"])
        sla = odps_doc["product"]["SLA"]
        self.assertIn("declarative", sla)
        self.assertIn("dimensions", sla["declarative"])

        # Verify data holder
        self.assertIn("dataHolder", odps_doc)
        data_holder = odps_doc["dataHolder"]["en"]
        self.assertEqual(data_holder["legalName"], "Owner 1")
        self.assertEqual(data_holder["email"], "owner1@example.com")

        # Verify product details
        product_details = odps_doc["product"]["details"]["en"]
        self.assertEqual(product_details["productVersion"], "2.0.0")
        self.assertEqual(len(product_details["tags"]), 3)
        self.assertEqual(product_details["status"], "active")

    def test_endpoint_handles_unicode_characters(self):
        """Test that endpoint handles unicode characters correctly."""
        unicode_hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-unicode",
            "info": {"name": "测试产品", "description": "测试描述"},
            "schema": {"fields": [{"name": "字段名称", "data_type": "string"}]},
        }

        unicode_contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test-unicode"}',
            hub_contract_version="1.0.0",
            hub_contract_json=unicode_hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{unicode_contract.id}/generate-odps/", {}, format="json"
        )

        # Should handle unicode characters
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("odps_document", response.data)

    def test_endpoint_handles_special_characters(self):
        """Test that endpoint handles special characters correctly."""
        special_hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-special",
            "info": {"name": "Test & Co. (Special)", "description": "Test <description> & more"},
            "schema": {"fields": [{"name": "field-name", "data_type": "string"}]},
        }

        special_contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test-special"}',
            hub_contract_version="1.0.0",
            hub_contract_json=special_hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{special_contract.id}/generate-odps/", {}, format="json"
        )

        # Should handle special characters
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("odps_document", response.data)

    def test_endpoint_handles_very_large_documents(self):
        """Test that endpoint handles very large documents correctly."""
        large_description = "A" * 100000  # 100KB string
        large_hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-large",
            "info": {"name": "Test Product", "description": large_description},
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        large_contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test-large"}',
            hub_contract_version="1.0.0",
            hub_contract_json=large_hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{large_contract.id}/generate-odps/", {}, format="json"
        )

        # Should handle very large documents
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_endpoint_handles_none_values(self):
        """Test that endpoint handles None values correctly."""
        none_hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-none",
            "info": {"name": "Test Product", "description": None},  # None value
            "schema": {"fields": [{"name": "id", "data_type": "string"}]},
        }

        none_contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test-none"}',
            hub_contract_version="1.0.0",
            hub_contract_json=none_hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{none_contract.id}/generate-odps/", {}, format="json"
        )

        # Should handle None values gracefully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_endpoint_handles_nested_structures(self):
        """Test that endpoint handles nested structures correctly."""
        nested_hub_contract = {
            "hub_contract_version": "1.0.0",
            "id": "test-nested",
            "info": {
                "name": "Test Product",
                "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
            },
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "data_type": "string",
                        "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                    }
                ]
            },
        }

        nested_contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test-nested"}',
            hub_contract_version="1.0.0",
            hub_contract_json=nested_hub_contract,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            f"/api/v1/contracts/{nested_contract.id}/generate-odps/", {}, format="json"
        )

        # Should handle nested structures
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("odps_document", response.data)
