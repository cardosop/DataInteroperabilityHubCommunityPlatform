"""
Add database-level DEFAULTs for NOT NULL columns on tenant_plans.

Django's AddField with a default backfills existing rows but then removes
the database DEFAULT, leaving only a Python-level default.  Historical
models in RunPython data migrations do not reliably apply Python-level
defaults, causing NOT NULL violations on fresh test databases.

Adding database-level defaults ensures every INSERT — through the ORM
(current or historical), raw SQL, or bulk_create — receives valid values.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0099_seed_default_plans"),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                ALTER TABLE tenant_plans ALTER COLUMN billing_interval SET DEFAULT 'month';
                ALTER TABLE tenant_plans ALTER COLUMN "order" SET DEFAULT 0;
                ALTER TABLE tenant_plans ALTER COLUMN price_amount_cents SET DEFAULT 0;
                ALTER TABLE tenant_plans ALTER COLUMN price_currency SET DEFAULT 'usd';
                ALTER TABLE tenant_plans ALTER COLUMN category SET DEFAULT 'BASE';
                ALTER TABLE tenant_plans ALTER COLUMN compliance_pro_pack SET DEFAULT false;
                ALTER TABLE tenant_plans ALTER COLUMN includes_regulations SET DEFAULT '{}';
                ALTER TABLE tenant_plans ALTER COLUMN marketplace_take_rate_bps SET DEFAULT 1500;
                ALTER TABLE tenant_plans ALTER COLUMN notification_opt_outs SET DEFAULT '{}'::jsonb;
            """,
            reverse_sql="""
                ALTER TABLE tenant_plans ALTER COLUMN billing_interval DROP DEFAULT;
                ALTER TABLE tenant_plans ALTER COLUMN "order" DROP DEFAULT;
                ALTER TABLE tenant_plans ALTER COLUMN price_amount_cents DROP DEFAULT;
                ALTER TABLE tenant_plans ALTER COLUMN price_currency DROP DEFAULT;
                ALTER TABLE tenant_plans ALTER COLUMN category DROP DEFAULT;
                ALTER TABLE tenant_plans ALTER COLUMN compliance_pro_pack DROP DEFAULT;
                ALTER TABLE tenant_plans ALTER COLUMN includes_regulations DROP DEFAULT;
                ALTER TABLE tenant_plans ALTER COLUMN marketplace_take_rate_bps DROP DEFAULT;
                ALTER TABLE tenant_plans ALTER COLUMN notification_opt_outs DROP DEFAULT;
            """,
        ),
    ]
