"""Phase 235.4.2 — RLS policy for ``impersonation_sessions``.

Paired with ``0059_phase_235_4_impersonation`` per the CLAUDE.md
contract: every new tenant-scoped model ships an RLS policy migration.

Tenant column choice
====================

``ImpersonationSession`` carries TWO tenant FKs:

* ``impersonator_tenant`` — the PLATFORM_ADMIN's home tenant (nullable,
  intentionally cross-tenant — the operator is acting on behalf of the
  platform, not their home tenant).
* ``impersonated_tenant`` — the tenant whose user is being impersonated.

The row-level boundary is ``impersonated_tenant_id``: this is the tenant
whose users' actions WILL appear under the JWT issued from the session,
and so is the tenant a tenant-admin would expect to see the session row
under when reviewing their own audit / governance surface.

PLATFORM_ADMIN write paths route through the ``admin`` BYPASSRLS alias
(see ``hub/db_router.py`` + ``hub/settings.py:DATABASES['admin']``) —
the same pattern Phase 234.4 / 234.5 / 235.1 use for cross-tenant
administrative work, so the create-session endpoint can write a row
scoped to a tenant other than the operator's own.

Policy shape mirrors Phase 235.1.4 (feature_flag_flip_approvals):

* SELECT (USING)     — soft: returns row when
                       ``app.rls_impersonation_sessions_enabled != 'true'``
                       OR ``impersonated_tenant_id::text == current_setting('app.current_tenant_id')``.
* INSERT/UPDATE/DELETE (WITH CHECK) — strict.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0073_merge_20260512_2259"),
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
