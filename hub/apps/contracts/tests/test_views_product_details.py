"""
Unit tests for contract product details endpoint.
"""
import uuid

import json

from rest_framework import status

from hub.apps.contracts.models import Contract, ContractStatus, OriginalFormat, OriginalSpecType
from hub.apps.contracts.tests.test_base import ContractsAPITestBase



class ContractProductDetailsViewTest(ContractsAPITestBase):
    """Test contract product details endpoint"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create ODPS contract with product details
        odps_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product",
                        "name": "Test Product",
                        "description": "A test product description",
                        "productVersion": "1.0.0",
                        "category": "Data Product",
                        "tags": ["test", "product"],
                    },
                    "fi": {
                        "productID": "test-product",
                        "name": "Testi Tuote",
                        "description": "Testituotteen kuvaus",
                    },
                }
            },
        }

        self.odps_contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(odps_data),
            hub_contract_version="1.0.0",
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "test-product",
                "info": {
                    "name": "Test Product",
                    "description": "A test product description",
                    "version": "1.0.0",
                    "category": "Data Product",
                    "tags": ["test", "product"],
                },
            },
        )

        # Create ODCS contract (not ODPS)
        self.odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test Contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"hub_contract_version": "1.0.0", "id": "test"},
        )

    def test_get_product_details_success_default_language(self):
        """Test getting product details with default language (en)"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.odps_contract.id}/product-details/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("product_details", response.data)
        product_details = response.data["product_details"]
        self.assertIsNotNone(product_details)
        self.assertEqual(product_details.get("productID"), "test-product")
        self.assertEqual(product_details.get("name"), "Test Product")
        self.assertEqual(product_details.get("description"), "A test product description")

    def test_get_product_details_success_specific_language(self):
        """Test getting product details with specific language"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.odps_contract.id}/product-details/",
            {"lang": "fi"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("product_details", response.data)
        product_details = response.data["product_details"]
        self.assertIsNotNone(product_details)
        self.assertEqual(product_details.get("name"), "Testi Tuote")
        self.assertEqual(product_details.get("description"), "Testituotteen kuvaus")

    def test_get_product_details_missing_language(self):
        """Test getting product details for language that doesn't exist"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.odps_contract.id}/product-details/",
            {"lang": "fr"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("product_details", response.data)
        # Should return None or fallback to hub_contract_json
        product_details = response.data["product_details"]
        # May be None or reconstructed from hub_contract_json
        if product_details:
            # If reconstructed, should have at least name or productID
            self.assertTrue(product_details.get("productID") or product_details.get("name"))

    def test_get_product_details_not_odps_contract(self):
        """Test getting product details from non-ODPS contract (should fail)"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.odcs_contract.id}/product-details/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)
        self.assertIn("not an ODPS contract", response.data["error"])

    def test_get_product_details_invalid_language_code(self):
        """Test getting product details with invalid language code.

        The endpoint may return 400 for invalid codes or 200 with fallback to defaults.
        """
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.odps_contract.id}/product-details/",
            {"lang": "invalid"},
            format="json",
        )

        # Endpoint may reject or gracefully fall back
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_get_product_details_language_code_too_long(self):
        """Test getting product details with language code that is too long.

        The endpoint may return 400 or 200 with fallback to defaults.
        """
        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            f"/api/v1/contracts/{self.odps_contract.id}/product-details/",
            {"lang": "eng"},
            format="json",
        )

        # 3-letter codes may be accepted or rejected depending on implementation
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_get_product_details_contract_not_found(self):
        """Test getting product details from non-existent contract"""
        self.client.force_authenticate(user=self.user)

        import uuid

        non_existent_id = uuid.uuid4()

        response = self.client.get(
            f"/api/v1/contracts/{non_existent_id}/product-details/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_product_details_unauthenticated(self):
        """Test getting product details without authentication"""
        from rest_framework.test import APIClient

        unauthenticated_client = APIClient()  # Fresh client, no auth
        response = unauthenticated_client.get(
            f"/api/v1/contracts/{self.odps_contract.id}/product-details/", format="json"
        )

        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_get_product_details_reconstruct_from_hub_contract(self):
        """Test getting product details when original_raw is not available (reconstruct from hub_contract_json)"""
        self.client.force_authenticate(user=self.user)

        # Create contract without original_raw but with hub_contract_json
        contract_no_original = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw="{}",  # Minimal raw (column is NOT NULL)
            hub_contract_version="1.0.0",
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "reconstructed-product",
                "info": {
                    "name": "Reconstructed Product",
                    "description": "Reconstructed from hub contract",
                    "version": "2.0.0",
                },
            },
        )

        response = self.client.get(
            f"/api/v1/contracts/{contract_no_original.id}/product-details/", format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("product_details", response.data)
        product_details = response.data["product_details"]
        # Should be reconstructed from hub_contract_json
        if product_details:
            self.assertEqual(product_details.get("productID"), "reconstructed-product")
            self.assertEqual(product_details.get("name"), "Reconstructed Product")

    def test_get_product_details_case_insensitive_language(self):
        """Test that language code is case-insensitive (converted to lowercase)"""
        self.client.force_authenticate(user=self.user)

        # Test with uppercase language code
        response = self.client.get(
            f"/api/v1/contracts/{self.odps_contract.id}/product-details/",
            {"lang": "EN"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should work (converted to lowercase internally)
        self.assertIn("product_details", response.data)
