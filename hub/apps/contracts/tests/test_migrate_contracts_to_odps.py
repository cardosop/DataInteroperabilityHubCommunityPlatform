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
import pytest
from io import StringIO
from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth import get_user_model

from hub.apps.contracts.models import Contract, OriginalSpecType, OriginalFormat
from hub.apps.contracts.management.commands.migrate_contracts_to_odps import Command
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import UserStatus
from hub.apps.assets.models import Asset, AssetStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class MigrateContractsToODPSTestBase(TestCase):
    """Base test class for migration command tests."""

    def setUp(self):
        """Set up test fixtures."""
        # Create tenant
        self.tenant = Tenant.objects.create(
            name="Migration Test Tenant",
            slug="migration-test",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )

        # Create user
        self.user = User.objects.create_user(
            email="migration-test@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            display_name="Migration Test User",
        )

        # Create asset
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-migration",
            name="Test Asset for Migration",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

    def _create_odcs_contract_with_marketplace(
        self,
        marketplace_data: dict = None,
        has_odps_link: bool = False
    ) -> Contract:
        """Create an ODCS contract with marketplace metadata."""
        from hub.apps.contracts.services import ContractService

        contract_service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create ODCS contract
        odcs_raw = json.dumps({
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-odcs-migration",
            "name": "Test ODCS for Migration",
            "version": "3.0.2",
            "schema": {
                "fields": [
                    {"name": "id", "type": "string"},
                    {"name": "name", "type": "string"}
                ]
            }
        })

        contract = contract_service.create_contract(
            original_raw=odcs_raw,
            original_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id),
            original_spec_type="ODCS"
        )

        # Add marketplace metadata to HubContract
        if marketplace_data or has_odps_link:
            hub_contract = contract.hub_contract_json or {}
            if marketplace_data:
                hub_contract['marketplace'] = marketplace_data
            if has_odps_link:
                # Add fake ODPS link
                if 'extensions' not in hub_contract:
                    hub_contract['extensions'] = {}
                if 'x_odps' not in hub_contract['extensions']:
                    hub_contract['extensions']['x_odps'] = {}
                hub_contract['extensions']['x_odps']['odps_link'] = '00000000-0000-0000-0000-000000000000'

            contract.hub_contract_json = hub_contract
            contract.save(update_fields=['hub_contract_json'])

        return contract


class FindEligibleContractsTest(MigrateContractsToODPSTestBase):
    """Tests for finding eligible contracts."""

    def test_find_contracts_with_marketplace_metadata(self):
        """Test finding ODCS contracts with marketplace metadata."""
        # Create contract with marketplace data
        marketplace_data = {
            'license_summary': 'Test license',
            'intended_use': ['analytics'],
            'x_odps': {
                'pricing_plans': [{'name': 'Basic', 'price': 10}]
            }
        }
        contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Find eligible contracts
        command = Command()
        eligible = command._find_eligible_contracts(
            tenant_id=str(self.tenant.id),
            skip_linked=False,
            min_marketplace_fields=1
        )

        self.assertEqual(len(eligible), 1)
        self.assertEqual(str(eligible[0].id), str(contract.id))

    def test_skip_contracts_without_marketplace_metadata(self):
        """Test skipping contracts without marketplace metadata."""
        # Create contract without marketplace data
        contract = self._create_odcs_contract_with_marketplace()

        # Find eligible contracts (requires at least 1 marketplace field)
        command = Command()
        eligible = command._find_eligible_contracts(
            tenant_id=str(self.tenant.id),
            skip_linked=False,
            min_marketplace_fields=1
        )

        self.assertEqual(len(eligible), 0)

    def test_skip_contracts_with_odps_link(self):
        """Test skipping contracts that already have ODPS links."""
        # Create ODCS contract first
        marketplace_data = {
            'license_summary': 'Test license'
        }
        odcs_contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Create and link ODPS contract
        from hub.apps.contracts.services import ODPSService, ContractService
        odps_service = ODPSService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Get the actual ODCS contract ID from the contract
        odcs_contract_id = odcs_contract.hub_contract_json.get('id', 'test-odcs-migration')

        # Create ODPS with embedded ODCS contract (required for linking)
        odcs_spec = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": odcs_contract_id,
            "name": "Test ODCS for Migration",
            "version": "3.0.2",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            }
        }

        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-odps",
                        "name": "Test ODPS"
                    }
                },
                "contract": {
                    "spec": odcs_spec
                }
            }
        })

        odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id)
        )

        # Link them
        contract_service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(odcs_contract.id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Find eligible contracts (skip linked)
        command = Command()
        eligible = command._find_eligible_contracts(
            tenant_id=str(self.tenant.id),
            skip_linked=True,
            min_marketplace_fields=1
        )

        self.assertEqual(len(eligible), 0)

    def test_count_marketplace_fields(self):
        """Test counting marketplace fields."""
        marketplace_data = {
            'license_summary': 'Test license',
            'intended_use': ['analytics'],
            'restricted_use': ['commercial'],
            'x_odps': {
                'pricing_plans': [{'name': 'Basic'}],
                'access_methods': {'api': {}},
                'payment_gateways': {'stripe': {}}
            }
        }
        contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        command = Command()
        count = command._count_marketplace_fields(contract)

        # Should count: license_summary, intended_use, restricted_use,
        # pricing_plans, access_methods, payment_gateways = 6
        self.assertEqual(count, 6)


class MigrateContractTest(MigrateContractsToODPSTestBase):
    """Tests for migrating individual contracts."""

    def test_migrate_contract_creates_odps_and_links(self):
        """Test migrating a contract creates ODPS and links it."""
        # Create ODCS contract with marketplace data
        marketplace_data = {
            'license_summary': 'Test license',
            'intended_use': ['analytics'],
            'x_odps': {
                'pricing_plans': [{'name': 'Basic', 'price': 10}]
            }
        }
        odcs_contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Migrate contract
        command = Command()
        result = command._migrate_contract(
            contract=odcs_contract,
            target_odps_version='4.1',
            dry_run=False
        )

        self.assertEqual(result['status'], 'migrated')
        self.assertIn('odps_contract_id', result)

        # Verify ODPS contract was created
        odps_contract_id = result['odps_contract_id']
        odps_contract = Contract.objects.get(id=odps_contract_id)
        self.assertEqual(odps_contract.original_spec_type, OriginalSpecType.ODPS)
        self.assertEqual(str(odps_contract.tenant_id), str(odcs_contract.tenant_id))

        # Verify bidirectional link
        odcs_contract.refresh_from_db()
        hub_contract = odcs_contract.hub_contract_json
        extensions = hub_contract.get('extensions', {})
        x_odps = extensions.get('x_odps', {})
        self.assertEqual(str(x_odps.get('odps_link')), str(odps_contract_id))

        odps_hub_contract = odps_contract.hub_contract_json
        odps_extensions = odps_hub_contract.get('extensions', {})
        odps_x_odps = odps_extensions.get('x_odps', {})
        self.assertEqual(odps_x_odps.get('odcs_link'), str(odcs_contract.id))

    def test_migrate_contract_dry_run(self):
        """Test dry-run mode doesn't create contracts."""
        marketplace_data = {
            'license_summary': 'Test license'
        }
        odcs_contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Count contracts before
        initial_count = Contract.objects.filter(
            original_spec_type=OriginalSpecType.ODPS
        ).count()

        # Migrate in dry-run mode
        command = Command()
        result = command._migrate_contract(
            contract=odcs_contract,
            target_odps_version='4.1',
            dry_run=True
        )

        self.assertEqual(result['status'], 'migrated')
        self.assertEqual(result['odps_contract_id'], 'DRY-RUN')

        # Verify no contracts were created
        final_count = Contract.objects.filter(
            original_spec_type=OriginalSpecType.ODPS
        ).count()
        self.assertEqual(initial_count, final_count)

    def test_migrate_contract_skips_if_already_linked(self):
        """Test migration skips contracts that already have ODPS links."""
        # Create ODPS contract first with embedded ODCS contract
        from hub.apps.contracts.services import ODPSService
        odps_service = ODPSService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Create ODPS with embedded ODCS contract (required for linking)
        odcs_spec = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": "test-odcs-migration",
            "name": "Test ODCS for Migration",
            "version": "3.0.2",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            }
        }

        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-odps",
                        "name": "Test ODPS"
                    }
                },
                "contract": {
                    "spec": odcs_spec
                }
            }
        })

        odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id)
        )

        # Create ODCS contract and link it
        marketplace_data = {
            'license_summary': 'Test license'
        }
        odcs_contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Link them
        from hub.apps.contracts.services import ContractService
        contract_service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(odcs_contract.id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Refresh contract from database to get updated links
        odcs_contract.refresh_from_db()

        # Try to migrate (should skip)
        command = Command()
        result = command._migrate_contract(
            contract=odcs_contract,
            target_odps_version='4.1',
            dry_run=False
        )

        self.assertEqual(result['status'], 'skipped')
        self.assertIn('already has ODPS link', result['reason'])


class CommandIntegrationTest(MigrateContractsToODPSTestBase):
    """Integration tests for the management command."""

    def test_command_dry_run_mode(self):
        """Test command in dry-run mode."""
        # Create contract with marketplace data
        marketplace_data = {
            'license_summary': 'Test license',
            'intended_use': ['analytics']
        }
        self._create_odcs_contract_with_marketplace(marketplace_data)

        # Run command in dry-run mode
        out = StringIO()
        call_command(
            'migrate_contracts_to_odps',
            '--dry-run',
            '--tenant-id', str(self.tenant.id),
            stdout=out
        )

        output = out.getvalue()
        self.assertIn('DRY-RUN MODE', output)
        self.assertIn('No database changes will be made', output)

    def test_command_per_contract_mode(self):
        """Test command in per-contract mode."""
        # Create contract with marketplace data
        marketplace_data = {
            'license_summary': 'Test license',
            'x_odps': {
                'pricing_plans': [{'name': 'Basic'}]
            }
        }
        contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Run command for specific contract
        out = StringIO()
        call_command(
            'migrate_contracts_to_odps',
            '--contract-id', str(contract.id),
            stdout=out
        )

        output = out.getvalue()
        self.assertIn('Migrated', output)

        # Verify ODPS contract was created
        odps_contracts = Contract.objects.filter(
            original_spec_type=OriginalSpecType.ODPS,
            tenant_id=self.tenant.id
        )
        self.assertEqual(odps_contracts.count(), 1)

    def test_command_batch_mode(self):
        """Test command in batch mode."""
        # Create multiple contracts with marketplace data
        for i in range(3):
            marketplace_data = {
                'license_summary': f'License {i}',
                'intended_use': ['analytics']
            }
            self._create_odcs_contract_with_marketplace(marketplace_data)

        # Run command in batch mode
        out = StringIO()
        call_command(
            'migrate_contracts_to_odps',
            '--tenant-id', str(self.tenant.id),
            '--batch-size', '10',
            stdout=out
        )

        output = out.getvalue()
        self.assertIn('Found 3 ODCS contract(s)', output)
        self.assertIn('Migrated: 3', output)

        # Verify ODPS contracts were created
        odps_contracts = Contract.objects.filter(
            original_spec_type=OriginalSpecType.ODPS,
            tenant_id=self.tenant.id
        )
        self.assertEqual(odps_contracts.count(), 3)

    def test_command_skip_linked(self):
        """Test command with --skip-linked option."""
        # Create ODCS contract with marketplace data
        marketplace_data = {
            'license_summary': 'Test license'
        }
        contract = self._create_odcs_contract_with_marketplace(marketplace_data)

        # Create and link ODPS contract
        from hub.apps.contracts.services import ODPSService, ContractService
        odps_service = ODPSService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Get the actual ODCS contract ID from the contract
        odcs_contract_id = contract.hub_contract_json.get('id', 'test-odcs-migration')

        # Create ODPS with embedded ODCS contract (required for linking)
        odcs_spec = {
            "apiVersion": "odcs.io/v3.0.2",
            "kind": "DataContract",
            "id": odcs_contract_id,
            "name": "Test ODCS for Migration",
            "version": "3.0.2",
            "schema": {
                "fields": [{"name": "id", "type": "string"}]
            }
        }

        odps_raw = json.dumps({
            "schema": "https://opendataproducts.org/schema/v4.1",
            "product": {
                "details": {
                    "en": {
                        "productID": "test-odps",
                        "name": "Test ODPS"
                    }
                },
                "contract": {
                    "spec": odcs_spec
                }
            }
        })

        odps_contract = odps_service.create_odps(
            odps_raw=odps_raw,
            odps_format="json",
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            asset_id=str(self.asset.id)
        )

        contract_service = ContractService(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        contract_service.link_odps_to_odcs(
            odcs_contract_id=str(contract.id),
            odps_contract_id=str(odps_contract.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id)
        )

        # Run command with --skip-linked
        out = StringIO()
        call_command(
            'migrate_contracts_to_odps',
            '--tenant-id', str(self.tenant.id),
            '--skip-linked',
            stdout=out
        )

        output = out.getvalue()
        self.assertIn('Found 0 ODCS contract(s)', output)

    def test_command_min_marketplace_fields(self):
        """Test command with --min-marketplace-fields option."""
        # Create contract with minimal marketplace data
        marketplace_data = {
            'license_summary': 'Test license'
        }
        self._create_odcs_contract_with_marketplace(marketplace_data)

        # Run command requiring 2 marketplace fields
        out = StringIO()
        call_command(
            'migrate_contracts_to_odps',
            '--tenant-id', str(self.tenant.id),
            '--min-marketplace-fields', '2',
            stdout=out
        )

        output = out.getvalue()
        self.assertIn('Found 0 ODCS contract(s)', output)

        # Run command requiring 1 marketplace field
        out = StringIO()
        call_command(
            'migrate_contracts_to_odps',
            '--tenant-id', str(self.tenant.id),
            '--min-marketplace-fields', '1',
            stdout=out
        )

        output = out.getvalue()
        self.assertIn('Found 1 ODCS contract(s)', output)

