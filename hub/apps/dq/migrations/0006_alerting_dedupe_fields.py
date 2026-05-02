"""
Phase 240.1.A.3 — additive fields for the alert-delivery dedup window.

Two columns are added to ``dq_alerting_rules``:

* ``last_alert_id``  (``CHAR(64)``, nullable) — the deterministic
  ``sha256(rule_id:run_id:alert_type)[:32]`` of the last delivered
  alert. The dispatcher compares against this column before
  delivering a fresh alert; a match within the dedup window short-
  circuits the delivery (D240.8).
* ``last_fired_at`` (``TIMESTAMPTZ``, nullable) — when the last
  delivery was attempted. Combined with the dedup window (24 h)
  this prevents a stuck condition from flooding partners with the
  same alert.

The composite index ``(tenant_id, id, last_alert_id)`` is split into
its own migration (``0007_alerting_dedupe_index``) with
``atomic = False`` so the ``CREATE INDEX CONCURRENTLY`` doesn't
block writes during deploy — see D240.5.
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    # Depend on BOTH leaves so this migration linearises the graph —
    # without the second dep ``0099_alter_dqrun_dataset_set_null`` and
    # ``0007_alerting_dedupe_index`` would both be terminal nodes and
    # ``manage.py migrate`` would fail with
    # ``Conflicting migrations detected; multiple leaf nodes``.
    dependencies = [
        ("dq", "0005_encrypt_channel_config"),
        ("dq", "0099_alter_dqrun_dataset_set_null"),
    ]

    operations = [
        migrations.AddField(
            model_name="dqalertingrule",
            name="last_alert_id",
            field=models.CharField(
                max_length=64,
                null=True,
                blank=True,
                help_text=(
                    "Phase 240.1.A — deterministic alert_id of the last "
                    "delivered alert (sha256(rule:run:type)[:32]). Used "
                    "for dedup against re-firing within the 24 h window."
                ),
            ),
        ),
        migrations.AddField(
            model_name="dqalertingrule",
            name="last_fired_at",
            field=models.DateTimeField(
                null=True,
                blank=True,
                help_text=(
                    "Phase 240.1.A — timestamp of the last delivery "
                    "attempt. NULL = never fired."
                ),
            ),
        ),
    ]
