# Phase 260.2.F — full audit sampling for GET /files/{id}/ metadata views.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0050_tenant_file_soft_delete_grace_days"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="compliance_audit_full_sampling",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When True, every successful GET /api/v1/files/{id}/ emits FILE_METADATA_VIEWED. "
                    "When False, the platform uses a deterministic ~10% sample per (tenant, file, user)."
                ),
            ),
        ),
    ]
