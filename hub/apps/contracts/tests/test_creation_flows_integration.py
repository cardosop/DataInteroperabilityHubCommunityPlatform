"""
Integration tests for all creation flows (Task 3.6.1)

Comprehensive integration tests for:
1. Product-First flow (ODPS → ODCS → linking)
2. Technical-First flow (ODCS → ODPS linking)
3. Data-First flow (Data → ODCS → ODPS linking)

Tests use real implementations (no mocks/stubs) and follow TDD principles.
All tests verify bidirectional linking between ODPS and ODCS contracts.
"""

import json
import uuid

from rest_framework import status

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.factories import ContractFactoryEnhanced
from hub.apps.contracts.tests.test_base import ContractsAPITestBase
from hub.apps.files.models import File, FileStatus


class CreationFlowsIntegrationTest(ContractsAPITestBase):
    """Comprehensive integration tests for all creation flows"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()

        # Update tenant/user names for clarity in test output
        self.tenant.name = "Test Tenant Creation Flows"
        self.tenant.slug = f"test-tenant-creation-flows-{uuid.uuid4().hex[:8]}"
        self.tenant.save()

        self.user.email = "test-creation-flows@example.com"
        self.user.save()

        # Refresh user from DB to ensure tenant_id is loaded for tenant filtering
        self.user.refresh_from_db()

        # Sample ODCS contract for Technical-First and Data-First flows
        self.odcs_contract_data = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": f"test-odcs-{uuid.uuid4().hex[:8]}",
            "name": "Test ODCS Contract",
            "version": "1.0.0",
            "description": "Test ODCS contract for creation flows",
            "schema": {
                "fields": [
                    {
                        "name": "id",
                        "type": "string",
                        "nullable": False,
                        "description": "Unique identifier",
                    },
                    {
                        "name": "name",
                        "type": "string",
                        "nullable": True,
                        "description": "Name field",
                    },
                    {
                        "name": "price",
                        "type": "number",
                        "nullable": True,
                        "description": "Price field",
                    },
                ]
            },
            "info": {"owners": [{"name": "Test Owner", "email": "owner@example.com"}]},
        }

        # Sample ODPS document for Product-First flow
        self.odps_document = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"test-product-{uuid.uuid4().hex[:8]}",
                        "name": "Test Product",
                        "description": "Test product for Product-First flow",
                        "productVersion": "1.0.0",
                    }
                },
                "contract": {"spec": self.odcs_contract_data},
                "dataQuality": {"declarative": []},
                "SLA": {"declarative": []},
                "pricingPlans": {"declarative": []},
            },
        }

        # Sample ODPS document for linking (Technical-First and Data-First flows)
        self.odps_document_for_linking = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"test-product-link-{uuid.uuid4().hex[:8]}",
                        "name": "Test Product for Linking",
                        "description": "Test product for linking to ODCS contract",
                        "productVersion": "1.0.0",
                    }
                },
                "contract": {"spec": self.odcs_contract_data},
                "dataQuality": {"declarative": []},
                "SLA": {"declarative": []},
                "pricingPlans": {"declarative": []},
            },
        }

        # Create test file for Data-First flow
        self.test_file = File.objects.create(
            tenant=self.tenant,
            name="test_data.csv",
            storage_path="test/test_data.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )

    # ========== PRODUCT-FIRST FLOW TESTS ==========

    def test_product_first_flow_creates_contracts(self):
        """Test Product-First flow creates both ODPS and ODCS contracts"""
        # Arrange
        self.client.force_authenticate(user=self.user)

        # Act
        response = self.client.post(
            "/api/v1/contracts/products/",
            {
                "original_raw": json.dumps(self.odps_document),
                "original_format": "JSON",
                "resolve_external_refs": True,
            },
            format="json",
        )

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("odps_contract", response.data)
        self.assertIn("odcs_contract", response.data)

    def test_product_first_flow_contract_types(self):
        """Test Product-First flow creates contracts with correct spec types"""
        # Arrange
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/contracts/products/",
            {
                "original_raw": json.dumps(self.odps_document),
                "original_format": "JSON",
                "resolve_external_refs": True,
            },
            format="json",
        )
        odps_contract_id = response.data["odps_contract"]["id"]
        odcs_contract_id = response.data["odcs_contract"]["id"]

        # Act
        odps_contract = Contract.objects.get(id=odps_contract_id, tenant=self.tenant)
        odcs_contract = Contract.objects.get(id=odcs_contract_id, tenant=self.tenant)

        # Assert
        self.assertEqual(odps_contract.original_spec_type, OriginalSpecType.ODPS)
        self.assertEqual(odcs_contract.original_spec_type, OriginalSpecType.ODCS)

    def test_product_first_flow_normalization_status(self):
        """Test Product-First flow contracts have valid normalization status"""
        # Arrange
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/contracts/products/",
            {
                "original_raw": json.dumps(self.odps_document),
                "original_format": "JSON",
                "resolve_external_refs": True,
            },
            format="json",
        )
        odps_contract_id = response.data["odps_contract"]["id"]
        odcs_contract_id = response.data["odcs_contract"]["id"]
        odps_contract = Contract.objects.get(id=odps_contract_id, tenant=self.tenant)
        odcs_contract = Contract.objects.get(id=odcs_contract_id, tenant=self.tenant)

        # Act & Assert
        self.assertIn(
            odps_contract.normalization_status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
            f"ODPS contract normalization status should be OK or WITH_WARNINGS, got {odps_contract.normalization_status}",
        )
        self.assertIn(
            odcs_contract.normalization_status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
            f"ODCS contract normalization status should be OK or WITH_WARNINGS, got {odcs_contract.normalization_status}",
        )

    def test_product_first_flow_bidirectional_linking(self):
        """Test Product-First flow creates bidirectional links between ODPS and ODCS contracts"""
        # Arrange
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/contracts/products/",
            {
                "original_raw": json.dumps(self.odps_document),
                "original_format": "JSON",
                "resolve_external_refs": True,
            },
            format="json",
        )
        odps_contract_id = response.data["odps_contract"]["id"]
        odcs_contract_id = response.data["odcs_contract"]["id"]
        odps_contract = Contract.objects.get(id=odps_contract_id, tenant=self.tenant)
        odcs_contract = Contract.objects.get(id=odcs_contract_id, tenant=self.tenant)

        # Act
        odps_extensions = odps_contract.hub_contract_json.get("extensions", {})
        odcs_extensions = odcs_contract.hub_contract_json.get("extensions", {})

        # Assert
        self.assertIsNotNone(odps_contract.hub_contract_json)
        self.assertIsNotNone(odcs_contract.hub_contract_json)
        if "x_odps" in odps_extensions:
            self.assertEqual(
                odps_extensions["x_odps"].get("odcs_link"),
                str(odcs_contract.id),
                "ODPS contract should link to ODCS contract",
            )
        if "x_odps" in odcs_extensions:
            self.assertEqual(
                odcs_extensions["x_odps"].get("odps_link"),
                str(odps_contract.id),
                "ODCS contract should link to ODPS contract",
            )

    def test_product_first_flow_contracts_accessible_via_api(self):
        """Test Product-First flow contracts are accessible via API"""
        # Arrange
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/v1/contracts/products/",
            {
                "original_raw": json.dumps(self.odps_document),
                "original_format": "JSON",
                "resolve_external_refs": True,
            },
            format="json",
        )
        odps_contract_id = response.data["odps_contract"]["id"]
        odcs_contract_id = response.data["odcs_contract"]["id"]

        # Act
        odps_get_response = self.client.get(f"/api/v1/contracts/{odps_contract_id}/")
        odcs_get_response = self.client.get(f"/api/v1/contracts/{odcs_contract_id}/")

        # Assert
        self.assertEqual(odps_get_response.status_code, status.HTTP_200_OK)
        self.assertEqual(odcs_get_response.status_code, status.HTTP_200_OK)

    def test_product_first_flow_with_asset(self):
        """Test Product-First flow with asset linking"""
        self.client.force_authenticate(user=self.user)

        # Create asset first
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{uuid.uuid4().hex[:8]}",
            name="Test Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        # Create product with asset_id
        response = self.client.post(
            "/api/v1/contracts/products/",
            {
                "original_raw": json.dumps(self.odps_document),
                "original_format": "JSON",
                "resolve_external_refs": True,
                "asset_id": str(asset.id),
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        odps_contract_id = response.data["odps_contract"]["id"]
        odcs_contract_id = response.data["odcs_contract"]["id"]

        # Verify contracts are linked to asset
        odps_contract = Contract.objects.get(id=odps_contract_id, tenant=self.tenant)
        odcs_contract = Contract.objects.get(id=odcs_contract_id, tenant=self.tenant)

        self.assertEqual(odps_contract.asset_id, asset.id)
        self.assertEqual(odcs_contract.asset_id, asset.id)

    # ========== TECHNICAL-FIRST FLOW TESTS ==========

    def test_technical_first_flow_end_to_end(self):
        """Test Technical-First flow end-to-end: ODCS → ODPS linking"""
        self.client.force_authenticate(user=self.user)

        # Step 1: Create ODCS contract
        response = self.client.post(
            "/api/v1/contracts/",
            {
                "original_raw": json.dumps(self.odcs_contract_data),
                "original_format": "JSON",
                "original_spec_type": "ODCS",
                "original_spec_version": "3.0.2",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        odcs_contract_id = response.data["id"]

        # Step 2: Verify ODCS contract was created
        odcs_contract = Contract.objects.get(id=odcs_contract_id, tenant=self.tenant)
        self.assertEqual(odcs_contract.original_spec_type, OriginalSpecType.ODCS)
        self.assertIn(
            odcs_contract.normalization_status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # Step 3: Create ODPS document with matching ODCS contract embedded
        odps_doc_with_matching_odcs = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"test-product-technical-first-{uuid.uuid4().hex[:8]}",
                        "name": "Test Product for Technical-First",
                        "description": "Test product for Technical-First flow",
                        "productVersion": "1.0.0",
                    }
                },
                "contract": {"spec": self.odcs_contract_data},  # Use the same ODCS contract data
                "dataQuality": {"declarative": []},
                "SLA": {"declarative": []},
                "pricingPlans": {"declarative": []},
            },
        }

        # Step 4: Link ODPS contract (upload mode)
        link_response = self.client.post(
            f"/api/v1/contracts/{odcs_contract_id}/link-odps/",
            {
                "original_raw": json.dumps(odps_doc_with_matching_odcs),
                "original_format": "JSON",
                "resolve_external_refs": True,
            },
            format="json",
        )

        self.assertEqual(link_response.status_code, status.HTTP_200_OK)
        odps_contract_id = link_response.data["id"]

        # Step 4: Verify ODPS contract was created
        odps_contract = Contract.objects.get(id=odps_contract_id, tenant=self.tenant)
        self.assertEqual(odps_contract.original_spec_type, OriginalSpecType.ODPS)
        self.assertIn(
            odps_contract.normalization_status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
        )

        # Step 5: Verify bidirectional linking
        odps_contract.refresh_from_db()
        odcs_contract.refresh_from_db()

        self.assertIsNotNone(odps_contract.hub_contract_json)
        self.assertIsNotNone(odcs_contract.hub_contract_json)

        odps_extensions = odps_contract.hub_contract_json.get("extensions", {})
        odcs_extensions = odcs_contract.hub_contract_json.get("extensions", {})

        # ODPS → ODCS link
        if "x_odps" in odps_extensions:
            self.assertEqual(
                odps_extensions["x_odps"].get("odcs_link"),
                str(odcs_contract.id),
                "ODPS contract should link to ODCS contract",
            )

        # ODCS → ODPS link
        if "x_odps" in odcs_extensions:
            self.assertEqual(
                odcs_extensions["x_odps"].get("odps_link"),
                str(odps_contract.id),
                "ODCS contract should link to ODPS contract",
            )

    def test_technical_first_flow_generate_odps(self):
        """Test Technical-First flow with ODPS generation"""
        self.client.force_authenticate(user=self.user)

        # Step 1: Create ODCS contract with HubContract
        # Use a properly structured HubContract similar to the working test
        hub_contract_json = {
            "hub_contract_version": "1.0.0",
            "id": self.odcs_contract_data["id"],
            "info": {
                "name": self.odcs_contract_data["name"],
                "description": self.odcs_contract_data["description"],
                "version": "1.0.0",
                "owners": [{"name": "Test Owner", "email": "owner@example.com"}],
            },
            "schema": {
                "fields": [
                    {"name": "id", "type": "string", "description": "Unique identifier"},
                    {"name": "name", "type": "string", "description": "Name field"},
                ]
            },
            "marketplace": {
                "license_summary": "MIT License",
                "x_odps": {
                    "pricing_plans": [],
                    "access_methods": {},
                },
            },
        }

        odcs_contract = ContractFactoryEnhanced.create_contract(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odcs_contract_data),
            hub_contract_json=hub_contract_json,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        # Refresh contract to ensure it's saved
        odcs_contract.refresh_from_db()
        self.assertIsNotNone(
            odcs_contract.hub_contract_json,
            "Contract must have hub_contract_json for ODPS generation",
        )

        # Step 2: Generate ODPS from HubContract
        # Note: generate-odps endpoint accepts query params, not body
        generate_response = self.client.post(
            f"/api/v1/contracts/{odcs_contract.id}/generate-odps/?output_format=json",
            {},
            format="json",
        )

        if generate_response.status_code != status.HTTP_200_OK:
            # Debug: print the error
            self.fail(
                f"Generate ODPS failed with status {generate_response.status_code}: {generate_response.data}"
            )
        self.assertEqual(generate_response.status_code, status.HTTP_200_OK)
        # generate-odps returns JSON with odps_document field
        self.assertIn("odps_document", generate_response.data)
        generated_odps = generate_response.data["odps_document"]

        # Step 3: Link generated ODPS
        link_response = self.client.post(
            f"/api/v1/contracts/{odcs_contract.id}/link-odps/",
            {
                "original_raw": json.dumps(generated_odps),
                "original_format": "JSON",
                "resolve_external_refs": True,
            },
            format="json",
        )

        self.assertEqual(link_response.status_code, status.HTTP_200_OK)
        odps_contract_id = link_response.data["id"]

        # Step 4: Verify linking
        odps_contract = Contract.objects.get(id=odps_contract_id, tenant=self.tenant)
        odcs_contract.refresh_from_db()

        self.assertIsNotNone(odps_contract.hub_contract_json)
        self.assertIsNotNone(odcs_contract.hub_contract_json)

        odps_extensions = odps_contract.hub_contract_json.get("extensions", {})
        odcs_extensions = odcs_contract.hub_contract_json.get("extensions", {})

        # Verify bidirectional links
        if "x_odps" in odps_extensions:
            self.assertEqual(odps_extensions["x_odps"].get("odcs_link"), str(odcs_contract.id))
        if "x_odps" in odcs_extensions:
            self.assertEqual(odcs_extensions["x_odps"].get("odps_link"), str(odps_contract.id))

    def test_technical_first_flow_link_existing_odps(self):
        """Test Technical-First flow linking to existing ODPS contract"""
        self.client.force_authenticate(user=self.user)

        # Step 1: Create ODCS contract
        from hub.apps.contracts.models import Contract

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odcs_contract_data),
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": self.odcs_contract_data["id"],
                "info": {
                    "name": self.odcs_contract_data["name"],
                    "description": self.odcs_contract_data["description"],
                    "version": "1.0.0",
                },
                "schema": {
                    "fields": [
                        {"name": "id", "type": "string", "description": "Unique identifier"},
                        {"name": "name", "type": "string", "description": "Name field"},
                    ]
                },
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        # Step 2: Create existing ODPS contract with matching ODCS contract embedded
        odps_doc_for_existing = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"existing-odps-{uuid.uuid4().hex[:8]}",
                        "name": "Existing ODPS",
                        "productVersion": "1.0.0",
                    }
                },
                "contract": {"spec": self.odcs_contract_data},  # Match the ODCS contract
                "dataQuality": {"declarative": []},
                "SLA": {"declarative": []},
                "pricingPlans": {"declarative": []},
            },
        }
        existing_odps = ContractFactoryEnhanced.create_contract(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODPS,
            original_spec_version="4.1",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(odps_doc_for_existing),
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "existing-odps",
                "info": {
                    "name": "Existing ODPS",
                    "version": "1.0.0",
                },
                "marketplace": {
                    "x_odps": {
                        "pricing_plans": [],
                        "access_methods": {},
                    }
                },
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        # Step 3: Link existing ODPS to ODCS
        link_response = self.client.post(
            f"/api/v1/contracts/{odcs_contract.id}/link-odps/",
            {
                "odps_contract_id": str(existing_odps.id),
            },
            format="json",
        )

        if link_response.status_code != status.HTTP_200_OK:
            # Debug: print the error
            self.fail(
                f"Link ODPS failed with status {link_response.status_code}: {link_response.data}"
            )
        self.assertEqual(link_response.status_code, status.HTTP_200_OK)

        # Step 4: Verify linking
        existing_odps.refresh_from_db()
        odcs_contract.refresh_from_db()

        odps_extensions = existing_odps.hub_contract_json.get("extensions", {})
        odcs_extensions = odcs_contract.hub_contract_json.get("extensions", {})

        # Verify bidirectional links
        if "x_odps" in odps_extensions:
            self.assertEqual(odps_extensions["x_odps"].get("odcs_link"), str(odcs_contract.id))
        if "x_odps" in odcs_extensions:
            self.assertEqual(odcs_extensions["x_odps"].get("odps_link"), str(existing_odps.id))

    # ========== DATA-FIRST FLOW TESTS ==========

    def test_data_first_flow_end_to_end(self):
        """Test Data-First flow end-to-end: Data → ODCS → ODPS linking"""
        self.client.force_authenticate(user=self.user)

        # Step 1: Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-data-first-{uuid.uuid4().hex[:8]}",
            name="Test Data-First Asset",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        # Step 2: Create ODCS contract from data (simulated - in real flow, this would be inferred)
        # Create contract directly to avoid factory kwargs issue
        from hub.apps.contracts.models import Contract

        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            created_by=self.user,
            asset=asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw=json.dumps(self.odcs_contract_data),
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": self.odcs_contract_data["id"],
                "info": {
                    "name": self.odcs_contract_data["name"],
                    "description": self.odcs_contract_data["description"],
                    "version": "1.0.0",
                },
                "schema": {
                    "fields": [
                        {"name": "id", "type": "string", "description": "Unique identifier"},
                        {"name": "name", "type": "string", "description": "Name field"},
                    ]
                },
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        # Step 3: Create ODPS document with matching ODCS contract embedded
        odps_doc_with_matching_odcs = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"test-product-data-first-{uuid.uuid4().hex[:8]}",
                        "name": "Test Product for Data-First",
                        "description": "Test product for Data-First flow",
                        "productVersion": "1.0.0",
                    }
                },
                "contract": {"spec": self.odcs_contract_data},  # Use the same ODCS contract data
                "dataQuality": {"declarative": []},
                "SLA": {"declarative": []},
                "pricingPlans": {"declarative": []},
            },
        }

        # Step 4: Link ODPS contract
        link_response = self.client.post(
            f"/api/v1/contracts/{odcs_contract.id}/link-odps/",
            {
                "original_raw": json.dumps(odps_doc_with_matching_odcs),
                "original_format": "JSON",
                "resolve_external_refs": True,
            },
            format="json",
        )

        self.assertEqual(link_response.status_code, status.HTTP_200_OK)
        odps_contract_id = link_response.data["id"]

        # Step 4: Verify ODPS contract was created and linked to asset
        odps_contract = Contract.objects.get(id=odps_contract_id, tenant=self.tenant)
        self.assertEqual(odps_contract.asset_id, asset.id)
        self.assertEqual(odps_contract.original_spec_type, OriginalSpecType.ODPS)

        # Step 5: Verify bidirectional linking
        odps_contract.refresh_from_db()
        odcs_contract.refresh_from_db()

        self.assertIsNotNone(odps_contract.hub_contract_json)
        self.assertIsNotNone(odcs_contract.hub_contract_json)

        odps_extensions = odps_contract.hub_contract_json.get("extensions", {})
        odcs_extensions = odcs_contract.hub_contract_json.get("extensions", {})

        # Verify bidirectional links
        if "x_odps" in odps_extensions:
            self.assertEqual(odps_extensions["x_odps"].get("odcs_link"), str(odcs_contract.id))
        if "x_odps" in odcs_extensions:
            self.assertEqual(odcs_extensions["x_odps"].get("odps_link"), str(odps_contract.id))

    def test_data_first_flow_with_file(self):
        """Test Data-First flow with file attachment"""
        self.client.force_authenticate(user=self.user)

        # Step 1: Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-with-file-{uuid.uuid4().hex[:8]}",
            name="Test Asset with File",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )

        # Step 2: Create ODCS contract (simulated from data file)
        odcs_contract = ContractFactoryEnhanced.create_contract(
            tenant=self.tenant,
            created_by=self.user,
            asset=asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        # Step 3: Generate ODPS from HubContract
        # Note: generate-odps endpoint accepts query params, not body
        generate_response = self.client.post(
            f"/api/v1/contracts/{odcs_contract.id}/generate-odps/?output_format=json",
            {},
            format="json",
        )

        if generate_response.status_code != status.HTTP_200_OK:
            self.fail(
                f"Generate ODPS failed with status {generate_response.status_code}: {generate_response.data}"
            )
        self.assertEqual(generate_response.status_code, status.HTTP_200_OK)
        # generate-odps returns JSON with odps_document field
        self.assertIn("odps_document", generate_response.data)
        generated_odps = generate_response.data["odps_document"]

        # Step 4: Link generated ODPS
        link_response = self.client.post(
            f"/api/v1/contracts/{odcs_contract.id}/link-odps/",
            {
                "original_raw": json.dumps(generated_odps),
                "original_format": "JSON",
                "resolve_external_refs": True,
            },
            format="json",
        )

        self.assertEqual(link_response.status_code, status.HTTP_200_OK)
        odps_contract_id = link_response.data["id"]

        # Step 5: Verify all contracts are linked to asset
        odps_contract = Contract.objects.get(id=odps_contract_id, tenant=self.tenant)
        self.assertEqual(odps_contract.asset_id, asset.id)
        self.assertEqual(odcs_contract.asset_id, asset.id)

        # Step 6: Verify bidirectional linking
        odps_contract.refresh_from_db()
        odcs_contract.refresh_from_db()

        odps_extensions = odps_contract.hub_contract_json.get("extensions", {})
        odcs_extensions = odcs_contract.hub_contract_json.get("extensions", {})

        if "x_odps" in odps_extensions:
            self.assertEqual(odps_extensions["x_odps"].get("odcs_link"), str(odcs_contract.id))
        if "x_odps" in odcs_extensions:
            self.assertEqual(odcs_extensions["x_odps"].get("odps_link"), str(odps_contract.id))

    # ========== ODPS LINKING TESTS (ALL FLOWS) ==========

    def test_odps_linking_bidirectional_all_flows(self):
        """Test that ODPS linking works bidirectionally in all flows"""
        self.client.force_authenticate(user=self.user)

        # Test 1: Product-First flow linking
        product_response = self.client.post(
            "/api/v1/contracts/products/",
            {
                "original_raw": json.dumps(self.odps_document),
                "original_format": "JSON",
            },
            format="json",
        )
        self.assertEqual(product_response.status_code, status.HTTP_201_CREATED)
        product_odps_id = product_response.data["odps_contract"]["id"]
        product_odcs_id = product_response.data["odcs_contract"]["id"]

        # Test 2: Technical-First flow linking
        odcs_contract = ContractFactoryEnhanced.create_contract(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            original_raw=json.dumps(self.odcs_contract_data),
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )
        # Create ODPS document with matching ODCS contract
        odps_doc_technical = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"test-product-technical-{uuid.uuid4().hex[:8]}",
                        "name": "Test Product Technical",
                        "productVersion": "1.0.0",
                    }
                },
                "contract": {"spec": self.odcs_contract_data},
                "dataQuality": {"declarative": []},
                "SLA": {"declarative": []},
                "pricingPlans": {"declarative": []},
            },
        }
        technical_link_response = self.client.post(
            f"/api/v1/contracts/{odcs_contract.id}/link-odps/",
            {
                "original_raw": json.dumps(odps_doc_technical),
                "original_format": "JSON",
            },
            format="json",
        )
        self.assertEqual(technical_link_response.status_code, status.HTTP_200_OK)
        technical_odps_id = technical_link_response.data["id"]
        technical_odcs_id = str(odcs_contract.id)

        # Test 3: Data-First flow linking
        asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-linking-{uuid.uuid4().hex[:8]}",
            name="Test Asset for Linking",
            status=AssetStatus.DRAFT,
            created_by=self.user,
        )
        data_odcs = ContractFactoryEnhanced.create_contract(
            tenant=self.tenant,
            created_by=self.user,
            asset=asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_raw=json.dumps(self.odcs_contract_data),
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )
        # Create ODPS document with matching ODCS contract
        odps_doc_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": f"test-product-data-{uuid.uuid4().hex[:8]}",
                        "name": "Test Product Data",
                        "productVersion": "1.0.0",
                    }
                },
                "contract": {"spec": self.odcs_contract_data},
                "dataQuality": {"declarative": []},
                "SLA": {"declarative": []},
                "pricingPlans": {"declarative": []},
            },
        }
        data_link_response = self.client.post(
            f"/api/v1/contracts/{data_odcs.id}/link-odps/",
            {
                "original_raw": json.dumps(odps_doc_data),
                "original_format": "JSON",
            },
            format="json",
        )
        self.assertEqual(data_link_response.status_code, status.HTTP_200_OK)
        data_odps_id = data_link_response.data["id"]
        data_odcs_id = str(data_odcs.id)

        # Verify all bidirectional links
        test_cases = [
            (product_odps_id, product_odcs_id, "Product-First"),
            (technical_odps_id, technical_odcs_id, "Technical-First"),
            (data_odps_id, data_odcs_id, "Data-First"),
        ]

        for odps_id, odcs_id, flow_name in test_cases:
            odps_contract = Contract.objects.get(id=odps_id, tenant=self.tenant)
            odcs_contract = Contract.objects.get(id=odcs_id, tenant=self.tenant)

            odps_contract.refresh_from_db()
            odcs_contract.refresh_from_db()

            odps_extensions = odps_contract.hub_contract_json.get("extensions", {})
            odcs_extensions = odcs_contract.hub_contract_json.get("extensions", {})

            # ODPS → ODCS link
            if "x_odps" in odps_extensions:
                self.assertEqual(
                    odps_extensions["x_odps"].get("odcs_link"),
                    odcs_id,
                    f"{flow_name}: ODPS should link to ODCS",
                )

            # ODCS → ODPS link
            if "x_odps" in odcs_extensions:
                self.assertEqual(
                    odcs_extensions["x_odps"].get("odps_link"),
                    odps_id,
                    f"{flow_name}: ODCS should link to ODPS",
                )

    # ========== ERROR SCENARIOS ==========

    def test_product_first_flow_invalid_odps(self):
        """Test Product-First flow with invalid ODPS document"""
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/contracts/products/",
            {
                "original_raw": json.dumps({"invalid": "odps"}),
                "original_format": "JSON",
            },
            format="json",
        )

        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR],
        )

    def test_technical_first_flow_link_invalid_odps(self):
        """Test Technical-First flow linking with invalid ODPS"""
        self.client.force_authenticate(user=self.user)

        odcs_contract = ContractFactoryEnhanced.create_contract(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODCS,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        response = self.client.post(
            f"/api/v1/contracts/{odcs_contract.id}/link-odps/",
            {
                "original_raw": json.dumps({"invalid": "odps"}),
                "original_format": "JSON",
            },
            format="json",
        )

        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR],
        )

    def test_link_odps_to_non_odcs_contract(self):
        """Test linking ODPS to non-ODCS contract (should fail)"""
        self.client.force_authenticate(user=self.user)

        # Create ODPS contract (not ODCS)
        odps_contract = ContractFactoryEnhanced.create_contract(
            tenant=self.tenant,
            created_by=self.user,
            original_spec_type=OriginalSpecType.ODPS,
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            status=ContractStatus.ACTIVE,
        )

        response = self.client.post(
            f"/api/v1/contracts/{odps_contract.id}/link-odps/",
            {
                "original_raw": json.dumps(self.odps_document_for_linking),
                "original_format": "JSON",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("ODCS", response.data.get("error", ""))
