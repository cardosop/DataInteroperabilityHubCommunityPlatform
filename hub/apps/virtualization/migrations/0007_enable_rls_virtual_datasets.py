"""285.12.2.8 — RLS on virtual_datasets."""
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [("virtualization", "0006_encrypt_sources")]
    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE virtual_datasets ENABLE ROW LEVEL SECURITY; DROP POLICY IF EXISTS tenant_isolation ON virtual_datasets; CREATE POLICY tenant_isolation ON virtual_datasets USING (current_setting('app.rls_virtual_datasets_enabled',true)<>'true' OR tenant_id::text=current_setting('app.current_tenant_id',true)) WITH CHECK (tenant_id::text=current_setting('app.current_tenant_id',true));",
            reverse_sql="DROP POLICY IF EXISTS tenant_isolation ON virtual_datasets; ALTER TABLE virtual_datasets DISABLE ROW LEVEL SECURITY;",
        ),
    ]
