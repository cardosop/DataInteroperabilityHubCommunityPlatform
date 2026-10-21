# Generated migration: enable RLS on data_movement tables missing policies.
from django.db import migrations

_TABLES = ["data_movement_config"]

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
        ("data_movement", "0001_initial"),
    ]
    operations = [
        migrations.RunSQL(sql=_SQL, reverse_sql=_REVERSE),
    ]
