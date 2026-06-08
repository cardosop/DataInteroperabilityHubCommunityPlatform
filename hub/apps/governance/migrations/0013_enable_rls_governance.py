"""285.12.2.7 — enable RLS on 5 governance tables."""
from django.db import migrations

_TABLES = ["access_requests","retention_policies","access_request_comments","approval_delegations","access_policies"]

class Migration(migrations.Migration):
    dependencies = [("governance", "0012_remove_accessrequestcomment_ar_comment_thread_idx_and_more")]
    operations = [
        migrations.RunSQL(
            sql="\n".join(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY; DROP POLICY IF EXISTS tenant_isolation ON {t}; CREATE POLICY tenant_isolation ON {t} USING (current_setting('app.rls_{t}_enabled',true)<>'true' OR tenant_id::text=current_setting('app.current_tenant_id',true)) WITH CHECK (tenant_id::text=current_setting('app.current_tenant_id',true));" for t in _TABLES),
            reverse_sql="\n".join(f"DROP POLICY IF EXISTS tenant_isolation ON {t}; ALTER TABLE {t} DISABLE ROW LEVEL SECURITY;" for t in _TABLES),
        ),
    ]
