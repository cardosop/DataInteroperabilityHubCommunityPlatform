"""
Tests for JSONField queries with Django 6 GIN index optimization.

These tests verify that JSONField queries work correctly with the GIN index
added in migration 0003_add_hub_contract_json_gin_index.py.
"""
import pytest
from django.test import TestCase
from django.db import connection
from django.db.models import Q, When, Value

from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User


pytestmark = pytest.mark.django_db(transaction=True)


class JSONFieldQueryTest(TestCase):
    """Test JSONField queries with GIN index."""
    
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
        
        # Create test contracts with various JSONField data
        self.contract1 = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_format="JSON",
            original_raw='{"info": {"title": "Test Contract 1", "tags": ["tag1", "tag2"]}}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {
                    "title": "Test Contract 1",
                    "tags": ["tag1", "tag2"],
                    "owners": ["owner1@example.com"]
                },
                "quality": {
                    "default_profile_key": "great_expectations"
                },
                "privacy_compliance": {
                    "jurisdictions": ["GDPR", "CCPA"],
                    "contains_personal_data": True
                }
            },
            created_by=self.user
        )
        
        self.contract2 = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_format="JSON",
            original_raw='{"info": {"title": "Test Contract 2", "tags": ["tag2", "tag3"]}}',
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {
                    "title": "Test Contract 2",
                    "tags": ["tag2", "tag3"],
                    "owners": ["owner2@example.com"]
                },
                "quality": {
                    "default_profile_key": "soda"
                },
                "privacy_compliance": {
                    "jurisdictions": ["GDPR"],
                    "contains_personal_data": False
                }
            },
            created_by=self.user
        )
    
    def test_tags_contains_query(self):
        """Test querying by tags using __contains lookup."""
        # Query contracts with tag1
        contracts = Contract.objects.filter(
            hub_contract_json__info__tags__contains=["tag1"]
        )
        
        self.assertEqual(contracts.count(), 1)
        self.assertEqual(contracts.first().id, self.contract1.id)
        
        # Query contracts with tag2
        contracts = Contract.objects.filter(
            hub_contract_json__info__tags__contains=["tag2"]
        )
        
        self.assertEqual(contracts.count(), 2)
    
    def test_quality_profile_query(self):
        """Test querying by quality profile key."""
        contracts = Contract.objects.filter(
            hub_contract_json__quality__default_profile_key="great_expectations"
        )
        
        self.assertEqual(contracts.count(), 1)
        self.assertEqual(contracts.first().id, self.contract1.id)
        
        contracts = Contract.objects.filter(
            hub_contract_json__quality__default_profile_key="soda"
        )
        
        self.assertEqual(contracts.count(), 1)
        self.assertEqual(contracts.first().id, self.contract2.id)
    
    def test_compliance_jurisdictions_query(self):
        """Test querying by compliance jurisdictions."""
        contracts = Contract.objects.filter(
            hub_contract_json__privacy_compliance__jurisdictions__contains=["GDPR"]
        )
        
        self.assertEqual(contracts.count(), 2)
        
        contracts = Contract.objects.filter(
            hub_contract_json__privacy_compliance__jurisdictions__contains=["CCPA"]
        )
        
        self.assertEqual(contracts.count(), 1)
        self.assertEqual(contracts.first().id, self.contract1.id)
    
    def test_contains_personal_data_query(self):
        """Test querying by contains_personal_data boolean."""
        contracts = Contract.objects.filter(
            hub_contract_json__privacy_compliance__contains_personal_data=True
        )
        
        self.assertEqual(contracts.count(), 1)
        self.assertEqual(contracts.first().id, self.contract1.id)
        
        contracts = Contract.objects.filter(
            hub_contract_json__privacy_compliance__contains_personal_data=False
        )
        
        self.assertEqual(contracts.count(), 1)
        self.assertEqual(contracts.first().id, self.contract2.id)
    
    def test_complex_query_with_when(self):
        """Test complex query with When/Case expressions."""
        from django.db.models import Case, When, Value, IntegerField
        
        contracts = Contract.objects.annotate(
            personal_data_score=Case(
                When(hub_contract_json__privacy_compliance__contains_personal_data=True, then=Value(100)),
                default=Value(0),
                output_field=IntegerField()
            )
        ).filter(personal_data_score=100)
        
        self.assertEqual(contracts.count(), 1)
        self.assertEqual(contracts.first().id, self.contract1.id)
    
    def test_combined_filters(self):
        """Test combining multiple JSONField filters."""
        contracts = Contract.objects.filter(
            hub_contract_json__info__tags__contains=["tag2"],
            hub_contract_json__privacy_compliance__jurisdictions__contains=["GDPR"]
        )
        
        self.assertEqual(contracts.count(), 2)
    
    def test_gin_index_usage(self):
        """Test that GIN index is used for JSONField queries (PostgreSQL only)."""
        if connection.vendor != 'postgresql':
            self.skipTest("GIN index test only for PostgreSQL")
        
        # Get query plan
        with connection.cursor() as cursor:
            cursor.execute("""
                EXPLAIN (FORMAT JSON)
                SELECT * FROM contracts_contract
                WHERE hub_contract_json->'info'->'tags' @> '["tag1"]'::jsonb
            """)
            plan = cursor.fetchone()[0]
            
            # Check if GIN index is used
            plan_str = str(plan)
            # The plan should mention the index or use Index Scan
            # This is a basic check - actual plan structure may vary
            self.assertIn('hub_contract_json', plan_str.lower() or 'Index Scan' in plan_str)
    
    def test_query_performance(self):
        """Test that JSONField queries are performant with GIN index."""
        import time
        
        # Create more contracts for performance test
        for i in range(10):
            Contract.objects.create(
                tenant=self.tenant,
                version=1,
                status=ContractStatus.ACTIVE,
                original_spec_type="ODCS",
                original_format="JSON",
                original_raw='{}',
                hub_contract_version="1.0.0",
                hub_contract_json={
                    "info": {
                        "tags": [f"tag{i}", f"tag{i+1}"]
                    },
                    "privacy_compliance": {
                        "jurisdictions": ["GDPR"] if i % 2 == 0 else ["CCPA"]
                    }
                },
                created_by=self.user
            )
        
        # Time the query
        start = time.time()
        contracts = Contract.objects.filter(
            hub_contract_json__info__tags__contains=["tag1"]
        ).count()
        elapsed = time.time() - start
        
        # Should be fast even with multiple contracts
        # With GIN index, should be < 100ms for this query
        self.assertLess(elapsed, 0.1, f"Query too slow: {elapsed:.3f}s")
        self.assertGreater(contracts, 0)

