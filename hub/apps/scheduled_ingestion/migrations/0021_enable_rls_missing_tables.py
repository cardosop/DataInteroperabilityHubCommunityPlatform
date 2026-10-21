# Generated migration: enable RLS on scheduled_ingestion tables missing policies.
from django.db import migrations

_TABLES = [
    "ingestion_templates",
]

_SQL = "\n".join(
    f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; "
    f"DROP POLICY IF EXISTS tenant_isolation ON {t}; "
    f"CREATE POLICY tenant_isolation ON {t} "
    f"USING (current_setting('app.rls_{t}_enabled',true)<>'true' "
    f"OR tenant_id::text=current_setting('app.current_tenant_id',true)) "
    f"WITH CHECK (tenant_id::text=current_setting('app.current_tenant_id',true));"
    for t in _TABLES
)

_REVERSE = "\n".join(
    f"DROP POLICY IF EXISTS tenant_isolation ON {t}; "
    f"ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;"
    for t in _TABLES
)


class Migration(migrations.Migration):
    dependencies = [
        ("scheduled_ingestion", "0020_add_credential_ref"),
    ]
    operations = [
        migrations.RunSQL(sql=_SQL, reverse_sql=_REVERSE),
    ]
