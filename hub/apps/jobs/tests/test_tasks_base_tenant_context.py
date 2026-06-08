import pytest
import uuid

from django.test import TestCase

from hub.apps.tenants.models import Tenant
from hub.apps.tenants.request_tenant import tenant_context


class JobsTasksBaseTenantContextTest(TestCase):
    """Tests that tenant-scoped RLS queries depend on active tenant context.

    The _tenant_lookup_requires_context helper mirrors the pattern used by
    worker/signal code: it queries Tenant via a WHERE clause that references
    ``current_setting('app.current_tenant_id', true)``, which is the RLS
    session variable set by ``tenant_context``.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(
            name=f"Tenant {uuid.uuid4().hex[:8]}",
            slug=f"tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

    def _tenant_lookup_requires_context(self):
        return Tenant.objects.extra(
            where=[
                "id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
            ]
        ).get(id=self.tenant.id)

    @pytest.mark.integration
    def test_without_tenant_context_raises_does_not_exist(self):
        """Without an active tenant_context, the RLS query returns no row."""
        with self.assertRaises(Tenant.DoesNotExist):
            self._tenant_lookup_requires_context()

    @pytest.mark.integration
    def test_with_tenant_context_returns_row(self):
        """Within an active tenant_context, the RLS query finds the tenant."""
        with tenant_context(str(self.tenant.id)):
            tenant = self._tenant_lookup_requires_context()
        self.assertEqual(str(tenant.id), str(self.tenant.id))
