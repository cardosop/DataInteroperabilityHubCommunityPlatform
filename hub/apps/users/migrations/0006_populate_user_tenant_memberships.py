# Data migration: populate UserTenantMembership for existing users with tenant_id.
# Per design D16. Idempotent.

from django.db import migrations


def create_memberships_for_existing_users(apps, schema_editor):
    """For each User with tenant_id, create UserTenantMembership if not exists."""
    User = apps.get_model("users", "User")
    UserTenantMembership = apps.get_model("users", "UserTenantMembership")

    for user in User.objects.filter(tenant_id__isnull=False).select_related("tenant"):
        UserTenantMembership.objects.get_or_create(
            user=user,
            tenant=user.tenant,
            defaults={},
        )


def noop_reverse(apps, schema_editor):
    """No reverse - memberships remain when rolling back schema."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0005_add_user_tenant_membership"),
    ]

    operations = [
        migrations.RunPython(create_memberships_for_existing_users, noop_reverse),
    ]
