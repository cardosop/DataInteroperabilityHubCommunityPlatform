"""Phase 111.7 — Database failover → meaningful error, not hang."""

import pytest
from django.db import connection
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)


class DatabaseFailoverTest(TestCase):
    """Database connection handling during failures."""

    def test_bad_query_raises_exception_not_hang(self):
        """Invalid SQL raises an exception, does not hang."""
        with self.assertRaises(Exception):
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM nonexistent_chaos_table_xyz")

    def test_sequential_queries_work(self):
        """Sequential queries don't exhaust connections."""
        from hub.apps.tenants.models import Tenant

        for _ in range(20):
            Tenant.objects.count()
        self.assertTrue(connection.is_usable())

    def test_connection_is_usable(self):
        """Basic connection check."""
        self.assertTrue(connection.is_usable())
