"""Phase 235.1.4 — RLS policy for ``feature_flag_flip_approvals``.

Paired with ``0056_feature_flag_flip_approval`` per the CLAUDE.md
contract: every new tenant-scoped model ships an RLS policy
migration. Policy shape mirrors the Phase 234.5 retention-policy
migration (``0009_enable_rls_audit_event_retention_policy``):

* SELECT (USING)     — soft: returns row when
                       ``app.rls_feature_flag_flip_approvals_enabled != 'true'``
                       OR ``tenant_id::text == current_setting('app.current_tenant_id')``.
* INSERT/UPDATE/DELETE (WITH CHECK) — strict: row must satisfy
                       ``tenant_id::text == current_setting('app.current_tenant_id')``.

PLATFORM_ADMIN write paths route through the ``admin`` BYPASSRLS
alias (see ``hub/db_router.py`` + ``hub/settings.py:DATABASES['admin']``)
— the same pattern Phase 234.4 / 234.5 use for cross-tenant
administrative work.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0073_merge_20260512_2259"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE feature_flag_flip_approvals ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON feature_flag_flip_approvals;
            CREATE POLICY tenant_isolation ON feature_flag_flip_approvals
            USING (
                current_setting('app.rls_feature_flag_flip_approvals_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON feature_flag_flip_approvals;
            ALTER TABLE feature_flag_flip_approvals DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
