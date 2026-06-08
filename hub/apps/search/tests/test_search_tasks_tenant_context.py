"""
Phase 260.B-RLS-0.4 — fail-loud regression for ``search.tasks``.

Closes the missing per-module regression test for the 10th worker module
that uses ``tenant_context()``. The pattern mirrors the other nine
modules' tests (notifications, integrations, webhooks, jobs/tasks_base,
jobs/tasks_prefect_sync, billing, contracts, semantic, compliance).

Contract
--------
``search.tasks._run_with_tenant_context`` is the helper that all
search-vector-update entry points route through. It wraps a callback in
``tenant_context(tenant_id)`` when ``tenant_id`` is provided, and in
``contextlib.nullcontext()`` when not. This test pins both ends:

1. **Without** a tenant context, a query that filters by the
   ``app.current_tenant_id`` GUC returns no row → callback raises
   ``Tenant.DoesNotExist``. This is the fail-loud signal that proves
   RLS policies (once enabled) will deny rows to a worker that forgot
   the wrap.
2. **With** a tenant context, the same query resolves the seeded tenant
   row.

The fail-loud expectation is identical to the other nine worker-module
tests so a regression in any module produces a uniform, recognisable
failure mode.
"""
from __future__ import annotations
import pytest

import uuid

from django.test import TestCase

from hub.apps.search.tasks import _run_with_tenant_context
from hub.apps.tenants.models import Tenant


class SearchTasksTenantContextTest(TestCase):
    def setUp(self) -> None:
        self.tenant = Tenant.objects.create(
            name=f"Tenant {uuid.uuid4().hex[:8]}",
            slug=f"tenant-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

    def _tenant_lookup_requires_context(self) -> Tenant:
        # Filter by the GUC value so the row is only visible when
        # ``tenant_context`` is active and ``app.current_tenant_id`` is
        # set. ``NULLIF(..., '')::uuid`` turns an unset/empty GUC into
        # NULL, which the equality test then refuses to match.
        return Tenant.objects.extra(
            where=[
                "id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid"
            ]
        ).get(id=self.tenant.id)

    @pytest.mark.integration
    def test_without_tenant_context_raises_does_not_exist(self) -> None:
        with self.assertRaises(Tenant.DoesNotExist):
            _run_with_tenant_context(None, self._tenant_lookup_requires_context)

    @pytest.mark.integration
    def test_with_tenant_context_returns_row(self) -> None:
        tenant = _run_with_tenant_context(
            str(self.tenant.id),
            self._tenant_lookup_requires_context,
        )
        self.assertEqual(str(tenant.id), str(self.tenant.id))
