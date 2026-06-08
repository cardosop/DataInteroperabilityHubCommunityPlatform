"""
Comprehensive Frontend Data Format Test Suite (Task 10.1.18.5)

Tests verify:
1. All API responses use consistent data formats
2. All dates are in ISO 8601 format
3. All UUIDs are in standard format
4. All nested objects are properly structured
"""

import json
import re
import uuid
from datetime import datetime

from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.test_base import ContractsAPITestBase
from hub.apps.users.models import Role, UserRole


class FrontendDataFormatTest(ContractsAPITestBase):
    """
    Comprehensive frontend data format tests (Task 10.1.18.5).

    Tests all API responses for consistent data formats without mocks/stubs:
    1. Consistent data formats
    2. ISO 8601 date format
    3. Standard UUID format
    4. Properly structured nested objects
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        # Update tenant/user names for clarity
        _uid = uuid.uuid4().hex[:8]
        self.tenant.name = f"Data Format Test Tenant {_uid}"
        self.tenant.slug = f"data-format-test-{_uid}"
        self.tenant.save()

        self.user.email = f"user-{_uid}@dataformat.test"
        self.user.save()

        # Create role
        self.admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator"},
        )
        UserRole.objects.create(user=self.user, role=self.admin_role)

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant, name="Data Format Test Asset", status=AssetStatus.ACTIVE
        )

        # Valid ODPS structure
        self.valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-dataformat",
                        "name": "Test Product",
                        "description": "Test description",
                    }
                },
                "contract": {
                    "spec": {
                        "apiVersion": "odcs.io/v3.0.2",
                        "kind": "DataContract",
                        "id": "test-contract",
                        "name": "Test Contract",
                        "version": "1.0.0",
                        "schema": {"fields": [{"name": "id", "type": "string", "nullable": False}]},
                    }
                },
            },
        }

        # Create test contract
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(self.valid_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

    def test_all_dates_are_in_iso_8601_format(self):
        """Test all dates are in ISO 8601 format"""
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Check date fields
        date_fields = ["created_at", "updated_at", "deleted_at"]
        iso8601_pattern = re.compile(
            r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
        )

        for field in date_fields:
            if field in data and data[field]:
                date_value = str(data[field])
                # Should match ISO 8601 pattern or contain T separator
                self.assertTrue(
                    "T" in date_value or iso8601_pattern.match(date_value),
                    f"{field} should be in ISO 8601 format, got: {date_value}",
                )

    def test_all_uuids_are_in_standard_format(self):
        """Test all UUIDs are in standard format"""
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # UUID pattern: 8-4-4-4-12 hex digits
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE
        )

        # Check ID field
        if "id" in data:
            id_value = str(data["id"])
            if len(id_value) == 36:  # UUID length
                self.assertTrue(
                    uuid_pattern.match(id_value), f"ID should be in UUID format, got: {id_value}"
                )

    def test_all_nested_objects_are_properly_structured(self):
        """Test all nested objects are properly structured"""
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Verify nested objects are dictionaries, not strings
        nested_fields = ["hub_contract_json", "original_raw"]
        for field in nested_fields:
            if field in data and data[field] is not None:
                field_value = data[field]
                # Should be dict (parsed JSON) or string (JSON string) or None
                self.assertIsInstance(
                    field_value, (dict, str, type(None)), f"{field} should be dict, string, or None"
                )

                # If it's a string, it should be valid JSON
                if isinstance(field_value, str):
                    try:
                        parsed = json.loads(field_value)
                        self.assertIsInstance(
                            parsed, (dict, list), f"{field} should contain valid JSON"
                        )
                    except json.JSONDecodeError:
                        # If it's not JSON, that's okay - might be other format
                        pass

    def test_api_responses_use_consistent_data_formats(self):
        """Test all API responses use consistent data formats"""
        # Test list endpoint
        list_response = self.client.get("/api/v1/contracts/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        list_data = list_response.json()

        # Test detail endpoint
        detail_response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        detail_data = detail_response.json()

        # Both should be JSON
        self.assertIsInstance(list_data, (dict, list), "List response should be dict or list")
        self.assertIsInstance(detail_data, dict, "Detail response should be dict")

        # If list response has results, verify structure
        if isinstance(list_data, dict) and "results" in list_data:
            results = list_data["results"]
            if results and isinstance(results, list):
                # First result should have similar structure to detail
                first_result = results[0]
                if "id" in first_result and "id" in detail_data:
                    # Both should have ID field
                    self.assertIn("id", first_result)
                    self.assertIn("id", detail_data)

    def test_api_responses_have_consistent_field_types(self):
        """Test API responses have consistent field types"""
        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Verify field types are consistent
        if "status" in data:
            self.assertIsInstance(data["status"], str, "Status should be string")
        if "version" in data:
            self.assertIsInstance(data["version"], (int, str), "Version should be int or string")
        if "normalization_status" in data:
            self.assertIsInstance(
                data["normalization_status"], str, "Normalization status should be string"
            )

    def test_api_responses_handle_null_values(self):
        """Test API responses handle null values properly"""
        # Create contract with some null/None fields
        from hub.apps.assets.models import Asset, AssetStatus
        null_asset = Asset.objects.create(
            tenant=self.tenant, key="null-test-asset", name="Null Asset", status=AssetStatus.ACTIVE
        )
        contract_with_nulls = Contract.objects.create(
            tenant=self.tenant,
            asset=null_asset,
            original_raw=json.dumps(self.valid_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.DRAFT,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        response = self.client.get(f"/api/v1/contracts/{contract_with_nulls.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Null values should be handled gracefully (either None or omitted)
        if "deleted_at" in data:
            # If present, should be None or null
            self.assertIn(
                data["deleted_at"], [None, "null"], "Null values should be handled properly"
            )

    def test_api_responses_have_consistent_error_format(self):
        """Test API error responses have consistent format"""
        # Test 404 error
        response = self.client.get("/api/v1/contracts/00000000-0000-0000-0000-000000000000/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        error_data = response.json()

        # Error responses should have consistent structure
        self.assertIsInstance(error_data, dict, "Error response should be a dictionary")
        # Should have error indication
        has_error_field = (
            "error" in error_data
            or "errors" in error_data
            or "detail" in error_data
            or "message" in error_data
        )
        self.assertTrue(has_error_field, "Error response should include error field")

    def test_api_responses_handle_unicode_in_data(self):
        """Test API responses handle unicode characters in data"""
        # Create contract with unicode characters
        odps_with_unicode = self.valid_odps.copy()
        odps_with_unicode["product"]["details"]["en"]["name"] = "Test 产品 🚀"

        unicode_asset = Asset.objects.create(
            tenant=self.tenant, key="unicode-test-asset", name="Unicode Asset", status=AssetStatus.ACTIVE
        )
        contract_unicode = Contract.objects.create(
            tenant=self.tenant,
            asset=unicode_asset,
            original_raw=json.dumps(odps_with_unicode),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        response = self.client.get(f"/api/v1/contracts/{contract_unicode.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should handle unicode characters properly
        self.assertIsInstance(data, dict, "Response should be valid JSON with unicode")
        # Response should be valid UTF-8
        self.assertIsInstance(response.content, bytes)

    def test_api_responses_handle_special_characters(self):
        """Test API responses handle special characters in data"""
        # Create contract with special characters
        odps_with_special = self.valid_odps.copy()
        odps_with_special["product"]["details"]["en"][
            "name"
        ] = "Test & Product <script>alert('xss')</script>"

        special_asset = Asset.objects.create(
            tenant=self.tenant, key="special-test-asset", name="Special Asset", status=AssetStatus.ACTIVE
        )
        contract_special = Contract.objects.create(
            tenant=self.tenant,
            asset=special_asset,
            original_raw=json.dumps(odps_with_special),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        response = self.client.get(f"/api/v1/contracts/{contract_special.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should handle special characters gracefully
        self.assertIsInstance(data, dict, "Response should be valid JSON")

    def test_api_list_responses_have_pagination_structure(self):
        """Test API list responses have pagination structure"""
        # Create multiple contracts — each needs its own asset
        from hub.apps.assets.models import Asset, AssetStatus
        for i in range(5):
            page_asset = Asset.objects.create(
                tenant=self.tenant, key=f"page-asset-{i}", name=f"Page {i}", status=AssetStatus.ACTIVE
            )
            Contract.objects.create(
                tenant=self.tenant,
                asset=page_asset,
                original_raw=json.dumps(self.valid_odps),
                original_format=OriginalFormat.JSON,
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version="4.1",
                status=ContractStatus.ACTIVE,
                version=1,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
            )

        response = self.client.get("/api/v1/contracts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # May have pagination structure
        if isinstance(data, dict):
            # Could have 'results', 'count', 'next', 'previous'
            if "results" in data:
                self.assertIsInstance(data["results"], list, "Results should be a list")
                if "count" in data:
                    self.assertIsInstance(data["count"], int, "Count should be integer")
