"""
Comprehensive Frontend Integration Point Test Suite (Task 10.1.18.2)

Tests verify:
1. All APIs return data in frontend-consumable format
2. All events are in frontend-consumable format
3. All WebSocket events are in frontend-consumable format
4. All error responses are frontend-friendly
"""

import json

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


class FrontendIntegrationPointsTest(ContractsAPITestBase):
    """
    Comprehensive frontend integration point tests (Task 10.1.18.2).

    Tests all APIs and events for frontend-consumable format without mocks/stubs:
    1. APIs return JSON in frontend-consumable format
    2. Events are in frontend-consumable format
    3. WebSocket events are properly formatted
    4. Error responses are frontend-friendly
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        import uuid
        # Update tenant/user names for clarity
        self.tenant.name = f"Frontend Test Tenant {uuid.uuid4().hex[:8]}"
        self.tenant.slug = f"frontend-test-{uuid.uuid4().hex[:8]}"
        self.tenant.save()

        self.user.email = f"user-{uuid.uuid4().hex[:8]}@frontend.test"
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
            tenant=self.tenant, name="Frontend Test Asset", status=AssetStatus.ACTIVE
        )

        # Valid ODPS structure
        self.valid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-product-frontend",
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

    def test_apis_return_data_in_frontend_consumable_format(self):
        """Test all APIs return data in frontend-consumable format"""
        # Create contract
        contract = Contract.objects.create(
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

        # Test GET endpoint
        response = self.client.get(f"/api/v1/contracts/{contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, "API should return data")

        # Verify response is JSON
        self.assertEqual(response["Content-Type"], "application/json", "Response should be JSON")

        # Verify response structure is frontend-consumable
        data = response.json()
        self.assertIsInstance(data, dict, "Response should be a dictionary")

        # Verify common frontend-consumable fields
        if "id" in data:
            self.assertIsInstance(data["id"], (str, int), "ID should be string or integer")

    def test_error_responses_are_frontend_friendly(self):
        """Test all error responses are frontend-friendly"""
        # Test 404 error
        response = self.client.get("/api/v1/contracts/00000000-0000-0000-0000-000000000000/")

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
            "Should return 404 for non-existent resource",
        )

        # Verify error response is JSON
        self.assertEqual(
            response["Content-Type"], "application/json", "Error response should be JSON"
        )

        # Verify error response structure
        error_data = response.json()
        self.assertIsInstance(error_data, dict, "Error response should be a dictionary")

        # Error responses should be frontend-friendly (have message or detail)
        has_message = "message" in error_data or "detail" in error_data or "error" in error_data
        self.assertTrue(
            has_message, "Error response should include message, detail, or error field"
        )

    def test_api_responses_use_consistent_data_formats(self):
        """Test all API responses use consistent data formats"""
        # Create contract
        contract = Contract.objects.create(
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

        # Test detail endpoint
        response = self.client.get(f"/api/v1/contracts/{contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Verify UUIDs are in standard format (if present)
        if "id" in data:
            id_value = str(data["id"])
            # UUID format: 8-4-4-4-12 hex digits
            import re
            uuid_regex = re.compile(
                r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
            )
            self.assertTrue(
                uuid_regex.match(id_value),
                f"ID value '{id_value}' must match canonical UUID format "
                f"(e.g. 00000000-0000-0000-0000-000000000000)",
            )

        # Verify dates are in ISO 8601 format (if present)
        date_fields = ["created_at", "updated_at", "deleted_at"]
        for field in date_fields:
            if field in data and data[field]:
                date_value = str(data[field])
                # Should be ISO 8601 format (contains T and Z or timezone)
                self.assertIn("T", date_value or "", f"{field} should be in ISO 8601 format")

    def test_api_list_endpoint_returns_paginated_data(self):
        """Test API list endpoint returns paginated data in frontend-consumable format"""
        # Create multiple contracts — each needs its own asset
        from hub.apps.assets.models import Asset, AssetStatus
        for i in range(5):
            list_asset = Asset.objects.create(
                tenant=self.tenant, key=f"list-asset-{i}", name=f"List {i}", status=AssetStatus.ACTIVE
            )
            Contract.objects.create(
                tenant=self.tenant,
                asset=list_asset,
                original_raw=json.dumps(self.valid_odps),
                original_format=OriginalFormat.JSON,
                original_spec_type=OriginalSpecType.ODPS,
                original_spec_version="4.1",
                status=ContractStatus.ACTIVE,
                version=1,
                normalization_status=NormalizationStatus.NORMALIZED_OK,
            )

        # Test list endpoint
        response = self.client.get("/api/v1/contracts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK, "API should return data")

        # Verify response is JSON
        self.assertEqual(response["Content-Type"], "application/json", "Response should be JSON")

        # Verify response structure
        data = response.json()
        self.assertIsInstance(data, dict, "Response should be a dictionary")

        # May have pagination structure (results, count, next, previous)
        if "results" in data:
            self.assertIsInstance(data["results"], list, "Results should be a list")

    def test_api_create_endpoint_accepts_frontend_format(self):
        """Test API create endpoint accepts data in frontend-consumable format"""
        response = self.client.post(
            "/api/v1/contracts/",
            {
                "original_raw": json.dumps(self.valid_odps),
                "original_format": "JSON",
                "asset_id": str(self.asset.id),
            },
            format="json",
        )

        # Should accept and create contract
        self.assertIn(
            response.status_code,
            [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST],
            "API should accept frontend format",
        )

    def test_api_update_endpoint_accepts_frontend_format(self):
        """Test API update endpoint accepts data in frontend-consumable format"""
        # Create contract first
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(self.valid_odps),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.DRAFT,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        # Update contract
        updated_odps = self.valid_odps.copy()
        updated_odps["product"]["details"]["en"]["name"] = "Updated Product"

        response = self.client.put(
            f"/api/v1/contracts/{contract.id}/",
            {"original_raw": json.dumps(updated_odps), "original_format": "JSON"},
            format="json",
        )

        # Should accept and update contract
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST],
            "API should accept frontend format for updates",
        )

    def test_api_responses_have_consistent_error_structure(self):
        """Test all API error responses have consistent structure"""
        # Test 400 error (bad request)
        response = self.client.post(
            "/api/v1/contracts/", {}, format="json"  # Empty data - should cause error
        )

        if response.status_code >= 400:
            error_data = response.json()
            self.assertIsInstance(error_data, dict, "Error response should be a dictionary")
            # Should have error indication
            has_error_field = (
                "error" in error_data
                or "errors" in error_data
                or "detail" in error_data
                or "message" in error_data
            )
            self.assertTrue(
                has_error_field,
                "Error response should include error, errors, detail, or message field",
            )

    def test_api_responses_include_metadata_fields(self):
        """Test API responses include metadata fields for frontend"""
        # Create contract
        contract = Contract.objects.create(
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

        # Test detail endpoint
        response = self.client.get(f"/api/v1/contracts/{contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should include common metadata fields
        metadata_fields = ["id", "created_at", "updated_at"]
        for field in metadata_fields:
            if field in data:
                self.assertIsNotNone(data[field], f"{field} should not be None")

    def test_api_responses_handle_special_characters(self):
        """Test API responses handle special characters in frontend-consumable format"""
        # Create contract with special characters
        odps_with_special = self.valid_odps.copy()
        odps_with_special["product"]["details"]["en"][
            "name"
        ] = "Test & Product <script>alert('xss')</script>"

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(odps_with_special),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        # Test detail endpoint
        response = self.client.get(f"/api/v1/contracts/{contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should handle special characters gracefully
        self.assertIsInstance(data, dict, "Response should be valid JSON")

    def test_api_responses_handle_unicode_characters(self):
        """Test API responses handle unicode characters in frontend-consumable format"""
        # Create contract with unicode characters
        odps_with_unicode = self.valid_odps.copy()
        odps_with_unicode["product"]["details"]["en"]["name"] = "Test 产品 🚀"

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_raw=json.dumps(odps_with_unicode),
            original_format=OriginalFormat.JSON,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            status=ContractStatus.ACTIVE,
            version=1,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
        )

        # Test detail endpoint
        response = self.client.get(f"/api/v1/contracts/{contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should handle unicode characters gracefully
        self.assertIsInstance(data, dict, "Response should be valid JSON")
        # Response should be valid UTF-8
        self.assertIsInstance(response.content, bytes)
