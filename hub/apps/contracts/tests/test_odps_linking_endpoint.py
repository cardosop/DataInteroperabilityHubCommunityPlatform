"""
Integration tests for ODPS linking endpoint (Task 3.5.2)

Tests verify:
1. POST /api/v1/contracts/{id}/link-odps/ endpoint
2. Accept ODPS document or ODPS contract ID
3. Validate link compatibility (ODPS product.contract must match ODCS)
4. Create bidirectional link relationship
5. Error handling for invalid inputs and mismatched contracts
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
from hub.apps.contracts.services import ContractService
from hub.apps.contracts.tests.test_base import ContractsAPITestBase


class ODPSLinkingEndpointIntegrationTest(ContractsAPITestBase):
    """Integration tests for ODPS linking endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create ODCS contract
        self.odcs_contract_json = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-odcs-contract",
                "name": "Test ODCS Contract",
                "version": "1.0.0",
                "description": "Test ODCS contract for linking",
                "schema": {
                    "fields": [
                        {
                            "name": "id",
                            "type": "string",
                            "nullable": False,
                            "description": "Unique identifier",
                        }
                    ]
                },
            },
            indent=2,
        )

        # Create ODCS contract using service
        self.odcs_contract = self.contract_service.create_contract(
            original_raw=self.odcs_contract_json,
            original_format=OriginalFormat.JSON,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODCS,
        )

        # Valid ODPS document with matching ODCS contract
        self.valid_odps_json = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-product-link",
                            "name": "Test Product for Linking",
                            "description": "A test product for linking to ODCS",
                            "productVersion": "1.0.0",
                        }
                    },
                    "contract": {
                        "spec": {
                            "apiVersion": "odcs.io/v3.0.2",
                            "kind": "DataContract",
                            "id": "test-odcs-contract",
                            "name": "Test ODCS Contract",
                            "version": "1.0.0",
                            "description": "Test ODCS contract for linking",
                            "schema": {
                                "fields": [
                                    {
                                        "name": "id",
                                        "type": "string",
                                        "nullable": False,
                                        "description": "Unique identifier",
                                    }
                                ]
                            },
                        }
                    },
                },
            },
            indent=2,
        )

    def test_link_odps_with_existing_odps_contract_id(self):
        """Test linking with existing ODPS contract ID"""
        # Create ODPS contract manually with normalized hub_contract_json
        # This ensures it's normalized but not already linked
        from hub.apps.contracts.models import ContractStatus, NormalizationStatus

        odps_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.odcs_contract.asset,
            version=self.odcs_contract.version,
            original_raw=self.valid_odps_json,
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "test-product-link",
                "info": {
                    "name": "Test Product for Linking",
                    "description": "A test product for linking to ODCS",
                    "version": "1.0.0",
                },
                "extensions": {
                    "x_odps": {
                        "contract": {
                            "hub_contract_version": "1.0.0",
                            "id": "test-odcs-contract",
                            "info": {
                                "name": "Test ODCS Contract",
                                "description": "Test ODCS contract for linking",
                                "version": "1.0.0",
                            },
                            "schema": {
                                "models": [
                                    {
                                        "name": "default",
                                        "fields": [
                                            {
                                                "name": "id",
                                                "type": "string",
                                                "nullable": False,
                                                "description": "Unique identifier",
                                            }
                                        ],
                                    }
                                ]
                            },
                        }
                    }
                },
            },
            hub_contract_version="1.0.0",
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            normalization_errors=[],
            normalization_warnings=[],
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Link ODPS to ODCS
        from django.urls import reverse

        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(url, {"odps_contract_id": str(odps_contract.id)}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(odps_contract.id))
        self.assertEqual(response.data["original_spec_type"], OriginalSpecType.ODPS)

        # Verify bidirectional links
        odps_contract.refresh_from_db()
        self.odcs_contract.refresh_from_db()

        self.assertIsNotNone(odps_contract.hub_contract_json)
        self.assertIsNotNone(self.odcs_contract.hub_contract_json)

        odps_extensions = odps_contract.hub_contract_json.get("extensions", {})
        odcs_extensions = self.odcs_contract.hub_contract_json.get("extensions", {})

        self.assertEqual(
            odps_extensions.get("x_odps", {}).get("odcs_link"), str(self.odcs_contract.id)
        )
        self.assertEqual(odcs_extensions.get("x_odps", {}).get("odps_link"), str(odps_contract.id))

    def test_link_odps_with_new_odps_document(self):
        """Test linking with new ODPS document"""
        from django.urls import reverse

        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url,
            {
                "original_raw": self.valid_odps_json,
                "original_format": "JSON",
                "resolve_external_refs": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["original_spec_type"], OriginalSpecType.ODPS)
        self.assertEqual(response.data["original_format"], OriginalFormat.JSON)

        # Verify ODPS contract was created and linked
        odps_contract_id = response.data["id"]
        odps_contract = Contract.objects.get(id=odps_contract_id)

        # Verify bidirectional links
        self.odcs_contract.refresh_from_db()

        self.assertIsNotNone(odps_contract.hub_contract_json)
        self.assertIsNotNone(self.odcs_contract.hub_contract_json)

        odps_extensions = odps_contract.hub_contract_json.get("extensions", {})
        odcs_extensions = self.odcs_contract.hub_contract_json.get("extensions", {})

        self.assertEqual(
            odps_extensions.get("x_odps", {}).get("odcs_link"), str(self.odcs_contract.id)
        )
        self.assertEqual(odcs_extensions.get("x_odps", {}).get("odps_link"), str(odps_contract.id))

    def test_link_odps_compatibility_validation_id_mismatch(self):
        """Test that linking fails when ODPS product.contract.id doesn't match ODCS contract.id"""
        # Create ODPS with mismatched contract ID
        mismatched_odps_json = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-product-mismatch",
                            "name": "Test Product Mismatch",
                        }
                    },
                    "contract": {
                        "spec": {
                            "apiVersion": "odcs.io/v3.0.2",
                            "kind": "DataContract",
                            "id": "different-odcs-contract-id",  # Mismatched ID
                            "name": "Test ODCS Contract",
                            "version": "1.0.0",
                            "schema": {"fields": [{"name": "id", "type": "string"}]},
                        }
                    },
                },
            },
            indent=2,
        )

        from django.urls import reverse

        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url,
            {
                "original_raw": mismatched_odps_json,
                "original_format": "JSON",
                "resolve_external_refs": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("CONTRACT_ID_MISMATCH", response.data.get("code", ""))

    def test_link_odps_compatibility_validation_name_mismatch(self):
        """Test that linking fails when ODPS product.contract.name doesn't match ODCS contract.name"""
        # Create ODPS with mismatched contract name
        mismatched_odps_json = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": "test-product-mismatch-name",
                            "name": "Test Product Mismatch Name",
                        }
                    },
                    "contract": {
                        "spec": {
                            "apiVersion": "odcs.io/v3.0.2",
                            "kind": "DataContract",
                            "id": "test-odcs-contract",
                            "name": "Different ODCS Contract Name",  # Mismatched name
                            "version": "1.0.0",
                            "schema": {"fields": [{"name": "id", "type": "string"}]},
                        }
                    },
                },
            },
            indent=2,
        )

        from django.urls import reverse

        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url,
            {
                "original_raw": mismatched_odps_json,
                "original_format": "JSON",
                "resolve_external_refs": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("CONTRACT_NAME_MISMATCH", response.data.get("code", ""))

    def test_link_odps_invalid_odcs_contract(self):
        """Test that linking fails when contract is not ODCS type"""
        # Create ODPS contract
        service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        odps_contract = service.create_contract(
            original_raw=self.valid_odps_json,
            original_format=OriginalFormat.JSON,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODPS,
        )

        # Try to link ODPS to ODPS (should fail)
        from django.urls import reverse

        url = reverse("contract-link-odps", kwargs={"id": str(odps_contract.id)})
        response = self.client.post(url, {"odps_contract_id": str(odps_contract.id)}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("INVALID_CONTRACT_TYPE", response.data.get("code", ""))

    def test_link_odps_missing_odps_contract_id(self):
        """Test that linking fails when ODPS contract ID doesn't exist"""
        from django.urls import reverse

        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url,
            {"odps_contract_id": "00000000-0000-0000-0000-000000000000"},  # Non-existent ID
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.data)

    def test_link_odps_missing_both_parameters(self):
        """Test that linking fails when neither odps_contract_id nor original_raw is provided"""
        from django.urls import reverse

        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(url, {}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_link_odps_both_parameters_provided(self):
        """Test that linking fails when both odps_contract_id and original_raw are provided"""
        # Create ODPS contract
        service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))
        odps_contract = service.create_contract(
            original_raw=self.valid_odps_json,
            original_format=OriginalFormat.JSON,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_spec_type=OriginalSpecType.ODPS,
        )

        from django.urls import reverse

        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url,
            {
                "odps_contract_id": str(odps_contract.id),
                "original_raw": self.valid_odps_json,
                "original_format": "JSON",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_link_odps_missing_original_format(self):
        """Test that linking fails when original_raw is provided without original_format"""
        from django.urls import reverse

        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url,
            {
                "original_raw": self.valid_odps_json
                # Missing original_format
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_link_odps_unauthenticated(self):
        """Test that linking fails without authentication"""
        self.client.force_authenticate(user=None)

        from django.urls import reverse

        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url, {"odps_contract_id": "00000000-0000-0000-0000-000000000000"}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_link_odps_yaml_format(self):
        """Test linking with YAML format ODPS document"""
        valid_odps_yaml = """
schema: https://opendataproducts.org/schema/v4.1
version: "4.1"
product:
  details:
    en:
      productID: test-product-yaml-link
      name: Test Product YAML Link
      description: A test product in YAML format for linking
      productVersion: "1.0.0"
  contract:
    spec:
      apiVersion: odcs.io/v3.0.2
      kind: DataContract
      id: test-odcs-contract
      name: Test ODCS Contract
      version: "1.0.0"
      description: Test ODCS contract for linking
      schema:
        fields:
          - name: id
            type: string
            nullable: false
            description: Unique identifier
"""

        from django.urls import reverse

        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url,
            {
                "original_raw": valid_odps_yaml,
                "original_format": "YAML",
                "resolve_external_refs": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["original_format"], OriginalFormat.YAML)

    def test_link_odps_resolve_external_refs_false(self):
        """Test linking with resolve_external_refs=False"""
        from django.urls import reverse

        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url,
            {
                "original_raw": self.valid_odps_json,
                "original_format": "JSON",
                "resolve_external_refs": False,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_linking_endpoint_handles_unicode_characters(self):
        """Test that linking endpoint handles unicode characters correctly."""
        from django.urls import reverse

        odps_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-unicode",
                        "name": "测试产品",
                        "description": "测试描述",
                    }
                },
                "contract": {"spec": json.loads(self.odcs_contract_json)},
            },
        }

        odps_json = json.dumps(odps_data)
        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url, {"original_raw": odps_json, "original_format": "JSON"}, format="json"
        )

        # Unicode characters in product details are valid; linking should succeed
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_linking_endpoint_handles_special_characters(self):
        """Test that linking endpoint handles special characters correctly."""
        from django.urls import reverse

        odps_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-special",
                        "name": "Test & Co. (Special)",
                        "description": "Test <description> & more",
                    }
                },
                "contract": {"spec": json.loads(self.odcs_contract_json)},
            },
        }

        odps_json = json.dumps(odps_data)
        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url, {"original_raw": odps_json, "original_format": "JSON"}, format="json"
        )

        # Special characters in product details are valid; linking should succeed
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_linking_endpoint_handles_very_large_documents(self):
        """Test that linking endpoint handles very large documents correctly."""
        from django.urls import reverse

        large_description = "A" * 100000  # 100KB string
        odps_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-large",
                        "name": "Test Product",
                        "description": large_description,
                    }
                },
                "contract": {"spec": json.loads(self.odcs_contract_json)},
            },
        }

        odps_json = json.dumps(odps_data)
        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url, {"original_raw": odps_json, "original_format": "JSON"}, format="json"
        )

        # Well-formed large documents must be accepted (200).  A 413
        # (payload too large) is an acceptable server-side limit; a 400
        # would indicate the payload is malformed, which it is not.
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_413_REQUEST_ENTITY_TOO_LARGE],
            f"Large well-formed document must return 200 or 413, got {response.status_code}",
        )

    def test_linking_endpoint_handles_none_values(self):
        """Test that linking endpoint handles None values correctly."""
        from django.urls import reverse

        odps_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-none",
                        "name": "Test Product",
                        "description": None,  # None value
                    }
                },
                "contract": {"spec": json.loads(self.odcs_contract_json)},
            },
        }

        odps_json = json.dumps(odps_data)
        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url, {"original_raw": odps_json, "original_format": "JSON"}, format="json"
        )

        # None description is valid (optional field); linking should succeed
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_linking_endpoint_handles_nested_structures(self):
        """Test that linking endpoint handles nested structures correctly."""
        from django.urls import reverse

        odps_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-nested",
                        "name": "Test Product",
                        "nested": {"level1": {"level2": {"level3": {"value": "deep"}}}},
                    }
                },
                "contract": {"spec": json.loads(self.odcs_contract_json)},
            },
        }

        odps_json = json.dumps(odps_data)
        url = reverse("contract-link-odps", kwargs={"id": str(self.odcs_contract.id)})
        response = self.client.post(
            url, {"original_raw": odps_json, "original_format": "JSON"}, format="json"
        )

        # Extra nested fields in product details are ignored; linking should succeed
        self.assertEqual(response.status_code, status.HTTP_200_OK)
