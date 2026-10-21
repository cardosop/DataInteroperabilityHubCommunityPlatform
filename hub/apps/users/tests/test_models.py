"""
Unit tests for User model.
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class UserModelTest(TestCase):
    """Test User model"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uuid.uuid4().hex[:8]}", slug=f"test-tenant-{uuid.uuid4().hex[:8]}"
        )

    def test_create_user(self):
        """Test user creation"""
        email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        user = User.objects.create_user(
            email=email,
            password="testpass123",
            tenant=self.tenant,
            display_name="Test User",
            status=UserStatus.ACTIVE,
        )

        self.assertEqual(user.email, email)
        self.assertEqual(user.tenant, self.tenant)
        self.assertEqual(user.status, UserStatus.ACTIVE)
        self.assertTrue(user.check_password("testpass123"))

    def test_user_status_choices(self):
        """Test user status enum"""
        user = User.objects.create_user(
            email=f"test-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

        user.status = UserStatus.SUSPENDED
        user.save()
        self.assertEqual(user.status, UserStatus.SUSPENDED)
