# Phase 260.3.E — tenant flag for sample PII redaction in UI/API.

from django.db import migrations, models


def forwards(apps, schema_editor):
    Tenant = apps.get_model("tenants", "Tenant")
    Tenant._default_manager.filter(kyc_status="VERIFIED").update(redact_sample_pii_in_ui=True)


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0052_tenant_datasets_files_flags"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="redact_sample_pii_in_ui",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Phase 260.3.E — sample preview responses replace suspected PII with "
                    "[redacted] for users without VIEW_PII (include_pii). Verified tenants "
                    "default True on create/migration backfill."
                ),
            ),
        ),
        migrations.RunPython(forwards, noop_reverse),
    ]
