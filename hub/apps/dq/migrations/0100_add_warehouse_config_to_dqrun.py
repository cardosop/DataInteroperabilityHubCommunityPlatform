"""
285.10.2.1.2 — Add warehouse_config JSONField to DQRun.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dq", "0099_alter_dqrun_dataset_set_null"),
    ]

    operations = [
        migrations.AddField(
            model_name="dqrun",
            name="warehouse_config",
            field=models.JSONField(
                blank=True,
                default=None,
                help_text="Warehouse-specific config: {warehouse_type, credential_ref, table_fqn, query_timeout_seconds (default 300), cost_tracking}",
                null=True,
            ),
        ),
    ]
