"""Phase 107: Database connection handling under load."""

from django.db import connection
from django.test import TestCase


class DatabaseConnectionExhaustionTest(TestCase):
    """Database connections are properly managed."""

    def test_connection_usable_after_query(self):
        """Connection remains usable after a query."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        self.assertEqual(result[0], 1)

    def test_multiple_sequential_queries_no_leak(self):
        """Multiple sequential queries don't leak connections."""
        for _ in range(20):
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchone()[0], 1)

    def test_connection_recovers_after_error(self):
        """Connection recovers after a query error."""
        from django.db import transaction

        try:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("SELECT * FROM nonexistent_table_xyz")
        except Exception:
            pass
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            self.assertEqual(cursor.fetchone()[0], 1)
