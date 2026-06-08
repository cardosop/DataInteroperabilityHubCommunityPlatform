"""285.12.4.2 — RLS on warehouse_connections + warehouse_connection_acls."""
from django.db import migrations

_TABLES = ["warehouse_connections", "warehouse_connection_acls"]

class Migration(migrations.Migration):
    dependencies = [("warehouses", "0001_initial")]
    operations = [
        migrations.RunSQL(
            sql="\n".join(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; DROP POLICY IF EXISTS tenant_isolation ON {t}; CREATE POLICY tenant_isolation ON {t} USING (current_setting('app.rls_{t}_enabled',true)<>'true' OR tenant_id::text=current_setting('app.current_tenant_id',true)) WITH CHECK (tenant_id::text=current_setting('app.current_tenant_id',true));" for t in _TABLES),
            reverse_sql="\n".join(f"DROP POLICY IF EXISTS tenant_isolation ON {t}; ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;" for t in _TABLES),
        ),
    ]
