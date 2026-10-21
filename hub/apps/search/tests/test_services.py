"""
Unit tests for SearchService.

Tests cover all service methods with 100% coverage target.
"""

import uuid

from django.test import TestCase

from hub.apps.search.models import SearchIndex
from hub.apps.search.services import SearchService
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus


class SearchServiceTest(TestCase):
    """Test SearchService operations"""

    def setUp(self):
        """Set up test data"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", tenant=self.tenant, status=UserStatus.ACTIVE
        )
        self.service = SearchService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_search_success(self):
        """Test successful search returns the indexed entry."""
        from django.contrib.postgres.search import SearchVector

        resource_id = uuid.uuid4()
        index = SearchIndex.objects.create(
            tenant=self.tenant,
            resource_type="CONTRACT",
            resource_id=resource_id,
            title="Test Contract",
        )
        # Populate a real PostgreSQL tsvector so FTS can match it.
        SearchIndex.objects.filter(pk=index.pk).update(
            search_vector=SearchVector("title", weight="A"),
        )

        results, total = self.service.search(
            tenant_id=str(self.tenant.id),
            query="Test",
        )

        self.assertIsInstance(results, list)
        self.assertIsInstance(total, int)
        self.assertGreater(
            total, 0, f"Search for 'Test' should return at least 1 result, got {total}"
        )
        self.assertEqual(
            results[0]["id"],
            str(resource_id),
            f"First result should be the indexed contract; got {results[0].get('id')}",
        )

    def test_search_empty_query_success(self):
        """Edge case: search with empty query returns filter_only results."""
        results, total = self.service.search(
            tenant_id=str(self.tenant.id),
            query="",
            limit=10,
        )
        self.assertIsInstance(results, list)
        self.assertIsInstance(total, int)
        self.assertGreaterEqual(total, 0)

    def test_rebuild_index_success(self):
        """Success: rebuild_index completes and returns dict with expected keys."""
        result = self.service.rebuild_index(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertIsInstance(result, dict)
        self.assertIn("resource_count", result)
        self.assertIn("duration_ms", result)
        self.assertIn("success", result)
        self.assertIn("resource_types", result)
        self.assertIsInstance(result["resource_types"], list)

    def test_search_with_invalid_tenant_id_returns_empty(self):
        """Edge case: search with non-existent tenant_id returns empty results (no exception)."""
        import uuid

        fake_tenant_id = str(uuid.uuid4())
        results, total = self.service.search(
            tenant_id=fake_tenant_id,
            query="test",
            limit=10,
        )
        self.assertIsInstance(results, list)
        self.assertEqual(len(results), 0)
        self.assertEqual(total, 0)
