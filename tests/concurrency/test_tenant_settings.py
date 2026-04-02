"""Phase 103: Tenant update consistency."""
import uuid
from django.test import TestCase
from hub.apps.tenants.models import Tenant


class TenantSettingsConsistencyTest(TestCase):
    """Sequential tenant updates produce consistent state."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"TS {uid}", slug=f"ts-{uid}",
        )

    def test_update_name_persists(self):
        self.tenant.name = "Updated Name"
        self.tenant.save()
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.name, "Updated Name")

    def test_two_sequential_updates_last_value_persists(self):
        self.tenant.name = "First Update"
        self.tenant.save()
        self.tenant.name = "Final Update"
        self.tenant.save()
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.name, "Final Update")
