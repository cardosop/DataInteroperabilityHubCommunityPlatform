"""
Injection test base class.

Per tasks 29.1.7. Parameterized payloads; assert no 500.
Real APIClient and DB; no mocks.
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus, UserTenantMembership

User = get_user_model()


class InjectionTestBase(TestCase):
    """Base for injection tests. Real client and DB."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        uid = str(uuid.uuid4())[:8]
        self.tenant = Tenant.objects.create(
            name=f"Injection Test Tenant {uid}",
            slug=f"injection-test-tenant-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"injection-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(
            user=self.user,
            tenant=self.tenant,
        )
        self.client.force_authenticate(user=self.user)
