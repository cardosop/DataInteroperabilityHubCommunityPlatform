"""
Phase 277.B.018a — enable RLS on `impersonation_sessions`.

Per CLAUDE.md RLS contract: every tenant-scoped model MUST ship a
paired RLS policy migration.

NOTE: ``impersonation_sessions`` has NO ``tenant_id`` column — it carries
two tenant FKs (``impersonator_tenant_id`` / ``impersonated_tenant_id``).
The row-level boundary is ``impersonated_tenant_id`` (see the canonical
``tenants.0060_enable_rls_impersonation_session`` for the rationale). The
policy below is idempotent (DROP POLICY IF EXISTS) and consistent with
that canonical definition.
"""
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("tenants", "0059_phase_235_4_impersonation"),
        ("hub_auth", "0008_customer_billing_fields"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE impersonation_sessions ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON impersonation_sessions;
            CREATE POLICY tenant_isolation ON impersonation_sessions
            USING (
                current_setting('app.rls_impersonation_sessions_enabled', true) <> 'true'
                OR impersonated_tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                impersonated_tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON impersonation_sessions;
            ALTER TABLE impersonation_sessions DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
