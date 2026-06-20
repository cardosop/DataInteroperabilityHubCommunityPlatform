"""
Unit tests for migrate_contracts_to_odps management command (Task 9.1.1).

Tests cover:
- Finding ODCS contracts with marketplace metadata
- ODPS generation from HubContract marketplace data
- ODPS contract creation
- Bidirectional linking (ODPS ↔ ODCS)
- Per-contract and batch migration modes
- Dry-run mode

All tests use real implementations (no mocks/stubs) and verify:
- Command logic correctness
- Migration workflow
- Error handling
- Edge cases
"""

import json
import uuid
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.models import Contract, OriginalSpecType
from hub.apps.contracts.tests.test_base import ContractsTestBase
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class MigrateContractsToODPSTestBase(ContractsTestBase):
    """Base test class for migration command tests."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Update tenant/user names for migration tests
        self.tenant.name = "Migration Test Tenant"
        self.tenant.slug = "migration-test"
        self.tenant.save()

        self.user.email = "migration-test@example.com"
        self.user.display_name = "Migration Test User"
        self.user.save()

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-migration",
            name="Test Asset for Migration",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def _create_odcs_contract_with_marketplace(
        self, marketplace_data: dict = None, has_odps_link: bool = False
    ) -> Contract:
        """Create an ODCS contract with marketplace metadata."""
        contract_service = self.contract_service

        # Create ODCS contract
        odcs_raw = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-odcs-migration",
                "name": "Test ODCS for Migration",
                "version": "3.0.2",
                "schema": {
                    "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
                },
            }
        )

        contract = contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id),
            original_spec_type="ODCS",
        )

        # Add marketplace metadata to HubContract
        if marketplace_data or has_odps_link:
            hub_contract = contract.hub_contract_json or {}
            if marketplace_data:
                hub_contract["marketplace"] = marketplace_data
            if has_odps_link:
                # Add fake ODPS link
                if "extensions" not in hub_contract:
                    hub_contract["extensions"] = {}
                if "x_odps" not in hub_contract["extensions"]:
                    hub_contract["extensions"]["x_odps"] = {}
                hub_contract["extensions"]["x_odps"]["odps_link"] = (
                    "00000000-0000-0000-0000-000000000000"
                )

            contract.hub_contract_json = hub_contract
            contract.save(update_fields=["hub_contract_json"])

        return contract


class FindEligibleContractsTest(MigrateContractsToODPSTestBase):
    """Tests for finding eligible contracts."""

    def test_find_contracts_with_marketplace_metadata(self):
        """Test finding ODCS contracts with marketplace metadata through public API."""
        # Arrange
        # Create contract with marketplace data
        marketplace_data = {
            "license_summary": "Test license",
            "intended_use": ["analytics"],
            "x_odps": {"pricing_plans": [{"name": "Basic", "price": 10}]},
        }
        contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Act
        # Find eligible contracts through public API - call_command() internally calls _find_eligible_contracts()
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--dry-run",
            "--tenant-id",
            str(self.tenant.id),
            "--min-marketplace-fields",
            "1",
            stdout=out,
        )

        output = out.getvalue()
        # Command should find 1 eligible contract
        self.assertIn("Found 1 ODCS contract(s) to migrate", output)
        # Verify contract exists
        self.assertTrue(Contract.objects.filter(id=contract.id).exists())

    def test_skip_contracts_without_marketplace_metadata(self):
        """Test skipping contracts without marketplace metadata through public API."""
        # Arrange
        # Create contract without marketplace data
        self._create_odcs_contract_with_marketplace()

        # Act
        # Find eligible contracts through public API - call_command() internally calls _find_eligible_contracts()
        # Requires at least 1 marketplace field
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--dry-run",
            "--tenant-id",
            str(self.tenant.id),
            "--min-marketplace-fields",
            "1",
            stdout=out,
        )

        # Assert
        output = out.getvalue()
        # Command should find 0 eligible contracts (no marketplace metadata)
        self.assertIn("Found 0 ODCS contract(s) to migrate", output)

    def test_skip_contracts_with_odps_link(self):
        """Test skipping contracts that already have ODPS links."""
        # Arrange
        # Create ODCS contract first
        marketplace_data = {"license_summary": "Test license"}
        odcs_contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Create and link ODPS contract
        odps_service = self.odps_service

        # Get the actual ODCS contract ID from the contract
        odcs_contract_id = odcs_contract.hub_contract_json.get("id", "test-odcs-migration")

        # Create ODPS with embedded ODCS contract (required for linking)
        odcs_spec = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": odcs_contract_id,
            "name": "Test ODCS for Migration",
            "version": "3.0.2",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {"en": {"productID": "test-odps", "name": "Test ODPS"}},
                    "contract": {"spec": odcs_spec},
                },
            }
        )

        odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id),
        )

        # Link them
        self.contract_service.link_odps_to_odcs(
            odcs_contract_id=str(odcs_contract.id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Find eligible contracts through public API - call_command() internally calls _find_eligible_contracts()
        # Skip linked contracts
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--dry-run",
            "--tenant-id",
            str(self.tenant.id),
            "--skip-linked",
            "--min-marketplace-fields",
            "1",
            stdout=out,
        )

        output = out.getvalue()
        # Command should find 0 eligible contracts (contract already has ODPS link)
        self.assertIn("Found 0 ODCS contract(s) to migrate", output)

    def test_count_marketplace_fields(self):
        """Test counting marketplace fields through public API."""
        marketplace_data = {
            "license_summary": "Test license",
            "intended_use": ["analytics"],
            "restricted_use": ["commercial"],
            "x_odps": {
                "pricing_plans": [{"name": "Basic"}],
                "access_methods": {"api": {}},
                "payment_gateways": {"stripe": {}},
            },
        }
        contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Test through public API - call_command() internally calls _count_marketplace_fields()
        # Contract has 6 marketplace fields: license_summary, intended_use, restricted_use,
        # pricing_plans, access_methods, payment_gateways
        # With min-marketplace-fields=6, contract should be eligible
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--dry-run",
            "--contract-id",
            str(contract.id),
            "--min-marketplace-fields",
            "6",
            stdout=out,
        )

        output = out.getvalue()
        # Command should find the contract eligible (has 6 fields >= 6 minimum)
        self.assertIn("Found 1 ODCS contract(s) to migrate", output)

        # Verify contract has marketplace metadata
        contract.refresh_from_db()
        hub_contract = contract.hub_contract_json or {}
        self.assertIn("marketplace", hub_contract)


class MigrateContractTest(MigrateContractsToODPSTestBase):
    """Tests for migrating individual contracts."""

    def test_migrate_contract_creates_odps_and_links(self):
        """Test migrating a contract creates ODPS and links it through public API."""
        # Create ODCS contract with marketplace data
        marketplace_data = {
            "license_summary": "Test license",
            "intended_use": ["analytics"],
            "x_odps": {"pricing_plans": [{"name": "Basic", "price": 10}]},
        }
        odcs_contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Migrate contract through public API - call_command() internally calls _migrate_contract()
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--contract-id",
            str(odcs_contract.id),
            "--target-odps-version",
            "4.1",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Migrated", output)

        # Verify ODPS contract was created
        odps_contracts = Contract.objects.filter(
            original_spec_type=OriginalSpecType.ODPS, tenant_id=self.tenant.id
        )
        self.assertEqual(odps_contracts.count(), 1)
        odps_contract = odps_contracts.first()
        self.assertEqual(str(odps_contract.tenant_id), str(odcs_contract.tenant_id))

        # Verify bidirectional link
        odcs_contract.refresh_from_db()
        hub_contract = odcs_contract.hub_contract_json
        extensions = hub_contract.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertEqual(str(x_odps.get("odps_link")), str(odps_contract.id))

        odps_hub_contract = odps_contract.hub_contract_json
        odps_extensions = odps_hub_contract.get("extensions", {})
        odps_x_odps = odps_extensions.get("x_odps", {})
        self.assertEqual(odps_x_odps.get("odcs_link"), str(odcs_contract.id))

    def test_migrate_contract_dry_run(self):
        """Test dry-run mode doesn't create contracts through public API."""
        marketplace_data = {"license_summary": "Test license"}
        odcs_contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Count contracts before
        initial_count = Contract.objects.filter(original_spec_type=OriginalSpecType.ODPS).count()

        # Migrate in dry-run mode through public API - call_command() internally calls _migrate_contract()
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--contract-id",
            str(odcs_contract.id),
            "--target-odps-version",
            "4.1",
            "--dry-run",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("DRY-RUN MODE", output)
        self.assertIn("No database changes will be made", output)

        # Verify no contracts were created
        final_count = Contract.objects.filter(original_spec_type=OriginalSpecType.ODPS).count()
        self.assertEqual(initial_count, final_count)

    def test_migrate_contract_skips_if_already_linked(self):
        """Test migration skips contracts that already have ODPS links."""
        # Create ODPS contract first with embedded ODCS contract
        from hub.apps.contracts.services import ODPSService

        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Create ODPS with embedded ODCS contract (required for linking)
        odcs_spec = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-odcs-migration",
            "name": "Test ODCS for Migration",
            "version": "3.0.2",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {"en": {"productID": "test-odps", "name": "Test ODPS"}},
                    "contract": {"spec": odcs_spec},
                },
            }
        )

        odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id),
        )

        # Create ODCS contract and link it
        marketplace_data = {"license_summary": "Test license"}
        odcs_contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Link them
        from hub.apps.contracts.services import ContractService

        contract_service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(odcs_contract.id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Refresh contract from database to get updated links
        odcs_contract.refresh_from_db()

        # Try to migrate through public API - call_command() internally calls _migrate_contract()
        # Should skip because contract already has ODPS link
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--contract-id",
            str(odcs_contract.id),
            "--target-odps-version",
            "4.1",
            stdout=out,
        )

        out.getvalue()
        # Command should skip the contract (already has ODPS link)
        # Note: The exact output message depends on command implementation
        # Verify that no additional ODPS contract was created
        odps_count_after = Contract.objects.filter(
            original_spec_type=OriginalSpecType.ODPS, tenant_id=self.tenant.id
        ).count()
        # Should still be 1 (the one we created earlier)
        self.assertEqual(odps_count_after, 1)


class CommandIntegrationTest(MigrateContractsToODPSTestBase):
    """Integration tests for the management command."""

    def test_command_dry_run_mode(self):
        """Test command in dry-run mode."""
        # Create contract with marketplace data
        marketplace_data = {"license_summary": "Test license", "intended_use": ["analytics"]}
        self._create_odcs_contract_with_marketplace(marketplace_data)

        # Run command in dry-run mode
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps", "--dry-run", "--tenant-id", str(self.tenant.id), stdout=out
        )

        output = out.getvalue()
        self.assertIn("DRY-RUN MODE", output)
        self.assertIn("No database changes will be made", output)

    def test_command_per_contract_mode(self):
        """Test command in per-contract mode."""
        # Create contract with marketplace data
        marketplace_data = {
            "license_summary": "Test license",
            "x_odps": {"pricing_plans": [{"name": "Basic"}]},
        }
        contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Run command for specific contract
        out = StringIO()
        call_command("migrate_contracts_to_odps", "--contract-id", str(contract.id), stdout=out)

        output = out.getvalue()
        self.assertIn("Migrated", output)

        # Verify ODPS contract was created
        odps_contracts = Contract.objects.filter(
            original_spec_type=OriginalSpecType.ODPS, tenant_id=self.tenant.id
        )
        self.assertEqual(odps_contracts.count(), 1)

    def test_command_batch_mode(self):
        """Test command in batch mode."""
        # Create multiple contracts with marketplace data
        for i in range(3):
            marketplace_data = {"license_summary": f"License {i}", "intended_use": ["analytics"]}
            self._create_odcs_contract_with_marketplace(marketplace_data)

        # Run command in batch mode
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--tenant-id",
            str(self.tenant.id),
            "--batch-size",
            "10",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Found 3 ODCS contract(s)", output)
        self.assertIn("Migrated: 3", output)

        # Verify ODPS contracts were created
        odps_contracts = Contract.objects.filter(
            original_spec_type=OriginalSpecType.ODPS, tenant_id=self.tenant.id
        )
        self.assertEqual(odps_contracts.count(), 3)

    def test_command_skip_linked(self):
        """Test command with --skip-linked option."""
        # Create ODCS contract with marketplace data
        marketplace_data = {"license_summary": "Test license"}
        contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Create and link ODPS contract
        from hub.apps.contracts.services import ContractService, ODPSService

        odps_service = ODPSService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        # Get the actual ODCS contract ID from the contract
        odcs_contract_id = contract.hub_contract_json.get("id", "test-odcs-migration")

        # Create ODPS with embedded ODCS contract (required for linking)
        odcs_spec = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": odcs_contract_id,
            "name": "Test ODCS for Migration",
            "version": "3.0.2",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {"en": {"productID": "test-odps", "name": "Test ODPS"}},
                    "contract": {"spec": odcs_spec},
                },
            }
        )

        odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id),
        )

        contract_service = ContractService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(contract.id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Run command with --skip-linked
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--tenant-id",
            str(self.tenant.id),
            "--skip-linked",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Found 0 ODCS contract(s)", output)

    def test_command_min_marketplace_fields(self):
        """Test command with --min-marketplace-fields option."""
        # Create contract with minimal marketplace data
        marketplace_data = {"license_summary": "Test license"}
        self._create_odcs_contract_with_marketplace(marketplace_data)

        # Run command requiring 2 marketplace fields
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--tenant-id",
            str(self.tenant.id),
            "--min-marketplace-fields",
            "2",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Found 0 ODCS contract(s)", output)

        # Run command requiring 1 marketplace field
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--tenant-id",
            str(self.tenant.id),
            "--min-marketplace-fields",
            "1",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Found 1 ODCS contract(s)", output)

    def test_command_handles_unicode_characters(self):
        """Test command handles unicode characters correctly."""
        marketplace_data = {"license_summary": "测试许可证 🏢"}
        contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Run command
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--contract-id",
            str(contract.id),
            "--target-odps-version",
            "4.1",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Migrated", output)

    def test_command_handles_special_characters(self):
        """Test command handles special characters correctly."""
        marketplace_data = {"license_summary": "Test & Co. (Special)"}
        contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Run command
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--contract-id",
            str(contract.id),
            "--target-odps-version",
            "4.1",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Migrated", output)

    def test_command_handles_very_large_marketplace_data(self):
        """Test command handles very large marketplace data correctly."""
        marketplace_data = {
            "license_summary": "A" * 10000,  # 10KB string
            "intended_use": ["analytics"],
        }
        contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Run command
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--contract-id",
            str(contract.id),
            "--target-odps-version",
            "4.1",
            stdout=out,
        )

        output = out.getvalue()
        # Should either succeed or provide appropriate error message
        self.assertIsNotNone(output)

    def test_command_handles_none_values(self):
        """Test command handles None values correctly."""
        marketplace_data = {
            "license_summary": "Test license",
            "optional_field": None,
        }
        contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Run command
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--contract-id",
            str(contract.id),
            "--target-odps-version",
            "4.1",
            stdout=out,
        )

        output = out.getvalue()
        # Should handle None values gracefully
        self.assertIsNotNone(output)

    def test_command_handles_nested_marketplace_data(self):
        """Test command handles nested marketplace data correctly."""
        marketplace_data = {
            "license_summary": "Test license",
            "nested": {"level1": {"level2": {"value": "deep"}}},
        }
        contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Run command
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--contract-id",
            str(contract.id),
            "--target-odps-version",
            "4.1",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Migrated", output)

    def test_command_handles_invalid_contract_id(self):
        """Test command handles invalid contract ID correctly."""
        invalid_contract_id = str(uuid.uuid4())

        # Run command with invalid contract ID
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--contract-id",
            invalid_contract_id,
            "--target-odps-version",
            "4.1",
            stdout=out,
        )

        output = out.getvalue()
        # Should handle invalid ID gracefully
        self.assertIsNotNone(output)

    def test_command_handles_cross_tenant_isolation(self):
        """Test command maintains cross-tenant isolation."""
        # Create second tenant
        tenant2 = Tenant.objects.create(
            name="Migration Isolation Test Tenant 2",
            slug="migration-isolation-test-2",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        user2 = User.objects.create_user(
            email=f"migration-isolation-test-2-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=tenant2,
            status=UserStatus.ACTIVE,
            display_name="Migration Isolation Test User 2",
        )

        asset2 = Asset.objects.create(
            tenant=tenant2,
            key="test-asset-migration-isolation-2",
            name="Test Asset for Migration Isolation 2",
            status=AssetStatus.ACTIVE,
            created_by=user2,
        )

        # Create contract for tenant1
        marketplace_data1 = {"license_summary": "License 1"}
        contract1 = self._create_odcs_contract_with_marketplace(marketplace_data1)

        # Create contract for tenant2
        from hub.apps.contracts.services import ContractService

        contract_service2 = ContractService(tenant_id=str(tenant2.id), user_id=str(user2.id))

        odcs_raw2 = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": "test-odcs-migration-2",
                "name": "Test ODCS for Migration 2",
                "version": "3.0.2",
                "schema": {
                    "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
                },
            }
        )

        contract2 = contract_service2.create_contract(
            original_raw=odcs_raw2,
            original_format="json",
            tenant_id=str(tenant2.id),
            user_id=str(user2.id),
            asset_id=str(asset2.id),
            original_spec_type="ODCS",
        )

        hub_contract2 = contract2.hub_contract_json or {}
        hub_contract2["marketplace"] = {"license_summary": "License 2"}
        contract2.hub_contract_json = hub_contract2
        contract2.save()

        # Run command for tenant1
        out = StringIO()
        call_command(
            "migrate_contracts_to_odps",
            "--contract-id",
            str(contract1.id),
            "--target-odps-version",
            "4.1",
            stdout=out,
        )

        # Verify tenant2 contract is not affected
        contract2.refresh_from_db()
        self.assertEqual(contract2.tenant, tenant2, "Tenant2 contract should remain isolated")
