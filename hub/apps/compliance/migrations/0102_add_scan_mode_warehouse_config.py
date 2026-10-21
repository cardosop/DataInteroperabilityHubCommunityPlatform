"""
285.10.3.1.2 — Add scan_mode + warehouse_config to ComplianceRun.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0101_compliancerun_webhook_fired_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="compliancerun",
            name="scan_mode",
            field=models.CharField(
                choices=[("FILE_SCAN", "File Scan"), ("IN_MEMORY", "In-Memory"), ("WAREHOUSE_SQL", "Warehouse SQL")],
                default="FILE_SCAN",
                help_text="Scan mode: FILE_SCAN, IN_MEMORY, or WAREHOUSE_SQL",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="compliancerun",
            name="warehouse_config",
            field=models.JSONField(
                blank=True,
                default=None,
                help_text="Warehouse-specific config: {warehouse_type, credential_ref, table_fqn, query_timeout_seconds, cost_tracking}",
                null=True,
            ),
        ),
    ]
