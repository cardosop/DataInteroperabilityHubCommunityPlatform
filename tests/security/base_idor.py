"""
IDOR test base class.

Per tasks 29.1.6. Two-tenant setup; assert 403/404 for cross-tenant GET.
Real APIClient; no mocks.
"""

import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import UserStatus, UserTenantMembership

User = get_user_model()


class IDORTestBase(TestCase):
    """Base for IDOR tests. Two tenants, two users; real client."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        uid = str(uuid.uuid4())[:8]
        self.tenant_a = Tenant.objects.create(
            name=f"IDOR Tenant A {uid}",
            slug=f"idor-tenant-a-{uid}",
        )
        self.tenant_b = Tenant.objects.create(
            name=f"IDOR Tenant B {uid}",
            slug=f"idor-tenant-b-{uid}",
        )
        self.user_a = User.objects.create_user(
            email=f"idora-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_a,
            status=UserStatus.ACTIVE,
        )
        self.user_b = User.objects.create_user(
            email=f"idorb-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant_b,
            status=UserStatus.ACTIVE,
        )
        UserTenantMembership.objects.get_or_create(user=self.user_a, tenant=self.tenant_a)
        UserTenantMembership.objects.get_or_create(user=self.user_b, tenant=self.tenant_b)
