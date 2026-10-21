"""Phase 277.B.111 — add ``trace_id`` UUIDField to AuditEvent for cross-system correlation.

Safe on large tables: ``null=True, default=None`` — no table rewrite.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0013_merge_20260513_1157"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditevent",
            name="trace_id",
            field=models.UUIDField(
                blank=True,
                db_index=True,
                default=None,
                help_text="OTel trace_id for cross-system audit/trace/log correlation.",
                null=True,
            ),
        ),
    ]
