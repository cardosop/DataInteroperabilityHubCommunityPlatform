import uuid

import pytest
from django.test import TestCase

from hub.apps.compliance.tasks import _run_with_tenant_context
from hub.apps.tenants.models import Tenant


class ComplianceTaskTenantContextTest(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name=f"Tenant {uuid.uuid4().hex[:8]}",
            slug=f"tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

    def _tenant_lookup_requires_context(self):
        return Tenant.objects.extra(
            where=["id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"]
        ).get(id=self.tenant.id)

    @pytest.mark.integration
    def test_without_tenant_context_raises_does_not_exist(self):
        with self.assertRaises(Tenant.DoesNotExist):
            _run_with_tenant_context(None, self._tenant_lookup_requires_context)

    @pytest.mark.integration
    def test_with_tenant_context_returns_row(self):
        tenant = _run_with_tenant_context(
            str(self.tenant.id),
            self._tenant_lookup_requires_context,
        )
        self.assertEqual(str(tenant.id), str(self.tenant.id))
