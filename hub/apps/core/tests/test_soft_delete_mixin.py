"""Phase 92: Soft-delete mixin tests."""

from django.test import TestCase
from django.utils import timezone

from hub.apps.tenants.models import Tenant


class TestTenantSoftDelete(TestCase):
    """Verify soft-delete managers work on Tenant model."""

    def test_default_manager_excludes_deleted(self):
        """Tenant.objects.all() must exclude soft-deleted rows."""
        tenant = Tenant.objects.create(
            name="Active Tenant",
            slug="active-tenant",
        )
        deleted_tenant = Tenant.all_objects.create(
            name="Deleted Tenant",
            slug="deleted-tenant",
            deleted_at=timezone.now(),
        )

        active_ids = set(Tenant.objects.values_list("id", flat=True))
        self.assertIn(tenant.id, active_ids)
        self.assertNotIn(deleted_tenant.id, active_ids)

    def test_all_objects_includes_deleted(self):
        """Tenant.all_objects.all() must include soft-deleted rows."""
        tenant = Tenant.objects.create(
            name="Active Tenant 2",
            slug="active-tenant-2",
        )
        deleted_tenant = Tenant.all_objects.create(
            name="Deleted Tenant 2",
            slug="deleted-tenant-2",
            deleted_at=timezone.now(),
        )

        all_ids = set(Tenant.all_objects.values_list("id", flat=True))
        self.assertIn(tenant.id, all_ids)
        self.assertIn(deleted_tenant.id, all_ids)

    def test_soft_delete_method(self):
        """soft_delete() sets deleted_at and hides from default manager."""
        tenant = Tenant.objects.create(
            name="To Delete",
            slug="to-delete",
        )
        self.assertIn(tenant.id, set(Tenant.objects.values_list("id", flat=True)))

        tenant.soft_delete()

        self.assertNotIn(tenant.id, set(Tenant.objects.values_list("id", flat=True)))
        self.assertIn(tenant.id, set(Tenant.all_objects.values_list("id", flat=True)))

    def test_restore_method(self):
        """restore() clears deleted_at and makes visible in default manager."""
        tenant = Tenant.all_objects.create(
            name="Restore Me",
            slug="restore-me",
            deleted_at=timezone.now(),
        )
        self.assertNotIn(tenant.id, set(Tenant.objects.values_list("id", flat=True)))

        tenant.restore()

        self.assertIn(tenant.id, set(Tenant.objects.values_list("id", flat=True)))
