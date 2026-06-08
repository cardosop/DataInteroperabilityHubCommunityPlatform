# Phase 232.4 — RoPA scaffolding fields on Asset.

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("assets", "0018_enable_rls_assets"),
        ("consent", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="asset",
            name="categories_of_subjects",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Categories of data subjects (structured labels for supervisory registers).",
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="recipient_categories",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Categories of recipients of personal data.",
            ),
        ),
        migrations.AddField(
            model_name="asset",
            name="processing_purposes",
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "Consent / processing purposes applicable to this asset for RoPA exports."
                ),
                related_name="ropa_assets",
                to="consent.consentpurpose",
            ),
        ),
    ]
