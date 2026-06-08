# Generated manually — Phase 231.4

from datetime import timedelta

from django.db import migrations, models
from django.db.models import F
from django.utils import timezone


def backfill_webhook_fired_at_for_old_succeeded(apps, schema_editor):
    """
    D231.9 — Retro rows should not replay ``compliance.completed`` on rollout.

    SUCCEEDED runs older than 7 days with no explicit stamp inherit
    ``webhook_fired_at = completed_at`` so newer signal wiring treats them as
    already delivered for idempotency purposes.
    """
    ComplianceRun = apps.get_model("compliance", "ComplianceRun")
    cutoff = timezone.now() - timedelta(days=7)
    ComplianceRun.objects.filter(
        status="SUCCEEDED",
        completed_at__isnull=False,
        completed_at__lte=cutoff,
        webhook_fired_at__isnull=True,
    ).update(webhook_fired_at=F("completed_at"))


class Migration(migrations.Migration):

    dependencies = [
        ("compliance", "0100_enable_rls_compliance_runs"),
    ]

    operations = [
        migrations.AddField(
            model_name="compliancerun",
            name="webhook_fired_at",
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text=(
                    "Set when a compliance.completed webhook emission attempt completed "
                    "successfully for this terminal run (SUCCEEDED/FAILED)."
                ),
            ),
        ),
        migrations.RunPython(
            backfill_webhook_fired_at_for_old_succeeded,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
