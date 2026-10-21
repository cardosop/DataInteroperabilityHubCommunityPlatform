# Phase 260.3.B.1 — per-tenant datasets and files kill switches (default True).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0051_tenant_compliance_audit_full_sampling"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="datasets_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Phase 260.3.B — when True (default), /api/v1/datasets/* is "
                    "enabled for this tenant. When False, every datasets endpoint "
                    "returns HTTP 403 with code DATASETS_DISABLED."
                ),
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="files_enabled",
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Phase 260.3.B — when True (default), /api/v1/files/* is "
                    "enabled for this tenant. When False, every files endpoint "
                    "returns HTTP 403 with code FILES_DISABLED."
                ),
            ),
        ),
    ]
