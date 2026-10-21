"""
Migration: Change ComplianceRun.dataset on_delete from CASCADE to SET_NULL.

Phase 26-OB.2: Preserves compliance audit trail when datasets are deleted.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0004_add_status_created_at_index"),
    ]

    operations = [
        migrations.AlterField(
            model_name="compliancerun",
            name="dataset",
            field=models.ForeignKey(
                blank=True,
                help_text="Dataset this compliance run is for (nullable; SET_NULL preserves audit trail)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="compliance_runs",
                to="datasets.dataset",
            ),
        ),
    ]
