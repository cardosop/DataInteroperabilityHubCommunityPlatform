"""285.12.2.9 — RLS on marketplace_connections."""
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [("integrations", "0012_openlineage_grace_audit")]
    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE marketplace_connections ENABLE ROW LEVEL SECURITY; DROP POLICY IF EXISTS tenant_isolation ON marketplace_connections; CREATE POLICY tenant_isolation ON marketplace_connections USING (current_setting('app.rls_marketplace_connections_enabled',true)<>'true' OR tenant_id::text=current_setting('app.current_tenant_id',true)) WITH CHECK (tenant_id::text=current_setting('app.current_tenant_id',true));",
            reverse_sql="DROP POLICY IF EXISTS tenant_isolation ON marketplace_connections; ALTER TABLE marketplace_connections DISABLE ROW LEVEL SECURITY;",
        ),
    ]
