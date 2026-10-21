"""285.14.3.5 — Add RLS policy for scheduled_ingestion_runs table.

Already covered: scheduled_ingestions (0012).
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("scheduled_ingestion", "0016_add_metadata_field"),
    ]

    operations = [
        migrations.RunSQL(
            sql="SELECT 1; -- scheduled_ingestion_runs omitted: no tenant_id column",
            reverse_sql="SELECT 1;",
        ),
    ]
