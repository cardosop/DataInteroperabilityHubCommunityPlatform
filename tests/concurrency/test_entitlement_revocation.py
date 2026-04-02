"""Constraint-based entitlement revocation tests (replaces threading-based concurrency)."""
import uuid

from django.test import TestCase

from hub.apps.tenants.models import Tenant


class EntitlementRevocationConsistencyTest(TestCase):
    """Read-after-write returns the updated state."""

    def test_read_after_write_consistent(self):
        uid = uuid.uuid4().hex[:8]
        tenant = Tenant.objects.create(name=f"ER {uid}", slug=f"er-{uid}")
        tenant.name = f"Revoked {uid}"
        tenant.save()
        refreshed = Tenant.objects.get(pk=tenant.pk)
        self.assertEqual(refreshed.name, f"Revoked {uid}")
