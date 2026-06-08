"""Allow repeated Idempotency-Key after the 24h window (Phase 232.2.10).

The previous partial unique on (tenant, idempotency_key) prevented any new
submission reusing a key after expiry. Application logic now dedupes only
within ``settings.DSAR_PUBLIC_IDEMPOTENCY_WINDOW_HOURS``.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("dsar", "0002_enable_rls_dsar"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="dsarrequest",
            name="uq_dsar_tenant_idempotency",
        ),
        migrations.AddIndex(
            model_name="dsarrequest",
            index=models.Index(
                fields=["tenant", "idempotency_key"],
                name="dsar_reques_tenant__idem_lu_idx",
            ),
        ),
    ]
