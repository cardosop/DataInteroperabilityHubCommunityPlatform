"""
Contract Migration Tests
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from hub.apps.tenants.models import Tenant
from hub.apps.contracts.models import Contract, ContractStatus, OriginalSpecType, OriginalFormat
from hub.apps.contracts.migration import (
    migrate_hubcontract,
    migrate_hubcontract_v1_to_v2,
    get_current_hubcontract_version,
    needs_migration,
    can_migrate,
    MigrationStrategy,
)
from hub.apps.contracts.migration_manager import ContractMigrationManager
from hub.apps.jobs.models import Job, JobType, JobStatus


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class MigrationTest(TestCase):
    """Test contract migration logic"""
    
    def setUp(self):
        """Set up test data"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        
        # Create a contract with v1.0.0 HubContract
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.DRAFT,
            original_spec_type=OriginalSpecType.ODCS,
            original_spec_version="3.0.0",
            original_format=OriginalFormat.JSON,
            original_raw='{"id": "test", "name": "Test Contract", "schema": {"fields": []}}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                'hub_contract_version': 1,
                'id': 'test',
                'info': {
                    'name': 'Test Contract',
                    'description': 'Test description',
                    'version': '1.0.0'
                },
                'schema': {
                    'fields': [
                        {'name': 'field1', 'type': 'string', 'nullable': True}
                    ]
                }
            },
            normalization_status="NORMALIZED_OK",
            created_by=self.user
        )
    
    def test_get_current_hubcontract_version(self):
        """Test getting current HubContract version"""
        version = get_current_hubcontract_version()
        self.assertEqual(version, "1.0.0")
    
    def test_needs_migration(self):
        """Test needs_migration check"""
        # Contract at current version doesn't need migration
        self.assertFalse(needs_migration("1.0.0"))
        
        # Contract at older version needs migration
        # needs_migration returns True if version differs from current
        self.assertTrue(needs_migration("0.9.0"))  # Different from current version
    
    def test_can_migrate(self):
        """Test can_migrate check"""
        # Can migrate v1 -> v2 (v2 migration is implemented)
        self.assertTrue(can_migrate("1.0.0", "2.0.0"))
        
        # Cannot downgrade
        self.assertFalse(can_migrate("2.0.0", "1.0.0"))
        
        # Same version doesn't need migration (but can_migrate checks if path exists)
        # Same version returns False (no migration path needed)
        self.assertFalse(can_migrate("1.0.0", "1.0.0"))
    
    def test_migrate_hubcontract_v1_to_v2(self):
        """Test migration from v1 to v2 (placeholder)"""
        hub_contract_v1 = {
            'hub_contract_version': 1,
            'id': 'test',
            'info': {
                'name': 'Test Contract',
                'description': 'Test description'
            },
            'schema': {
                'fields': []
            }
        }
        
        # For now, v2 migration is a placeholder (returns same structure)
        migrated, warnings = migrate_hubcontract_v1_to_v2(hub_contract_v1)
        
        self.assertIsNotNone(migrated)
        self.assertEqual(migrated['hub_contract_version'], 2)
        self.assertIsInstance(warnings, list)
    
    def test_migrate_hubcontract_same_version(self):
        """Test migration with same version (no-op)"""
        hub_contract = {
            'hub_contract_version': 1,
            'id': 'test',
            'info': {'name': 'Test'},
            'schema': {'fields': []}
        }
        
        migrated, warnings, errors = migrate_hubcontract(
            hub_contract,
            "1.0.0",
            "1.0.0"
        )
        
        self.assertEqual(migrated, hub_contract)
        self.assertEqual(len(warnings), 0)
        self.assertEqual(len(errors), 0)
    
    def test_migrate_hubcontract_invalid_version(self):
        """Test migration with invalid version format"""
        hub_contract = {
            'hub_contract_version': 1,
            'id': 'test',
            'info': {'name': 'Test'},
            'schema': {'fields': []}
        }
        
        migrated, warnings, errors = migrate_hubcontract(
            hub_contract,
            "invalid",
            "1.0.0"
        )
        
        self.assertIsNone(migrated)
        self.assertGreater(len(errors), 0)
    
    def test_migrate_on_write(self):
        """Test ON_WRITE migration strategy"""
        # Contract is at v1.0.0, current is v1.0.0, so no migration needed
        migrated, migrated_hub_contract, warnings = ContractMigrationManager.migrate_on_write(self.contract)
        
        # No migration needed (v1 is current)
        self.assertFalse(migrated)
    
    def test_migrate_on_read(self):
        """Test ON_READ migration strategy (lazy migration)"""
        # Contract is at v1.0.0, current is v1.0.0, so no migration needed
        migrated_hub_contract, warnings = ContractMigrationManager.migrate_on_read(self.contract)
        
        # Should return original contract (no migration needed)
        self.assertEqual(migrated_hub_contract, self.contract.hub_contract_json)
    
    def test_migrate_background(self):
        """Test BACKGROUND migration strategy"""
        # Contract is at v1.0.0, current is v1.0.0, so no migration needed
        job = ContractMigrationManager.migrate_background(self.contract, user=self.user)
        
        # No migration needed (v1 is current)
        self.assertIsNone(job)
    
    def test_ensure_migrated_on_read(self):
        """Test ensure_migrated with ON_READ strategy"""
        hub_contract, warnings = ContractMigrationManager.ensure_migrated(
            self.contract,
            strategy=MigrationStrategy.ON_READ
        )
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(hub_contract, self.contract.hub_contract_json)
    
    def test_ensure_migrated_on_write(self):
        """Test ensure_migrated with ON_WRITE strategy"""
        hub_contract, warnings = ContractMigrationManager.ensure_migrated(
            self.contract,
            strategy=MigrationStrategy.ON_WRITE
        )
        
        self.assertIsNotNone(hub_contract)
        self.assertEqual(hub_contract, self.contract.hub_contract_json)

