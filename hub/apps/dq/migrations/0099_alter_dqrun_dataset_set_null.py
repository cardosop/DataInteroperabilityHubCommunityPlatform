"""
Migration: Change DQRun.dataset on_delete from CASCADE to SET_NULL.

Phase 26-OB.1: Preserves DQ audit trail when datasets are deleted.
"""
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("dq", "0005_encrypt_channel_config"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dqrun",
            name="dataset",
            field=models.ForeignKey(
                blank=True,
                help_text="Dataset this DQ run is for (nullable; SET_NULL preserves audit trail)",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="dq_runs",
                to="datasets.dataset",
            ),
        ),
    ]
