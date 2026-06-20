"""Unit tests for TenantLifecycleService.

Covers suspend_tenant() and resume_tenant() with real DB — no mocks
at the service boundary.  Previously these paths were only exercised
through API views.
"""

from __future__ import annotations

import uuid

import pytest
from django.test import TestCase

from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.tenants.models import Tenant, TenantStatus
from hub.apps.tenants.services import TenantLifecycleService

pytestmark = pytest.mark.django_db(transaction=True)


class SuspendTenantTests(TestCase):
    """Tests for TenantLifecycleService.suspend_tenant()."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Lifecycle {uid}",
            slug=f"lifecycle-{uid}",
            status=TenantStatus.ACTIVE,
        )
        self.service = TenantLifecycleService(
            tenant_id=str(self.tenant.id),
            user_id=None,
        )

    def test_suspend_active_tenant_sets_suspended(self):
        """Success: ACTIVE tenant is suspended and returned."""
        result = self.service.suspend_tenant(str(self.tenant.id))
        self.assertEqual(result.status, TenantStatus.SUSPENDED)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.status, TenantStatus.SUSPENDED)

    def test_suspend_already_suspended_returns_as_is(self):
        """Idempotent: already-SUSPENDED tenant returns unchanged."""
        self.tenant.status = TenantStatus.SUSPENDED
        self.tenant.save()
        result = self.service.suspend_tenant(str(self.tenant.id))
        self.assertEqual(result.status, TenantStatus.SUSPENDED)

    def test_suspend_deleted_tenant_raises_validation_error(self):
        """Failure: DELETED tenant cannot be suspended."""
        self.tenant.status = TenantStatus.DELETED
        self.tenant.save()
        with pytest.raises(ValidationError) as exc_info:
            self.service.suspend_tenant(str(self.tenant.id))
        self.assertEqual(exc_info.value.code, "TENANT_DELETED")

    def test_suspend_nonexistent_tenant_raises_not_found(self):
        """Failure: nonexistent tenant ID raises NotFoundError."""
        fake_id = str(uuid.uuid4())
        with pytest.raises(NotFoundError):
            self.service.suspend_tenant(fake_id)


class ResumeTenantTests(TestCase):
    """Tests for TenantLifecycleService.resume_tenant()."""

    def setUp(self):
        super().setUp()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Lifecycle {uid}",
            slug=f"lifecycle-{uid}",
            status=TenantStatus.SUSPENDED,
        )
        self.service = TenantLifecycleService(
            tenant_id=str(self.tenant.id),
            user_id=None,
        )

    def test_resume_suspended_tenant_reactivates(self):
        """Success: SUSPENDED tenant is reactivated to ACTIVE."""
        result = self.service.resume_tenant(str(self.tenant.id))
        self.assertEqual(result.status, TenantStatus.ACTIVE)
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.status, TenantStatus.ACTIVE)

    def test_resume_active_tenant_raises_validation_error(self):
        """Failure: ACTIVE tenant cannot be resumed."""
        self.tenant.status = TenantStatus.ACTIVE
        self.tenant.save()
        with pytest.raises(ValidationError) as exc_info:
            self.service.resume_tenant(str(self.tenant.id))
        self.assertEqual(exc_info.value.code, "TENANT_NOT_SUSPENDED")
