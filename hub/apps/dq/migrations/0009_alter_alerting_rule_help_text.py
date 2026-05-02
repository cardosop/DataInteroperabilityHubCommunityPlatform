"""
Phase 240.5.C audit-fix — DQAlertingRule help_text drift.

After the original Phase 240.1.A.3 migration
(``0006_alerting_dedupe_fields.py``) was generated, the model's
``help_text`` strings on ``DQAlertingRule.last_alert_id`` and
``DQAlertingRule.last_fired_at`` were intentionally pruned to
one-liners — the long-form context already lives in the comment
block above each field, so duplicating it in ``help_text=`` was
redundant.  No accompanying migration was generated at the time,
which left the model + migration's tracked ``help_text`` values
out of sync.

The Phase 240.5.C.1 CI gate (`test-dq-migrations-check`) caught
this on its first run with::

    Migrations for 'dq':
      hub/apps/dq/migrations/0009_alter_alerting_rule_help_text.py
        ~ Alter field last_alert_id on dqalertingrule
        ~ Alter field last_fired_at on dqalertingrule

This migration captures the help_text pruning explicitly so the
gate goes green.

Schema impact: NONE.  ``help_text`` is purely Django-side metadata
(used by admin / form rendering); it never appears in DDL.  The
``AlterField`` operations execute as no-ops at the database level
— the only state change is in Django's internal migration history.
Safe to run on production at any time; no lock acquisition.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dq", "0008_softdelete_dq_models"),
    ]

    operations = [
        migrations.AlterField(
            model_name="dqalertingrule",
            name="last_alert_id",
            field=models.CharField(
                blank=True,
                help_text=(
                    "Phase 240.1.A — deterministic alert_id of the last "
                    "delivered alert (sha256(rule:run:type)[:32])."
                ),
                max_length=64,
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="dqalertingrule",
            name="last_fired_at",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Phase 240.1.A — timestamp of the last delivery attempt."
                ),
                null=True,
            ),
        ),
    ]
