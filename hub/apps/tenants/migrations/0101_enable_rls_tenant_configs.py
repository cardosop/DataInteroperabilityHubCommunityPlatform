"""RLS policy for ``tenant_configs`` table.

``TenantConfig`` has a ``OneToOneField(Tenant)`` creating a ``tenant_id``
column, but no RLS policy existed. This migration brings ``tenant_configs``
in line with the CLAUDE.md contract: every tenant-scoped model ships a
paired RLS policy migration.

Policy shape mirrors the canonical pattern (e.g.
``0057_enable_rls_feature_flag_flip_approval.py``):

* SELECT (USING)     — soft: returns row when
                       ``app.rls_tenant_configs_enabled != 'true'``
                       OR ``tenant_id::text == current_setting('app.current_tenant_id')``.
* INSERT/UPDATE/DELETE (WITH CHECK) — strict: row must satisfy
                       ``tenant_id::text == current_setting('app.current_tenant_id')``.

PLATFORM_ADMIN write paths route through the ``admin`` BYPASSRLS
alias (see ``hub/db_router.py`` + ``hub/settings.py:DATABASES['admin']``).
"""
from __future__ import annotations

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0100_add_billing_interval_db_default"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE tenant_configs ENABLE ROW LEVEL SECURITY;
            DROP POLICY IF EXISTS tenant_isolation ON tenant_configs;
            CREATE POLICY tenant_isolation ON tenant_configs
            USING (
                current_setting('app.rls_tenant_configs_enabled', true) <> 'true'
                OR tenant_id::text =
                   current_setting('app.current_tenant_id', true)
            )
            WITH CHECK (
                tenant_id::text =
                current_setting('app.current_tenant_id', true)
            );
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation ON tenant_configs;
            ALTER TABLE tenant_configs DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
