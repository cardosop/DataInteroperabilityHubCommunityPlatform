"""
Comprehensive integration tests for all export endpoints (Task 2.3.2)

This test suite verifies:
1. Export in all formats (contract export endpoint)
2. Download in all formats (contract download and marketplace download endpoints)
3. Format conversion and data integrity across all endpoints
4. Cross-endpoint consistency (same contract, same format = same output)

Tests use real implementations (no mocks/stubs) and follow TDD principles.
"""

import json
import yaml
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    OriginalSpecType,
    OriginalFormat,
    NormalizationStatus,
)
from hub.apps.users.models import UserStatus
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.marketplace.models import Listing, ListingStatus, PricingModel, Entitlement


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ExportEndpointsIntegrationTest(TestCase):
    """
    Comprehensive integration tests for all export endpoints.

    Tests cover:
    - Contract export endpoint (/api/v1/contracts/contracts/{id}/export/)
    - Contract download endpoint (/api/v1/contracts/contracts/{id}/download/)
    - Marketplace download endpoint (/api/v1/marketplace/listings/{id}/download/)
    - Format conversion and data integrity
    """

    def setUp(self):
        """Set up comprehensive test fixtures"""
        self.client = APIClient()

        # Create provider tenant
        self.provider_tenant = Tenant.objects.create(
            name="Provider Tenant",
            slug="provider-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create consumer tenant
        self.consumer_tenant = Tenant.objects.create(
            name="Consumer Tenant",
            slug="consumer-tenant",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create users
        self.provider_user = User.objects.create_user(
            email="provider@example.com",
            password="testpass123",
            tenant=self.provider_tenant,
            status=UserStatus.ACTIVE,
        )

        self.consumer_user = User.objects.create_user(
            email="consumer@example.com",
            password="testpass123",
            tenant=self.consumer_tenant,
            status=UserStatus.ACTIVE,
        )

        # Create comprehensive ODCS contract data
        self.odcs_contract_data = {
            "id": "test-contract-comprehensive",
            "name": "Comprehensive Test Contract",
            "description": "Test contract for comprehensive export endpoint testing",
            "version": "1.0.0",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "description": "Unique identifier"},
                    {"name": "name", "type": "string", "description": "Name field"},
                    {"name": "value", "type": "number", "description": "Numeric value"},
                ]
            },
            "terms": {
                "usage": "commercial",
                "restrictions": ["no-resale"],
            },
        }

        # Create comprehensive HubContract data with marketplace info
        self.hub_contract_data = {
            "hub_contract_version": "1.0.0",
            "id": "test-contract-comprehensive",
            "info": {
                "name": "Comprehensive Test Contract",
                "description": "Test contract for comprehensive export endpoint testing",
                "version": "1.0.0",
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "description": "Unique identifier"},
                    {"name": "name", "type": "string", "description": "Name field"},
                    {"name": "value", "type": "number", "description": "Numeric value"},
                ]
            },
            "marketplace": {
                "license_summary": "Test license for comprehensive export",
                "intended_use": ["analytics", "reporting", "machine-learning"],
                "x_odps": {
                    "pricing_plans": [
                        {
                            "id": "free-plan",
                            "name": "Free Plan",
                            "price": 0,
                            "currency": "USD"
                        },
                        {
                            "id": "premium-plan",
                            "name": "Premium Plan",
                            "price": 99.99,
                            "currency": "USD"
                        }
                    ],
                    "access_methods": {
                        "api": {"url": "https://api.example.com/data"},
                        "s3": {"bucket": "test-bucket", "path": "/data/"}
                    }
                }
            },
        }

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.provider_tenant,
            key="test-asset-comprehensive",
            name="Test Asset",
            description="Asset for comprehensive export testing",
            status=AssetStatus.ACTIVE,
            created_by=self.provider_user,
        )

        # Create contract with comprehensive data
        self.contract = Contract.objects.create(
            tenant=self.provider_tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odcs_contract_data),
            hub_contract_json=self.hub_contract_data,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
            created_by=self.provider_user,
        )

        # Create marketplace listing
        self.listing = Listing.objects.create(
            tenant=self.provider_tenant,
            asset=self.asset,
            status=ListingStatus.PUBLISHED,
            pricing_model=PricingModel.FREE,
            metadata_json={
                "title": "Comprehensive Test Listing",
                "short_description": "Listing for comprehensive export testing",
                "long_description": "Long description for comprehensive export testing",
            },
        )

        # Create entitlement for consumer
        self.entitlement = Entitlement.objects.create(
            tenant=self.consumer_tenant,
            listing=self.listing,
            asset=self.asset,
            expires_at=None,  # No expiration
        )

    def _parse_response_content(self, response, output_format):
        """Helper to parse response content based on output format"""
        if output_format == "yaml":
            return yaml.safe_load(response.content)
        else:  # json
            return json.loads(response.content)

    def _extract_core_data(self, data, format_type):
        """Extract core contract data from different format structures"""
        # Ensure data is a dict
        if not isinstance(data, dict):
            if isinstance(data, str):
                # Try to parse as JSON
                try:
                    data = json.loads(data)
                except (json.JSONDecodeError, TypeError):
                    # Try to parse as YAML
                    try:
                        data = yaml.safe_load(data)
                    except (yaml.YAMLError, TypeError):
                        return {}
            else:
                return {}

        if format_type == "hubcontract":
            return {
                "id": data.get("id"),
                "name": data.get("info", {}).get("name"),
                "description": data.get("info", {}).get("description"),
                "version": data.get("info", {}).get("version"),
            }
        elif format_type == "odcs":
            return {
                "id": data.get("id"),
                "name": data.get("name"),
                "description": data.get("description"),
                "version": data.get("version"),
            }
        elif format_type == "odps":
            # ODPS has different structure: product.details[lang].productID, product.details[lang].name
            product = data.get("product", {})
            if not isinstance(product, dict):
                return {}

            details = product.get("details", {})
            if not isinstance(details, dict):
                return {}

            # Get first language entry (usually "en")
            lang_details = details.get("en") if "en" in details else {}
            if not lang_details:
                # If no "en" key, get first available language
                lang_details = next(iter(details.values())) if details else {}

            if not isinstance(lang_details, dict):
                return {}

            return {
                "id": lang_details.get("productID") or data.get("version"),  # Fallback to version if productID not found
                "name": lang_details.get("name"),
                "description": lang_details.get("description"),
                "version": data.get("version"),
            }
        elif format_type == "original":
            return {
                "id": data.get("id"),
                "name": data.get("name"),
                "description": data.get("description"),
                "version": data.get("version"),
            }
        return {}

    # ==================== Contract Export Endpoint Tests ====================

    def test_contract_export_all_formats_json(self):
        """Test contract export endpoint with all formats in JSON"""
        self.client.force_authenticate(user=self.provider_user)

        formats = ["hubcontract", "odcs", "odps"]
        for format_type in formats:
            with self.subTest(format=format_type):
                response = self.client.get(
                    f"/api/v1/contracts/contracts/{self.contract.id}/export/",
                    {"format": format_type, "output_format": "json"},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response["Content-Type"], "application/json")

                data = json.loads(response.content)
                core_data = self._extract_core_data(data, format_type)

                # Verify core data is preserved
                self.assertEqual(core_data["id"], "test-contract-comprehensive")
                self.assertEqual(core_data["name"], "Comprehensive Test Contract")
                # For ODPS, version is the schema version (4.1), not contract version
                if format_type != "odps":
                    self.assertEqual(core_data["version"], "1.0.0")
                else:
                    # ODPS version is schema version, not contract version
                    self.assertIsNotNone(core_data["version"])

    def test_contract_export_all_formats_yaml(self):
        """Test contract export endpoint with all formats in YAML"""
        self.client.force_authenticate(user=self.provider_user)

        formats = ["hubcontract", "odcs", "odps"]
        for format_type in formats:
            with self.subTest(format=format_type):
                response = self.client.get(
                    f"/api/v1/contracts/contracts/{self.contract.id}/export/",
                    {"format": format_type, "output_format": "yaml"},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("yaml", response["Content-Type"].lower())

                data = yaml.safe_load(response.content)
                core_data = self._extract_core_data(data, format_type)

                # Verify core data is preserved
                self.assertEqual(core_data["id"], "test-contract-comprehensive")
                self.assertEqual(core_data["name"], "Comprehensive Test Contract")
                # For ODPS, version is the schema version (4.1), not contract version
                if format_type != "odps":
                    self.assertEqual(core_data["version"], "1.0.0")
                else:
                    # ODPS version is schema version, not contract version
                    self.assertIsNotNone(core_data["version"])

    # ==================== Contract Download Endpoint Tests ====================

    def test_contract_download_all_formats_json(self):
        """Test contract download endpoint with all formats in JSON"""
        self.client.force_authenticate(user=self.provider_user)

        formats = ["hubcontract", "odcs", "odps"]
        for format_type in formats:
            with self.subTest(format=format_type):
                response = self.client.get(
                    f"/api/v1/contracts/contracts/{self.contract.id}/download/",
                    {"format": format_type, "output_format": "json"},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response["Content-Type"], "application/json")
                self.assertIn("Content-Disposition", response)
                self.assertIn("attachment", response["Content-Disposition"])

                data = json.loads(response.content)
                core_data = self._extract_core_data(data, format_type)

                # Verify core data is preserved
                self.assertEqual(core_data["id"], "test-contract-comprehensive")
                self.assertEqual(core_data["name"], "Comprehensive Test Contract")

    def test_contract_download_all_formats_yaml(self):
        """Test contract download endpoint with all formats in YAML"""
        self.client.force_authenticate(user=self.provider_user)

        formats = ["hubcontract", "odcs", "odps"]
        for format_type in formats:
            with self.subTest(format=format_type):
                response = self.client.get(
                    f"/api/v1/contracts/contracts/{self.contract.id}/download/",
                    {"format": format_type, "output_format": "yaml"},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("yaml", response["Content-Type"].lower())
                self.assertIn("Content-Disposition", response)
                self.assertIn("attachment", response["Content-Disposition"])

                data = yaml.safe_load(response.content)
                core_data = self._extract_core_data(data, format_type)

                # Verify core data is preserved
                self.assertEqual(core_data["id"], "test-contract-comprehensive")
                self.assertEqual(core_data["name"], "Comprehensive Test Contract")

    # ==================== Marketplace Download Endpoint Tests ====================

    def test_marketplace_download_all_formats_json(self):
        """Test marketplace download endpoint with all formats in JSON"""
        self.client.force_authenticate(user=self.consumer_user)

        formats = ["original", "hubcontract", "odcs", "odps"]
        for format_type in formats:
            with self.subTest(format=format_type):
                response = self.client.get(
                    f"/api/v1/marketplace/listings/{self.listing.id}/download/",
                    {"format": format_type, "output_format": "json"},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("contract_content", response.data)

                # Parse contract content
                contract_content = response.data["contract_content"]
                data = json.loads(contract_content)
                core_data = self._extract_core_data(data, format_type)

                # Verify core data is preserved
                self.assertEqual(core_data["id"], "test-contract-comprehensive")
                self.assertEqual(core_data["name"], "Comprehensive Test Contract")

    def test_marketplace_download_all_formats_yaml(self):
        """Test marketplace download endpoint with all formats in YAML"""
        self.client.force_authenticate(user=self.consumer_user)

        formats = ["original", "hubcontract", "odcs", "odps"]
        for format_type in formats:
            with self.subTest(format=format_type):
                response = self.client.get(
                    f"/api/v1/marketplace/listings/{self.listing.id}/download/",
                    {"format": format_type, "output_format": "yaml"},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertIn("contract_content", response.data)

                # Parse contract content
                contract_content = response.data["contract_content"]
                data = yaml.safe_load(contract_content)
                core_data = self._extract_core_data(data, format_type)

                # Verify core data is preserved
                self.assertEqual(core_data["id"], "test-contract-comprehensive")
                self.assertEqual(core_data["name"], "Comprehensive Test Contract")

    # ==================== Format Conversion Tests ====================

    def test_format_conversion_hubcontract_to_odps(self):
        """Test format conversion: HubContract -> ODPS preserves data"""
        self.client.force_authenticate(user=self.provider_user)

        # Export as HubContract
        hubcontract_response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
            {"format": "hubcontract", "output_format": "json"},
        )
        hubcontract_data = json.loads(hubcontract_response.content)

        # Export as ODPS
        odps_response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
            {"format": "odps", "output_format": "json"},
        )
        odps_data = json.loads(odps_response.content)

        # Verify core data is preserved in conversion
        hubcontract_core = self._extract_core_data(hubcontract_data, "hubcontract")
        odps_core = self._extract_core_data(odps_data, "odps")

        self.assertEqual(hubcontract_core["id"], odps_core["id"])
        self.assertEqual(hubcontract_core["name"], odps_core["name"])
        self.assertEqual(hubcontract_core["description"], odps_core["description"])

    def test_format_conversion_odcs_to_hubcontract(self):
        """Test format conversion: ODCS -> HubContract preserves data"""
        self.client.force_authenticate(user=self.provider_user)

        # Export as ODCS
        odcs_response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
            {"format": "odcs", "output_format": "json"},
        )
        odcs_data = json.loads(odcs_response.content)

        # Export as HubContract
        hubcontract_response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
            {"format": "hubcontract", "output_format": "json"},
        )
        hubcontract_data = json.loads(hubcontract_response.content)

        # Verify core data is preserved in conversion
        odcs_core = self._extract_core_data(odcs_data, "odcs")
        hubcontract_core = self._extract_core_data(hubcontract_data, "hubcontract")

        self.assertEqual(odcs_core["id"], hubcontract_core["id"])
        self.assertEqual(odcs_core["name"], hubcontract_core["name"])
        self.assertEqual(odcs_core["description"], hubcontract_core["description"])

    def test_format_conversion_json_to_yaml(self):
        """Test output format conversion: JSON -> YAML preserves data"""
        self.client.force_authenticate(user=self.provider_user)

        # Export as JSON
        json_response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
            {"format": "hubcontract", "output_format": "json"},
        )
        json_data = json.loads(json_response.content)

        # Export as YAML
        yaml_response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
            {"format": "hubcontract", "output_format": "yaml"},
        )
        yaml_data = yaml.safe_load(yaml_response.content)

        # Verify data is preserved in format conversion
        json_core = self._extract_core_data(json_data, "hubcontract")
        yaml_core = self._extract_core_data(yaml_data, "hubcontract")

        self.assertEqual(json_core["id"], yaml_core["id"])
        self.assertEqual(json_core["name"], yaml_core["name"])
        self.assertEqual(json_core["description"], yaml_core["description"])

    # ==================== Cross-Endpoint Consistency Tests ====================

    def test_export_download_consistency_hubcontract(self):
        """Test that export and download endpoints return same data for HubContract"""
        self.client.force_authenticate(user=self.provider_user)

        # Export
        export_response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
            {"format": "hubcontract", "output_format": "json"},
        )
        export_data = json.loads(export_response.content)

        # Download
        download_response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/download/",
            {"format": "hubcontract", "output_format": "json"},
        )
        download_data = json.loads(download_response.content)

        # Verify data is identical
        export_core = self._extract_core_data(export_data, "hubcontract")
        download_core = self._extract_core_data(download_data, "hubcontract")

        self.assertEqual(export_core["id"], download_core["id"])
        self.assertEqual(export_core["name"], download_core["name"])
        self.assertEqual(export_core["description"], download_core["description"])

    def test_export_marketplace_consistency_odps(self):
        """Test that contract export and marketplace download return same ODPS data"""
        self.client.force_authenticate(user=self.provider_user)

        # Export from contract endpoint
        export_response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
            {"format": "odps", "output_format": "json"},
        )
        export_data = json.loads(export_response.content)

        # Download from marketplace endpoint (as consumer)
        self.client.force_authenticate(user=self.consumer_user)
        marketplace_response = self.client.get(
            f"/api/v1/marketplace/listings/{self.listing.id}/download/",
            {"format": "odps", "output_format": "json"},
        )
        marketplace_content = marketplace_response.data["contract_content"]
        marketplace_data = json.loads(marketplace_content)

        # Verify core data is preserved
        export_core = self._extract_core_data(export_data, "odps")
        marketplace_core = self._extract_core_data(marketplace_data, "odps")

        self.assertEqual(export_core["id"], marketplace_core["id"])
        self.assertEqual(export_core["name"], marketplace_core["name"])
        self.assertEqual(export_core["description"], marketplace_core["description"])

    def test_all_endpoints_same_contract_same_format(self):
        """Test that all endpoints return consistent data for same contract and format"""
        self.client.force_authenticate(user=self.provider_user)

        # Get data from contract export
        export_response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/export/",
            {"format": "hubcontract", "output_format": "json"},
        )
        export_data = json.loads(export_response.content)

        # Get data from contract download
        download_response = self.client.get(
            f"/api/v1/contracts/contracts/{self.contract.id}/download/",
            {"format": "hubcontract", "output_format": "json"},
        )
        download_data = json.loads(download_response.content)

        # Get data from marketplace download (as consumer)
        self.client.force_authenticate(user=self.consumer_user)
        marketplace_response = self.client.get(
            f"/api/v1/marketplace/listings/{self.listing.id}/download/",
            {"format": "hubcontract", "output_format": "json"},
        )
        marketplace_content = marketplace_response.data["contract_content"]
        marketplace_data = json.loads(marketplace_content)

        # Verify all three return same core data
        export_core = self._extract_core_data(export_data, "hubcontract")
        download_core = self._extract_core_data(download_data, "hubcontract")
        marketplace_core = self._extract_core_data(marketplace_data, "hubcontract")

        self.assertEqual(export_core["id"], download_core["id"])
        self.assertEqual(export_core["id"], marketplace_core["id"])
        self.assertEqual(export_core["name"], download_core["name"])
        self.assertEqual(export_core["name"], marketplace_core["name"])

    # ==================== Comprehensive Format Matrix Tests ====================

    def test_all_format_output_combinations(self):
        """Test all combinations of format and output_format across all endpoints"""
        self.client.force_authenticate(user=self.provider_user)

        formats = ["hubcontract", "odcs", "odps"]
        output_formats = ["json", "yaml"]
        endpoints = [
            ("export", f"/api/v1/contracts/contracts/{self.contract.id}/export/"),
            ("download", f"/api/v1/contracts/contracts/{self.contract.id}/download/"),
        ]

        for endpoint_name, endpoint_url in endpoints:
            for format_type in formats:
                for output_format in output_formats:
                    with self.subTest(
                        endpoint=endpoint_name,
                        format=format_type,
                        output=output_format
                    ):
                        response = self.client.get(
                            endpoint_url,
                            {"format": format_type, "output_format": output_format},
                        )

                        self.assertEqual(
                            response.status_code,
                            status.HTTP_200_OK,
                            f"Failed for {endpoint_name}/{format_type}/{output_format}",
                        )

                        # Verify content is parseable
                        if output_format == "yaml":
                            data = yaml.safe_load(response.content)
                        else:
                            data = json.loads(response.content)

                        # Verify core data exists
                        core_data = self._extract_core_data(data, format_type)
                        self.assertIsNotNone(core_data.get("id"))
                        self.assertIsNotNone(core_data.get("name"))

    def test_marketplace_all_format_output_combinations(self):
        """Test all combinations of format and output_format for marketplace endpoint"""
        self.client.force_authenticate(user=self.consumer_user)

        formats = ["original", "hubcontract", "odcs", "odps"]
        output_formats = ["json", "yaml"]

        for format_type in formats:
            for output_format in output_formats:
                with self.subTest(format=format_type, output=output_format):
                    response = self.client.get(
                        f"/api/v1/marketplace/listings/{self.listing.id}/download/",
                        {"format": format_type, "output_format": output_format},
                    )

                    self.assertEqual(
                        response.status_code,
                        status.HTTP_200_OK,
                        f"Failed for marketplace/{format_type}/{output_format}",
                    )

                    # Verify contract_content exists and is parseable
                    self.assertIn("contract_content", response.data)
                    contract_content = response.data["contract_content"]

                    if output_format == "yaml":
                        data = yaml.safe_load(contract_content)
                    else:
                        data = json.loads(contract_content)

                    # Verify core data exists
                    core_data = self._extract_core_data(data, format_type)
                    self.assertIsNotNone(core_data.get("id"))
                    self.assertIsNotNone(core_data.get("name"))

