# Phase 278.O.1 — RLS policy for form_drafts table.
# Per CLAUDE.md Tenant Isolation RLS Contract: every new model
# with a tenant_id FK must ship a paired RLS policy migration.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0007_form_draft"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE form_drafts ENABLE ROW LEVEL SECURITY;

            CREATE POLICY tenant_isolation_form_drafts
            ON form_drafts
            FOR ALL
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation_form_drafts ON form_drafts;

            ALTER TABLE form_drafts DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
