# Phase 260.3.E — PII_VIEWER role per tenant (explicit VIEW_PII for sample unmask).

from django.db import migrations

_ROLE_NAME = "PII_VIEWER"
_ROLE_DESCRIPTION = (
    "May request unredacted dataset sample previews where tenant policy allows"
)


def forwards(apps, schema_editor):
    Role = apps.get_model("users", "Role")
    Tenant = apps.get_model("tenants", "Tenant")
    for tenant in Tenant._default_manager.all().iterator():
        Role._default_manager.get_or_create(
            tenant=tenant,
            name=_ROLE_NAME,
            defaults={"description": _ROLE_DESCRIPTION},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0019_phase232_privacy_roles_backfill"),
        ("tenants", "0053_tenant_redact_sample_pii_in_ui"),
    ]

    operations = [
        migrations.RunPython(forwards, noop_reverse),
    ]
