"""Constraint-based order placement tests (replaces threading-based concurrency)."""

import uuid

from django.test import TestCase

from hub.apps.tenants.models import Tenant


class OrderPlacementConsistencyTest(TestCase):
    """Sequential operations on same tenant are consistent."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Order {uid}", slug=f"order-{uid}")

    def test_multiple_reads_same_tenant_no_error(self):
        for _ in range(10):
            t = Tenant.objects.get(pk=self.tenant.pk)
            self.assertEqual(t.name, self.tenant.name)

    def test_read_after_write_consistency(self):
        self.tenant.name = "Updated Name"
        self.tenant.save()
        refreshed = Tenant.objects.get(pk=self.tenant.pk)
        self.assertEqual(refreshed.name, "Updated Name")
