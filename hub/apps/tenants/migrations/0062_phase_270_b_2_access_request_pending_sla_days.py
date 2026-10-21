"""Phase 270.B.2.3 — Tenant.access_request_pending_sla_days field.

Per-tenant SLA (days) for an ``AccessRequest`` to stay in PENDING
before the daily ``revoke_expired_access`` sweep transitions it to
EXPIRED + emits ``ACCESS_REQUEST_EXPIRED_BY_SLA`` audit.

Default 14 d — two work-weeks for the provider's data-owner to
decide. Bounds [1, 365]: lower 1 day so a tenant operating in a
regulated regime can opt into same-day SLA enforcement; upper 365
days prevents an effectively-never SLA (an indefinitely-pending
request is governance debt the provider's tooling should be
flagging anyway).

The default applies to existing rows via Django's standard
``AddField`` semantics — no separate backfill needed because the
default is sane for every tenant (the SLA fires on rows older than
the configured value; a tenant who wants to opt out can set the
field to 365 d via the tenant-admin API).

This migration was deliberately stripped to ONLY the new field's
AddField op. ``makemigrations`` proposed several unrelated
RenameIndex / AlterField operations that reflect accumulated
help_text + index-naming drift from earlier phases — those are
pre-existing churn outside this phase's scope and should land via
a dedicated state-sync migration (not as a hidden side-effect of
the SLA field add).
"""
import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0061_phase_270_a_1_order_plan_limit"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="access_request_pending_sla_days",
            field=models.PositiveIntegerField(
                default=14,
                help_text=(
                    "Phase 270.B.2 — number of days an AccessRequest "
                    "can stay in PENDING before the daily "
                    "``revoke_expired_access`` sweep transitions it "
                    "to EXPIRED. Default 14 d. Bounds [1, 365]."
                ),
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(365),
                ],
            ),
        ),
    ]
