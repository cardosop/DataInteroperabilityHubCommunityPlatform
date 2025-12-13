"""
Regression tests for JSONField functionality after Django 6 upgrade.

These tests verify that JSONField queries and operations continue to work
correctly with Django 6 and the new GIN index.
"""
import pytest
from django.test import TestCase
from django.db import connection

from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User


pytestmark = pytest.mark.django_db(transaction=True)


class JSONFieldRegressionTest(TestCase):
    """Comprehensive regression tests for JSONField operations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            tenant=self.tenant
        )
        
        # Create test contract with JSONField data
        self.contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="DATACONTRACT_COM",
            original_format="JSON",
            original_raw='{"info": {"title": "Test Contract", "tags": ["tag1"]}}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {
                    "title": "Test Contract",
                    "tags": ["tag1", "tag2"],
                    "owners": ["owner@example.com"]
                },
                "quality": {
                    "default_profile_key": "great_expectations"
                },
                "privacy_compliance": {
                    "jurisdictions": ["GDPR"],
                    "contains_personal_data": True
                }
            },
            created_by=self.user
        )
    
    def test_jsonfield_storage_regression(self):
        """Verify JSONField storage works correctly after Django 6 upgrade."""
        # Retrieve contract
        contract = Contract.objects.get(id=self.contract.id)
        
        # Verify JSONField data is stored correctly
        self.assertIsNotNone(contract.hub_contract_json)
        self.assertIn("info", contract.hub_contract_json)
        self.assertEqual(contract.hub_contract_json["info"]["title"], "Test Contract")
    
    def test_jsonfield_query_regression(self):
        """Verify JSONField queries work correctly after Django 6 upgrade."""
        # Test various query patterns
        contracts = Contract.objects.filter(
            hub_contract_json__info__tags__contains=["tag1"]
        )
        self.assertEqual(contracts.count(), 1)
        
        contracts = Contract.objects.filter(
            hub_contract_json__quality__default_profile_key="great_expectations"
        )
        self.assertEqual(contracts.count(), 1)
        
        contracts = Contract.objects.filter(
            hub_contract_json__privacy_compliance__contains_personal_data=True
        )
        self.assertEqual(contracts.count(), 1)
    
    def test_jsonfield_update_regression(self):
        """Verify JSONField updates work correctly after Django 6 upgrade."""
        # Update JSONField
        contract = Contract.objects.get(id=self.contract.id)
        contract.hub_contract_json["info"]["tags"].append("tag3")
        contract.save()
        
        # Verify update
        contract.refresh_from_db()
        self.assertIn("tag3", contract.hub_contract_json["info"]["tags"])
    
    def test_jsonfield_index_regression(self):
        """Verify GIN index is used for JSONField queries (PostgreSQL only)."""
        if connection.vendor != 'postgresql':
            self.skipTest("GIN index test only for PostgreSQL")
        
        # Verify index exists
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'contracts_contract'
                AND indexdef LIKE '%hub_contract_json%'
            """)
            indexes = cursor.fetchall()
            
            # Should have at least one index on hub_contract_json
            self.assertGreater(len(indexes), 0, "GIN index on hub_contract_json not found")
    
    def test_jsonfield_null_handling_regression(self):
        """Verify JSONField null handling works correctly after Django 6 upgrade."""
        # Create contract with null JSONField
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=2,
            status=ContractStatus.DRAFT,
            original_spec_type="DATACONTRACT_COM",
            original_format="JSON",
            original_raw='{}',
            hub_contract_json=None,
            created_by=self.user
        )
        
        # Verify null handling
        contract.refresh_from_db()
        self.assertIsNone(contract.hub_contract_json)
        
        # Query with isnull
        contracts = Contract.objects.filter(hub_contract_json__isnull=True)
        self.assertGreaterEqual(contracts.count(), 1)

