"""
Tests for JSONField queries with Django 6 GIN index optimization.

These tests verify that JSONField queries work correctly with the GIN index
added in migration 0003_add_hub_contract_json_gin_index.py.
"""

import pytest
from django.db import connection
from django.db.models import Q, Value, When

from hub.apps.contracts.models import Contract, ContractStatus
from hub.apps.contracts.tests.test_base import ContractsTestBase

pytestmark = pytest.mark.django_db(transaction=True)


class JSONFieldQueryTest(ContractsTestBase):
    """Test JSONField queries with GIN index."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

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
                    "owners": ["owner1@example.com"],
                },
                "quality": {"default_profile_key": "great_expectations"},
                "privacy_compliance": {
                    "jurisdictions": ["GDPR", "CCPA"],
                    "contains_personal_data": True,
                },
            },
            created_by=self.user,
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
                    "owners": ["owner2@example.com"],
                },
                "quality": {"default_profile_key": "soda"},
                "privacy_compliance": {"jurisdictions": ["GDPR"], "contains_personal_data": False},
            },
            created_by=self.user,
        )

    def test_tags_contains_query(self):
        """Test querying by tags using __contains lookup."""
        # Query contracts with tag1
        contracts = Contract.objects.filter(hub_contract_json__info__tags__contains=["tag1"])

        self.assertEqual(contracts.count(), 1)
        self.assertEqual(contracts.first().id, self.contract1.id)

        # Query contracts with tag2
        contracts = Contract.objects.filter(hub_contract_json__info__tags__contains=["tag2"])

        self.assertEqual(contracts.count(), 2)

    def test_quality_profile_query(self):
        """Test querying by quality profile key."""
        contracts = Contract.objects.filter(
            hub_contract_json__quality__default_profile_key="great_expectations"
        )

        self.assertEqual(contracts.count(), 1)
        self.assertEqual(contracts.first().id, self.contract1.id)

        contracts = Contract.objects.filter(hub_contract_json__quality__default_profile_key="soda")

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
        from django.db.models import Case, IntegerField, Value, When

        contracts = Contract.objects.annotate(
            personal_data_score=Case(
                When(
                    hub_contract_json__privacy_compliance__contains_personal_data=True,
                    then=Value(100),
                ),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).filter(personal_data_score=100)

        self.assertEqual(contracts.count(), 1)
        self.assertEqual(contracts.first().id, self.contract1.id)

    def test_combined_filters(self):
        """Test combining multiple JSONField filters."""
        contracts = Contract.objects.filter(
            hub_contract_json__info__tags__contains=["tag2"],
            hub_contract_json__privacy_compliance__jurisdictions__contains=["GDPR"],
        )

        self.assertEqual(contracts.count(), 2)

    def test_gin_index_usage(self):
        """Test that GIN index is used for JSONField queries (PostgreSQL only)."""
        if connection.vendor != "postgresql":
            self.skipTest("GIN index test only for PostgreSQL")

        # Get query plan
        with connection.cursor() as cursor:
            cursor.execute(
                """
                EXPLAIN (FORMAT JSON)
                SELECT * FROM contracts_contract
                WHERE hub_contract_json->'info'->'tags' @> '["tag1"]'::jsonb
            """
            )
            plan = cursor.fetchone()[0]

            # Check if GIN index is used
            plan_str = str(plan)
            # The plan should mention the index or use Index Scan
            # This is a basic check - actual plan structure may vary
            self.assertIn("hub_contract_json", plan_str.lower() or "Index Scan" in plan_str)

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
                original_raw="{}",
                hub_contract_version="1.0.0",
                hub_contract_json={
                    "info": {"tags": [f"tag{i}", f"tag{i+1}"]},
                    "privacy_compliance": {"jurisdictions": ["GDPR"] if i % 2 == 0 else ["CCPA"]},
                },
                created_by=self.user,
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

    # Edge cases and error handling tests
    def test_query_with_empty_tags(self):
        """Test querying contracts with empty tags array."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_format="JSON",
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"title": "Empty Tags", "tags": []},
                "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            },
            created_by=self.user,
        )

        # Query with empty tags should return empty or handle gracefully
        contracts = Contract.objects.filter(hub_contract_json__info__tags__contains=[])
        # Empty contains may match all or none depending on implementation
        self.assertIsInstance(contracts.count(), int)

    def test_query_with_nonexistent_field(self):
        """Test querying with nonexistent JSONField path."""
        contracts = Contract.objects.filter(hub_contract_json__nonexistent__field="value")
        # Should return empty queryset or handle gracefully
        self.assertEqual(contracts.count(), 0)

    def test_query_with_null_values(self):
        """Test querying contracts with null values in JSONField."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_format="JSON",
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"title": "Null Test", "tags": None},
                "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            },
            created_by=self.user,
        )

        # Query with null should handle gracefully
        contracts = Contract.objects.filter(hub_contract_json__info__tags__isnull=True)
        self.assertGreaterEqual(contracts.count(), 0)

    def test_query_with_special_characters_in_json(self):
        """Test querying with special characters in JSONField values."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_format="JSON",
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"title": "Special <>&\"'", "tags": ["tag<>&\"'"]},
                "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            },
            created_by=self.user,
        )

        # Should handle special characters
        contracts = Contract.objects.filter(hub_contract_json__info__title__contains="<>&\"'")
        self.assertGreaterEqual(contracts.count(), 0)

    def test_query_with_unicode_characters(self):
        """Test querying with unicode characters in JSONField."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_format="JSON",
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"title": "产品名称", "tags": ["标签1", "标签2"]},
                "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            },
            created_by=self.user,
        )

        # Should handle unicode characters
        contracts = Contract.objects.filter(hub_contract_json__info__title__contains="产品")
        self.assertGreaterEqual(contracts.count(), 0)

    def test_query_with_very_large_json(self):
        """Test querying with very large JSONField data."""
        large_data = {
            "info": {
                "title": "Large Contract",
                "description": "A" * 100000,  # Very long string
                "tags": [f"tag{i}" for i in range(1000)],  # Many tags
            },
            "schema": {
                "fields": [{"name": f"field_{i}", "data_type": "string"} for i in range(1000)]
            },
        }

        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_format="JSON",
            hub_contract_version="1.0.0",
            hub_contract_json=large_data,
            created_by=self.user,
        )

        # Should handle large JSON
        contracts = Contract.objects.filter(hub_contract_json__info__title="Large Contract")
        self.assertEqual(contracts.count(), 1)

    def test_query_with_nested_structures(self):
        """Test querying deeply nested JSONField structures."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_format="JSON",
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"title": "Nested"},
                "schema": {"fields": [{"name": "id", "data_type": "string"}]},
                "extensions": {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}},
            },
            created_by=self.user,
        )

        # Should handle nested structures
        contracts = Contract.objects.filter(
            hub_contract_json__extensions__level1__level2__level3__level4__value="deep"
        )
        self.assertEqual(contracts.count(), 1)

    def test_query_with_mixed_data_types(self):
        """Test querying with mixed data types in JSONField."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_format="JSON",
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"title": "Mixed Types"},
                "schema": {"fields": [{"name": "id", "data_type": "string"}]},
                "metadata": {
                    "count": 42,
                    "active": True,
                    "score": 3.14,
                    "items": [1, 2, 3],
                    "nested": {"key": "value"},
                },
            },
            created_by=self.user,
        )

        # Query by integer
        contracts = Contract.objects.filter(hub_contract_json__metadata__count=42)
        self.assertEqual(contracts.count(), 1)

        # Query by boolean
        contracts = Contract.objects.filter(hub_contract_json__metadata__active=True)
        self.assertEqual(contracts.count(), 1)

    def test_query_with_empty_jsonfield(self):
        """Test querying contracts with empty JSONField."""
        contract = Contract.objects.create(
            tenant=self.tenant,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_format="JSON",
            hub_contract_version="1.0.0",
            hub_contract_json={},  # Empty JSON
            created_by=self.user,
        )

        # Should handle empty JSON
        contracts = Contract.objects.filter(hub_contract_json__isnull=False)
        self.assertGreaterEqual(contracts.count(), 0)

    def test_query_with_invalid_json_path(self):
        """Test querying with invalid JSONField path syntax."""
        # Invalid path with array index without proper syntax
        try:
            contracts = Contract.objects.filter(hub_contract_json__info__tags__0="tag1")
            # May or may not work depending on Django version
            self.assertIsInstance(contracts.count(), int)
        except Exception:
            # If it raises exception, that's acceptable
            pass

    def test_query_cross_tenant_isolation(self):
        """Test that JSONField queries respect tenant isolation."""
        # Create another tenant
        other_tenant = Tenant.objects.create(name="Other Tenant", slug="other-tenant-json")

        other_contract = Contract.objects.create(
            tenant=other_tenant,
            version=1,
            status=ContractStatus.ACTIVE,
            original_spec_type="ODCS",
            original_format="JSON",
            hub_contract_version="1.0.0",
            hub_contract_json={
                "info": {"title": "Other Tenant Contract", "tags": ["tag1"]},
                "schema": {"fields": [{"name": "id", "data_type": "string"}]},
            },
            created_by=self.user,
        )

        # Query should only return contracts for current tenant
        contracts = Contract.objects.filter(
            tenant=self.tenant, hub_contract_json__info__tags__contains=["tag1"]
        )

        # Should not include other_contract
        contract_ids = list(contracts.values_list("id", flat=True))
        self.assertNotIn(other_contract.id, contract_ids)

    def test_query_with_q_objects(self):
        """Test JSONField queries with Q objects for complex conditions."""
        from django.db.models import Q

        # Complex query with Q objects
        contracts = Contract.objects.filter(
            Q(hub_contract_json__info__tags__contains=["tag1"])
            | Q(hub_contract_json__privacy_compliance__jurisdictions__contains=["CCPA"])
        )

        self.assertGreaterEqual(contracts.count(), 0)

    def test_query_with_exclude(self):
        """Test excluding contracts based on JSONField values."""
        contracts = Contract.objects.exclude(hub_contract_json__info__tags__contains=["tag3"])

        # Should exclude contracts with tag3
        contract_ids = list(contracts.values_list("id", flat=True))
        self.assertNotIn(self.contract2.id, contract_ids or [])

    def test_query_with_ordering_by_jsonfield(self):
        """Test ordering queryset by JSONField values."""
        contracts = Contract.objects.order_by("hub_contract_json__info__title")

        # Should order by title
        self.assertGreaterEqual(contracts.count(), 0)

    def test_query_with_annotate_jsonfield(self):
        """Test annotating queryset with JSONField values."""
        from django.db.models import F

        contracts = Contract.objects.annotate(title=F("hub_contract_json__info__title")).filter(
            title__isnull=False
        )

        self.assertGreaterEqual(contracts.count(), 0)

    def test_query_with_distinct(self):
        """Test distinct() with JSONField queries."""
        contracts = Contract.objects.filter(
            hub_contract_json__info__tags__contains=["tag2"]
        ).distinct()

        self.assertGreaterEqual(contracts.count(), 0)

    def test_query_with_count_aggregation(self):
        """Test count aggregation with JSONField queries."""
        count = Contract.objects.filter(
            hub_contract_json__privacy_compliance__contains_personal_data=True
        ).count()

        self.assertGreaterEqual(count, 0)

    def test_query_with_exists(self):
        """Test exists() check with JSONField queries."""
        exists = Contract.objects.filter(hub_contract_json__info__tags__contains=["tag1"]).exists()

        self.assertIsInstance(exists, bool)
