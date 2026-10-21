"""
285.14.2.7 — RLS policy for all 6 observability tenant-scoped tables.

Pre-flight tenant_context audit (285.14.1.3):
  - views.py:35 — ObservabilityViewSet is read-only aggregations over
    tenant-owned data; each data source (metrics/trends/drifts/executions/
    SLAs/incidents) is written by ingestion workers running inside
    tenant_context(tenant_id) via the RQ worker.
  - No unguarded cross-tenant query paths found.
  - management/commands: no observability-specific commands exist.
"""
from django.db import migrations


_TABLES = [
    "data_observability_metrics",
    "volume_trends",
    "schema_drifts",
    "pipeline_executions",
    "data_slas",
    "data_incidents",
]

_SQL_UP = "\n".join(
    f"""
    ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
    CREATE POLICY tenant_isolation_{t}
    ON {t}
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);
    """
    for t in _TABLES
)

_SQL_DOWN = "\n".join(
    f"""
    DROP POLICY IF EXISTS tenant_isolation_{t} ON {t};
    ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;
    """
    for t in _TABLES
)


class Migration(migrations.Migration):
    dependencies = [
        ("observability", "0006_rename_data_incid_tenant__idx_data_incide_tenant__9799c7_idx_and_more"),
    ]

    operations = [
        migrations.RunSQL(sql=_SQL_UP, reverse_sql=_SQL_DOWN),
    ]
