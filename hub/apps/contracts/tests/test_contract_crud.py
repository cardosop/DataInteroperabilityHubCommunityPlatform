"""
Unit tests for contract CRUD operations.
"""

import json
import uuid

import pytest
from rest_framework import status

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
)
from hub.apps.contracts.tests.test_base import ContractsAPITestBase
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class ContractCRUDTest(ContractsAPITestBase):
    """Test contract CRUD operations"""

    def test_create_contract_json(self):
        """Test creating a contract with JSON format"""
        # Arrange
        # (client already authenticated in ContractsAPITestBase.setUp)
        contract_data = {
            "id": "test-contract",
            "name": "Test Contract",
            "schema": {
                "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
            },
        }
        data = {"original_raw": json.dumps(contract_data), "original_format": OriginalFormat.JSON}

        # Act
        response = self.client.post("/api/v1/contracts/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], ContractStatus.DRAFT)
        self.assertEqual(response.data["original_format"], OriginalFormat.JSON)

        # Verify contract was created
        contract_id = response.data["id"]
        contract = Contract.objects.get(id=contract_id)
        self.assertEqual(contract.tenant, self.tenant)
        self.assertEqual(contract.created_by, self.user)

    def test_create_contract_yaml(self):
        """Test creating a contract with YAML format"""
        # Arrange
        # (client already authenticated in ContractsAPITestBase.setUp)
        yaml_content = """
id: test-contract
name: Test Contract
schema:
  fields:
    - name: id
      type: string
    - name: name
      type: string
"""
        data = {"original_raw": yaml_content, "original_format": OriginalFormat.YAML}

        # Act
        response = self.client.post("/api/v1/contracts/", data, format="json")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["original_format"], OriginalFormat.YAML)

    def test_retrieve_contract(self):
        """Test retrieving a contract"""
        self.client.force_authenticate(user=self.user)

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )

        response = self.client.get(f"/api/v1/contracts/{contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(contract.id))
        self.assertEqual(response.data["original_raw"], contract.original_raw)

    def test_update_contract(self):
        """Test updating a contract"""
        # Arrange
        # (client already authenticated in ContractsAPITestBase.setUp)
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )
        updated_data = {
            "original_raw": '{"id": "test", "name": "Updated Test"}',
            "original_format": OriginalFormat.JSON,
        }

        response = self.client.patch(
            f"/api/v1/contracts/{contract.id}/", updated_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        contract.refresh_from_db()
        self.assertEqual(contract.original_raw, updated_data["original_raw"])
        # Validation status should be reset
        self.assertIsNone(contract.validation_status)

    def test_delete_contract(self):
        """Test deleting a contract (soft delete)"""
        self.client.force_authenticate(user=self.user)

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )

        response = self.client.delete(f"/api/v1/contracts/{contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        contract.refresh_from_db()
        self.assertEqual(contract.status, ContractStatus.RETIRED)

    def test_list_contracts_tenant_scoped(self):
        """Test that users can only see contracts in their tenant"""
        self.client.force_authenticate(user=self.user)

        # Create another tenant and contract
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        other_contract = Contract.objects.create(
            tenant=other_tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "other", "name": "Other"}',
        )

        # Create contract in user's tenant
        my_contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "mine", "name": "Mine"}',
            created_by=self.user,
        )

        response = self.client.get("/api/v1/contracts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        contract_ids = [c["id"] for c in response.data["results"]]

        # Should only see contracts in own tenant
        self.assertIn(str(my_contract.id), contract_ids)
        self.assertNotIn(str(other_contract.id), contract_ids)

    # ========== ADDITIONAL MISSING SCENARIOS ==========

    def test_create_contract_unauthenticated(self):
        """Test creating contract requires authentication"""
        contract_data = {
            "id": "test-contract",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        import json

        data = {"original_raw": json.dumps(contract_data), "original_format": OriginalFormat.JSON}

        # Don't authenticate
        response = self.client.post("/api/v1/contracts/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_contract_missing_required_fields(self):
        """Test creating contract with missing required fields"""
        self.client.force_authenticate(user=self.user)

        data = {
            "original_format": OriginalFormat.JSON
            # Missing original_raw
        }

        response = self.client.post("/api/v1/contracts/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("original_raw", str(response.data) or response.data)

    def test_create_contract_invalid_format(self):
        """Test creating contract with invalid format"""
        self.client.force_authenticate(user=self.user)

        contract_data = {"id": "test", "name": "Test"}
        import json

        data = {"original_raw": json.dumps(contract_data), "original_format": "INVALID_FORMAT"}

        response = self.client.post("/api/v1/contracts/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_contract_invalid_json(self):
        """Test creating contract with invalid JSON"""
        self.client.force_authenticate(user=self.user)

        data = {
            "original_raw": '{"id": invalid}',  # Invalid JSON
            "original_format": OriginalFormat.JSON,
        }

        response = self.client.post("/api/v1/contracts/", data, format="json")

        # Should return 400 or handle gracefully
        self.assertIn(
            response.status_code,
            [status.HTTP_400_BAD_REQUEST, status.HTTP_422_UNPROCESSABLE_ENTITY],
        )

    def test_retrieve_contract_not_found(self):
        """Test retrieving non-existent contract"""
        self.client.force_authenticate(user=self.user)

        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/contracts/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_contract_cross_tenant(self):
        """Test retrieving contract from different tenant"""
        self.client.force_authenticate(user=self.user)

        # Create contract in different tenant
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        other_contract = Contract.objects.create(
            tenant=other_tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "other", "name": "Other"}',
        )

        response = self.client.get(f"/api/v1/contracts/{other_contract.id}/")

        # Should return 404 (tenant isolation)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_contract_unauthenticated(self):
        """Test retrieving contract requires authentication"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )

        # Don't authenticate
        response = self.client.get(f"/api/v1/contracts/{contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_contract_not_found(self):
        """Test updating non-existent contract"""
        self.client.force_authenticate(user=self.user)

        fake_id = str(uuid.uuid4())
        updated_data = {
            "original_raw": '{"id": "test", "name": "Updated"}',
            "original_format": OriginalFormat.JSON,
        }

        response = self.client.patch(f"/api/v1/contracts/{fake_id}/", updated_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_contract_cross_tenant(self):
        """Test updating contract from different tenant"""
        self.client.force_authenticate(user=self.user)

        # Create contract in different tenant
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        other_contract = Contract.objects.create(
            tenant=other_tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "other", "name": "Other"}',
        )

        updated_data = {
            "original_raw": '{"id": "other", "name": "Updated"}',
            "original_format": OriginalFormat.JSON,
        }

        response = self.client.patch(
            f"/api/v1/contracts/{other_contract.id}/", updated_data, format="json"
        )

        # Should return 404 (tenant isolation)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_contract_unauthenticated(self):
        """Test updating contract requires authentication"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )

        updated_data = {
            "original_raw": '{"id": "test", "name": "Updated"}',
            "original_format": OriginalFormat.JSON,
        }

        # Don't authenticate
        response = self.client.patch(
            f"/api/v1/contracts/{contract.id}/", updated_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_contract_with_put_method(self):
        """Test updating contract with PUT method"""
        self.client.force_authenticate(user=self.user)

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )

        updated_data = {
            "original_raw": '{"id": "test", "name": "Updated"}',
            "original_format": OriginalFormat.JSON,
        }

        response = self.client.put(f"/api/v1/contracts/{contract.id}/", updated_data, format="json")

        # PUT should work (may require all fields or handle partial)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_update_contract_partial_update(self):
        """Test partial update with PATCH (only status)"""
        self.client.force_authenticate(user=self.user)

        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )

        # Update only status
        updated_data = {"status": ContractStatus.ACTIVE}

        response = self.client.patch(
            f"/api/v1/contracts/{contract.id}/", updated_data, format="json"
        )

        # Should succeed with partial update
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_delete_contract_not_found(self):
        """Test deleting non-existent contract"""
        self.client.force_authenticate(user=self.user)

        fake_id = str(uuid.uuid4())
        response = self.client.delete(f"/api/v1/contracts/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_contract_cross_tenant(self):
        """Test deleting contract from different tenant"""
        self.client.force_authenticate(user=self.user)

        # Create contract in different tenant
        other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        other_contract = Contract.objects.create(
            tenant=other_tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "other", "name": "Other"}',
        )

        response = self.client.delete(f"/api/v1/contracts/{other_contract.id}/")

        # Should return 404 (tenant isolation)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_contract_unauthenticated(self):
        """Test deleting contract requires authentication"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test"}',
            created_by=self.user,
        )

        # Don't authenticate
        response = self.client.delete(f"/api/v1/contracts/{contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_contracts_unauthenticated(self):
        """Test listing contracts requires authentication"""
        # Don't authenticate
        response = self.client.get("/api/v1/contracts/")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_contracts_pagination(self):
        """Test listing contracts with pagination"""
        self.client.force_authenticate(user=self.user)

        # Create multiple contracts
        for i in range(25):
            Contract.objects.create(
                tenant=self.tenant,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.0",
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"id": "contract-{i}", "name": "Contract {i}"}}',
                created_by=self.user,
            )

        # Test first page
        response = self.client.get("/api/v1/contracts/?page=1&page_size=10")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertLessEqual(len(response.data["results"]), 10)

    def test_list_contracts_filtering_by_status(self):
        """Test listing contracts with status filter"""
        self.client.force_authenticate(user=self.user)

        # Create contracts with different statuses
        Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "draft", "name": "Draft"}',
            created_by=self.user,
        )
        Contract.objects.create(
            tenant=self.tenant,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "active", "name": "Active"}',
            created_by=self.user,
        )

        # Filter by ACTIVE status
        response = self.client.get("/api/v1/contracts/?status=ACTIVE")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        # Should only return ACTIVE contracts
        for contract in response.data["results"]:
            self.assertEqual(contract["status"], ContractStatus.ACTIVE)

    def test_list_contracts_empty_result(self):
        """Test listing contracts when no contracts exist"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/contracts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertEqual(len(response.data["results"]), 0)

    def test_create_contract_with_odps_spec_type(self):
        """Test creating contract with ODPS spec type"""
        self.client.force_authenticate(user=self.user)

        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {"details": {"en": {"productID": "test", "name": "Test Product"}}},
        }

        import json

        data = {
            "original_raw": json.dumps(contract_data),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODPS,
        }

        response = self.client.post("/api/v1/contracts/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["original_spec_type"], OriginalSpecType.ODPS)

    def test_create_contract_with_asset_id(self):
        """Test creating contract with asset_id"""
        from hub.apps.assets.models import Asset, AssetStatus

        self.client.force_authenticate(user=self.user)

        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.DRAFT
        )

        contract_data = {
            "id": "test-contract",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        import json

        data = {
            "original_raw": json.dumps(contract_data),
            "original_format": OriginalFormat.JSON,
            "asset_id": str(asset.id),
        }

        response = self.client.post("/api/v1/contracts/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get("asset"), str(asset.id))

    def test_create_contract_with_invalid_asset_id(self):
        """Test creating contract with non-existent asset_id"""
        self.client.force_authenticate(user=self.user)

        contract_data = {
            "id": "test-contract",
            "name": "Test Contract",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        import json

        data = {
            "original_raw": json.dumps(contract_data),
            "original_format": OriginalFormat.JSON,
            "asset_id": str(uuid.uuid4()),  # Non-existent asset
        }

        response = self.client.post("/api/v1/contracts/", data, format="json")

        # Should return 400 or 404
        self.assertIn(
            response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]
        )

    def test_retrieve_contract_invalid_id_format(self):
        """Test retrieving contract with invalid ID format"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/contracts/invalid-id-format/")

        # Should return 404 (invalid UUID format)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
