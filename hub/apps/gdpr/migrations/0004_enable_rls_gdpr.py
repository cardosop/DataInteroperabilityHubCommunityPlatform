"""285.12.2.11 — RLS on data_export_jobs + erasure_requests."""
from django.db import migrations

_TABLES = ["data_export_jobs", "erasure_requests"]

class Migration(migrations.Migration):
    dependencies = [("gdpr", "0003_rename_data_export_user_status_idx_data_export_user_id_4da15a_idx_and_more")]
    operations = [
        migrations.RunSQL(
            sql="\n".join(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; DROP POLICY IF EXISTS tenant_isolation ON {t}; CREATE POLICY tenant_isolation ON {t} USING (current_setting('app.rls_{t}_enabled',true)<>'true' OR tenant_id::text=current_setting('app.current_tenant_id',true)) WITH CHECK (tenant_id::text=current_setting('app.current_tenant_id',true));" for t in _TABLES),
            reverse_sql="\n".join(f"DROP POLICY IF EXISTS tenant_isolation ON {t}; ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;" for t in _TABLES),
        ),
    ]
