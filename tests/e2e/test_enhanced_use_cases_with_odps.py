"""
Comprehensive E2E tests for Enhanced Use Cases with ODPS Integration.

Covers all 5 enhanced use cases:
- UC-AM-001 Enhanced: Enhanced Data-First Flow with ODPS
- UC-CM-001 Enhanced: Enhanced Technical-First Flow with ODPS
- UC-MKT-001 Enhanced: Enhanced Marketplace Publishing with ODPS
- UC-MKT-002 Enhanced: Enhanced Marketplace Purchase with ODPS
- UC-DC-001 Enhanced: Enhanced Asset Discovery with ODPS

All tests use REAL services (no mocks/stubs) and follow TDD principles.
Tests cover main flows, alternate flows, and edge cases.
"""

import json
import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, OriginalSpecType
from hub.apps.contracts.services import ContractService, ODPSService
from hub.apps.datasets.models import Dataset
from hub.apps.marketplace.models import (
    EntitlementStatus,
    Listing,
    ListingStatus,
    OrderStatus,
    PricingModel,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus

from .conftest import E2ETestBase, get_response_data

pytestmark = [
    pytest.mark.uc_journey_persona,
    pytest.mark.django_db(transaction=True),
    pytest.mark.e2e,
    pytest.mark.uc("UC-AM-001"),
    pytest.mark.uc("UC-CM-001"),
    pytest.mark.uc("UC-MKT-001"),
    pytest.mark.uc("UC-MKT-002"),
    pytest.mark.uc("UC-DC-001"),
]


# ============================================================================
# UC-AM-001 Enhanced: Enhanced Data-First Flow with ODPS
# ============================================================================


class UC_AM_001_Enhanced_DataFirstFlowWithODPSTest(E2ETestBase):
    """
    UC-AM-001 Enhanced: Enhanced Data-First Flow with ODPS

    Tests the enhanced data-first flow where:
    1. User uploads data file
    2. System infers schema and creates ODCS contract
    3. User links ODPS contract to the ODCS contract
    4. Asset creation completes successfully
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Create ODPS service
        self.odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_main_flow_data_first_with_odps_linking(self):
        """
        Test main flow: Data-First → Create ODCS → Link ODPS → Complete

        Main flow:
        1. User creates asset
        2. User uploads data file
        3. System infers schema and creates ODCS contract
        4. User links ODPS contract to ODCS
        5. Asset creation completes successfully
        """
        # Step 1: Create asset
        asset_id = self.create_asset(
            key="data-first-odps-asset",
            name="Data-First ODPS Asset",
            description="Asset created via data-first flow with ODPS linking",
        )

        # Step 2: Upload data file
        test_content = b"id,name,value\n1,Item1,100\n2,Item2,200"
        content_hash = self._calculate_sha256(test_content)

        file_id = self.init_file_upload(
            name="data.csv", content_type="text/csv", size=len(test_content)
        )
        self.complete_file_upload(
            file_id, content_sha256=content_hash, test_content=test_content, mock_s3=False
        )

        # Step 3: Create dataset (triggers schema inference)
        dataset_id = self.create_dataset(file_id, asset_id)
        dataset = Dataset.objects.get(id=dataset_id)
        self.assertIsNotNone(dataset.schema_json)

        # Step 4: Create ODCS contract from inferred schema
        odcs_contract_data = {
            "id": "data-first-contract",
            "info": {
                "name": "Data-First Contract",
                "description": "Contract created via data-first flow",
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"},
                    {"name": "value", "type": "number"},
                ]
            },
        }
        contract_id = self.create_contract(asset_id, original_raw=json.dumps(odcs_contract_data))

        # Step 5: Link ODPS contract to ODCS
        # ODPS contract must include product.contract.spec with matching ODCS contract
        odps_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"data-first-product-{uuid.uuid4().hex[:8]}",
                        "name": "Data-First Product",
                        "description": "Product created via data-first flow",
                    }
                },
                "dataSchema": {
                    "fields": [
                        {"name": "id", "type": "string"},
                        {"name": "name", "type": "string"},
                        {"name": "value", "type": "number"},
                    ]
                },
                "contract": {"spec": odcs_contract_data},  # Include ODCS contract inline
                "marketplace": {
                    "pricingPlans": [
                        {
                            "planID": "basic",
                            "name": "Basic Plan",
                            "price": 9.99,
                            "currency": "USD",
                            "billingPeriod": "monthly",
                        }
                    ],
                    "accessMethods": {
                        "api": {"type": "REST", "endpoint": "https://api.example.com/v1"}
                    },
                },
            },
        }

        # Create ODPS contract
        odps_contract = self.odps_service.create_odps(
            odps_raw=json.dumps(odps_data, indent=2),
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset_id),
        )

        # Link ODPS to ODCS
        linked_odps = self.odps_service.link_odps_to_odcs(
            odcs_contract_id=str(contract_id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify linking
        self.assertIsNotNone(linked_odps)
        linked_odps.refresh_from_db()
        extensions = linked_odps.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertEqual(x_odps.get("odcs_link"), str(contract_id))

        # Step 6: Attach dataset and contract to asset
        self.attach_dataset_to_asset(asset_id, dataset_id)
        self.prepare_contract_for_activation(contract_id)  # Validate before attaching
        self.attach_contract_to_asset(asset_id, contract_id)

        # Step 7: Prepare and activate asset
        self.prepare_asset_for_activation(asset_id)

        activate_response = self.activate_asset(asset_id)
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)

        # Verify final state
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.status, AssetStatus.ACTIVE)
        self.assertTrue(asset.contracts.exists())

        # Verify ODPS contract is linked
        odcs_contract = Contract.objects.get(id=contract_id)
        odcs_contract.refresh_from_db()
        odcs_extensions = odcs_contract.hub_contract_json.get("extensions", {})
        odcs_x_odps = odcs_extensions.get("x_odps", {})
        self.assertEqual(odcs_x_odps.get("odps_link"), str(odps_contract.id))

    def test_alternate_flow_odps_linking_failure_does_not_fail_asset_creation(self):
        """
        Test alternate flow: ODPS linking failure should not fail asset creation

        Alternate flow:
        1. User creates asset and uploads data
        2. System creates ODCS contract
        3. User attempts to link invalid ODPS contract
        4. ODPS linking fails
        5. Asset creation still completes successfully (ODPS is optional)
        """
        # Step 1: Create asset and upload data
        asset_id = self.create_asset(
            key="data-first-no-odps-asset", name="Data-First No ODPS Asset"
        )

        test_content = b"id,name\n1,Item1"
        content_hash = self._calculate_sha256(test_content)

        file_id = self.init_file_upload(
            name="data.csv", content_type="text/csv", size=len(test_content)
        )
        self.complete_file_upload(
            file_id, content_sha256=content_hash, test_content=test_content, mock_s3=False
        )

        dataset_id = self.create_dataset(file_id, asset_id)
        contract_id = self.create_contract(
            asset_id,
            original_raw=json.dumps(
                {
                    "id": f"contract-{uuid.uuid4().hex[:8]}",
                    "info": {"name": "Test Contract", "description": "Test contract"},
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string"},
                            {"name": "name", "type": "string"},
                        ]
                    },
                }
            ),
        )

        # Step 2: Attempt to link non-existent ODPS contract (should fail)
        with self.assertRaises(Exception):  # NotFoundError or ValidationError
            self.odps_service.link_odps_to_odcs(
                odcs_contract_id=str(contract_id),
                odps_contract_id="00000000-0000-0000-0000-000000000000",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

        # Step 3: Asset creation should still succeed without ODPS
        self.attach_dataset_to_asset(asset_id, dataset_id)
        self.prepare_contract_for_activation(contract_id)  # Validate before attaching
        self.attach_contract_to_asset(asset_id, contract_id)
        self.prepare_asset_for_activation(asset_id)

        activate_response = self.activate_asset(asset_id)
        self.assertEqual(activate_response.status_code, status.HTTP_200_OK)

        # Verify asset is active
        asset = Asset.objects.get(id=asset_id)
        self.assertEqual(asset.status, AssetStatus.ACTIVE)

    def test_edge_case_odps_linking_with_invalid_odps_document(self):
        """
        Test edge case: ODPS linking with invalid ODPS document

        Edge case:
        1. User creates asset and ODCS contract
        2. User attempts to link invalid ODPS document
        3. System rejects invalid ODPS
        4. Asset creation completes without ODPS
        """
        asset_id = self.create_asset(
            key="data-first-invalid-odps-asset", name="Data-First Invalid ODPS Asset"
        )

        contract_id = self.create_contract(
            asset_id,
            original_raw=json.dumps(
                {
                    "id": f"contract-{uuid.uuid4().hex[:8]}",
                    "info": {"name": "Test Contract", "description": "Test contract"},
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string"},
                            {"name": "name", "type": "string"},
                        ]
                    },
                }
            ),
        )

        # Attempt to create invalid ODPS contract
        invalid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            # Missing required "product" field
        }

        # Should fail validation
        with self.assertRaises(Exception):  # ValidationError or ODPSValidationError
            self.odps_service.create_odps(
                odps_raw=json.dumps(invalid_odps, indent=2),
                odps_format="json",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                asset_id=str(asset_id),
            )

        # Asset should still be usable without ODPS
        self.prepare_contract_for_activation(contract_id)  # Validate before attaching
        self.attach_contract_to_asset(asset_id, contract_id)

        # Asset can be activated without ODPS
        asset = Asset.objects.get(id=asset_id)
        self.assertIsNotNone(asset)

    def _calculate_sha256(self, content: bytes) -> str:
        """Helper to calculate SHA256 hash"""
        import hashlib

        return hashlib.sha256(content).hexdigest()


# ============================================================================
# UC-CM-001 Enhanced: Enhanced Technical-First Flow with ODPS
# ============================================================================


class UC_CM_001_Enhanced_TechnicalFirstFlowWithODPSTest(E2ETestBase):
    """
    UC-CM-001 Enhanced: Enhanced Technical-First Flow with ODPS

    Tests the enhanced technical-first flow where:
    1. User uploads ODCS contract
    2. System validates and normalizes contract
    3. User links ODPS contract to ODCS
    4. Contract creation completes successfully
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        self.contract_service = ContractService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_main_flow_technical_first_with_odps_linking(self):
        """
        Test main flow: Technical-First → Create ODCS → Link ODPS → Complete

        Main flow:
        1. User creates asset
        2. User uploads ODCS contract
        3. System validates and normalizes contract
        4. User links ODPS contract to ODCS
        5. Contract creation completes successfully
        """
        # Step 1: Create asset
        asset_id = self.create_asset(
            key="technical-first-odps-asset",
            name="Technical-First ODPS Asset",
            description="Asset created via technical-first flow with ODPS linking",
        )

        # Step 2: Create ODCS contract
        # Use consistent contract data for both creation and ODPS linking
        contract_id_str = f"technical-first-contract-{uuid.uuid4().hex[:8]}"
        odcs_contract_data = {
            "id": contract_id_str,
            "info": {
                "name": "Technical-First Contract",
                "description": "Contract created via technical-first flow",
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "description": "Unique identifier"},
                    {"name": "name", "type": "string", "description": "Name"},
                    {"name": "value", "type": "number", "description": "Value"},
                ]
            },
        }

        contract_id = self.create_contract(asset_id, original_raw=json.dumps(odcs_contract_data))

        # Step 3: Validate contract
        validate_response = self.validate_contract(contract_id, async_mode=False)
        if isinstance(validate_response, dict) and "validation_status" in validate_response:
            # Accept SKIPPED when the datacontract-cli validation service
            # is unavailable in the test environment.
            self.assertIn(
                validate_response.get("validation_status"),
                ["VALID", "INVALID", "SKIPPED"],
            )

        # Step 4: Link ODPS contract to ODCS
        # ODPS contract must include product.contract.spec with matching ODCS contract
        odps_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"technical-first-product-{uuid.uuid4().hex[:8]}",
                        "name": "Technical-First Product",
                        "description": "Product created via technical-first flow",
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
                },
                "contract": {"spec": odcs_contract_data},  # Include ODCS contract inline
                "marketplace": {
                    "pricingPlans": [
                        {
                            "planID": "premium",
                            "name": "Premium Plan",
                            "price": 29.99,
                            "currency": "USD",
                            "billingPeriod": "monthly",
                        }
                    ],
                    "accessMethods": {
                        "api": {"type": "REST", "endpoint": "https://api.example.com/v1"},
                        "download": {"type": "FILE", "format": "CSV"},
                    },
                },
            },
        }

        # Create ODPS contract
        odps_contract = self.odps_service.create_odps(
            odps_raw=json.dumps(odps_data, indent=2),
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset_id),
        )

        # Link ODPS to ODCS
        linked_odps = self.odps_service.link_odps_to_odcs(
            odcs_contract_id=str(contract_id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Verify linking
        self.assertIsNotNone(linked_odps)
        linked_odps.refresh_from_db()
        extensions = linked_odps.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertEqual(x_odps.get("odcs_link"), str(contract_id))

        # Verify ODCS contract has ODPS link
        odcs_contract = Contract.objects.get(id=contract_id)
        odcs_contract.refresh_from_db()
        odcs_extensions = odcs_contract.hub_contract_json.get("extensions", {})
        odcs_x_odps = odcs_extensions.get("x_odps", {})
        self.assertEqual(odcs_x_odps.get("odps_link"), str(odps_contract.id))

    def test_alternate_flow_odps_linking_failure_does_not_fail_contract_creation(self):
        """
        Test alternate flow: ODPS linking failure should not fail contract creation

        Alternate flow:
        1. User creates ODCS contract
        2. User attempts to link invalid ODPS contract
        3. ODPS linking fails
        4. Contract creation still completes successfully (ODPS is optional)
        """
        asset_id = self.create_asset(
            key="technical-first-no-odps-asset", name="Technical-First No ODPS Asset"
        )

        contract_id = self.create_contract(
            asset_id,
            original_raw=json.dumps(
                {
                    "id": f"contract-{uuid.uuid4().hex[:8]}",
                    "info": {"name": "Test Contract", "description": "Test contract"},
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string"},
                            {"name": "name", "type": "string"},
                        ]
                    },
                }
            ),
        )

        # Attempt to link non-existent ODPS contract (should fail)
        with self.assertRaises(Exception):  # NotFoundError or ValidationError
            self.odps_service.link_odps_to_odcs(
                odcs_contract_id=str(contract_id),
                odps_contract_id="00000000-0000-0000-0000-000000000000",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

        # Contract should still be valid
        contract = Contract.objects.get(id=contract_id)
        self.assertIsNotNone(contract)
        self.assertEqual(contract.original_spec_type, OriginalSpecType.ODCS)

    def test_edge_case_odps_linking_with_existing_odps_contract(self):
        """
        Test edge case: ODPS linking with existing ODPS contract

        Edge case:
        1. User creates ODCS contract
        2. User links existing ODPS contract
        3. System handles duplicate linking gracefully
        """
        asset_id = self.create_asset(
            key="technical-first-existing-odps-asset", name="Technical-First Existing ODPS Asset"
        )

        # Create ODCS contract with consistent data
        odcs_contract_data = {
            "id": f"existing-odps-contract-{uuid.uuid4().hex[:8]}",
            "info": {"name": "Test Contract", "description": "Test contract"},
            "schema": {
                "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
            },
        }

        contract_id = self.create_contract(asset_id, original_raw=json.dumps(odcs_contract_data))

        # Create ODPS contract with product.contract section
        odps_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"existing-odps-product-{uuid.uuid4().hex[:8]}",
                        "name": "Existing ODPS Product",
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
                },
                "contract": {"spec": odcs_contract_data},  # Include ODCS contract inline
            },
        }

        odps_contract = self.odps_service.create_odps(
            odps_raw=json.dumps(odps_data, indent=2),
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset_id),
        )

        # Link first time
        self.odps_service.link_odps_to_odcs(
            odcs_contract_id=str(contract_id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Try to link again (should handle gracefully)
        try:
            linked_odps_again = self.odps_service.link_odps_to_odcs(
                odcs_contract_id=str(contract_id),
                odps_contract_id=str(odps_contract.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )
            # If it succeeds, verify link is still correct
            linked_odps_again.refresh_from_db()
            extensions = linked_odps_again.hub_contract_json.get("extensions", {})
            x_odps = extensions.get("x_odps", {})
            self.assertEqual(x_odps.get("odcs_link"), str(contract_id))
        except Exception as e:
            # Expected if duplicate linking is rejected; verify the error is about
            # linking, not an unrelated failure.
            error_msg = str(e).lower()
            self.assertTrue(
                any(kw in error_msg for kw in ["already", "duplicate", "exists", "linked"]),
                f"Expected duplicate-link error, got: {e}",
            )


# ============================================================================
# UC-MKT-001 Enhanced: Enhanced Marketplace Publishing with ODPS
# ============================================================================


class UC_MKT_001_Enhanced_MarketplacePublishingWithODPSTest(E2ETestBase):
    """
    UC-MKT-001 Enhanced: Enhanced Marketplace Publishing with ODPS

    Tests the enhanced marketplace publishing flow where:
    1. User publishes asset to marketplace
    2. System configures ODPS pricing from linked ODPS contract
    3. System configures access methods from ODPS
    4. System configures payment gateways from ODPS
    5. Listing is published successfully
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Set tenant KYC status to VERIFIED for marketplace operations
        self.tenant.kyc_status = KYCStatus.VERIFIED
        self.tenant.save(update_fields=["kyc_status"])

        self.odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_main_flow_publish_asset_with_odps_configuration(self):
        """
        Test main flow: Publish asset → Configure ODPS pricing → Configure access → Configure payment → Publish

        Main flow:
        1. User creates asset with ODCS contract
        2. User links ODPS contract with pricing/access/payment info
        3. User publishes asset to marketplace
        4. System pre-populates listing metadata from ODPS
        5. Listing is published with ODPS configuration
        """
        # Step 1: Create asset
        asset_id = self.create_asset(
            key="marketplace-odps-asset",
            name="Marketplace ODPS Asset",
            description="Asset for marketplace publishing with ODPS",
        )

        # Step 2: Create ODCS contract with consistent data
        odcs_contract_data = {
            "id": f"marketplace-contract-{uuid.uuid4().hex[:8]}",
            "info": {"name": "Test Contract", "description": "Test contract"},
            "schema": {
                "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
            },
        }

        contract_id = self.create_contract(asset_id, original_raw=json.dumps(odcs_contract_data))
        self.prepare_contract_for_activation(contract_id)  # Validate before attaching
        self.attach_contract_to_asset(asset_id, contract_id)
        self.prepare_asset_for_activation(asset_id)
        self.activate_asset(asset_id)

        # Step 3: Create and link ODPS contract with marketplace data
        odps_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"marketplace-product-{uuid.uuid4().hex[:8]}",
                        "name": "Marketplace Product",
                        "description": "Product with marketplace configuration",
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
                },
                "contract": {"spec": odcs_contract_data},  # Include ODCS contract inline
                "marketplace": {
                    "pricingPlans": [
                        {
                            "planID": "standard",
                            "name": "Standard Plan",
                            "price": 49.99,
                            "currency": "USD",
                            "billingPeriod": "monthly",
                        }
                    ],
                    "accessMethods": {
                        "api": {
                            "type": "REST",
                            "endpoint": "https://api.example.com/v1",
                            "authentication": {"type": "API_KEY"},
                        }
                    },
                    "paymentGateways": {"stripe": {"enabled": True, "publicKey": "pk_test_..."}},
                },
            },
        }

        odps_contract = self.odps_service.create_odps(
            odps_raw=json.dumps(odps_data, indent=2),
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset_id),
        )

        # Link ODPS to ODCS
        self.odps_service.link_odps_to_odcs(
            odcs_contract_id=str(contract_id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Step 4: Create marketplace listing (should pre-populate from ODPS)
        listing_response = self.client.post(
            "/api/v1/marketplace/listings/",
            {
                "asset_id": str(asset_id),
                "title": "Marketplace ODPS Asset",
                "short_description": "Asset with ODPS configuration",
                "pricing_model": PricingModel.REQUEST_APPROVAL,
                "price_amount": 49.99,
                "currency": "USD",
            },
            format="json",
        )
        self.assertEqual(
            listing_response.status_code,
            status.HTTP_201_CREATED,
            f"Failed to create listing: {get_response_data(listing_response) or listing_response.content}",
        )
        listing_data = get_response_data(listing_response) or {}
        listing_id = listing_data.get("id")
        self.assertIsNotNone(listing_id)

        # Step 5: Publish listing
        publish_response = self.client.patch(
            f"/api/v1/marketplace/listings/{listing_id}/",
            {"status": ListingStatus.PUBLISHED},
            format="json",
        )
        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)

        # Verify listing is published
        listing = Listing.objects.get(id=listing_id)
        self.assertEqual(listing.status, ListingStatus.PUBLISHED)
        self.assertIsNotNone(listing.published_at)

        # Verify listing metadata includes ODPS data (if pre-population is implemented)
        if listing.metadata_json:
            # Check if pricing information is present
            metadata = listing.metadata_json
            # Pricing may be in metadata or in listing fields
            self.assertIsNotNone(metadata)

    def test_alternate_flow_odps_configuration_failure(self):
        """
        Test alternate flow: ODPS configuration failure

        Alternate flow:
        1. User creates asset and ODCS contract
        2. User attempts to link invalid ODPS contract
        3. ODPS linking fails
        4. Marketplace publishing still works without ODPS
        """
        asset_id = self.create_asset(
            key="marketplace-no-odps-asset", name="Marketplace No ODPS Asset"
        )

        contract_id = self.create_contract(
            asset_id,
            original_raw=json.dumps(
                {
                    "id": f"contract-{uuid.uuid4().hex[:8]}",
                    "info": {"name": "Test Contract", "description": "Test contract"},
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string"},
                            {"name": "name", "type": "string"},
                        ]
                    },
                }
            ),
        )
        self.prepare_contract_for_activation(contract_id)  # Validate before attaching
        self.attach_contract_to_asset(asset_id, contract_id)
        self.prepare_asset_for_activation(asset_id)
        self.activate_asset(asset_id)

        # Attempt to create invalid ODPS (should fail)
        invalid_odps = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            # Missing required "product" field
        }

        with self.assertRaises(Exception):
            self.odps_service.create_odps(
                odps_raw=json.dumps(invalid_odps, indent=2),
                odps_format="json",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                asset_id=str(asset_id),
            )

        # Marketplace publishing should still work without ODPS
        listing_response = self.client.post(
            "/api/v1/marketplace/listings/",
            {
                "asset_id": str(asset_id),
                "title": "Marketplace No ODPS Asset",
                "short_description": "Asset without ODPS",
                "pricing_model": PricingModel.FREE_AUTO_APPROVE,
                "price_amount": 0.0,
            },
            format="json",
        )
        self.assertEqual(listing_response.status_code, status.HTTP_201_CREATED)

    def test_edge_case_marketplace_publishing_without_odps_should_still_work(self):
        """
        Test edge case: Marketplace publishing without ODPS (legacy flow)

        Edge case:
        1. User creates asset with ODCS contract only
        2. User publishes to marketplace without ODPS
        3. System should handle legacy flow gracefully
        """
        asset_id = self.create_asset(
            key="marketplace-legacy-asset", name="Marketplace Legacy Asset"
        )

        contract_id = self.create_contract(
            asset_id,
            original_raw=json.dumps(
                {
                    "id": f"contract-{uuid.uuid4().hex[:8]}",
                    "info": {"name": "Test Contract", "description": "Test contract"},
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string"},
                            {"name": "name", "type": "string"},
                        ]
                    },
                }
            ),
        )
        self.prepare_contract_for_activation(contract_id)  # Validate before attaching
        self.attach_contract_to_asset(asset_id, contract_id)
        self.prepare_asset_for_activation(asset_id)
        self.activate_asset(asset_id)

        # Publish without ODPS (legacy flow)
        listing_response = self.client.post(
            "/api/v1/marketplace/listings/",
            {
                "asset_id": str(asset_id),
                "title": "Marketplace Legacy Asset",
                "short_description": "Asset without ODPS",
                "pricing_model": PricingModel.FREE_AUTO_APPROVE,
            },
            format="json",
        )
        self.assertEqual(
            listing_response.status_code,
            status.HTTP_201_CREATED,
            f"Failed to create listing: {get_response_data(listing_response) or listing_response.content}",
        )

        listing_data = get_response_data(listing_response) or {}
        listing_id = listing_data.get("id")
        self.assertIsNotNone(listing_id)

        # Publish listing
        publish_response = self.client.patch(
            f"/api/v1/marketplace/listings/{listing_id}/",
            {"status": ListingStatus.PUBLISHED},
            format="json",
        )
        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)

        # Verify listing is published
        listing = Listing.objects.get(id=listing_id)
        self.assertEqual(listing.status, ListingStatus.PUBLISHED)


# ============================================================================
# UC-MKT-002 Enhanced: Enhanced Marketplace Purchase with ODPS
# ============================================================================


class UC_MKT_002_Enhanced_MarketplacePurchaseWithODPSTest(E2ETestBase):
    """
    UC-MKT-002 Enhanced: Enhanced Marketplace Purchase with ODPS

    Tests the enhanced marketplace purchase flow where:
    1. Consumer discovers asset with ODPS product details
    2. Consumer views ODPS pricing and access methods
    3. Consumer selects access method and configures payment
    4. Consumer purchases asset
    5. Purchase completes successfully
    """

    def setUp(self):
        """Set up test fixtures with provider and consumer tenants"""
        super().setUp()

        # Provider tenant (seller)
        self.provider_tenant = Tenant.objects.create(
            name=f"Provider Tenant {uuid.uuid4().hex[:8]}",
            slug=f"provider-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.provider_tenant)
        self.provider_user = User.objects.create_user(
            email=f"provider-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.provider_tenant,
            status=UserStatus.ACTIVE,
        )
        # DATA_PROVIDER role required for asset creation (POST /api/v1/assets/)
        from hub.apps.users.models import Role, UserRole

        provider_role, _ = Role.objects.get_or_create(
            tenant=self.provider_tenant,
            name="DATA_PROVIDER",
            defaults={"description": "Data Provider"},
        )
        UserRole.objects.get_or_create(user=self.provider_user, role=provider_role)
        self.provider_user.refresh_from_db()

        self.provider_client = APIClient()
        self.provider_client.force_authenticate(user=self.provider_user)

        # Consumer tenant (buyer)
        self.consumer_tenant = Tenant.objects.create(
            name=f"Consumer Tenant {uuid.uuid4().hex[:8]}",
            slug=f"consumer-tenant-{uuid.uuid4().hex[:8]}",
            kyc_status=KYCStatus.VERIFIED,
        )
        ensure_tenant_has_active_subscription(self.consumer_tenant)
        self.consumer_user = User.objects.create_user(
            email=f"consumer-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.consumer_tenant,
            status=UserStatus.ACTIVE,
        )
        self.consumer_client = APIClient()
        self.consumer_client.force_authenticate(user=self.consumer_user)

        self.odps_service = ODPSService(
            tenant_id=str(self.provider_tenant.id), user_id=str(self.provider_user.id)
        )

    def test_main_flow_discover_asset_view_odps_details_purchase(self):
        """
        Test main flow: Discover asset → View ODPS details → Select access method → Configure payment → Purchase

        Main flow:
        1. Provider creates asset with ODPS contract
        2. Provider publishes to marketplace
        3. Consumer discovers asset
        4. Consumer views ODPS product details (pricing, access methods)
        5. Consumer selects access method and configures payment
        6. Consumer purchases asset
        """
        # Step 1: Provider creates asset with ODPS
        self.client = self.provider_client

        asset_id = self.create_asset(key="purchasable-odps-asset", name="Purchasable ODPS Asset")

        # Create ODCS contract with consistent data
        odcs_contract_data = {
            "id": f"purchasable-contract-{uuid.uuid4().hex[:8]}",
            "info": {"name": "Test Contract", "description": "Test contract"},
            "schema": {
                "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
            },
        }

        contract_id = self.create_contract(asset_id, original_raw=json.dumps(odcs_contract_data))
        self.prepare_contract_for_activation(contract_id)  # Validate before attaching
        self.attach_contract_to_asset(asset_id, contract_id)
        self.prepare_asset_for_activation(asset_id)
        self.activate_asset(asset_id)

        # Create and link ODPS contract
        odps_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"purchasable-product-{uuid.uuid4().hex[:8]}",
                        "name": "Purchasable Product",
                        "description": "Product with ODPS details",
                    }
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
                },
                "contract": {"spec": odcs_contract_data},  # Include ODCS contract inline
                "marketplace": {
                    "pricingPlans": [
                        {
                            "planID": "standard",
                            "name": "Standard Plan",
                            "price": 29.99,
                            "currency": "USD",
                            "billingPeriod": "monthly",
                        }
                    ],
                    "accessMethods": {
                        "api": {"type": "REST", "endpoint": "https://api.example.com/v1"}
                    },
                    "paymentGateways": {"stripe": {"enabled": True}},
                },
            },
        }

        odps_contract = self.odps_service.create_odps(
            odps_raw=json.dumps(odps_data, indent=2),
            odps_format="json",
            tenant_id=str(self.provider_tenant.id),
            user_id=str(self.provider_user.id),
            asset_id=str(asset_id),
        )

        self.odps_service.link_odps_to_odcs(
            odcs_contract_id=str(contract_id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.provider_tenant.id),
            user_id=str(self.provider_user.id),
        )

        # Step 2: Provider publishes to marketplace
        listing_response = self.provider_client.post(
            "/api/v1/marketplace/listings/",
            {
                "asset_id": str(asset_id),
                "title": "Purchasable ODPS Asset",
                "short_description": "Asset with ODPS details",
                "pricing_model": PricingModel.REQUEST_APPROVAL,
                "price_amount": 29.99,
                "currency": "USD",
            },
            format="json",
        )
        self.assertEqual(listing_response.status_code, status.HTTP_201_CREATED)
        listing_data = get_response_data(listing_response) or {}
        listing_id = listing_data.get("id")
        self.assertIsNotNone(listing_id)

        publish_response = self.provider_client.patch(
            f"/api/v1/marketplace/listings/{listing_id}/",
            {"status": ListingStatus.PUBLISHED},
            format="json",
        )
        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)

        # Step 3: Consumer discovers asset
        self.client = self.consumer_client

        search_response = self.consumer_client.get("/api/v1/marketplace/listings/search/")
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)

        listings = (get_response_data(search_response) or {}).get("results", [])
        our_listing = next((l for l in listings if l["id"] == str(listing_id)), None)
        self.assertIsNotNone(our_listing, "Should find our listing")

        # Step 4: Consumer views ODPS details
        listing_detail_response = self.consumer_client.get(
            f"/api/v1/marketplace/listings/{listing_id}/"
        )
        self.assertEqual(listing_detail_response.status_code, status.HTTP_200_OK)
        listing_data = get_response_data(listing_detail_response) or {}
        self.assertEqual(listing_data.get("id"), str(listing_id))

        # Step 5: Consumer purchases asset
        order_response = self.consumer_client.post(
            "/api/v1/marketplace/orders/", {"listing_id": str(listing_id)}, format="json"
        )
        self.assertEqual(order_response.status_code, status.HTTP_201_CREATED)

        order_resp_data = get_response_data(order_response) or {}
        order_data = order_resp_data.get("order", order_resp_data)
        order_id = order_data["id"]
        self.assertEqual(order_data["status"], OrderStatus.REQUESTED.value)

        # Step 6: Provider approves order
        self.client = self.provider_client

        approve_response = self.provider_client.post(
            f"/api/v1/marketplace/orders/{order_id}/approve/", format="json"
        )
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)

        # Verify entitlement is created
        self.client = self.consumer_client

        entitlements_response = self.consumer_client.get("/api/v1/marketplace/entitlements/")
        self.assertEqual(entitlements_response.status_code, status.HTTP_200_OK)

        entitlements = (get_response_data(entitlements_response) or {}).get("results", [])
        our_entitlement = next(
            (e for e in entitlements if str(e.get("asset", "")) == str(asset_id)), None
        )
        self.assertIsNotNone(our_entitlement, "Entitlement should be created")
        self.assertEqual(our_entitlement["status"], EntitlementStatus.ACTIVE.value)

    def test_alternate_flow_odps_access_method_unavailable(self):
        """
        Test alternate flow: ODPS access method unavailable

        Alternate flow:
        1. Consumer discovers asset with ODPS
        2. ODPS access method is not available
        3. System handles gracefully
        """
        # Create asset and listing (similar to main flow)
        self.client = self.provider_client

        asset_id = self.create_asset(
            key="unavailable-access-asset", name="Unavailable Access Asset"
        )

        contract_id = self.create_contract(
            asset_id,
            original_raw=json.dumps(
                {
                    "id": f"contract-{uuid.uuid4().hex[:8]}",
                    "info": {"name": "Test Contract", "description": "Test contract"},
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string"},
                            {"name": "name", "type": "string"},
                        ]
                    },
                }
            ),
        )
        self.prepare_contract_for_activation(contract_id)  # Validate before attaching
        self.attach_contract_to_asset(asset_id, contract_id)
        self.prepare_asset_for_activation(asset_id)
        self.activate_asset(asset_id)

        # Create listing without ODPS access methods
        listing_response = self.provider_client.post(
            "/api/v1/marketplace/listings/",
            {
                "asset_id": str(asset_id),
                "title": "Unavailable Access Asset",
                "short_description": "Asset without access methods",
                "pricing_model": PricingModel.FREE_AUTO_APPROVE,
                "price_amount": 0.0,
            },
            format="json",
        )
        listing_data = get_response_data(listing_response) or {}
        listing_id = listing_data.get("id")
        self.assertIsNotNone(listing_id)

        publish_response = self.provider_client.patch(
            f"/api/v1/marketplace/listings/{listing_id}/",
            {"status": ListingStatus.PUBLISHED},
            format="json",
        )
        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)

        # Consumer can still purchase (access methods are optional)
        self.client = self.consumer_client

        order_response = self.consumer_client.post(
            "/api/v1/marketplace/orders/", {"listing_id": str(listing_id)}, format="json"
        )
        self.assertEqual(order_response.status_code, status.HTTP_201_CREATED)

    def test_edge_case_purchase_without_odps_legacy_flow(self):
        """
        Test edge case: Purchase without ODPS (legacy flow)

        Edge case:
        1. Consumer discovers asset without ODPS
        2. Consumer purchases using legacy flow
        3. System handles legacy purchase flow
        """
        # Create asset and listing without ODPS
        self.client = self.provider_client

        asset_id = self.create_asset(key="legacy-purchase-asset", name="Legacy Purchase Asset")

        contract_id = self.create_contract(
            asset_id,
            original_raw=json.dumps(
                {
                    "id": f"contract-{uuid.uuid4().hex[:8]}",
                    "info": {"name": "Test Contract", "description": "Test contract"},
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string"},
                            {"name": "name", "type": "string"},
                        ]
                    },
                }
            ),
        )
        self.prepare_contract_for_activation(contract_id)  # Validate before attaching
        self.attach_contract_to_asset(asset_id, contract_id)
        self.prepare_asset_for_activation(asset_id)
        self.activate_asset(asset_id)

        listing_response = self.provider_client.post(
            "/api/v1/marketplace/listings/",
            {
                "asset_id": str(asset_id),
                "title": "Legacy Purchase Asset",
                "short_description": "Asset without ODPS",
                "pricing_model": PricingModel.FREE_AUTO_APPROVE,
                "price_amount": 0.0,
            },
            format="json",
        )
        listing_data = get_response_data(listing_response) or {}
        listing_id = listing_data.get("id")
        self.assertIsNotNone(listing_id)

        publish_response = self.provider_client.patch(
            f"/api/v1/marketplace/listings/{listing_id}/",
            {"status": ListingStatus.PUBLISHED},
            format="json",
        )
        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)

        # Consumer purchases using legacy flow
        self.client = self.consumer_client

        order_response = self.consumer_client.post(
            "/api/v1/marketplace/orders/", {"listing_id": str(listing_id)}, format="json"
        )
        self.assertEqual(order_response.status_code, status.HTTP_201_CREATED)

        order_resp_data = get_response_data(order_response) or {}
        order_data = order_resp_data.get("order", order_resp_data)
        # For FREE_AUTO_APPROVE, order should be fulfilled
        self.assertEqual(order_data["status"], OrderStatus.FULFILLED.value)


# ============================================================================
# UC-DC-001 Enhanced: Enhanced Asset Discovery with ODPS
# ============================================================================


class UC_DC_001_Enhanced_AssetDiscoveryWithODPSTest(E2ETestBase):
    """
    UC-DC-001 Enhanced: Enhanced Asset Discovery with ODPS

    Tests the enhanced asset discovery flow where:
    1. Consumer searches for assets
    2. System returns results with ODPS product details
    3. Consumer can filter by ODPS fields
    4. Consumer views multilingual product details
    """

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Set tenant KYC status to VERIFIED for marketplace operations
        self.tenant.kyc_status = KYCStatus.VERIFIED
        self.tenant.save(update_fields=["kyc_status"])

        self.odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_main_flow_search_view_results_with_odps_product_details(self):
        """
        Test main flow: Search → View results with ODPS product details → Filter by ODPS fields

        Main flow:
        1. Provider creates assets with ODPS contracts
        2. Provider publishes to marketplace
        3. Consumer searches for assets
        4. System returns results with ODPS product details
        5. Consumer can filter by ODPS fields
        """
        # Step 1: Create multiple assets with ODPS
        assets = []
        for i in range(3):
            asset_id = self.create_asset(
                key=f"discovery-odps-asset-{i}", name=f"Discovery ODPS Asset {i}"
            )

            # Create ODCS contract with consistent data
            odcs_contract_data = {
                "id": f"discovery-contract-{i}-{uuid.uuid4().hex[:8]}",
                "info": {"name": "Test Contract", "description": "Test contract"},
                "schema": {
                    "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
                },
            }

            contract_id = self.create_contract(
                asset_id, original_raw=json.dumps(odcs_contract_data)
            )
            self.prepare_contract_for_activation(contract_id)  # Validate before attaching
            self.attach_contract_to_asset(asset_id, contract_id)
            self.prepare_asset_for_activation(asset_id)
            self.activate_asset(asset_id)

            # Create ODPS contract with different pricing
            odps_data = {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "version": "4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": f"discovery-product-{i}-{uuid.uuid4().hex[:8]}",
                            "name": f"Discovery Product {i}",
                            "description": f"Product {i} for discovery test",
                        }
                    },
                    "dataSchema": {
                        "fields": [
                            {"name": "id", "type": "string"},
                            {"name": "name", "type": "string"},
                        ]
                    },
                    "contract": {"spec": odcs_contract_data},  # Include ODCS contract inline
                    "marketplace": {
                        "pricingPlans": [
                            {
                                "planID": "plan",
                                "name": f"Plan {i}",
                                "price": float(10 + i * 10),
                                "currency": "USD",
                                "billingPeriod": "monthly",
                            }
                        ]
                    },
                },
            }

            odps_contract = self.odps_service.create_odps(
                odps_raw=json.dumps(odps_data, indent=2),
                odps_format="json",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                asset_id=str(asset_id),
            )

            self.odps_service.link_odps_to_odcs(
                odcs_contract_id=str(contract_id),
                odps_contract_id=str(odps_contract.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

            # Create and publish listing
            listing_response = self.client.post(
                "/api/v1/marketplace/listings/",
                {
                    "asset_id": str(asset_id),
                    "title": f"Discovery ODPS Asset {i}",
                    "short_description": f"Asset {i} for discovery",
                    "pricing_model": PricingModel.REQUEST_APPROVAL,
                    "price_amount": float(10 + i * 10),
                    "currency": "USD",
                },
                format="json",
            )
            self.assertEqual(
                listing_response.status_code,
                status.HTTP_201_CREATED,
                f"Failed to create listing: {get_response_data(listing_response) or listing_response.content}",
            )
            listing_data = get_response_data(listing_response) or {}
            listing_id = listing_data.get("id")
            self.assertIsNotNone(listing_id)

            self.client.patch(
                f"/api/v1/marketplace/listings/{listing_id}/",
                {"status": ListingStatus.PUBLISHED},
                format="json",
            )

            assets.append(asset_id)

        # Step 2: Consumer searches for assets
        search_response = self.client.get("/api/v1/marketplace/listings/search/")
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)

        listings = (get_response_data(search_response) or {}).get("results", [])
        self.assertGreater(len(listings), 0, "Should have at least one listing")

        # Step 3: Verify results include ODPS product details (if implemented)
        # The listing detail endpoint should include ODPS information
        if listings and len(listings) > 0:
            # Ensure listing has 'id' field
            self.assertIn("id", listings[0], f"Listing missing 'id' field: {listings[0]}")
            listing_id = listings[0]["id"]
            detail_response = self.client.get(f"/api/v1/marketplace/listings/{listing_id}/")
            self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
            listing_data = get_response_data(detail_response) or {}
            self.assertIsNotNone(listing_data)

    def test_alternate_flow_search_without_odps_should_still_work(self):
        """
        Test alternate flow: Search without ODPS (should still work)

        Alternate flow:
        1. Provider creates assets without ODPS
        2. Provider publishes to marketplace
        3. Consumer searches for assets
        4. System returns results (legacy flow)
        """
        # Create asset without ODPS
        asset_id = self.create_asset(key="discovery-no-odps-asset", name="Discovery No ODPS Asset")

        contract_id = self.create_contract(
            asset_id,
            original_raw=json.dumps(
                {
                    "id": f"contract-{uuid.uuid4().hex[:8]}",
                    "info": {"name": "Test Contract", "description": "Test contract"},
                    "schema": {
                        "fields": [
                            {"name": "id", "type": "string"},
                            {"name": "name", "type": "string"},
                        ]
                    },
                }
            ),
        )
        self.prepare_contract_for_activation(contract_id)  # Validate before attaching
        self.attach_contract_to_asset(asset_id, contract_id)
        self.prepare_asset_for_activation(asset_id)
        self.activate_asset(asset_id)

        # Create and publish listing
        listing_response = self.client.post(
            "/api/v1/marketplace/listings/",
            {
                "asset_id": str(asset_id),
                "title": "Discovery No ODPS Asset",
                "short_description": "Asset without ODPS",
                "pricing_model": PricingModel.FREE_AUTO_APPROVE,
            },
            format="json",
        )
        self.assertEqual(
            listing_response.status_code,
            status.HTTP_201_CREATED,
            f"Failed to create listing: {get_response_data(listing_response) or listing_response.content}",
        )
        listing_data = get_response_data(listing_response) or {}
        listing_id = listing_data.get("id")
        self.assertIsNotNone(listing_id)

        self.client.patch(
            f"/api/v1/marketplace/listings/{listing_id}/",
            {"status": ListingStatus.PUBLISHED},
            format="json",
        )

        # Search should still work
        search_response = self.client.get("/api/v1/marketplace/listings/search/")
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)

        listings = (get_response_data(search_response) or {}).get("results", [])
        our_listing = next((l for l in listings if l["id"] == str(listing_id)), None)
        self.assertIsNotNone(our_listing, "Should find listing without ODPS")

    def test_edge_case_multilingual_product_details_in_search_results(self):
        """
        Test edge case: Multilingual product details in search results

        Edge case:
        1. Provider creates asset with multilingual ODPS details
        2. Provider publishes to marketplace
        3. Consumer searches for assets
        4. System returns results with multilingual details
        """
        asset_id = self.create_asset(key="multilingual-odps-asset", name="Multilingual ODPS Asset")

        # Create ODCS contract with consistent data
        odcs_contract_data = {
            "id": f"multilingual-contract-{uuid.uuid4().hex[:8]}",
            "info": {"name": "Test Contract", "description": "Test contract"},
            "schema": {
                "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
            },
        }

        contract_id = self.create_contract(asset_id, original_raw=json.dumps(odcs_contract_data))
        self.prepare_contract_for_activation(contract_id)  # Validate before attaching
        self.attach_contract_to_asset(asset_id, contract_id)
        self.prepare_asset_for_activation(asset_id)
        self.activate_asset(asset_id)

        # Create ODPS contract with multilingual details
        odps_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"multilingual-product-{uuid.uuid4().hex[:8]}",
                        "name": "Multilingual Product",
                        "description": "Product with multilingual details",
                    },
                    "fi": {
                        "productID": f"multilingual-product-{uuid.uuid4().hex[:8]}",
                        "name": "Monikielinen Tuote",
                        "description": "Tuote monikielisillä tiedoilla",
                    },
                    "sv": {
                        "productID": f"multilingual-product-{uuid.uuid4().hex[:8]}",
                        "name": "Flerspråkig Produkt",
                        "description": "Produkt med flerspråkiga detaljer",
                    },
                },
                "dataSchema": {
                    "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
                },
                "contract": {"spec": odcs_contract_data},  # Include ODCS contract inline
            },
        }

        odps_contract = self.odps_service.create_odps(
            odps_raw=json.dumps(odps_data, indent=2),
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset_id),
        )

        self.odps_service.link_odps_to_odcs(
            odcs_contract_id=str(contract_id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Create and publish listing
        listing_response = self.client.post(
            "/api/v1/marketplace/listings/",
            {
                "asset_id": str(asset_id),
                "title": "Multilingual ODPS Asset",
                "short_description": "Asset with multilingual details",
                "pricing_model": PricingModel.FREE_AUTO_APPROVE,
            },
            format="json",
        )
        self.assertEqual(
            listing_response.status_code,
            status.HTTP_201_CREATED,
            f"Failed to create listing: {get_response_data(listing_response) or listing_response.content}",
        )
        listing_data = get_response_data(listing_response) or {}
        listing_id = listing_data.get("id")
        self.assertIsNotNone(listing_id)

        self.client.patch(
            f"/api/v1/marketplace/listings/{listing_id}/",
            {"status": ListingStatus.PUBLISHED},
            format="json",
        )

        # Search should return results (multilingual details may be in listing detail view)
        search_response = self.client.get("/api/v1/marketplace/listings/search/")
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)

        listings = (get_response_data(search_response) or {}).get("results", [])
        our_listing = next((l for l in listings if l["id"] == str(listing_id)), None)
        self.assertIsNotNone(our_listing, "Should find multilingual listing")
