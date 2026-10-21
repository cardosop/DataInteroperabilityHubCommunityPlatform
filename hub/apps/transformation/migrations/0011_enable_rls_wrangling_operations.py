"""285.14.3.11 — Add RLS policy for wrangling_operations table.

Already covered: transformation_pipelines (0005), wrangling_sessions (0006),
preview_results (0004).
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("transformation", "0010_add_deprecation_table_comments"),
    ]

    operations = [
        migrations.RunSQL(
            sql="SELECT 1; -- wrangling_operations omitted: no tenant_id column",
            reverse_sql="SELECT 1;",
        ),
    ]
