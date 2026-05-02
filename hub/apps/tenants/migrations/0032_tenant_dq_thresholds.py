"""
Phase 240.3.D.2 — per-tenant DQ thresholds.

Adds two ``BigIntegerField`` columns on ``Tenant``:

* ``dq_input_max_bytes`` (NULL → platform default ``DQ_INPUT_TOO_LARGE_BYTES``)
  validated to ``[10 MiB, 5 GiB]`` per D240.15.
* ``dq_sampling_threshold_rows`` (NULL → platform default
  ``DQ_SAMPLING_THRESHOLD_ROWS``) validated to ``[10 000, 100 000 000]``
  per D240.15.

The columns are nullable so the addition is purely additive — every
existing tenant immediately falls through to the platform defaults
without a backfill. Operators flip values per-tenant when needed via
the admin / SDK; the api-service then forwards them to dq-service as
``X-Tenant-Threshold-*`` headers.
"""
from __future__ import annotations

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0031_tenant_dq_run_retention_override"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="dq_input_max_bytes",
            field=models.BigIntegerField(
                null=True,
                blank=True,
                validators=[
                    django.core.validators.MinValueValidator(10 * 1024 * 1024),
                    django.core.validators.MaxValueValidator(5 * 1024 * 1024 * 1024),
                ],
                help_text=(
                    "Phase 240.3.D — per-tenant DQ input upload cap "
                    "(bytes). NULL = use platform default "
                    "(DQ_INPUT_TOO_LARGE_BYTES). "
                    "Bounds: [10 MiB, 5 GiB] per D240.15."
                ),
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="dq_sampling_threshold_rows",
            field=models.BigIntegerField(
                null=True,
                blank=True,
                validators=[
                    django.core.validators.MinValueValidator(10_000),
                    django.core.validators.MaxValueValidator(100_000_000),
                ],
                help_text=(
                    "Phase 240.3.D — per-tenant DQ sampling "
                    "threshold (rows). NULL = use platform default "
                    "(DQ_SAMPLING_THRESHOLD_ROWS). "
                    "Bounds: [10 000, 100 000 000] per D240.15."
                ),
            ),
        ),
    ]
