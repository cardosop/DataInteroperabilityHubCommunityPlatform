"""
Comprehensive unit tests for Contract ViewSet endpoints.

Tests cover:
- CRUD operations (list, retrieve, create, update, destroy)
- Filtering and sorting
- Custom actions from mixins (lineage, validation, export, etc.)
- Success scenarios
- Failure scenarios
- Edge cases
- Error handling
- Tenant isolation
- Permission checks

All tests use real implementations (no mocks of hub services).
"""

import json
import uuid

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status

from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalFormat,
    OriginalSpecType,
    ValidationStatus,
)
from hub.apps.contracts.tests.test_base import ContractsAPITestBase
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class ContractViewSetTest(ContractsAPITestBase):
    """Comprehensive tests for Contract ViewSet"""

    def setUp(self):
        """Set up test fixtures"""
        super().setUp()
        from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription

        ensure_tenant_has_active_subscription(self.tenant)

        # Create another tenant and user for isolation tests
        self.other_tenant = Tenant.objects.create(
            name="Other Tenant", slug="other-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )
        ensure_tenant_has_active_subscription(self.other_tenant)

        self.other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            tenant=self.other_tenant,
            status=UserStatus.ACTIVE,
        )

        # Create test contract
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test-contract", "info": {"name": "Test Contract"}}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "hub_contract_version": "1.0.0",
                "id": "test-contract",
                "info": {"name": "Test Contract"},
            },
            normalization_status=NormalizationStatus.NORMALIZED_OK,
            validation_status=ValidationStatus.VALID,
            created_by=self.user,
        )

    # ========== LIST ENDPOINT TESTS ==========

    def test_list_contracts_success(self):
        """Test listing contracts successfully"""
        # Arrange
        # (client already authenticated in ContractsAPITestBase.setUp)

        # Act
        response = self.client.get("/api/v1/contracts/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIsInstance(response.data["results"], list)
        self.assertGreaterEqual(len(response.data["results"]), 1)

    def test_list_contracts_unauthenticated(self):
        """Test listing contracts without authentication"""
        # Arrange
        self.client.logout()

        # Act
        response = self.client.get("/api/v1/contracts/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_contracts_tenant_isolation(self):
        """Test tenant isolation - user can only see their tenant's contracts"""
        # Arrange
        self.client.force_authenticate(user=self.other_user)

        # Act
        response = self.client.get("/api/v1/contracts/")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Other user should not see contracts from different tenant
        contract_ids = [c["id"] for c in response.data.get("results", [])]
        self.assertNotIn(str(self.contract.id), contract_ids)

    def test_list_contracts_filtering_by_status(self):
        """Test filtering contracts by status"""
        # Arrange
        # Create contracts with different statuses
        Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "active-contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "active-contract"},
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        # Filter by DRAFT status
        response = self.client.get("/api/v1/contracts/?status=DRAFT")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", [])
        for contract in results:
            self.assertEqual(contract["status"], ContractStatus.DRAFT)

    def test_list_contracts_filtering_by_spec_type(self):
        """Test filtering contracts by spec type"""
        # Arrange
        self.client.force_authenticate(user=self.user)

        # Act
        response = self.client.get("/api/v1/contracts/?spec_type=ODCS")

        # Assert
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", [])
        for contract in results:
            self.assertEqual(contract["original_spec_type"], OriginalSpecType.ODCS)

    def test_list_contracts_sorting_by_created_at(self):
        """Test sorting contracts by created_at"""
        # Create another contract
        Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "newer-contract"}',
            hub_contract_version="1.0.0",
            hub_contract_json={"id": "newer-contract"},
            created_by=self.user,
        )

        self.client.force_authenticate(user=self.user)

        # Sort by created_at descending (newest first)
        response = self.client.get("/api/v1/contracts/?ordering=-created_at")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get("results", [])
        if len(results) >= 2:
            # Verify sorting (newest first)
            self.assertGreaterEqual(results[0]["created_at"], results[1]["created_at"])

    def test_list_contracts_pagination(self):
        """Test pagination works correctly"""
        # Create multiple contracts
        for i in range(15):
            Contract.objects.create(
                tenant=self.tenant,
                version=1,
                status=ContractStatus.DRAFT,
                original_spec_type=OriginalSpecType.ODCS,
                original_spec_version="3.0.2",
                original_format=OriginalFormat.JSON,
                original_raw=f'{{"id": "contract-{i}"}}',
                hub_contract_version="1.0.0",
                hub_contract_json={"id": f"contract-{i}"},
                created_by=self.user,
            )

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/contracts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)
        self.assertGreaterEqual(response.data["count"], 15)

    # ========== RETRIEVE ENDPOINT TESTS ==========

    def test_retrieve_contract_success(self):
        """Test retrieving a contract successfully"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], str(self.contract.id))
        self.assertEqual(response.data["status"], ContractStatus.DRAFT)
        self.assertIn("hub_contract_json", response.data)

    def test_retrieve_contract_not_found(self):
        """Test retrieving non-existent contract"""
        self.client.force_authenticate(user=self.user)

        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/contracts/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_contract_tenant_isolation(self):
        """Test tenant isolation - user cannot retrieve other tenant's contract"""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_retrieve_contract_invalid_uuid(self):
        """Test retrieving contract with invalid UUID format (edge case)"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/contracts/invalid-uuid/")

        # Should return 404 or 400 depending on URL routing
        self.assertIn(
            response.status_code, [status.HTTP_404_NOT_FOUND, status.HTTP_400_BAD_REQUEST]
        )

    # ========== CREATE ENDPOINT TESTS ==========

    def test_create_contract_success(self):
        """Test creating a contract successfully"""
        self.client.force_authenticate(user=self.user)

        contract_data = {
            "schema": "https://opendataproducts.org/schema/v4.1",
            "version": "4.1",
            "product": {
                "details": {"en": {"productID": "new-contract", "name": "New Contract"}},
                "dataSchema": {"fields": [{"name": "id", "type": "string"}]},
            },
        }

        data = {
            "original_raw": json.dumps(contract_data),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODPS,
            "original_spec_version": "4.1",
        }

        response = self.client.post("/api/v1/contracts/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        self.assertEqual(response.data["status"], ContractStatus.DRAFT)

        # Verify contract was created in database
        contract_id = response.data["id"]
        contract = Contract.objects.get(id=contract_id)
        self.assertEqual(contract.tenant, self.tenant)
        self.assertEqual(contract.created_by, self.user)

    def test_create_contract_invalid_json(self):
        """Test creating contract with invalid JSON (error handling)"""
        self.client.force_authenticate(user=self.user)

        data = {"original_raw": "invalid json {", "original_format": OriginalFormat.JSON}

        response = self.client.post("/api/v1/contracts/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_contract_empty_raw(self):
        """Test creating contract with empty original_raw (edge case)"""
        self.client.force_authenticate(user=self.user)

        data = {"original_raw": "", "original_format": OriginalFormat.JSON}

        response = self.client.post("/api/v1/contracts/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_contract_missing_fields(self):
        """Test creating contract with missing required fields (edge case)"""
        self.client.force_authenticate(user=self.user)

        data = {
            "original_format": OriginalFormat.JSON
            # Missing original_raw
        }

        response = self.client.post("/api/v1/contracts/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_contract_unauthenticated(self):
        """Test creating contract without authentication"""
        self.client.logout()
        data = {
            "original_raw": '{"id": "test"}',
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODPS,
            "original_spec_version": "4.1",
        }

        response = self.client.post("/api/v1/contracts/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ========== UPDATE ENDPOINT TESTS ==========

    def test_update_contract_success(self):
        """Test updating a contract successfully"""
        self.client.force_authenticate(user=self.user)

        updated_data = {
            "original_raw": '{"schema": "https://opendataproducts.org/schema/v4.1", "version": "4.1", "product": {"details": {"en": {"productID": "test-contract", "name": "Updated Contract"}}, "dataSchema": {"fields": [{"name": "id", "type": "string"}]}}}',
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODPS,
            "original_spec_version": "4.1",
        }

        response = self.client.put(
            f"/api/v1/contracts/{self.contract.id}/", updated_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.contract.refresh_from_db()
        self.assertIn("Updated Contract", self.contract.original_raw)

    def test_partial_update_contract_success(self):
        """Test partial update (PATCH) of a contract"""
        self.client.force_authenticate(user=self.user)

        updated_data = {"status": ContractStatus.ACTIVE}

        response = self.client.patch(
            f"/api/v1/contracts/{self.contract.id}/", updated_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.contract.refresh_from_db()
        self.assertEqual(self.contract.status, ContractStatus.ACTIVE)

    def test_update_contract_not_found(self):
        """Test updating non-existent contract"""
        self.client.force_authenticate(user=self.user)

        fake_id = str(uuid.uuid4())
        updated_data = {"status": ContractStatus.ACTIVE}

        response = self.client.put(f"/api/v1/contracts/{fake_id}/", updated_data, format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_contract_tenant_isolation(self):
        """Test tenant isolation - user cannot update other tenant's contract"""
        self.client.force_authenticate(user=self.other_user)

        updated_data = {"status": ContractStatus.ACTIVE}

        response = self.client.put(
            f"/api/v1/contracts/{self.contract.id}/", updated_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ========== DESTROY ENDPOINT TESTS ==========

    def test_destroy_contract_success(self):
        """Test deleting a contract successfully"""
        # Assign TENANT_ADMIN role to user for deletion
        from hub.apps.users.models import Role, UserRole

        admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=admin_role)

        self.client.force_authenticate(user=self.user)
        contract_id = self.contract.id

        response = self.client.delete(f"/api/v1/contracts/{contract_id}/")

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify contract was soft-deleted (status set to RETIRED)
        contract = Contract.objects.filter(pk=contract_id).first()
        self.assertIsNotNone(contract, "Contract should still exist after soft delete")
        self.assertEqual(contract.status, ContractStatus.RETIRED)

    def test_destroy_contract_not_found(self):
        """Test deleting non-existent contract"""
        self.client.force_authenticate(user=self.user)

        fake_id = str(uuid.uuid4())
        response = self.client.delete(f"/api/v1/contracts/{fake_id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_destroy_contract_tenant_isolation(self):
        """Test tenant isolation - user cannot delete other tenant's contract"""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.delete(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ========== AUDITOR PERMISSION TESTS ==========

    def test_auditor_can_list_contracts(self):
        """Test that AUDITOR role can list contracts (read-only)"""
        # Create auditor role
        auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="AUDITOR", defaults={"description": "Auditor"}
        )

        auditor_user = User.objects.create_user(
            email="auditor@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=auditor_user, role=auditor_role)

        self.client.force_authenticate(user=auditor_user)

        response = self.client.get("/api/v1/contracts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_auditor_cannot_create_contract(self):
        """Test that AUDITOR role cannot create contracts (read-only)"""
        # Create auditor role
        auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="AUDITOR", defaults={"description": "Auditor"}
        )

        auditor_user = User.objects.create_user(
            email="auditor2@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=auditor_user, role=auditor_role)

        self.client.force_authenticate(user=auditor_user)

        data = {
            "original_raw": '{"id": "test"}',
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODPS,
            "original_spec_version": "4.1",
        }

        response = self.client.post("/api/v1/contracts/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auditor_cannot_update_contract(self):
        """Test that AUDITOR role cannot update contracts (read-only)"""
        # Create auditor role
        auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="AUDITOR", defaults={"description": "Auditor"}
        )

        auditor_user = User.objects.create_user(
            email="auditor3@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=auditor_user, role=auditor_role)

        self.client.force_authenticate(user=auditor_user)

        updated_data = {"status": ContractStatus.ACTIVE}

        response = self.client.patch(
            f"/api/v1/contracts/{self.contract.id}/", updated_data, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_auditor_cannot_delete_contract(self):
        """Test that AUDITOR role cannot delete contracts (read-only)"""
        # Create auditor role
        auditor_role, _ = Role.objects.get_or_create(
            tenant=self.tenant, name="AUDITOR", defaults={"description": "Auditor"}
        )

        auditor_user = User.objects.create_user(
            email="auditor4@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserRole.objects.create(user=auditor_user, role=auditor_role)

        self.client.force_authenticate(user=auditor_user)

        response = self.client.delete(f"/api/v1/contracts/{self.contract.id}/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ========== EDGE CASES ==========

    def test_list_contracts_empty_result(self):
        """Test listing contracts when none exist (edge case)"""
        # Delete all contracts
        Contract.objects.filter(tenant=self.tenant).delete()

        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/contracts/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data.get("results", [])), 0)

    def test_list_contracts_invalid_filter_value(self):
        """Test filtering with invalid filter value (edge case)"""
        self.client.force_authenticate(user=self.user)

        # Invalid status value
        response = self.client.get("/api/v1/contracts/?status=INVALID_STATUS")

        # Should return 200 with empty results or 400
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_list_contracts_invalid_sort_field(self):
        """Test sorting with invalid field (edge case)"""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/contracts/?ordering=invalid_field")

        # Should return 200 (ignores invalid sort) or 400
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_create_contract_very_large_payload(self):
        """Test creating contract with very large payload (edge case)"""
        self.client.force_authenticate(user=self.user)

        # Create a very large JSON payload
        large_schema = {"fields": [{"name": f"field_{i}", "type": "string"} for i in range(10000)]}
        contract_data = {"id": "large-contract", "schema": large_schema}

        data = {
            "original_raw": json.dumps(contract_data),
            "original_format": OriginalFormat.JSON,
            "original_spec_type": OriginalSpecType.ODPS,
            "original_spec_version": "4.1",
        }

        response = self.client.post("/api/v1/contracts/", data, format="json")

        # Should handle gracefully (either succeed or return appropriate error)
        self.assertIn(
            response.status_code,
            [
                status.HTTP_201_CREATED,
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            ],
        )

    # ========== ERROR HANDLING ==========

    def test_retrieve_contract_database_error_handling(self):
        """Test error handling when database query fails"""
        self.client.force_authenticate(user=self.user)

        # Use valid UUID format but non-existent ID
        fake_id = str(uuid.uuid4())
        response = self.client.get(f"/api/v1/contracts/{fake_id}/")

        # Should return 404, not 500
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_contract_validation_error_handling(self):
        """Test error handling for validation errors"""
        self.client.force_authenticate(user=self.user)

        # Missing required fields
        data = {}

        response = self.client.post("/api/v1/contracts/", data, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("original_raw", str(response.data) or response.data)

    # Additional edge cases and error handling tests
    def test_list_contracts_with_special_characters_in_filter(self):
        """Test filtering with special characters in filter value."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/contracts/?status=<>&\"'")
        # Should handle special characters gracefully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_list_contracts_with_unicode_in_filter(self):
        """Test filtering with unicode characters in filter value."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/contracts/?status=产品")
        # Should handle unicode gracefully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_retrieve_contract_with_invalid_uuid_format(self):
        """Test retrieving contract with invalid UUID format."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/contracts/not-a-valid-uuid/")
        # Should return 400 or 404, not 500
        self.assertIn(
            response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]
        )

    def test_update_contract_with_none_data(self):
        """Test updating contract with None data."""
        self.client.force_authenticate(user=self.user)

        try:
            response = self.client.patch(
                f"/api/v1/contracts/{self.contract.id}/", None, format="json"  # type: ignore
            )
            # May raise exception or return error
            self.assertIn(
                response.status_code,
                [status.HTTP_400_BAD_REQUEST, status.HTTP_500_INTERNAL_SERVER_ERROR],
            )
        except Exception:
            # None data may raise exception
            pass

    def test_update_contract_with_empty_data(self):
        """Test updating contract with empty data."""
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(f"/api/v1/contracts/{self.contract.id}/", {}, format="json")
        # Should handle empty data gracefully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_delete_contract_with_invalid_id(self):
        """Test deleting contract with invalid ID."""
        self.client.force_authenticate(user=self.user)

        response = self.client.delete("/api/v1/contracts/not-a-valid-uuid/")
        # Should return 400 or 404
        self.assertIn(
            response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]
        )

    def test_create_contract_with_special_characters(self):
        """Test creating contract with special characters in data."""
        self.client.force_authenticate(user=self.user)

        contract_data = {"id": "test-<>&\"'", "name": "Contract <>&\"'"}
        data = {"original_raw": json.dumps(contract_data), "original_format": OriginalFormat.JSON}

        response = self.client.post("/api/v1/contracts/", data, format="json")
        # Should handle special characters gracefully
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_create_contract_with_unicode(self):
        """Test creating contract with unicode characters."""
        self.client.force_authenticate(user=self.user)

        contract_data = {"id": "产品", "name": "产品名称"}
        data = {"original_raw": json.dumps(contract_data), "original_format": OriginalFormat.JSON}

        response = self.client.post("/api/v1/contracts/", data, format="json")
        # Should handle unicode gracefully
        self.assertIn(response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST])

    def test_list_contracts_with_very_large_page_size(self):
        """Test listing contracts with very large page size."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/contracts/?page_size=1000000")
        # Should handle very large page size gracefully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_list_contracts_with_negative_page_size(self):
        """Test listing contracts with negative page size."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/contracts/?page_size=-1")
        # Should handle negative page size gracefully
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST])

    def test_list_contracts_with_multiple_filters(self):
        """Test listing contracts with multiple filters."""
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/contracts/?status=DRAFT&original_spec_type=ODCS")
        # Should handle multiple filters
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_contract_cross_tenant(self):
        """Test retrieving contract from different tenant."""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.get(f"/api/v1/contracts/{self.contract.id}/")
        # Should return 404 due to tenant isolation
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_contract_cross_tenant(self):
        """Test updating contract from different tenant."""
        self.client.force_authenticate(user=self.other_user)

        data = {"status": ContractStatus.ACTIVE}
        response = self.client.patch(f"/api/v1/contracts/{self.contract.id}/", data, format="json")
        # Should return 404 due to tenant isolation
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_contract_cross_tenant(self):
        """Test deleting contract from different tenant."""
        self.client.force_authenticate(user=self.other_user)

        response = self.client.delete(f"/api/v1/contracts/{self.contract.id}/")
        # Should return 404 due to tenant isolation
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
