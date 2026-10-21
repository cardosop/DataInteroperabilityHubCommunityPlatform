"""
Integration tests for multi-tenant isolation (T.8).

Tests that tenants cannot access each other's data.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class MultiTenantIsolationTest(TestCase):
    """Integration tests for multi-tenant isolation (T.8)"""

    def setUp(self):
        """Set up test fixtures"""
