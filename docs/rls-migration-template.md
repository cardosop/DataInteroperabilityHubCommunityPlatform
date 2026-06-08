# RLS Migration Template & Pre-Flight Audit

285.14.1.2 + 285.14.1.3 — Canonical RLS migration template and pre-flight
tenant_context audit requirements for all new tenant-scoped models.

## Migration Template

Every new model with a `tenant_id` ForeignKey MUST ship a paired RLS
policy migration in the same migration file or the next sequential one.

### Template — Direct FK (tenant_id on model itself)

```python
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("<app_label>", "<previous_migration>"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
            ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;

            CREATE POLICY tenant_isolation_<table_name>
            ON <table_name>
            FOR ALL
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid)
            WITH CHECK (tenant_id = current_setting('app.current_tenant_id')::uuid);
            """,
            reverse_sql="""
            DROP POLICY IF EXISTS tenant_isolation_<table_name> ON <table_name>;

            ALTER TABLE <table_name> DISABLE ROW LEVEL SECURITY;
            """,
        ),
    ]
```

### Template — Indirect FK (tenant accessed through parent chain)

```python
migrations.RunSQL(
    sql="""
    ALTER TABLE <child_table> ENABLE ROW LEVEL SECURITY;

    CREATE POLICY tenant_isolation_<child_table>
    ON <child_table>
    FOR ALL
    USING (
        <parent_fk_column> IN (
            SELECT id FROM <parent_table>
            WHERE tenant_id = current_setting('app.current_tenant_id')::uuid
        )
    )
    WITH CHECK (
        <parent_fk_column> IN (
            SELECT id FROM <parent_table>
            WHERE tenant_id = current_setting('app.current_tenant_id')::uuid
        )
    );
    """,
    reverse_sql="""
    DROP POLICY IF EXISTS tenant_isolation_<child_table> ON <child_table>;
    ALTER TABLE <child_table> DISABLE ROW LEVEL SECURITY;
    """,
)
```

### Rules

| Rule | Detail |
|------|--------|
| **Order** | `ENABLE ROW LEVEL SECURITY` MUST be in the same transaction as `CREATE POLICY`. Do NOT enable RLS without a policy — it would immediately block all access. |
| **Naming** | Policy name: `tenant_isolation_<table_name>`. Use the exact table name from `db_table` Meta option. |
| **Direct FK** | `USING (tenant_id = current_setting('app.current_tenant_id')::uuid)` with matching `WITH CHECK`. |
| **Indirect FK** | Subquery through the parent chain to the table that has the `tenant_id`. Include both `USING` and `WITH CHECK`. |
| **Reverse SQL** | Always provide `reverse_sql` with `DROP POLICY IF EXISTS` before `DISABLE ROW LEVEL SECURITY`. |
| **Idempotency** | Use `DROP POLICY IF EXISTS` before `CREATE POLICY` when retrofitting RLS to an existing table. |

## Pre-Flight tenant_context Audit (285.14.1.3)

Before enabling RLS on any table:

1. **Grep all code paths** that query the model:
   ```bash
   grep -rn "ModelName.objects\." hub/apps/ --include="*.py" | grep -v test | grep -v migration
   ```

2. **Verify tenant context** — every query path MUST either:
   - Run inside `tenant_context(tenant_id)` (sets `app.current_tenant_id` GUC), OR
   - Use `DATABASES["admin"]` (`meshant_admin`, `BYPASSRLS`) — for cross-tenant queries (dashboards, management commands, platform-admin views), OR
   - Be a worker/signal handler that wraps its work in `tenant_context(tenant_id)`.

3. **Document findings** in the migration file docstring. Example:

   ```python
   """Phase XXX — RLS policy for <table_name>.

   Pre-flight tenant_context audit (285.14.1.3):
     - views.py:123 — TenantConfigViewSet.usage() → uses get_request_tenant_id()
       which resolves the tenant from the JWT and routes through
       TenantScopedThrottle — the request's DB connection has
       app.current_tenant_id set by TenantMiddleware.
     - services.py:456 — BillingService.record_usage() → wrapped in
       tenant_context(tenant_id) by the caller.
     - management/commands/reconcile_stripe.py — uses
       DATABASES["admin"] (BYPASSRLS) for cross-tenant reconciliation.

   No unguarded query paths found. RLS policy is safe to enable.
   """
   ```

4. **Run the `lint-rls-policies` CI check:**
   ```bash
   python scripts/lint_rls_policies.py
   ```
   This script verifies every model with a `tenant_id` field has a
   corresponding RLS migration. CI blocks merges that add a `tenant_id`
   without a paired policy.

## Existing RLS Migration Examples

| Model | Migration | Pattern |
|-------|-----------|--------|
| `form_drafts` | `core/migrations/0008_form_draft_rls.py` | Direct FK |
| `audit_events` | `audit/migrations/0005_enable_rls_audit_events.py` | Direct FK + feature flag guard |
| `assets` | `assets/migrations/0018_enable_rls_assets.py` | Direct FK |
| `datasets` | `datasets/migrations/0004_enable_rls.py` | Direct FK |
| `subscriptions` | `billing/migrations/0006_enable_rls.py` | Direct FK |
