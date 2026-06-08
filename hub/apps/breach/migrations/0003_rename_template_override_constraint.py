"""Rename template-override unique constraint to satisfy Django E034 (≤30 chars).

Uses ``SeparateDatabaseAndState`` + PostgreSQL ``ALTER TABLE ... RENAME CONSTRAINT`` for
a reliable rename across Django versions (avoids ``RenameConstraint`` import/signature drift).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("breach", "0002_enable_rls_breach"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql=(
                        'ALTER TABLE breach_tenant_template_override '
                        'RENAME CONSTRAINT "breach_templ_override_tenant_regime_uniq" '
                        'TO "br_tt_ovr_tnt_reg_uniq";'
                    ),
                    reverse_sql=(
                        'ALTER TABLE breach_tenant_template_override '
                        'RENAME CONSTRAINT "br_tt_ovr_tnt_reg_uniq" '
                        'TO "breach_templ_override_tenant_regime_uniq";'
                    ),
                ),
            ],
            state_operations=[
                migrations.RemoveConstraint(
                    model_name="breachtenanttemplateoverride",
                    name="breach_templ_override_tenant_regime_uniq",
                ),
                migrations.AddConstraint(
                    model_name="breachtenanttemplateoverride",
                    constraint=models.UniqueConstraint(
                        fields=("tenant", "regime"),
                        name="br_tt_ovr_tnt_reg_uniq",
                    ),
                ),
            ],
        ),
    ]
