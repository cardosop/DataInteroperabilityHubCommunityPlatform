"""
Migration 0009 — Phase 12.4

1. Add nullable ``tenant`` FK to UserRole (populated from role.tenant).
2. Data-migrate: set tenant = role.tenant for every existing row.
3. Remove old (user, role) unique constraint.
4. Add new (user, tenant, role) unique constraint.

The tenant column is left nullable at the DB level to keep the migration
safe on large tables (no NOT NULL scan on add); application code always
supplies tenant via get_or_create, so nulls will not reappear after this
migration runs.
"""
from django.db import migrations, models
import django.db.models.deletion


def _populate_tenant_from_role(apps, schema_editor):
    """Backfill tenant from role.tenant for all existing UserRole rows."""
    UserRole = apps.get_model("users", "UserRole")
    for ur in UserRole.objects.select_related("role").all():
        if ur.tenant_id is None:
            ur.tenant_id = ur.role.tenant_id
            ur.save(update_fields=["tenant_id"])


def _noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0008_hash_existing_user_tokens"),
        ("tenants", "0014_add_user_tenant_membership"),
    ]

    operations = [
        # Step 1: add nullable tenant FK
        migrations.AddField(
            model_name="userrole",
            name="tenant",
            field=models.ForeignKey(
                help_text="Tenant this role assignment belongs to (denormalised from role.tenant)",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="user_role_assignments",
                to="tenants.tenant",
            ),
        ),
        # Step 2: populate tenant from role
        migrations.RunPython(_populate_tenant_from_role, reverse_code=_noop),
        # Step 3: drop old (user, role) unique constraint
        migrations.RemoveConstraint(
            model_name="userrole",
            name="unique_user_role",
        ),
        # Step 4: add new (user, tenant, role) unique constraint
        migrations.AddConstraint(
            model_name="userrole",
            constraint=models.UniqueConstraint(
                fields=["user", "tenant", "role"],
                name="unique_user_tenant_role",
            ),
        ),
        # Step 5: add index on (user, tenant) for has_role() lookups
        migrations.AddIndex(
            model_name="userrole",
            index=models.Index(fields=["user", "tenant"], name="user_roles_user_tenant_idx"),
        ),
    ]
