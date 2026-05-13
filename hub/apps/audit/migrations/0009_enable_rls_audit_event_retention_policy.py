"""Phase 234.5.1 — RLS policy for ``audit_event_retention_policies``.

Paired with ``0008_audit_event_retention_policy`` per the CLAUDE.md
contract: every new tenant-scoped model ships an RLS policy migration.

Policy shape mirrors ``audit_events`` (Phase 234.1 ``0005_enable_rls_audit_events``):

* SELECT (USING)     — soft: returns row when
                       ``app.rls_audit_event_retention_policies_enabled != 'true'``
                       OR ``tenant_id::text == current_setting('app.current_tenant_id')``.
* INSERT/UPDATE/DELETE (WITH CHECK) — strict: row must satisfy
                       ``tenant_id::text == current_setting('app.current_tenant_id')``.

Management-command access uses the ``admin`` BYPASSRLS alias (see
``hub/db_router.py`` + ``hub/settings.py:DATABASES['admin']``).
"""
from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0004_auditevent_full_details_json"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE audit_event_retention_policies ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON audit_event_retention_policies;
            CREATE POLICY tenant_isolation ON audit_event_retention_policies
            USING (
                current_setting('app.rls_audit_event_retention_policies_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON audit_event_retention_policies;
            ALTER TABLE audit_event_retention_policies DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
