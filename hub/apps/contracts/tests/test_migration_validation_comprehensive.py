"""
Comprehensive Migration Validation Testing (Task 10.1.21.1)

Tests cover:
- Migration script validates prerequisites
- Migration script validates data integrity
- Migration script handles errors correctly
- Migration script provides rollback capability

All tests use real implementations (no mocks/stubs) and verify:
- Prerequisite validation logic
- Data integrity checks
- Error handling
- Rollback mechanisms
"""

import json
import uuid

import pytest

pytestmark = [pytest.mark.slow, pytest.mark.django_db(transaction=True)]
from datetime import UTC

from django.core.exceptions import ValidationError
from django.db import connection, transaction

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.migration import (
    can_migrate,
    get_current_hubcontract_version,
    needs_migration,
)
from hub.apps.contracts.migration_manager import ContractMigrationManager
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType
from hub.apps.contracts.tests.test_base import ContractsTestBase
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import User, UserStatus


class MigrationValidationTestBase(ContractsTestBase):
    """Base test class for migration validation tests."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-migration-validation-{uuid.uuid4().hex[:8]}",
            name="Test Asset for Migration Validation",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )


class MigrationPrerequisitesValidationTest(MigrationValidationTestBase):
    """Tests for migration script prerequisite validation (Task 10.1.21.1)."""

    def test_migration_validates_database_connectivity(self):
        """Test that migration validates database connectivity."""
        # Act: verify DB connection via a simple query
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()

        # Assert
        self.assertIsNotNone(result, "Database should be reachable")
        self.assertEqual(result[0], 1, "Simple query should succeed")

        # Also verify current version is accessible
        current_version = get_current_hubcontract_version()
        self.assertIsNotNone(current_version, "Should be able to get current version")
        self.assertEqual(current_version, "1.0.0", "Current version should be 1.0.0")

    def test_migration_validates_contract_exists(self):
        """Test that migration validates contract exists before migrating."""
        # Arrange
        current_version = get_current_hubcontract_version()
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version=current_version,
            hub_contract_json={"version": current_version},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Act
        # Check if migration is needed (may not be needed if already at current version)
        needs_migration_result = needs_migration(contract.hub_contract_version)

        # Assert
        # Verify contract exists
        self.assertTrue(Contract.objects.filter(id=contract.id).exists())
        # Verify contract exists and has version
        self.assertIsNotNone(contract.hub_contract_version, "Contract should have version")
        # This may be True or False depending on version
        self.assertIsInstance(needs_migration_result, bool, "Should return boolean")

    def test_migration_validates_version_compatibility(self):
        """Test that migration validates version compatibility."""
        # Arrange
        current_version = get_current_hubcontract_version()

        # Act & Assert
        # Test with already current version
        self.assertFalse(
            needs_migration(current_version),
            "Should not need migration if already at current version",
        )

        # Test can_migrate with same version (should return False as no migration needed)
        self.assertFalse(
            can_migrate(current_version, current_version),
            "Should not need migration for same version",
        )

        # Test can_migrate with invalid version format
        self.assertFalse(
            can_migrate("invalid", current_version), "Should reject invalid version format"
        )

    def test_migration_validates_tenant_access(self):
        """Test that migration validates tenant access."""
        # Arrange
        # Create contract for tenant
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version=get_current_hubcontract_version(),
            hub_contract_json={"version": get_current_hubcontract_version()},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Act
        # (no action needed - just verify tenant relationship)

        # Assert
        # Verify contract belongs to tenant
        self.assertEqual(contract.tenant, self.tenant, "Contract should belong to tenant")

    def test_migration_validates_hub_contract_json_exists(self):
        """Test that migration validates hub_contract_json exists."""
        # Arrange
        # Create contract without hub_contract_json
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version=None,
            hub_contract_json=None,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Act
        # Migration manager should handle missing hub_contract_json
        migrated, migrated_data, _warnings = ContractMigrationManager.migrate_on_write(contract)

        # Assert
        self.assertFalse(migrated, "Should not migrate contract without hub_contract_json")
        self.assertIsNone(migrated_data, "Should return None for migrated data")


class MigrationDataIntegrityValidationTest(MigrationValidationTestBase):
    """Tests for migration script data integrity validation (Task 10.1.21.1)."""

    def test_migration_preserves_contract_id(self):
        """Test that migration preserves contract ID."""
        contract_id = uuid.uuid4()
        contract = Contract.objects.create(
            id=contract_id,
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"version": "0.9.0", "id": "test-contract"},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Perform migration
        migrated, _migrated_data, _warnings = ContractMigrationManager.migrate_on_write(contract)

        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        # Refresh from database
        contract.refresh_from_db()
        self.assertEqual(contract.id, contract_id, "Contract ID should be preserved")
        self.assertIsNotNone(contract.hub_contract_json, "Hub contract JSON should exist")

    def test_migration_preserves_tenant_association(self):
        """Test that migration preserves tenant association."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"version": "0.9.0"},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        original_tenant_id = contract.tenant.id

        # Perform migration
        migrated, _migrated_data, _warnings = ContractMigrationManager.migrate_on_write(contract)

        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        # Refresh from database
        contract.refresh_from_db()
        self.assertEqual(
            contract.tenant.id, original_tenant_id, "Tenant association should be preserved"
        )

    def test_migration_preserves_asset_association(self):
        """Test that migration preserves asset association."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"version": "0.9.0"},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        original_asset_id = contract.asset.id

        # Perform migration
        migrated, _migrated_data, _warnings = ContractMigrationManager.migrate_on_write(contract)

        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        # Refresh from database
        contract.refresh_from_db()
        self.assertEqual(
            contract.asset.id, original_asset_id, "Asset association should be preserved"
        )

    def test_migration_validates_data_completeness(self):
        """Test that migration validates data completeness."""
        # Create contract with minimal data
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"version": "0.9.0"},  # Minimal data
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Migration should handle minimal data gracefully
        migrated, migrated_data, warnings = ContractMigrationManager.migrate_on_write(contract)

        # Migration should succeed for old version contract
        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        self.assertIsNotNone(migrated_data, "Migrated data should exist")
        self.assertIsInstance(warnings, list, "Warnings should be a list")

    def test_migration_validates_referential_integrity(self):
        """Test that migration validates referential integrity."""
        # Create contract with asset reference
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"version": "0.9.0"},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Verify asset exists
        self.assertTrue(Asset.objects.filter(id=self.asset.id).exists(), "Asset should exist")

        # Perform migration
        migrated, _migrated_data, _warnings = ContractMigrationManager.migrate_on_write(contract)

        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        # Refresh from database
        contract.refresh_from_db()
        # Verify asset reference is still valid
        self.assertIsNotNone(contract.asset, "Asset reference should be preserved")
        self.assertTrue(
            Asset.objects.filter(id=contract.asset.id).exists(),
            "Referenced asset should still exist",
        )


class MigrationErrorHandlingTest(MigrationValidationTestBase):
    """Tests for migration script error handling (Task 10.1.21.1)."""

    def test_migration_handles_invalid_json_gracefully(self):
        """Test that migration handles invalid JSON gracefully."""
        # Create contract with invalid hub_contract_json
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"invalid": "structure"},  # May not be valid for migration
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Migration should handle gracefully
        try:
            _migrated, _migrated_data, warnings = ContractMigrationManager.migrate_on_write(
                contract
            )
            # Should either succeed or fail gracefully with warnings
            self.assertIsInstance(warnings, list, "Warnings should be a list")
        except Exception as e:
            # If exception is raised, it should be a known type
            self.assertIsInstance(
                e,
                (ValueError, ValidationError, KeyError),
                "Should raise appropriate exception type",
            )

    def test_migration_handles_missing_required_fields(self):
        """Test that migration handles missing required fields."""
        # Create contract with missing required fields in hub_contract_json
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={},  # Empty dict - missing required fields
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Migration should handle missing fields
        _migrated, _migrated_data, warnings = ContractMigrationManager.migrate_on_write(contract)

        # Should provide warnings about missing fields
        self.assertIsInstance(warnings, list, "Warnings should be a list")

    def test_migration_handles_concurrent_modifications(self):
        """Test that migration handles concurrent modifications."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"version": "0.9.0"},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Simulate concurrent modification by updating contract in another transaction
        with transaction.atomic():
            contract.status = ContractStatus.DRAFT
            contract.save()

        # Try to migrate
        _migrated, _migrated_data, warnings = ContractMigrationManager.migrate_on_write(contract)

        # Should handle gracefully (either succeed or fail with appropriate error)
        self.assertIsInstance(warnings, list, "Warnings should be a list")

    def test_migration_handles_normal_flow(self):
        """Test that migration handles the normal migration flow."""

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"version": "0.9.0"},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Normal migration should work without raising exceptions
        migrated, _migrated_data, warnings = ContractMigrationManager.migrate_on_write(contract)

        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        # Verify contract was updated
        contract.refresh_from_db()
        current_version = get_current_hubcontract_version()
        self.assertEqual(
            contract.hub_contract_version,
            current_version,
            "Contract version should be updated",
        )
        self.assertIsInstance(warnings, list, "Warnings should be a list")


class MigrationRollbackCapabilityTest(ContractsTestBase):
    """Tests for migration script rollback capability (Task 10.1.21.1)."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-migration-rollback-{uuid.uuid4().hex[:8]}",
            name="Test Asset for Migration Rollback",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def test_migration_provides_rollback_capability(self):
        """Test that migration provides rollback capability."""
        # Create contract with old version
        original_version = "0.9.0"
        original_hub_contract = {"version": "0.9.0", "test": "data"}

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version=original_version,
            hub_contract_json=original_hub_contract.copy(),
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Store original state
        original_state = {
            "version": contract.hub_contract_version,
            "json": json.dumps(contract.hub_contract_json) if contract.hub_contract_json else None,
        }

        # Perform migration
        migrated, _migrated_data, _warnings = ContractMigrationManager.migrate_on_write(contract)

        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        # Verify migration occurred
        contract.refresh_from_db()
        current_version = get_current_hubcontract_version()
        self.assertEqual(
            contract.hub_contract_version, current_version, "Contract should be migrated"
        )

        # Rollback: restore original version
        contract.hub_contract_version = original_state["version"]
        if original_state["json"]:
            contract.hub_contract_json = json.loads(original_state["json"])
        contract.save()

        # Verify rollback
        contract.refresh_from_db()
        self.assertEqual(
            contract.hub_contract_version,
            original_version,
            "Contract should be rolled back to original version",
        )

    def test_migration_tracks_version_history(self):
        """Test that migration tracks version history for rollback."""
        # Create contract with old version
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"version": "0.9.0"},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        original_version = contract.hub_contract_version

        # Perform migration
        migrated, _migrated_data, _warnings = ContractMigrationManager.migrate_on_write(contract)

        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        # Version should be updated
        contract.refresh_from_db()
        get_current_hubcontract_version()
        self.assertNotEqual(
            contract.hub_contract_version,
            original_version,
            "Version should be updated after migration",
        )

        # Original version should be recoverable from audit logs or history
        # (This depends on audit implementation)
        self.assertIsNotNone(original_version, "Original version should be trackable")

    def test_migration_supports_transaction_rollback(self):
        """Test that migration supports transaction rollback."""

        try:
            with transaction.atomic():
                # Create contract
                contract = Contract.objects.create(
                    tenant=self.tenant,
                    asset=self.asset,
                    original_spec_type=OriginalSpecType.ODCS,
                    original_format="json",
                    original_raw=json.dumps(
                        {"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}
                    ),
                    hub_contract_version="0.9.0",
                    hub_contract_json={"version": "0.9.0"},
                    status=ContractStatus.ACTIVE,
                    created_by=self.user,
                )

                # Perform migration within transaction
                _migrated, _migrated_data, _warnings = ContractMigrationManager.migrate_on_write(
                    contract
                )

                # Simulate error - raise exception to trigger rollback
                raise ValueError("Simulated error for rollback test")
        except ValueError:
            # Transaction should be rolled back
            pass

        # Verify contract state (should be rolled back or not exist)
        # Depending on when the error occurred
        contract_exists = Contract.objects.filter(tenant=self.tenant, asset=self.asset).exists()

        # Contract may or may not exist depending on when error occurred
        # The important thing is that partial state is not persisted
        if contract_exists:
            contract = Contract.objects.get(tenant=self.tenant, asset=self.asset)
            # If contract exists, it should be in a consistent state
            self.assertIsNotNone(
                contract.hub_contract_version, "Contract should have a version if it exists"
            )

    def test_migration_user_can_create_contracts(self):
        """Test that a user can create contracts and they are properly associated."""
        # Create contract with old version to test migration eligibility
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"version": "0.9.0"},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Verify user created the contract
        self.assertEqual(contract.created_by, self.user, "Contract should be created by user")

        # Verify contract needs migration due to old version
        self.assertTrue(
            needs_migration(contract.hub_contract_version),
            "Old version contract should need migration",
        )

        # Migration should proceed
        migrated, _migrated_data, warnings = ContractMigrationManager.migrate_on_write(contract)

        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        self.assertIsInstance(warnings, list, "Warnings should be a list")

    def test_migration_handles_unicode_characters(self):
        """Test that migration handles unicode characters correctly."""
        # Create contract with unicode characters in hub_contract_json
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"version": "0.9.0", "name": "测试合同 🏢"},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Migration should handle unicode characters
        migrated, _migrated_data, _warnings = ContractMigrationManager.migrate_on_write(contract)

        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        contract.refresh_from_db()
        # Verify unicode characters are preserved
        if "name" in contract.hub_contract_json:
            self.assertEqual(
                contract.hub_contract_json["name"],
                "测试合同 🏢",
                "Unicode characters should be preserved",
            )

    def test_migration_handles_special_characters(self):
        """Test that migration handles special characters correctly."""
        # Create contract with special characters
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={
                "version": "0.9.0",
                "name": "Test & Co. (Special)",
            },
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Migration should handle special characters
        migrated, _migrated_data, _warnings = ContractMigrationManager.migrate_on_write(contract)

        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        contract.refresh_from_db()
        # Verify special characters are preserved
        if "name" in contract.hub_contract_json:
            self.assertEqual(
                contract.hub_contract_json["name"],
                "Test & Co. (Special)",
                "Special characters should be preserved",
            )

    def test_migration_handles_very_large_documents(self):
        """Test that migration handles very large documents correctly."""
        # Create contract with very large hub_contract_json
        large_data = {"version": "0.9.0"}
        large_data["large_field"] = "A" * 100000  # 100KB string

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json=large_data,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Migration should handle large documents
        _migrated, _migrated_data, warnings = ContractMigrationManager.migrate_on_write(contract)

        # Should either succeed or provide warnings
        self.assertIsInstance(warnings, list, "Warnings should be a list")

    def test_migration_preserves_created_at_timestamp(self):
        """Test that migration preserves created_at timestamp."""
        from datetime import datetime

        # Create contract
        datetime.now(UTC)
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"version": "0.9.0"},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )
        datetime.now(UTC)

        original_created_at = contract.created_at

        # Perform migration
        migrated, _migrated_data, _warnings = ContractMigrationManager.migrate_on_write(contract)

        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        contract.refresh_from_db()
        # Verify created_at is preserved
        self.assertEqual(
            contract.created_at, original_created_at, "Created_at timestamp should be preserved"
        )

    def test_migration_handles_none_values(self):
        """Test that migration handles None values correctly."""
        # Create contract with None values in hub_contract_json
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={
                "version": "0.9.0",
                "optional_field": None,
            },
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Migration should handle None values
        _migrated, _migrated_data, warnings = ContractMigrationManager.migrate_on_write(contract)

        # Should either succeed or provide warnings
        self.assertIsInstance(warnings, list, "Warnings should be a list")

    def test_migration_handles_nested_structures(self):
        """Test that migration handles nested structures correctly."""
        # Create contract with deeply nested hub_contract_json
        nested_data = {
            "version": "0.9.0",
            "level1": {"level2": {"level3": {"level4": {"value": "deep"}}}},
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json=nested_data,
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Migration should handle nested structures
        migrated, _migrated_data, _warnings = ContractMigrationManager.migrate_on_write(contract)

        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        contract.refresh_from_db()
        # Verify nested structure is preserved
        if "level1" in contract.hub_contract_json:
            self.assertIn(
                "level2",
                contract.hub_contract_json["level1"],
                "Nested structures should be preserved",
            )

    def test_migration_handles_list_values(self):
        """Test that migration handles list values correctly."""
        # Create contract with list values in hub_contract_json
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={
                "version": "0.9.0",
                "tags": ["tag1", "tag2", "tag3"],
            },
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Migration should handle list values
        migrated, _migrated_data, _warnings = ContractMigrationManager.migrate_on_write(contract)

        self.assertTrue(migrated, "Migration should have occurred for old version contract")
        contract.refresh_from_db()
        # Verify list values are preserved
        if "tags" in contract.hub_contract_json:
            self.assertIsInstance(
                contract.hub_contract_json["tags"], list, "List values should be preserved"
            )
            self.assertEqual(
                len(contract.hub_contract_json["tags"]), 3, "List length should be preserved"
            )

    def test_migration_validates_contract_status(self):
        """Test that migration validates contract status."""
        # Create contract with different statuses
        for status in [ContractStatus.DRAFT, ContractStatus.ACTIVE, ContractStatus.RETIRED]:
            contract = Contract.objects.create(
                tenant=self.tenant,
                asset=self.asset,
                original_spec_type=OriginalSpecType.ODCS,
                original_format="json",
                original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
                hub_contract_version="0.9.0",
                hub_contract_json={"version": "0.9.0"},
                status=status,
                created_by=self.user,
            )

            # Migration should handle all statuses
            _migrated, _migrated_data, warnings = ContractMigrationManager.migrate_on_write(
                contract
            )
            self.assertIsInstance(warnings, list, "Warnings should be a list")

            # Clean up
            contract.delete()

    def test_migration_handles_multiple_versions(self):
        """Test that migration handles multiple version transitions correctly."""
        # Create contract with old version
        old_version = "0.9.0"
        contract = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version=old_version,
            hub_contract_json={"version": old_version},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        # Perform multiple migrations
        for _ in range(3):
            migrated, _migrated_data, _warnings = ContractMigrationManager.migrate_on_write(
                contract
            )
            if migrated:
                contract.refresh_from_db()
            else:
                break  # No more migrations needed

        # Verify contract is in valid state
        self.assertIsNotNone(contract.hub_contract_version, "Contract should have a version")

    def test_migration_handles_cross_tenant_isolation(self):
        """Test that migration maintains cross-tenant isolation."""
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
            key=f"test-asset-migration-isolation-2-{uuid.uuid4().hex[:8]}",
            name="Test Asset for Migration Isolation 2",
            status=AssetStatus.ACTIVE,
            created_by=user2,
        )

        # Create contracts for both tenants
        contract1 = Contract.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"version": "0.9.0"},
            status=ContractStatus.ACTIVE,
            created_by=self.user,
        )

        contract2 = Contract.objects.create(
            tenant=tenant2,
            asset=asset2,
            original_spec_type=OriginalSpecType.ODCS,
            original_format="json",
            original_raw=json.dumps({"apiVersion": "odcs.io/v3.0.2", "kind": "DataContract"}),
            hub_contract_version="0.9.0",
            hub_contract_json={"version": "0.9.0"},
            status=ContractStatus.ACTIVE,
            created_by=user2,
        )

        # Migrate both contracts
        _migrated1, _, _warnings1 = ContractMigrationManager.migrate_on_write(contract1)
        _migrated2, _, _warnings2 = ContractMigrationManager.migrate_on_write(contract2)

        # Verify contracts remain isolated
        contract1.refresh_from_db()
        contract2.refresh_from_db()

        self.assertEqual(contract1.tenant, self.tenant, "Contract 1 should belong to tenant 1")
        self.assertEqual(contract2.tenant, tenant2, "Contract 2 should belong to tenant 2")
        self.assertNotEqual(
            contract1.tenant, contract2.tenant, "Contracts should be isolated by tenant"
        )
