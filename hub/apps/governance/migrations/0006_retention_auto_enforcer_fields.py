# Phase 232.7 — regulation-driven horizons + tombstone scheduling for auto-sweep.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("governance", "0005_accessrequest_order_fk"),
    ]

    operations = [
        migrations.AddField(
            model_name="retentionpolicy",
            name="regulation_keys",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text=(
                    "Regime keys (uppercase strings) for TIME_BASED policies; "
                    "when non-empty they drive retention_period_days automatically."
                ),
            ),
        ),
        migrations.AddField(
            model_name="retentionpolicy",
            name="tombstoned_at",
            field=models.DateTimeField(
                blank=True,
                help_text=(
                    "Phase 232.7 auto-sweep tombstone marker (UTC) before the 90-calendar-day "
                    "hard-delete grace completes."
                ),
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="retentionpolicy",
            name="hard_delete_scheduled_at",
            field=models.DateTimeField(
                blank=True,
                help_text="UTC deadline for hard-delete execution by the Phase 232.7 auto-sweep.",
                null=True,
            ),
        ),
        migrations.AddIndex(
            model_name="retentionpolicy",
            index=models.Index(fields=["tenant", "tombstoned_at"], name="ret_pol_tenant_tomb_ix"),
        ),
    ]
