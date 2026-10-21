"""
285.5.2 — Add 7 new per-tenant feature flag BooleanFields.

Per CLAUDE.md: additive migration, default=False for existing tenants.
"""
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0080_alter_tenant_data_quality_advanced_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="marketplace_integrations_enabled",
            field=models.BooleanField(default=False, help_text="285.5.2.1 — DRAFT. Gates external marketplace integrations."),
        ),
        migrations.AddField(
            model_name="tenant",
            name="data_mesh_enabled",
            field=models.BooleanField(default=False, help_text="285.5.2.2 — CANARY. Gates Data Mesh domains feature."),
        ),
        migrations.AddField(
            model_name="tenant",
            name="virtualization_enabled",
            field=models.BooleanField(default=False, help_text="285.5.2.3 — CANARY. Gates data virtualization. Review 2027-03-01."),
        ),
        migrations.AddField(
            model_name="tenant",
            name="developer_enabled",
            field=models.BooleanField(default=False, help_text="285.5.2.4 — DRAFT. Gates developer portal + plugins."),
        ),
        migrations.AddField(
            model_name="tenant",
            name="ml_enabled",
            field=models.BooleanField(default=False, help_text="285.5.2.5 — CANARY. Gates ML Model Registry + Inference."),
        ),
        migrations.AddField(
            model_name="tenant",
            name="transformation_enabled",
            field=models.BooleanField(default=False, help_text="285.5.2.6 — DRAFT. Gates ETL/ELT pipelines."),
        ),
        migrations.AddField(
            model_name="tenant",
            name="baas_enabled",
            field=models.BooleanField(default=False, help_text="285.5.2.7 — CANARY. Gates Backend-as-a-Service."),
        ),
    ]
