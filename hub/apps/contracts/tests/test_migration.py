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


class EnhancedMigrationTest(TestCase):
    """Test enhanced migration logic for all sections (GAP-10.2.1)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="VERIFIED"
        )
        
        # Create v1 contract with all sections
        self.contract_v1_full = {
            'hub_contract_version': 1,
            'info': {
                'name': 'Test Contract',
                'owners': [
                    {'name': 'John Doe', 'email': 'john@example.com'}
                ],
                'tags': ['analytics', 'sales']
            },
            'schema': {
                'fields': [
                    {
                        'name': 'id',
                        'data_type': 'string',
                        'nullable': False
                    },
                    {
                        'name': 'email',
                        'data_type': 'string',
                        'nullable': True
                    }
                ],
                'primary_key': ['id']
            },
            'quality': {
                'rules': [
                    {
                        'rule_id': 'rule1',
                        'dimension': 'completeness',
                        'expression': 'id IS NOT NULL',
                        'severity': 'ERROR'
                    }
                ],
                'default_profile_key': 'custom_profile'
            },
            'privacy_compliance': {
                'contains_personal_data': True,
                'personal_data_categories': ['EMAIL'],
                'jurisdictions': ['GDPR'],
                'legal_bases': ['CONSENT']
            },
            'lifecycle': {
                'data_source': 'database',
                'refresh_cadence': 'daily'
            },
            'marketplace': {
                'license_summary': 'MIT License',
                'intended_use': ['ANALYTICS'],
                'restricted_use': ['COMMERCIAL']
            }
        }
        
        # Create v1 contract with missing sections
        self.contract_v1_minimal = {
            'hub_contract_version': 1,
            'info': {
                'name': 'Minimal Contract'
            },
            'schema': {
                'fields': [
                    {
                        'name': 'id',
                        'data_type': 'string'
                    }
                ]
            }
        }
        
        # Create v1 contract with owners/tags in extensions
        self.contract_v1_extensions = {
            'hub_contract_version': 1,
            'info': {
                'name': 'Contract with Extensions'
            },
            'schema': {
                'fields': []
            },
            'extensions': {
                'odcs': {
                    'owners': [
                        {'name': 'Jane Smith', 'email': 'jane@example.com'}
                    ],
                    'tags': ['marketing']
                }
            }
        }
    
    def test_migration_of_all_sections(self):
        """Test migration of all sections from v1 to v2 (GAP-10.2.1)"""
        migrated, warnings = migrate_hubcontract_v1_to_v2(self.contract_v1_full)
        
        # Verify version is updated
        self.assertEqual(migrated['hub_contract_version'], 2)
        
        # Verify all sections are preserved
        self.assertIn('info', migrated)
        self.assertIn('schema', migrated)
        self.assertIn('quality', migrated)
        self.assertIn('privacy_compliance', migrated)
        self.assertIn('lifecycle', migrated)
        self.assertIn('marketplace', migrated)
        
        # Verify owners and tags are preserved
        self.assertIn('owners', migrated['info'])
        self.assertEqual(len(migrated['info']['owners']), 1)
        self.assertIn('tags', migrated['info'])
        self.assertEqual(len(migrated['info']['tags']), 2)
        
        # Verify quality section is preserved
        self.assertIn('rules', migrated['quality'])
        self.assertEqual(len(migrated['quality']['rules']), 1)
        self.assertEqual(migrated['quality']['default_profile_key'], 'custom_profile')
        
        # Verify compliance section is preserved
        self.assertTrue(migrated['privacy_compliance']['contains_personal_data'])
        self.assertEqual(len(migrated['privacy_compliance']['personal_data_categories']), 1)
        self.assertEqual(len(migrated['privacy_compliance']['jurisdictions']), 1)
        
        # Verify lifecycle section is preserved
        self.assertEqual(migrated['lifecycle']['data_source'], 'database')
        self.assertEqual(migrated['lifecycle']['refresh_cadence'], 'daily')
        
        # Verify marketplace section is preserved
        self.assertEqual(migrated['marketplace']['license_summary'], 'MIT License')
        self.assertEqual(len(migrated['marketplace']['intended_use']), 1)
        self.assertEqual(len(migrated['marketplace']['restricted_use']), 1)
    
    def test_migration_warnings_generated_for_missing_sections(self):
        """Test that migration warnings are generated for missing sections (GAP-10.2.1)"""
        migrated, warnings = migrate_hubcontract_v1_to_v2(self.contract_v1_minimal)
        
        # Verify warnings are generated
        self.assertGreater(len(warnings), 0)
        
        # Verify warnings mention missing sections
        warning_text = ' '.join(warnings)
        self.assertIn('quality', warning_text.lower())
        self.assertIn('privacy_compliance', warning_text.lower())
        self.assertIn('lifecycle', warning_text.lower())
        self.assertIn('marketplace', warning_text.lower())
    
    def test_migration_of_owners_from_extensions(self):
        """Test migration of owners from extensions (GAP-10.2.1)"""
        migrated, warnings = migrate_hubcontract_v1_to_v2(self.contract_v1_extensions)
        
        # Verify owners are migrated from extensions
        self.assertIn('owners', migrated['info'])
        self.assertEqual(len(migrated['info']['owners']), 1)
        self.assertEqual(migrated['info']['owners'][0]['name'], 'Jane Smith')
        
        # Verify warning is generated
        warning_text = ' '.join(warnings)
        self.assertIn('owners', warning_text.lower())
        self.assertIn('extensions', warning_text.lower())
    
    def test_migration_of_tags_from_extensions(self):
        """Test migration of tags from extensions (GAP-10.2.1)"""
        migrated, warnings = migrate_hubcontract_v1_to_v2(self.contract_v1_extensions)
        
        # Verify tags are migrated from extensions
        self.assertIn('tags', migrated['info'])
        self.assertEqual(len(migrated['info']['tags']), 1)
        self.assertIn('marketing', migrated['info']['tags'])
        
        # Verify warning is generated
        warning_text = ' '.join(warnings)
        self.assertIn('tags', warning_text.lower())
        self.assertIn('extensions', warning_text.lower())
    
    def test_migration_of_field_properties(self):
        """Test migration of field properties (GAP-10.2.1)"""
        migrated, warnings = migrate_hubcontract_v1_to_v2(self.contract_v1_full)
        
        # Verify field properties are added
        fields = migrated['schema']['fields']
        self.assertEqual(len(fields), 2)
        
        # Verify all enhanced properties are present (even if None)
        for field in fields:
            self.assertIn('semantic_type', field)
            self.assertIn('format', field)
            self.assertIn('pattern', field)
            self.assertIn('enum', field)
            self.assertIn('default', field)
            self.assertIn('min_length', field)
            self.assertIn('max_length', field)
            self.assertIn('minimum', field)
            self.assertIn('maximum', field)
            self.assertIn('metadata', field)
            self.assertIn('is_primary_key', field)
            self.assertIn('is_unique', field)
            self.assertIn('is_indexed', field)
        
        # Verify primary key flag is set correctly
        id_field = next(f for f in fields if f['name'] == 'id')
        self.assertTrue(id_field['is_primary_key'])
    
    def test_migration_of_compliance_section_rename(self):
        """Test migration of old 'compliance' key to 'privacy_compliance' (GAP-10.2.1)"""
        contract_v1_old_compliance = {
            'hub_contract_version': 1,
            'info': {'name': 'Test'},
            'schema': {'fields': []},
            'compliance': {
                'contains_personal_data': True
            }
        }
        
        migrated, warnings = migrate_hubcontract_v1_to_v2(contract_v1_old_compliance)
        
        # Verify old 'compliance' key is renamed
        self.assertNotIn('compliance', migrated)
        self.assertIn('privacy_compliance', migrated)
        self.assertTrue(migrated['privacy_compliance']['contains_personal_data'])
        
        # Verify warning is generated
        warning_text = ' '.join(warnings)
        self.assertIn('compliance', warning_text.lower())
        self.assertIn('privacy_compliance', warning_text.lower())


class BackwardCompatibilityTest(TestCase):
    """Test backward compatibility with v1 and v2 contracts (GAP-10.2.2)"""
    
    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant",
            status="ACTIVE",
            kyc_status="VERIFIED"
        )
        
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        
        # Create v1 contract
        self.contract_v1 = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.DATACONTRACT_COM,
            original_spec_version="2.2.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "2.2.2", "name": "test"}',
            status=ContractStatus.DRAFT,
            hub_contract_version="1.0.0",
            hub_contract_json={
                'hub_contract_version': 1,
                'info': {'name': 'V1 Contract'},
                'schema': {'fields': []}
            }
        )
        
        # Create v2 contract
        self.contract_v2 = Contract.objects.create(
            tenant=self.tenant,
            original_spec_type=OriginalSpecType.DATACONTRACT_COM,
            original_spec_version="2.2.2",
            original_format=OriginalFormat.JSON,
            original_raw='{"version": "2.2.2", "name": "test"}',
            status=ContractStatus.DRAFT,
            hub_contract_version="2.0.0",
            hub_contract_json={
                'hub_contract_version': 2,
                'info': {
                    'name': 'V2 Contract',
                    'owners': [{'name': 'John', 'email': 'john@example.com'}],
                    'tags': ['analytics']
                },
                'schema': {'fields': []},
                'quality': {'rules': []},
                'privacy_compliance': {'contains_personal_data': False},
                'lifecycle': {},
                'marketplace': {}
            }
        )
    
    def test_v1_contract_works(self):
        """Test that v1 contracts work (backward compatible) (GAP-10.2.2)"""
        # Verify v1 contract can be retrieved
        self.assertEqual(self.contract_v1.hub_contract_version, "1.0.0")
        self.assertIsNotNone(self.contract_v1.hub_contract_json)
        self.assertIn('info', self.contract_v1.hub_contract_json)
        
        # Verify ON_READ migration works (lazy migration)
        migrated, warnings = ContractMigrationManager.migrate_on_read(self.contract_v1)
        self.assertIsNotNone(migrated)
    
    def test_v2_contract_works(self):
        """Test that v2 contracts work (GAP-10.2.2)"""
        # Verify v2 contract can be retrieved
        self.assertEqual(self.contract_v2.hub_contract_version, "2.0.0")
        self.assertIsNotNone(self.contract_v2.hub_contract_json)
        self.assertIn('info', self.contract_v2.hub_contract_json)
        self.assertIn('owners', self.contract_v2.hub_contract_json['info'])
        self.assertIn('tags', self.contract_v2.hub_contract_json['info'])
        self.assertIn('quality', self.contract_v2.hub_contract_json)
        self.assertIn('privacy_compliance', self.contract_v2.hub_contract_json)
        self.assertIn('lifecycle', self.contract_v2.hub_contract_json)
        self.assertIn('marketplace', self.contract_v2.hub_contract_json)
    
    def test_api_handles_both_versions(self):
        """Test that API handles both v1 and v2 contracts (GAP-10.2.2)"""
        from rest_framework.test import APIClient
        
        client = APIClient()
        client.force_authenticate(user=self.user)
        
        # Retrieve v1 contract
        response1 = client.get(f'/api/v1/contracts/{self.contract_v1.id}/')
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        data1 = response1.json()
        self.assertIn('hub_contract_json', data1)
        
        # Retrieve v2 contract
        response2 = client.get(f'/api/v1/contracts/{self.contract_v2.id}/')
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        data2 = response2.json()
        self.assertIn('hub_contract_json', data2)
        
        # Verify both contracts have computed fields
        self.assertIn('owners', data2)
        self.assertIn('tags', data2)
        self.assertIn('quality_rules', data2)
        self.assertIn('compliance_policy', data2)
    
    def test_migration_tool_works(self):
        """Test that migration tool works (GAP-10.2.2)"""
        from django.core.management import call_command
        from io import StringIO
        
        # Test dry-run mode
        out = StringIO()
        call_command(
            'migrate_contracts',
            '--dry-run',
            '--target-version', '2.0.0',
            stdout=out
        )
        
        output = out.getvalue()
        self.assertIn('Starting contract migration', output)
        self.assertIn('DRY-RUN MODE', output)
        
        # Verify tool can identify contracts needing migration
        # (v1 contracts would need migration to v2)
        # Note: Actual migration requires v2 to be the current version

