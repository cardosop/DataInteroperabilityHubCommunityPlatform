"""
Phase 240.1.C.1 — soft-delete fields on DQRun / DQAnomaly / DQTrend.

Each model gains:

* ``is_deleted`` (BooleanField, default False, db_index=True) — the
  tombstone marker. The default manager filters this out so existing
  callers don't need to be touched.
* ``deleted_at`` (DateTimeField, null=True) — pins the soft-delete
  moment so the purge command can compare against the 30-day
  hard-delete grace window (D240.7).

Plus per-table composite indexes ``(tenant, is_deleted, <ts>)`` to
support the purge query pattern::

    UPDATE dq_runs SET is_deleted=True, deleted_at=NOW()
    WHERE tenant_id = ? AND is_deleted = False AND created_at < ?

without a sequential scan over the entire history.

The migration is purely additive (AddField + AddIndex) so an
already-running deployment keeps serving traffic while it runs.
Index creation is NOT wrapped in CONCURRENTLY here — at the row
counts we see today (single-digit-millions per tenant) the SHARE
lock window is sub-second; for the next phase that grows past 100M
rows we'd promote this to ``AddIndexConcurrently``.
"""
from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("dq", "0007_alerting_dedupe_index"),
    ]

    operations = [
        # ----- DQRun ------------------------------------------------------
        migrations.AddField(
            model_name="dqrun",
            name="is_deleted",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text=(
                    "Phase 240.1.C — soft-delete tombstone. True = "
                    "hidden from default manager + eligible for hard-"
                    "delete after the 30-day grace window."
                ),
            ),
        ),
        migrations.AddField(
            model_name="dqrun",
            name="deleted_at",
            field=models.DateTimeField(
                null=True, blank=True,
                help_text=(
                    "Phase 240.1.C — when this row was soft-deleted. "
                    "NULL when ``is_deleted=False``."
                ),
            ),
        ),
        migrations.AddIndex(
            model_name="dqrun",
            index=models.Index(
                fields=["tenant", "is_deleted", "created_at"],
                name="dq_runs_softdelete_purge_idx",
            ),
        ),
        # ----- DQAnomaly --------------------------------------------------
        migrations.AddField(
            model_name="dqanomaly",
            name="is_deleted",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Phase 240.1.C — soft-delete tombstone.",
            ),
        ),
        migrations.AddField(
            model_name="dqanomaly",
            name="deleted_at",
            field=models.DateTimeField(
                null=True, blank=True,
                help_text="Phase 240.1.C — when this row was soft-deleted.",
            ),
        ),
        migrations.AddIndex(
            model_name="dqanomaly",
            index=models.Index(
                fields=["tenant", "is_deleted", "detected_at"],
                name="dq_anomalies_softdelete_idx",
            ),
        ),
        # ----- DQTrend ----------------------------------------------------
        migrations.AddField(
            model_name="dqtrend",
            name="is_deleted",
            field=models.BooleanField(
                default=False,
                db_index=True,
                help_text="Phase 240.1.C — soft-delete tombstone.",
            ),
        ),
        migrations.AddField(
            model_name="dqtrend",
            name="deleted_at",
            field=models.DateTimeField(
                null=True, blank=True,
                help_text="Phase 240.1.C — when this row was soft-deleted.",
            ),
        ),
        migrations.AddIndex(
            model_name="dqtrend",
            index=models.Index(
                fields=["tenant", "is_deleted", "period_start"],
                name="dq_trends_softdelete_idx",
            ),
        ),
    ]
