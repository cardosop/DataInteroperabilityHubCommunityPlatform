"""Rename DSAR idempotency index to satisfy Django E034 (≤30 char names)."""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("dsar", "0003_dsar_idempotency_24h_window"),
    ]

    operations = [
        migrations.RenameIndex(
            model_name="dsarrequest",
            new_name="dsar_req_tnt_idem_ix",
            old_name="dsar_reques_tenant__idem_lu_idx",
        ),
    ]
