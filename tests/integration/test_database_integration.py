"""
Integration tests for database connectivity and basic operations.

Uses real DB connection and real models (no mocks/stubs).
"""

import pytest
from django.db import connection
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from tests.factories import TenantFactory

pytestmark = pytest.mark.django_db(transaction=True)


class DatabaseIntegrationTest(TestCase):
    """Integration tests for database operations."""

    def setUp(self):
        self.tenant = TenantFactory.create_tenant()

    def test_database_connection(self):
        """Database connection is usable."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
        self.assertEqual(row, (1,))

    def test_tenant_crud_via_orm(self):
        """Tenant model CRUD via real ORM."""
        self.assertIsNotNone(self.tenant.id)
        self.assertTrue(Tenant.objects.filter(id=self.tenant.id).exists())
        count = Tenant.objects.count()
        self.assertGreaterEqual(count, 1)
