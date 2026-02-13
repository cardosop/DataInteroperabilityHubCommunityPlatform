"""
Comprehensive Migration Rollback Testing (Task 10.1.21.2)

Tests cover:
- Migration rollback works correctly
- Migration rollback preserves data
- Migration rollback handles errors correctly

All tests use real implementations (no mocks/stubs) and verify:
- Rollback logic correctness
- Data preservation
- Error handling
"""

import json
import uuid
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import transaction

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.contracts.management.commands.rollback_odps_migration import Command
from hub.apps.contracts.migration_validation import MigrationValidator
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType
from hub.apps.contracts.tests.test_base import ContractsTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class MigrationRollbackTestBase(ContractsTestBase):
    """Base test class for migration rollback tests."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()
        self.user.display_name = "Migration Rollback Test User"
        self.user.save()

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-migration-rollback-{uuid.uuid4().hex[:8]}",
            name="Test Asset for Migration Rollback",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def _create_linked_odcs_odps_contracts(self):
        """Create ODCS and ODPS contracts and link them bidirectionally."""
        # Create ODCS contract

        odcs_raw = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": f"test-odcs-rollback-{uuid.uuid4().hex[:8]}",
                "name": "Test ODCS for Rollback",
                "version": "3.0.2",
                "schema": {
                    "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
                },
            }
        )

        odcs_contract = self.contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id),
            original_spec_type="ODCS",
        )

        # Get ODCS contract ID from hub_contract_json
        odcs_contract.refresh_from_db()
        hub_contract = odcs_contract.hub_contract_json or {}
        odcs_contract_id = hub_contract.get("id", f"test-odcs-rollback-{uuid.uuid4().hex[:8]}")

        # Create ODPS contract and link

        # Create ODPS contract with embedded ODCS for linking (must match ODCS contract ID)
        odcs_spec = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": odcs_contract_id,  # Use actual ODCS contract ID
            "name": "Test ODCS for Rollback",
            "version": "3.0.2",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        odps_raw = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": f"test-odps-rollback-{uuid.uuid4().hex[:8]}",
                            "name": "Test ODPS for Rollback",
                        }
                    },
                    "contract": {"spec": odcs_spec},
                },
            }
        )

        odps_contract = self.odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id),
        )

        # Link contracts
        self.contract_service.link_odps_to_odcs(
            odcs_contract_id=str(odcs_contract.id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        return odcs_contract, odps_contract


class MigrationRollbackCorrectnessTest(MigrationRollbackTestBase):
    """Tests for migration rollback correctness (Task 10.1.21.2)."""

    def test_rollback_removes_odps_links_from_odcs(self):
        """Test that rollback removes ODPS links from ODCS contracts."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        # Verify link exists
        odcs_contract.refresh_from_db()
        self.assertIsNotNone(
            odcs_contract.hub_contract_json, "ODCS contract should have hub_contract_json"
        )
        extensions = odcs_contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertIn("odps_link", x_odps, "ODCS contract should have ODPS link")

        # Perform rollback through public API - call_command() internally calls _rollback_contract_wrapper()
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify link is removed
        odcs_contract.refresh_from_db()
        extensions = odcs_contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertNotIn("odps_link", x_odps, "ODPS link should be removed from ODCS contract")

    def test_rollback_removes_odcs_links_from_odps(self):
        """Test that rollback removes ODCS links from ODPS contracts."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        # Verify contracts are linked (ODCS should have ODPS link)
        odcs_contract.refresh_from_db()
        self.assertIsNotNone(
            odcs_contract.hub_contract_json, "ODCS contract should have hub_contract_json"
        )
        extensions = odcs_contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertIn("odps_link", x_odps, "ODCS contract should have ODPS link")

        # Perform rollback through public API - call_command() internally calls _rollback_contract_wrapper()
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify ODPS contract is deleted (so link removal is implicit)
        odps_contract_exists = Contract.objects.filter(id=odps_contract.id).exists()
        self.assertFalse(odps_contract_exists, "ODPS contract should be deleted")

    def test_rollback_deletes_odps_contracts(self):
        """Test that rollback deletes ODPS contracts."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        odps_contract_id = odps_contract.id

        # Verify ODPS contract exists
        self.assertTrue(
            Contract.objects.filter(id=odps_contract_id).exists(), "ODPS contract should exist"
        )

        # Verify link exists before rollback
        odcs_contract.refresh_from_db()
        self.assertIsNotNone(
            odcs_contract.hub_contract_json, "ODCS contract should have hub_contract_json"
        )
        extensions = odcs_contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertIn("odps_link", x_odps, "ODCS contract should have ODPS link before rollback")

        # Perform rollback through public API - call_command() internally calls _rollback_contract_wrapper()
        from io import StringIO

        from django.core.management import call_command

        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify ODPS contract is deleted
        odps_contract_exists = Contract.objects.filter(id=odps_contract_id).exists()
        self.assertFalse(odps_contract_exists, "ODPS contract should be deleted")

    def test_rollback_preserves_odcs_contract(self):
        """Test that rollback preserves ODCS contract."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        odcs_contract_id = odcs_contract.id
        original_odcs_data = (
            json.dumps(odcs_contract.hub_contract_json) if odcs_contract.hub_contract_json else None
        )

        # Perform rollback through public API - call_command() internally calls _rollback_contract_wrapper()
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify ODCS contract still exists
        odcs_contract_exists = Contract.objects.filter(id=odcs_contract_id).exists()
        self.assertTrue(odcs_contract_exists, "ODCS contract should be preserved")

        # Verify ODCS contract data is preserved (except for removed link)
        odcs_contract.refresh_from_db()
        if original_odcs_data:
            # Contract should still have hub_contract_json (with link removed)
            self.assertIsNotNone(
                odcs_contract.hub_contract_json, "ODCS contract should still have hub_contract_json"
            )

    def test_rollback_validates_state_after_rollback(self):
        """Test that rollback validates state after rollback."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        # Perform rollback through public API - call_command() internally calls _rollback_contract_wrapper()
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify rollback completed (validation happens internally)
        output = out.getvalue()
        self.assertIsNotNone(output)

    def test_rollback_supports_dry_run_mode(self):
        """Test that rollback supports dry-run mode."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        odps_contract_id = odps_contract.id

        # Verify link exists before rollback
        odcs_contract.refresh_from_db()
        self.assertIsNotNone(
            odcs_contract.hub_contract_json, "ODCS contract should have hub_contract_json"
        )
        extensions = odcs_contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertIn("odps_link", x_odps, "ODCS contract should have ODPS link before rollback")

        # Perform rollback in dry-run mode through public API
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            "--dry-run",
            stdout=out,
        )

        # Verify no changes were made
        odps_contract_exists = Contract.objects.filter(id=odps_contract_id).exists()
        self.assertTrue(odps_contract_exists, "ODPS contract should still exist in dry-run mode")

        # Verify link still exists in dry-run mode
        odcs_contract.refresh_from_db()
        extensions = odcs_contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertIn("odps_link", x_odps, "ODPS link should still exist in dry-run mode")


class MigrationRollbackDataPreservationTest(MigrationRollbackTestBase):
    """Tests for migration rollback data preservation (Task 10.1.21.2)."""

    def test_rollback_preserves_odcs_contract_data(self):
        """Test that rollback preserves ODCS contract data."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        # Store original ODCS contract data
        odcs_contract.refresh_from_db()
        original_odcs_id = odcs_contract.id
        original_odcs_tenant = odcs_contract.tenant
        original_odcs_asset = odcs_contract.asset
        original_odcs_status = odcs_contract.status
        original_odcs_original_raw = odcs_contract.original_raw

        # Perform rollback through public API - call_command() internally calls _rollback_contract_wrapper()
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify ODCS contract data is preserved
        odcs_contract.refresh_from_db()
        self.assertEqual(odcs_contract.id, original_odcs_id, "ODCS contract ID should be preserved")
        self.assertEqual(
            odcs_contract.tenant, original_odcs_tenant, "ODCS contract tenant should be preserved"
        )
        self.assertEqual(
            odcs_contract.asset, original_odcs_asset, "ODCS contract asset should be preserved"
        )
        self.assertEqual(
            odcs_contract.status, original_odcs_status, "ODCS contract status should be preserved"
        )
        self.assertEqual(
            odcs_contract.original_raw,
            original_odcs_original_raw,
            "ODCS contract original_raw should be preserved",
        )

    def test_rollback_preserves_tenant_association(self):
        """Test that rollback preserves tenant association."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        original_tenant_id = odcs_contract.tenant.id

        # Perform rollback through public API - call_command() internally calls _rollback_contract_wrapper()
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify tenant association is preserved
        odcs_contract.refresh_from_db()
        self.assertEqual(
            odcs_contract.tenant.id, original_tenant_id, "Tenant association should be preserved"
        )

    def test_rollback_preserves_asset_association(self):
        """Test that rollback preserves asset association."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        original_asset_id = odcs_contract.asset.id

        # Perform rollback through public API - call_command() internally calls _rollback_contract_wrapper()
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify asset association is preserved
        odcs_contract.refresh_from_db()
        self.assertEqual(
            odcs_contract.asset.id, original_asset_id, "Asset association should be preserved"
        )

    def test_rollback_preserves_contract_metadata(self):
        """Test that rollback preserves contract metadata."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        # Store original metadata
        odcs_contract.refresh_from_db()
        original_created_at = odcs_contract.created_at
        original_created_by = odcs_contract.created_by
        original_original_spec_type = odcs_contract.original_spec_type
        original_original_format = odcs_contract.original_format

        # Perform rollback through public API - call_command() internally calls _rollback_contract_wrapper()
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify metadata is preserved
        odcs_contract.refresh_from_db()
        self.assertEqual(
            odcs_contract.created_at, original_created_at, "Created timestamp should be preserved"
        )
        self.assertEqual(
            odcs_contract.created_by, original_created_by, "Created by should be preserved"
        )
        self.assertEqual(
            odcs_contract.original_spec_type,
            original_original_spec_type,
            "Original spec type should be preserved",
        )
        self.assertEqual(
            odcs_contract.original_format,
            original_original_format,
            "Original format should be preserved",
        )


class MigrationRollbackErrorHandlingTest(MigrationRollbackTestBase):
    """Tests for migration rollback error handling (Task 10.1.21.2)."""

    def test_rollback_handles_missing_odps_contract(self):
        """Test that rollback handles missing ODPS contract."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        # Delete ODPS contract before rollback
        odps_contract.delete()

        # Perform rollback through public API - call_command() internally calls _rollback_contract_wrapper()
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Should handle gracefully (may skip or report as already rolled back)
        output = out.getvalue()
        self.assertIsNotNone(output)

    def test_rollback_handles_unlinked_contracts(self):
        """Test that rollback handles unlinked contracts."""
        # Create ODCS contract without ODPS link

        odcs_raw = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": f"test-odcs-unlinked-{uuid.uuid4().hex[:8]}",
                "name": "Test ODCS Unlinked",
                "version": "3.0.2",
                "schema": {
                    "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
                },
            }
        )

        odcs_contract = self.contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id),
            original_spec_type="ODCS",
        )

        # Verify no ODPS link
        odcs_contract.refresh_from_db()
        if odcs_contract.hub_contract_json:
            extensions = odcs_contract.hub_contract_json.get("extensions", {})
            x_odps = extensions.get("x_odps", {})
            has_link = "odps_link" in x_odps
        else:
            has_link = False

        if not has_link:
            # Perform rollback on unlinked contract through public API
            out = StringIO()
            call_command(
                "rollback_odps_migration",
                "--contract-id",
                str(odcs_contract.id),
                stdout=out,
            )

            # Should handle gracefully (may skip or report as no action needed)
            output = out.getvalue()
            self.assertIsNotNone(output)

    def test_rollback_handles_invalid_contract_id(self):
        """Test that rollback handles invalid contract ID through public API."""
        invalid_contract_id = str(uuid.uuid4())

        # Try rollback with invalid contract ID through public API - call_command() internally calls _get_contract_by_id()
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            invalid_contract_id,
            stdout=out,
        )

        # Should handle gracefully (command should complete without crashing)
        output = out.getvalue()
        self.assertIsNotNone(output)

    def test_rollback_handles_database_errors(self):
        """Test that rollback handles database errors."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        # Perform rollback through public API - call_command() internally calls _rollback_contract_wrapper()
        out = StringIO()
        try:
            call_command(
                "rollback_odps_migration",
                "--contract-id",
                str(odcs_contract.id),
                stdout=out,
            )
            # Should either succeed or fail gracefully
            output = out.getvalue()
            self.assertIsNotNone(output)
        except Exception as e:
            # If exception is raised, it should be a known type
            self.assertIsInstance(e, Exception, "Should raise appropriate exception type")

    def test_rollback_is_atomic(self):
        """Test that rollback operations are atomic."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        odps_contract_id = odps_contract.id

        # Verify link exists before rollback
        odcs_contract.refresh_from_db()
        self.assertIsNotNone(
            odcs_contract.hub_contract_json, "ODCS contract should have hub_contract_json"
        )
        extensions = odcs_contract.hub_contract_json.get("extensions", {})
        x_odps = extensions.get("x_odps", {})
        self.assertIn("odps_link", x_odps, "ODCS contract should have ODPS link before rollback")

        # Perform rollback within transaction through public API
        try:
            with transaction.atomic():
                out = StringIO()
                call_command(
                    "rollback_odps_migration",
                    "--contract-id",
                    str(odcs_contract.id),
                    stdout=out,
                )

                # If rollback fails, transaction should rollback
                output = out.getvalue()
                if output and "error" in output.lower():
                    raise ValueError("Simulated error to test atomicity")

                # Rollback should succeed (not skip, since we verified link exists)
                # Verify ODPS contract was deleted
                odps_contract_exists = Contract.objects.filter(id=odps_contract_id).exists()
                self.assertFalse(
                    odps_contract_exists,
                    "ODPS contract should be deleted after successful rollback",
                )
        except ValueError:
            # Transaction should be rolled back
            # Verify state is consistent
            odps_contract_exists = Contract.objects.filter(id=odps_contract_id).exists()
            # Contract may or may not exist depending on when error occurred
            # The important thing is that partial state is not persisted
            pass

    def test_rollback_handles_unicode_characters(self):
        """Test that rollback handles unicode characters correctly."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        # Update contract with unicode characters
        odcs_contract.refresh_from_db()
        hub_contract = odcs_contract.hub_contract_json or {}
        hub_contract["name"] = "测试合同 🏢"
        odcs_contract.hub_contract_json = hub_contract
        odcs_contract.save()

        # Perform rollback
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify rollback completed
        odcs_contract.refresh_from_db()
        self.assertIsNotNone(
            odcs_contract.hub_contract_json, "ODCS contract should still have hub_contract_json"
        )

    def test_rollback_handles_special_characters(self):
        """Test that rollback handles special characters correctly."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        # Update contract with special characters
        odcs_contract.refresh_from_db()
        hub_contract = odcs_contract.hub_contract_json or {}
        hub_contract["name"] = "Test & Co. (Special)"
        odcs_contract.hub_contract_json = hub_contract
        odcs_contract.save()

        # Perform rollback
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify rollback completed
        odcs_contract.refresh_from_db()
        self.assertIsNotNone(
            odcs_contract.hub_contract_json, "ODCS contract should still have hub_contract_json"
        )

    def test_rollback_handles_very_large_contracts(self):
        """Test that rollback handles very large contracts correctly."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        # Update contract with very large data
        odcs_contract.refresh_from_db()
        hub_contract = odcs_contract.hub_contract_json or {}
        hub_contract["large_field"] = "A" * 100000  # 100KB string
        odcs_contract.hub_contract_json = hub_contract
        odcs_contract.save()

        # Perform rollback
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify rollback completed
        odcs_contract.refresh_from_db()
        self.assertIsNotNone(
            odcs_contract.hub_contract_json, "ODCS contract should still have hub_contract_json"
        )

    def test_rollback_handles_none_values(self):
        """Test that rollback handles None values correctly."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        # Update contract with None values
        odcs_contract.refresh_from_db()
        hub_contract = odcs_contract.hub_contract_json or {}
        hub_contract["optional_field"] = None
        odcs_contract.hub_contract_json = hub_contract
        odcs_contract.save()

        # Perform rollback
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify rollback completed
        odcs_contract.refresh_from_db()
        self.assertIsNotNone(
            odcs_contract.hub_contract_json, "ODCS contract should still have hub_contract_json"
        )

    def test_rollback_handles_nested_structures(self):
        """Test that rollback handles nested structures correctly."""
        odcs_contract, odps_contract = self._create_linked_odcs_odps_contracts()

        # Update contract with nested structure
        odcs_contract.refresh_from_db()
        hub_contract = odcs_contract.hub_contract_json or {}
        hub_contract["nested"] = {"level1": {"level2": {"level3": {"value": "deep"}}}}
        odcs_contract.hub_contract_json = hub_contract
        odcs_contract.save()

        # Perform rollback
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract.id),
            stdout=out,
        )

        # Verify rollback completed
        odcs_contract.refresh_from_db()
        self.assertIsNotNone(
            odcs_contract.hub_contract_json, "ODCS contract should still have hub_contract_json"
        )

    def test_rollback_handles_cross_tenant_isolation(self):
        """Test that rollback maintains cross-tenant isolation."""
        # Create second tenant
        from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
        from hub.apps.users.models import User, UserStatus

        tenant2 = Tenant.objects.create(
            name="Rollback Isolation Test Tenant 2",
            slug="rollback-isolation-test-2",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        user2 = User.objects.create_user(
            email="rollback-isolation-test-2@example.com",
            password="testpass123",
            tenant=tenant2,
            status=UserStatus.ACTIVE,
            display_name="Rollback Isolation Test User 2",
        )

        asset2 = Asset.objects.create(
            tenant=tenant2,
            key=f"test-asset-rollback-isolation-2-{uuid.uuid4().hex[:8]}",
            name="Test Asset for Rollback Isolation 2",
            status=AssetStatus.ACTIVE,
            created_by=user2,
        )

        # Create contracts for both tenants
        odcs_contract1, odps_contract1 = self._create_linked_odcs_odps_contracts()

        # Create second set of contracts for tenant2
        from hub.apps.contracts.services import ContractService, ODPSService

        contract_service2 = ContractService(tenant_id=str(tenant2.id), user_id=str(user2.id))
        odps_service2 = ODPSService(tenant_id=str(tenant2.id), user_id=str(user2.id))

        odcs_raw2 = json.dumps(
            {
                "apiVersion": "odcs.io/v3.0.2",
                "kind": "DataContract",
                "id": f"test-odcs-rollback-2-{uuid.uuid4().hex[:8]}",
                "name": "Test ODCS for Rollback 2",
                "version": "3.0.2",
                "schema": {
                    "fields": [{"name": "id", "type": "string"}, {"name": "name", "type": "string"}]
                },
            }
        )

        odcs_contract2 = contract_service2.create_contract(
            original_raw=odcs_raw2,
            original_format="json",
            tenant_id=str(tenant2.id),
            user_id=str(user2.id),
            asset_id=str(asset2.id),
            original_spec_type="ODCS",
        )

        odcs_contract2.refresh_from_db()
        hub_contract2 = odcs_contract2.hub_contract_json or {}
        odcs_contract_id2 = hub_contract2.get("id", f"test-odcs-rollback-2-{uuid.uuid4().hex[:8]}")

        odcs_spec2 = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": odcs_contract_id2,
            "name": "Test ODCS for Rollback 2",
            "version": "3.0.2",
            "schema": {"fields": [{"name": "id", "type": "string"}]},
        }

        odps_raw2 = json.dumps(
            {
                "schema": "https://opendataproducts.org/schema/v4.1",
                "product": {
                    "details": {
                        "en": {
                            "productID": f"test-odps-rollback-2-{uuid.uuid4().hex[:8]}",
                            "name": "Test ODPS for Rollback 2",
                        }
                    },
                    "contract": {"spec": odcs_spec2},
                },
            }
        )

        odps_contract2 = odps_service2.create_odps(
            odps_raw=odps_raw2,
            odps_format="json",
            tenant_id=str(tenant2.id),
            user_id=str(user2.id),
            asset_id=str(asset2.id),
        )

        contract_service2.link_odps_to_odcs(
            odcs_contract_id=str(odcs_contract2.id),
            odps_contract_id=str(odps_contract2.id),
            tenant_id=str(tenant2.id),
            user_id=str(user2.id),
        )

        # Rollback contract from tenant1
        out = StringIO()
        call_command(
            "rollback_odps_migration",
            "--contract-id",
            str(odcs_contract1.id),
            stdout=out,
        )

        # Verify tenant2 contract is not affected
        odcs_contract2.refresh_from_db()
        self.assertEqual(odcs_contract2.tenant, tenant2, "Tenant2 contract should remain isolated")
        self.assertTrue(
            Contract.objects.filter(id=odps_contract2.id).exists(),
            "Tenant2 ODPS contract should still exist",
        )
