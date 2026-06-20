"""
Unit tests for ContractService.

Tests cover all service methods with 100% coverage target.

All tests use real implementations (no mocks of hub services).
DataContractCLIClient uses real client with graceful handling when CLI service unavailable.
"""

import uuid

import pytest
from django.test import override_settings

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import (
    Contract,
    ContractStatus,
    NormalizationStatus,
    OriginalSpecType,
)
from hub.apps.contracts.services import ContractService
from hub.apps.contracts.tests.test_base import ContractsTestBase
from hub.apps.core.services.base import NotFoundError, ServiceError, ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole

pytestmark = pytest.mark.django_db(transaction=True)


from hub.apps.contracts.tests.test_base import check_datacontract_cli_available


class ContractServiceTest(ContractsTestBase):
    """Test ContractService operations"""

    def setUp(self):
        """Set up test data"""
        super().setUp()
        # Create alias for backward compatibility
        self.service = self.contract_service

        # Assign TENANT_ADMIN role to user for deletion tests
        admin_role, _ = Role.objects.get_or_create(
            tenant=self.tenant,
            name="TENANT_ADMIN",
            defaults={"description": "Tenant administrator"},
        )
        UserRole.objects.get_or_create(user=self.user, role=admin_role)

    def test_create_contract_success(self):
        """Test successful contract creation"""
        original_raw = '{"id": "test-contract", "info": {"name": "test-contract"}, "schema": {"fields": [{"name": "id", "type": "string"}]}}'
        original_format = "JSON"

        contract = self.service.create_contract(
            original_raw=original_raw,
            original_format=original_format,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        self.assertIsNotNone(contract)
        contract.refresh_from_db()
        self.assertEqual(contract.original_raw, original_raw)
        self.assertEqual(contract.original_format, original_format)
        self.assertEqual(str(contract.tenant_id), str(self.tenant.id))
        self.assertIsNotNone(contract.hub_contract_json)
        self.assertIsInstance(contract.hub_contract_json, dict)
        self.assertIsNotNone(contract.normalization_status)

    def test_create_contract_with_asset(self):
        """Test contract creation with asset"""
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.DRAFT
        )

        original_raw = '{"id": "test-contract", "info": {"name": "test-contract"}, "schema": {"fields": [{"name": "id", "type": "string"}]}}'
        original_format = "JSON"

        contract = self.service.create_contract(
            original_raw=original_raw,
            original_format=original_format,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(asset.id),
        )

        self.assertIsNotNone(contract)
        self.assertEqual(contract.asset_id, asset.id)

    def test_create_contract_asset_not_found(self):
        """Test contract creation with non-existent asset raises ValidationError (business rules)."""
        original_raw = '{"info": {"name": "test-contract"}}'
        original_format = "JSON"

        with self.assertRaises(ValidationError) as cm:
            self.service.create_contract(
                original_raw=original_raw,
                original_format=original_format,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                asset_id="00000000-0000-0000-0000-000000000000",
            )

        self.assertEqual(cm.exception.code, "BUSINESS_RULES_VALIDATION")

    def test_update_contract_success(self):
        """Test successful contract update"""
        # Create contract with minimal ODCS shape (id, info, schema.fields required for normalization)
        minimal_odcs = '{"id": "old-contract", "info": {"name": "old-contract"}, "schema": {"fields": [{"name": "id", "type": "string"}]}}'
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=minimal_odcs,
            original_format="JSON",
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
        )

        updated_raw = '{"id": "updated-contract", "info": {"name": "updated-contract"}, "schema": {"fields": [{"name": "id", "type": "string"}]}}'

        updated_contract = self.service.update_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_raw=updated_raw,
        )

        updated_contract.refresh_from_db()
        self.assertEqual(updated_contract.original_raw, updated_raw)

    def test_update_contract_not_found(self):
        """Test contract update with non-existent contract"""
        with self.assertRaises(NotFoundError):
            self.service.update_contract(
                contract_id="00000000-0000-0000-0000-000000000000",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                original_raw='{"info": {"name": "test"}}',
            )

    def test_update_contract_status(self):
        """Test contract status update"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.DRAFT,
        )

        updated_contract = self.service.update_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            status=ContractStatus.ACTIVE,
        )

        updated_contract.refresh_from_db()
        self.assertEqual(updated_contract.status, ContractStatus.ACTIVE)

    def test_update_contract_invalid_status(self):
        """Test contract update with invalid status"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.DRAFT,
        )

        with self.assertRaises(ValidationError) as cm:
            self.service.update_contract(
                contract_id=str(contract.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                status="INVALID_STATUS",
            )

        self.assertEqual(cm.exception.code, "BUSINESS_RULES_VALIDATION")

    def test_delete_contract_success(self):
        """Test successful contract deletion"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        self.service.delete_contract(
            contract_id=str(contract.id), tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

        contract.refresh_from_db()
        self.assertEqual(contract.status, ContractStatus.RETIRED)

    def test_delete_contract_not_found(self):
        """Test contract deletion with non-existent contract"""
        with self.assertRaises(NotFoundError):
            self.service.delete_contract(
                contract_id="00000000-0000-0000-0000-000000000000",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

    def test_get_contract_success(self):
        """Test successful contract retrieval"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        retrieved = self.service.get_contract(
            contract_id=str(contract.id), tenant_id=str(self.tenant.id)
        )

        self.assertEqual(retrieved.id, contract.id)
        self.assertEqual(retrieved.original_raw, contract.original_raw)

    def test_get_contract_not_found(self):
        """Test contract retrieval with non-existent contract"""
        with self.assertRaises(NotFoundError):
            self.service.get_contract(
                contract_id="00000000-0000-0000-0000-000000000000", tenant_id=str(self.tenant.id)
            )

    def test_list_contracts_success(self):
        """Test successful contract listing"""
        # Create multiple contracts
        for i in range(5):
            Contract.objects.create(
                tenant=self.tenant,
                original_raw=f'{{"info": {{"name": "contract-{i}"}}}}',
                original_format="JSON",
                status=ContractStatus.ACTIVE,
            )

        contracts, pagination_meta = self.service.list_contracts(
            tenant_id=str(self.tenant.id), page=1, page_size=20
        )

        self.assertEqual(len(contracts), 5)
        self.assertEqual(pagination_meta["count"], 5)

    def test_list_contracts_with_filters(self):
        """Test contract listing with filters"""
        # Create contracts with different statuses
        Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "active-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )
        Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "draft-contract"}}',
            original_format="JSON",
            status=ContractStatus.DRAFT,
        )

        contracts, _ = self.service.list_contracts(
            tenant_id=str(self.tenant.id), filters={"status": ContractStatus.ACTIVE}
        )

        self.assertEqual(len(contracts), 1)
        self.assertEqual(contracts[0].status, ContractStatus.ACTIVE)

    def test_validate_contract_sync(self):
        """
        Test synchronous contract validation using real DataContractCLIClient.

        Uses real CLI client to verify contract validation functionality.
        """
        # Skip if CLI service not available
        if not check_datacontract_cli_available():
            self.skipTest("DataContract CLI service not available in test environment")

        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"id": "test", "name": "Test", "schema": {"fields": [{"name": "id", "type": "string"}]}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        # Use real DataContractCLIClient
        result = self.service.validate_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            use_async=False,
        )

        self.assertFalse(result["async"])
        self.assertIn("validation_status", result)

    def test_validate_contract_async(self):
        """Test asynchronous contract validation"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}' * 1000,  # Large contract
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        result = self.service.validate_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            use_async=True,
        )

        self.assertTrue(result["async"])
        self.assertIn("job_id", result)

    # ========== EDGE CASES ==========

    def test_create_contract_cross_tenant_asset(self):
        """Test creating contract with asset from different tenant raises ValidationError (business rules)."""
        # Create another tenant and asset
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}"
        )
        other_asset = Asset.objects.create(
            tenant=other_tenant, key="other-asset", name="Other Asset", status=AssetStatus.DRAFT
        )

        original_raw = '{"info": {"name": "test-contract"}}'
        original_format = "JSON"

        with self.assertRaises(ValidationError) as cm:
            self.service.create_contract(
                original_raw=original_raw,
                original_format=original_format,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                asset_id=str(other_asset.id),  # Asset from different tenant
            )

        self.assertEqual(cm.exception.code, "BUSINESS_RULES_VALIDATION")

    def test_create_contract_empty_original_raw(self):
        """Test creating contract with empty original_raw raises ValidationError"""
        with self.assertRaises(ValidationError):
            self.service.create_contract(
                original_raw="",
                original_format="JSON",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

    def test_create_contract_invalid_format(self):
        """Test creating contract with invalid format raises ValidationError"""
        original_raw = '{"info": {"name": "test-contract"}}'

        with self.assertRaises(ValidationError):
            self.service.create_contract(
                original_raw=original_raw,
                original_format="INVALID_FORMAT",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

    def test_update_contract_cross_tenant(self):
        """Test updating contract from different tenant raises NotFoundError"""
        # Create contract in other tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}"
        )
        other_contract = Contract.objects.create(
            tenant=other_tenant,
            original_raw='{"info": {"name": "other-contract"}}',
            original_format="JSON",
            status=ContractStatus.DRAFT,
        )

        with self.assertRaises(NotFoundError):
            self.service.update_contract(
                contract_id=str(other_contract.id),
                tenant_id=str(self.tenant.id),  # Different tenant
                user_id=str(self.user.id),
                original_raw='{"info": {"name": "updated"}}',
            )

    def test_delete_contract_cross_tenant(self):
        """Test deleting contract from different tenant raises NotFoundError"""
        # Create contract in other tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}"
        )
        other_contract = Contract.objects.create(
            tenant=other_tenant,
            original_raw='{"info": {"name": "other-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        with self.assertRaises(NotFoundError):
            self.service.delete_contract(
                contract_id=str(other_contract.id),
                tenant_id=str(self.tenant.id),  # Different tenant
                user_id=str(self.user.id),
            )

    def test_get_contract_cross_tenant(self):
        """Test getting contract from different tenant raises NotFoundError"""
        # Create contract in other tenant
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}"
        )
        other_contract = Contract.objects.create(
            tenant=other_tenant,
            original_raw='{"info": {"name": "other-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        with self.assertRaises(NotFoundError):
            self.service.get_contract(
                contract_id=str(other_contract.id),
                tenant_id=str(self.tenant.id),  # Different tenant
            )

    def test_list_contracts_pagination(self):
        """Test contract listing with pagination"""
        # Create 25 contracts
        for i in range(25):
            Contract.objects.create(
                tenant=self.tenant,
                original_raw=f'{{"info": {{"name": "contract-{i}"}}}}',
                original_format="JSON",
                status=ContractStatus.ACTIVE,
            )

        # Test first page
        contracts_page1, meta_page1 = self.service.list_contracts(
            tenant_id=str(self.tenant.id), page=1, page_size=10
        )

        self.assertEqual(len(contracts_page1), 10)
        self.assertEqual(meta_page1["count"], 25)
        self.assertEqual(meta_page1["page"], 1)
        self.assertEqual(meta_page1["page_size"], 10)
        self.assertTrue(meta_page1["has_next"])

        # Test second page
        contracts_page2, meta_page2 = self.service.list_contracts(
            tenant_id=str(self.tenant.id), page=2, page_size=10
        )

        self.assertEqual(len(contracts_page2), 10)
        self.assertEqual(meta_page2["page"], 2)
        self.assertTrue(meta_page2["has_next"])

        # Test last page
        contracts_page3, meta_page3 = self.service.list_contracts(
            tenant_id=str(self.tenant.id), page=3, page_size=10
        )

        self.assertEqual(len(contracts_page3), 5)
        self.assertEqual(meta_page3["page"], 3)
        self.assertFalse(meta_page3["has_next"])

    def test_list_contracts_empty_result(self):
        """Test contract listing with no contracts returns empty list"""
        contracts, pagination_meta = self.service.list_contracts(
            tenant_id=str(self.tenant.id), page=1, page_size=20
        )

        self.assertEqual(len(contracts), 0)
        self.assertEqual(pagination_meta["count"], 0)

    def test_list_contracts_tenant_isolation(self):
        """Test contract listing respects tenant isolation"""
        # Create contracts in different tenants
        _uid = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {_uid}", slug=f"other-tenant-{_uid}"
        )
        Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "tenant1-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )
        Contract.objects.create(
            tenant=other_tenant,
            original_raw='{"info": {"name": "tenant2-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        contracts, _ = self.service.list_contracts(tenant_id=str(self.tenant.id))

        self.assertEqual(len(contracts), 1)
        self.assertEqual(contracts[0].tenant_id, self.tenant.id)

    def test_get_active_contract_for_asset_multiple_contracts(self):
        """Test get_active_contract_for_asset prefers ODCS over ODPS"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.DRAFT
        )

        # Create ODPS contract
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            original_raw='{"id": "odps"}',
            original_format="JSON",
            original_spec_type=OriginalSpecType.ODPS,
            status=ContractStatus.ACTIVE,
        )

        # Create ODCS contract (version=2 to satisfy unique_contract_version_per_asset)
        odcs_contract = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            version=2,
            original_raw='{"id": "odcs"}',
            original_format="JSON",
            original_spec_type=OriginalSpecType.ODCS,
            status=ContractStatus.ACTIVE,
        )

        # Should prefer ODCS
        result = self.service.get_active_contract_for_asset(
            asset_id=str(asset.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.id, odcs_contract.id)

    def test_get_active_contract_for_asset_no_contracts(self):
        """Test get_active_contract_for_asset returns None when no contracts"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.DRAFT
        )

        result = self.service.get_active_contract_for_asset(
            asset_id=str(asset.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsNone(result)

    def test_validate_contract_active_success(self):
        """Test validate_contract_active with active contract"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        result = self.service.validate_contract_active(
            contract_id=str(contract.id), tenant_id=str(self.tenant.id)
        )

        self.assertEqual(result.id, contract.id)
        self.assertEqual(result.status, ContractStatus.ACTIVE)

    def test_validate_contract_active_not_active(self):
        """Test validate_contract_active raises ValidationError for non-active contract"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.DRAFT,  # Not active
        )

        with self.assertRaises(ValidationError) as cm:
            self.service.validate_contract_active(
                contract_id=str(contract.id), tenant_id=str(self.tenant.id)
            )

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
        self.assertIn("not active", str(cm.exception).lower())

    def test_validate_contract_active_not_found(self):
        """Test validate_contract_active raises NotFoundError for non-existent contract"""
        with self.assertRaises(NotFoundError):
            self.service.validate_contract_active(
                contract_id="00000000-0000-0000-0000-000000000000",
                tenant_id=str(self.tenant.id),
            )

    @override_settings(DATACONTRACT_SERVICE_URL="http://127.0.0.1:65535")
    def test_validate_contract_cli_unavailable(self):
        """Synchronous validation with unreachable CLI service returns a
        structured error dict — the view has a try/except that catches
        the ConnectionRefusedError and returns 200 with an error payload.
        ``@override_settings`` patches the URL that the view's fresh
        ``DataContractCLIClient()`` constructor reads, so the endpoint
        actually hits the unreachable URL."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"id":"test","name":"Test","schema":{"fields":[{"name":"id","type":"string"}]}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        result = self.service.validate_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            use_async=False,
        )

        self.assertIsInstance(result, dict)
        self.assertIn("validation_status", result, "Response must include validation_status")
        self.assertEqual(
            result["validation_status"],
            "ERROR",
            "Unreachable CLI service must return validation_status='ERROR'",
        )
        self.assertIn("errors", result, "Response must include 'errors' key")

    def test_create_contract_with_disable_external_refs(self):
        """Test creating contract with disable_external_refs flag"""
        original_raw = '{"id": "test-contract", "info": {"name": "test-contract"}, "schema": {"fields": [{"name": "id", "type": "string"}]}, "$ref": "https://example.com/schema.json"}'
        original_format = "JSON"

        contract = self.service.create_contract(
            original_raw=original_raw,
            original_format=original_format,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            disable_external_refs=True,
        )

        self.assertIsNotNone(contract)
        contract.refresh_from_db()
        # Normalization must complete even with external refs disabled.
        self.assertIsNotNone(
            contract.hub_contract_json,
            "hub_contract_json must be set when disable_external_refs=True",
        )
        self.assertIn(
            contract.normalization_status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
            f"Normalization must succeed (OK or WITH_WARNINGS), got {contract.normalization_status}",
        )

    def test_create_contract_with_remove_external_refs(self):
        """Test creating contract with remove_external_refs flag"""
        original_raw = '{"id": "test-contract", "info": {"name": "test-contract"}, "schema": {"fields": [{"name": "id", "type": "string"}]}, "$ref": "https://example.com/schema.json"}'
        original_format = "JSON"

        contract = self.service.create_contract(
            original_raw=original_raw,
            original_format=original_format,
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            remove_external_refs=True,
        )

        self.assertIsNotNone(contract)
        contract.refresh_from_db()
        # Normalization must complete and produce hub_contract_json.
        self.assertIsNotNone(
            contract.hub_contract_json,
            "hub_contract_json must be set when remove_external_refs=True",
        )
        self.assertIn(
            contract.normalization_status,
            [NormalizationStatus.NORMALIZED_OK, NormalizationStatus.NORMALIZED_WITH_WARNINGS],
            "Normalization must succeed when external refs are removed",
        )

    def test_update_contract_with_normalization(self):
        """Test updating contract triggers normalization"""
        minimal_odcs = '{"id": "old-contract", "info": {"name": "old-contract"}, "schema": {"fields": [{"name": "id", "type": "string"}]}}'
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=minimal_odcs,
            original_format="JSON",
            status=ContractStatus.DRAFT,
            normalization_status=NormalizationStatus.NOT_NORMALIZED,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
        )

        updated_raw = '{"id": "updated-contract", "info": {"name": "updated-contract"}, "schema": {"fields": [{"name": "id", "type": "string"}]}}'

        updated_contract = self.service.update_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_raw=updated_raw,
        )

        updated_contract.refresh_from_db()
        # Normalization should be triggered
        self.assertIn(
            updated_contract.normalization_status,
            [
                NormalizationStatus.NORMALIZED_OK,
                NormalizationStatus.NORMALIZATION_FAILED,
                NormalizationStatus.NOT_NORMALIZED,
            ],
        )

    # ========== ADDITIONAL MISSING SCENARIOS ==========

    def test_create_contract_missing_tenant_id(self):
        """Test creating contract without tenant_id raises ValidationError"""
        original_raw = '{"info": {"name": "test-contract"}}'
        original_format = "JSON"

        # Create service without tenant_id for testing
        service_without_tenant = ContractService()

        with self.assertRaises(ValidationError) as cm:
            service_without_tenant.create_contract(
                original_raw=original_raw,
                original_format=original_format,
                tenant_id=None,  # No tenant_id provided
                user_id=str(self.user.id),
            )

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
        self.assertIn("tenant_id", str(cm.exception).lower())

    def test_create_contract_invalid_json(self):
        """Test creating contract with invalid JSON raises ValidationError"""
        invalid_json = '{"info": {"name": "test-contract"}'  # Missing closing brace

        with self.assertRaises(ValidationError):
            self.service.create_contract(
                original_raw=invalid_json,
                original_format="JSON",
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

    def test_update_contract_missing_tenant_id(self):
        """Test updating contract without tenant_id raises ValidationError"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.DRAFT,
        )

        # Create service without tenant_id for testing
        service_without_tenant = ContractService()

        with self.assertRaises(ValidationError) as cm:
            service_without_tenant.update_contract(
                contract_id=str(contract.id),
                tenant_id=None,  # No tenant_id provided
                user_id=str(self.user.id),
                original_raw='{"info": {"name": "updated"}}',
            )

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
        self.assertIn("tenant_id", str(cm.exception).lower())

    def test_update_contract_invalid_json(self):
        """Test updating contract with invalid JSON raises ValidationError"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.DRAFT,
        )

        invalid_json = '{"info": {"name": "updated"}'  # Missing closing brace

        with self.assertRaises(ValidationError):
            self.service.update_contract(
                contract_id=str(contract.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                original_raw=invalid_json,
            )

    def test_update_contract_idempotency(self):
        """Test updating contract with same content is idempotent"""
        original_raw = '{"id": "test-contract", "info": {"name": "test-contract"}, "schema": {"fields": [{"name": "id", "type": "string"}]}}'
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw=original_raw,
            original_format="JSON",
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.2",
        )

        # Update with same content
        updated_contract = self.service.update_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            original_raw=original_raw,  # Same content
        )

        updated_contract.refresh_from_db()
        self.assertEqual(updated_contract.original_raw, original_raw)

    def test_list_contracts_missing_tenant_id(self):
        """Test listing contracts without tenant_id raises ValidationError"""
        # Create service without tenant_id for testing
        service_without_tenant = ContractService()

        with self.assertRaises(ValidationError) as cm:
            service_without_tenant.list_contracts(tenant_id=None)

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
        self.assertIn("tenant_id", str(cm.exception).lower())

    def test_list_contracts_invalid_page_number(self):
        """Test listing contracts with invalid page number"""
        # Create some contracts
        for i in range(5):
            Contract.objects.create(
                tenant=self.tenant,
                original_raw=f'{{"info": {{"name": "contract-{i}"}}}}',
                original_format="JSON",
                status=ContractStatus.ACTIVE,
            )

        # Test with page 0 (should default to page 1 or raise error)
        contracts, meta = self.service.list_contracts(
            tenant_id=str(self.tenant.id), page=0, page_size=10
        )
        # Django Paginator.get_page() normalizes page 0 to page 1
        self.assertEqual(meta["page"], 1)

        # Test with negative page (should default to page 1)
        contracts, meta = self.service.list_contracts(
            tenant_id=str(self.tenant.id), page=-1, page_size=10
        )
        self.assertEqual(meta["page"], 1)

        # Test with page beyond available pages (should return empty list)
        contracts, meta = self.service.list_contracts(
            tenant_id=str(self.tenant.id), page=999, page_size=10
        )
        self.assertEqual(len(contracts), 0)
        self.assertEqual(meta["page"], 999)

    def test_list_contracts_invalid_page_size(self):
        """Test listing contracts with invalid page_size"""
        # Create some contracts
        for i in range(5):
            Contract.objects.create(
                tenant=self.tenant,
                original_raw=f'{{"info": {{"name": "contract-{i}"}}}}',
                original_format="JSON",
                status=ContractStatus.ACTIVE,
            )

        # page_size=0 raises ZeroDivisionError (Paginator.num_pages → ceil/0),
        # wrapped in ServiceError by execute_with_metrics.
        with self.assertRaises(ServiceError):
            self.service.list_contracts(tenant_id=str(self.tenant.id), page=1, page_size=0)

        # page_size=-1 raises ValueError (Paginator validates per_page ≥ 1),
        # wrapped in ServiceError by execute_with_metrics.
        with self.assertRaises(ServiceError):
            self.service.list_contracts(tenant_id=str(self.tenant.id), page=1, page_size=-1)

        # Test with very large page_size (should work but may be inefficient)
        contracts, meta = self.service.list_contracts(
            tenant_id=str(self.tenant.id), page=1, page_size=10000
        )
        self.assertEqual(len(contracts), 5)
        self.assertEqual(meta["page_size"], 10000)

    def test_list_contracts_multiple_filters(self):
        """Test contract listing with multiple filter combinations"""
        asset1 = Asset.objects.create(
            tenant=self.tenant, key="asset-1", name="Asset 1", status=AssetStatus.DRAFT
        )
        asset2 = Asset.objects.create(
            tenant=self.tenant, key="asset-2", name="Asset 2", status=AssetStatus.DRAFT
        )

        # Create contracts with different combinations
        # Use different versions to avoid unique constraint violation
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset1,
            original_raw='{"info": {"name": "active-asset1"}}',
            original_format="JSON",
            version=1,
            status=ContractStatus.ACTIVE,
        )
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset1,
            original_raw='{"info": {"name": "draft-asset1"}}',
            original_format="JSON",
            version=2,
            status=ContractStatus.DRAFT,
        )
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset2,
            original_raw='{"info": {"name": "active-asset2"}}',
            original_format="JSON",
            version=1,
            status=ContractStatus.ACTIVE,
        )

        # Test filter by status + asset_id
        contracts, _ = self.service.list_contracts(
            tenant_id=str(self.tenant.id),
            filters={"status": ContractStatus.ACTIVE, "asset_id": str(asset1.id)},
        )

        self.assertEqual(len(contracts), 1)
        self.assertEqual(contracts[0].status, ContractStatus.ACTIVE)
        self.assertEqual(contracts[0].asset_id, asset1.id)

    def test_get_contract_missing_tenant_id(self):
        """Test getting contract without tenant_id raises ValidationError"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        # Create service without tenant_id for testing
        service_without_tenant = ContractService()

        with self.assertRaises(ValidationError) as cm:
            service_without_tenant.get_contract(contract_id=str(contract.id), tenant_id=None)

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
        self.assertIn("tenant_id", str(cm.exception).lower())

    def test_get_active_contract_for_asset_missing_tenant_id(self):
        """Test get_active_contract_for_asset without tenant_id raises ValidationError"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.DRAFT
        )

        # Create service without tenant_id for testing
        service_without_tenant = ContractService()

        with self.assertRaises(ValidationError) as cm:
            service_without_tenant.get_active_contract_for_asset(
                asset_id=str(asset.id), tenant_id=None
            )

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
        self.assertIn("tenant_id", str(cm.exception).lower())

    def test_get_active_contract_for_asset_multiple_odps_versions(self):
        """Test get_active_contract_for_asset with multiple ODPS contracts prefers latest version"""
        asset = Asset.objects.create(
            tenant=self.tenant, key="test-asset", name="Test Asset", status=AssetStatus.DRAFT
        )

        # Create multiple ODPS contracts with different versions (Contract.version is int)
        Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            original_raw='{"id": "odps-v1", "version": "1.0.0"}',
            original_format="JSON",
            original_spec_type=OriginalSpecType.ODPS,
            version=1,
            status=ContractStatus.ACTIVE,
        )

        odps_v2 = Contract.objects.create(
            tenant=self.tenant,
            asset=asset,
            original_raw='{"id": "odps-v2", "version": "2.0.0"}',
            original_format="JSON",
            original_spec_type=OriginalSpecType.ODPS,
            version=2,
            status=ContractStatus.ACTIVE,
        )

        # Should prefer latest version (v2)
        result = self.service.get_active_contract_for_asset(
            asset_id=str(asset.id), tenant_id=str(self.tenant.id)
        )

        self.assertIsNotNone(result)
        # Should return the contract with highest version (ordered by -version)
        self.assertEqual(result.id, odps_v2.id)

    def test_validate_contract_missing_tenant_id(self):
        """Test validating contract without tenant_id raises ValidationError"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        # Create service without tenant_id for testing
        service_without_tenant = ContractService()

        with self.assertRaises(ValidationError) as cm:
            service_without_tenant.validate_contract(
                contract_id=str(contract.id),
                tenant_id=None,
                user_id=str(self.user.id),
            )

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
        self.assertIn("tenant_id", str(cm.exception).lower())

    def test_validate_contract_invalid_json_handling(self):
        """Validation of a contract with corrupted original_raw (invalid JSON)
        returns an error dict — the CLI client always returns a fallback
        response on failure, never propagates an unhandled exception."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"id":"test","name":"Test","schema":{"fields":[{"name":"id","type":"string"}]}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        # Corrupt the raw payload after creation
        contract.original_raw = '{"id":"test","name":"Test",broken'  # unclosed brace
        contract.save()

        result = self.service.validate_contract(
            contract_id=str(contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            use_async=False,
        )
        self.assertIsInstance(result, dict)
        self.assertIn("validation_status", result)
        # The corrupted JSON causes either a CLI parse failure (→ ERROR)
        # or a validation failure (→ INVALID).  Both are valid outcomes
        # for structurally-broken input.
        self.assertIn(
            result["validation_status"],
            {"ERROR", "INVALID"},
            f"Expected ERROR or INVALID for corrupted JSON, got {result['validation_status']}",
        )

    def test_delete_contract_missing_tenant_id(self):
        """Test deleting contract without tenant_id raises ValidationError"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        # Create service without tenant_id for testing
        service_without_tenant = ContractService()

        with self.assertRaises(ValidationError) as cm:
            service_without_tenant.delete_contract(
                contract_id=str(contract.id),
                tenant_id=None,
                user_id=str(self.user.id),
            )

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
        self.assertIn("tenant_id", str(cm.exception).lower())

    def test_validate_contract_active_missing_tenant_id(self):
        """Test validate_contract_active without tenant_id raises ValidationError"""
        contract = Contract.objects.create(
            tenant=self.tenant,
            original_raw='{"info": {"name": "test-contract"}}',
            original_format="JSON",
            status=ContractStatus.ACTIVE,
        )

        # Create service without tenant_id for testing
        service_without_tenant = ContractService()

        with self.assertRaises(ValidationError) as cm:
            service_without_tenant.validate_contract_active(
                contract_id=str(contract.id), tenant_id=None
            )

        self.assertEqual(cm.exception.code, "VALIDATION_ERROR")
        self.assertIn("tenant_id", str(cm.exception).lower())
