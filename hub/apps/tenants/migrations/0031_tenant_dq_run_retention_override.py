"""
Phase 240.1.C.2 — per-tenant DQ-run retention override.

Adds ``Tenant.dq_run_retention_days`` (PositiveIntegerField, default
90, validators bounding the value to ``[7, 365]`` per D240.7).

Bound rationale (D240.7):
* Lower 7 d — compliance requires keeping enough history for incident
  forensics; values below a week make audit trails un-auditable.
* Upper 365 d — storage / cost guard. Tenants who genuinely need
  multi-year history should use the dedicated audit-log archive
  pathway, not keep raw DQ run rows hot.

Default 90 d matches the platform-wide retention SLA; tenants whose
workloads need shorter (e.g. dev / sandbox) or longer (regulated)
windows can override per-row.
"""
from __future__ import annotations

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0030_tenant_semantic_graphql_ld_enabled"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="dq_run_retention_days",
            field=models.PositiveIntegerField(
                default=90,
                validators=[
                    django.core.validators.MinValueValidator(7),
                    django.core.validators.MaxValueValidator(365),
                ],
                help_text=(
                    "Phase 240.1.C — number of days to retain DQRun "
                    "rows for this tenant before soft-delete "
                    "(purge_dq_runs). Bounds: [7, 365] per D240.7."
                ),
            ),
        ),
    ]
